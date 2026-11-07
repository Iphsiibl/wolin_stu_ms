# 演示数据重置机制

> 一键把数据库恢复到「种子基线」——被删的、被改坏的、被塞了垃圾的，全部归零。

---

## 一、为什么需要它

系统部署到公网后，**任何拿到网址的人都能增删改数据**。后端目前没有鉴权，
前端登录页是演示模式。这带来三类破坏：

| 破坏方式 | 现象 | 能不能救回来 |
|---|---|---|
| **软删除** | 某条记录从列表消失（`is_del=1`） | ✅ 能 |
| **改字段值** | 学生 1 的院校被改成 `string` | ❌ 旧脚本救不回 |
| **插入垃圾行** | 列表页多出几十条 `Z######`、`回归班2759` | ✅ 能 |

项目里原本有一个 `frontend/scripts/reset-demo-data.sql`，但它只按「命名特征」删多余的行，
**对「被改值」的种子行无能为力**（脚本自己的注释里也写了这条局限）。

所以新增了这套机制：**删表重建 + 重新灌种子**，保证 100% 回到初始状态。

---

## 二、怎么用

### 方式 A：网页按钮（日常用）

1. 登录后台，**顶栏右侧**有个 ⟲ 按钮（服务器配置了 `RESET_TOKEN` 才会显示）
2. 点开弹窗，能看到：
   - 重置前总行数 → 重置后总行数
   - 每张表的当前行数 / 基线行数 / 差异
3. 输入**重置口令** + 确认短语 `RESET`
4. 二次确认后执行，完成后页面自动刷新

### 方式 B：命令行（网页坏了时的兜底）

```bash
# 服务器上（Docker 部署）
docker compose exec backend python -c "
from database import Session
from utils.reset_service import reset_to_baseline
db = Session(); print(reset_to_baseline(db)); db.close()
"

# 本地
python -c "
from database import Session
from utils.reset_service import reset_to_baseline
db = Session(); print(reset_to_baseline(db)); db.close()
"
```

### 方式 C：HTTP 直调

```bash
curl -X POST http://你的域名/api/reset/execute \
  -H 'Content-Type: application/json' \
  -d '{"token":"你的口令","confirm":"RESET"}'
```

---

## 三、安全设计（三道闸门）

```
┌─────────────────────────────────────────────────────────┐
│  闸门 0：功能是否启用                                    │
│    未配置 RESET_TOKEN → 返回 404，整个功能不存在          │
├─────────────────────────────────────────────────────────┤
│  闸门 1：确认短语                                        │
│    confirm != 'RESET' → 400                              │
├─────────────────────────────────────────────────────────┤
│  闸门 2：口令                                            │
│    token 不匹配 → 401（常量时间比较，防计时侧信道）       │
└─────────────────────────────────────────────────────────┘
```

### 为什么闸门 0 最重要

公开部署时如果忘了配 `RESET_TOKEN`，**正确的行为是「这个功能用不了」**，
而不是「任何人都能重置你的库」。

所以代码里的逻辑是：

```python
# utils/reset_service.py
def get_reset_token() -> Optional[str]:
    token = os.getenv('RESET_TOKEN', '').strip()
    return token or None      # 没配就是 None，不是空字符串
```

而且前端按钮在 `enabled=false` 时**整个不渲染**——
功能不存在时，界面上也不该有一个点了必报错的按钮。

### 口令为什么放请求体

放 query 参数（`?token=xxx`）会进 Nginx 访问日志、进浏览器历史、进 Referer 头。
放请求体里不会。**这是密码字段的通用做法**，接口实现里专门写了注释。

### 接口不出现在 Swagger

```python
@router09.post('/execute', include_in_schema=False)
```

`/docs` 页面上看不到这个接口。知道路径的人照样能用（靠口令保护），
但自动扫描器不会白扫到它。

---

## 四、审计日志

每一次尝试（包括被拒绝的）都会记录到 `logs/reset-audit.log`：

```
[2026-11-06 11:00:25] action=reset result=rejected operator=unknown ip=1.2.3.4 client=Mozilla/5.0... duration_ms=0 detail=口令错误
[2026-11-06 11:00:25] action=reset result=success operator=admin ip=1.2.3.4 client=Mozilla/5.0... duration_ms=343 detail=重置成功，数据库已恢复到种子基线。
```

| 字段 | 含义 |
|---|---|
| `result` | `success` / `partial` / `rejected` |
| `operator` | `admin` / `unknown` |
| `ip` | 真实客户端 IP（穿透 Nginx 的 `X-Forwarded-For`） |
| `duration_ms` | 耗时 |
| `detail` | 拒绝原因或执行结果 |

**日志里不记录口令本身**，只记操作人和来源 IP。

> 为什么单独写文件而不只用 `logging`：`logging` 的输出可能被容器日志轮转、
> 可能被日志级别过滤掉。审计日志要独立留存、不能丢，所以直接追加写文件。

查看审计日志：

```bash
# 服务器上
docker compose exec backend cat logs/reset-audit.log

# 或
tail -f logs/reset-audit.log
```

---

## 五、实现要点

### 为什么删表重建，而不是 `DELETE FROM`

| | `DELETE FROM` | `DROP TABLE` + 重建 |
|---|---|---|
| 清数据 | ✅ | ✅ |
| 修表结构 | ❌ | ✅ |
| `AUTO_INCREMENT` 归零 | ❌（新记录从 601 开始） | ✅ |
| 外键顺序 | 要小心 | 统一关掉再打开 |

### 为什么不动库

`sql/01_create_schema.sql` 里有 `DROP DATABASE IF EXISTS`。
如果照搬，库会被整个删掉——后端连接池里的连接会全部失效。

所以 `utils/reset_service.py` 里**跳过了所有库级语句**：

```python
if re.match(r'^\s*(USE\s|DROP\s+DATABASE|CREATE\s+DATABASE)', stmt, re.IGNORECASE):
    logger.info('跳过库级语句: %s', head)
    continue
```

只重建 7 张表，库本身和连接池都不受影响，对在线服务友好得多。

### 表名白名单

重建的表名来自代码里的常量 `_ALLOWED_TABLES`，**不接受任何外部输入**——不存在 SQL 注入面。

### 幂等性

重复执行任意多次，结果完全一样：每次都从种子文件重建。
实测两次执行后各表行数完全相同。

### 事务

整个重建过程在一个事务里。失败会 `rollback`，不会留下「删了一半」的中间状态。

---

## 六、部署时必须做的两件事

### 1. 在服务器 `.env` 里加 `RESET_TOKEN`

```ini
# 服务器上的 .env（绝不进 Git）
RESET_TOKEN=换成一串足够随机的东西
```

生成一个强口令：

```bash
openssl rand -base64 24
```

> **不配就不生效** —— 这是设计意图，不是 bug。
> 但配了之后务必自己记牢，因为这个口令就是「清空线上数据」的钥匙。

### 2. 把 `logs/` 加进 `.gitignore`（已加）

审计日志含 IP 和 User-Agent，属于运行日志，不该进仓库。

---

## 七、注意事项

⚠️ **重置会清空当前库里的一切**，包括你自己新添加的记录。
所以这个按钮是给「演示环境被人搞乱了」用的，不是日常操作。

⚠️ **重置期间后端会短暂无法服务**。整个过程约 300～500ms，
期间进来的请求可能失败。这是可接受的——一次破坏性操作换回完整状态。

⚠️ **小助手（kb_assistant）连的是只读账号**，重置后它会自动看到新数据，
不需要额外操作。

---

## 八、文件清单

| 文件 | 作用 |
|---|---|
| `utils/reset_service.py` | 核心：SQL 拆分、表重建、种子灌入、基线自检、口令校验、审计写盘 |
| `API/reset_api.py` | 接口层：`GET /reset/status`、`POST /reset/execute` |
| `frontend/src/api/reset.ts` | 前端接口封装 |
| `frontend/src/components/ResetDataDialog/index.vue` | 重置弹窗组件 |
| `frontend/src/layouts/components/Header/components/ResetButton.vue` | 顶栏入口按钮 |
| `logs/reset-audit.log` | 审计日志（运行时生成，不入库） |

---

## 九、基线数据

重置后的目标状态（与 `sql/02_seed_demo_data.sql` 核对过）：

| 表 | 行数 |
|---|---|
| `agent`（招生顾问） | 12 |
| `class_teacher`（班主任） | 12 |
| `teacher`（授课老师） | 24 |
| `clazz`（班级） | 36 |
| `student_info`（学生） | 200 |
| `scores`（成绩） | 600 |
| `employment`（就业） | 134 |
| **合计** | **1018** |

重置后会逐表比对，不达标会在返回结果里标出来（`baseline_check`）。
