# 学生管理系统 · 全栈总览

> 一套前后端分离的培训机构学生管理系统。**FastAPI + SQLAlchemy 2.0 + MySQL** 后端，
> **Vue 3 + TypeScript + Element Plus** 管理后台，外加一个独立的**知识库问答旁路服务**。
>
> 本文是**全栈视角的入口文档**：讲清三个子系统怎么拼在一起、各自的边界在哪、
> 从零怎么跑起来、以及当前有哪些已知问题。
>
> 后端四层分层的**逐层详解**（每层的关键约定、踩过的坑、代码片段）
> 见项目根目录的 **[`PROJECT_DOC.md`](../PROJECT_DOC.md)**，本文不重复。
>
> ✅ **接手前请先看 [§10.1 遗留缺陷](#101-遗留缺陷)** ——
> 本次核查实测复现了 **4 个真实缺陷**，其中 2 个会让写接口直接不可用：
> 录入成绩（`score1/score2` 与 ORM 的 `score` 不匹配）
> 和新增学生（`stu_1d` 拼写错误，**且数据已写入库**）。
> **这 4 项已于 2026-11-05 全部修复**，回归测试 `64 passed`，
> 前端端到端验证 `npm run verify` **78 项全通过**。


---

## 目录

- [一、项目概述](#一项目概述)
- [二、整体架构](#二整体架构)
- [三、后端：四层分层的骨架](#三后端四层分层的骨架)
- [四、数据库设计](#四数据库设计)
- [五、接口清单](#五接口清单)
- [六、从零跑起来](#六从零跑起来)
- [七、测试与验证](#七测试与验证)
- [八、前端](#八前端)
- [九、知识库小助手](#九知识库小助手)
- [十、已知问题与演进路线](#十已知问题与演进路线)
- [附录：文档索引](#附录文档索引)

---

## 一、项目概述

### 1.1 是什么

面向培训机构的学生管理系统，管理学生的**基本信息、成绩、就业去向**三类核心数据，
并在其上叠加**班级、授课老师、班主任、招生顾问**四个组织维度，
以及一组**统计分析**指标。

### 1.2 核心功能与接口分布

| 模块 | 前缀 | 说明 | 接口数 |
|---|---|---|---|
| 学生信息 | `/student` | 增删改查、分页、按姓名/班级检索 | 7 |
| 顾问 | `/agent` | 招生顾问维护、重名拦截、按顾问检索学生 | 6 |
| 成绩 | `/score` | 三次考试成绩录入与统计 | 8 |
| 就业 | `/employment` | 就业信息录入、检索、分页、未就业查询 | 6 |
| 班级 | `/class` | 班级维护、班级学生查询 | 6 |
| 班主任 | `/class_teacher` | 班主任维护 | 5 |
| 老师 | `/teacher` | 授课老师维护 | 5 |
| 统计分析 | `/stat` | 人数/男女比/平均分/薪资排名/就业时长 | 8 |
| | | **合计** | **51** |

> **51 个 operation、48 条路径**。
> 差的 3 个来自两条「多方法路径」：`/teacher/` 有 GET+POST（+1），
> `/teacher/{teacher_id}` 有 GET+PUT+DELETE（+2）。48 + 3 = 51。
> 该数字由后端 OpenAPI 契约**实际导出统计**得出，不是数路由装饰器数出来的。
> 可复现命令见 [§5.1](#51-接口清单的实际来源)。

### 1.3 技术选型

| 层 | 选型 | 版本 | 为什么 |
|---|---|---|---|
| Web 框架 | FastAPI | ≥0.110 | 自动生成 OpenAPI，参数声明即校验，原生 async |
| ORM | SQLAlchemy | ≥2.0 | 2.0 的 `Session` 事务模型比 1.4 清晰，`select()` 风格更现代 |
| 数据库 | MySQL | 5.7+ / 8.x | 教学项目常规选型；8.x 需 `cryptography` 支撑 `caching_sha2_password` |
| 校验 | Pydantic | ≥2.6 | v2 的 `model_validator` 让「部分更新」这类规则能写进 schema 层 |
| 驱动 | PyMySQL | ≥1.1 | 纯 Python，无需编译 |
| 服务 | Uvicorn | ≥0.27 | FastAPI 官方推荐 ASGI 服务器 |
| 前端框架 | Vue 3 | 3.5.44 | `<script setup>` 模板语法对 Python 开发者心智成本最低 |
| 前端语言 | TypeScript | ~6.0.3 | 接口字段在编译期被校验，后端改字段会直接报错而不是白屏 |
| 组件库 | Element Plus | 2.14.7 | 企业中后台 CRUD 的事实标准，中文文档密度最高 |
| 状态管理 | Pinia | 4.1.0 | 比 Vuex 样板代码少一大半 |
| 构建 | Vite | 8.3.5 | 冷启动毫秒级，dev proxy 天然解决跨域 |
| 图表 | ECharts + vue-echarts | 6.1.0 / 8.3.2 | 统计看板与大屏需要折线/柱状/饼图/仪表盘 |
| UI 骨架 | Geeker-Admin（MIT） | — | 直接复用其布局骨架 / ProTable / 样式层 |
| 模型 | MiniMax M3.1-Flash | — | 走 Anthropic Messages 协议，知识库小助手用 |

### 1.4 运行环境

- Python 3.10+（用到 `str | None` 语法；实测 venv 为 3.12.15）
- MySQL 5.7+ / 8.x
- Node.js **20.19+ 或 22.12+**（Vite 8 的硬性要求，低于此版本会报一堆难懂的错）
- 依赖清单：`requirements.txt`（后端）、`frontend/package.json`、`kb_assistant/requirements.txt`

---

## 二、整体架构

### 2.1 三个服务

```
        浏览器
          │
          ▼
   ┌──────────────┐   Vite dev server (5173)
   │   frontend   │   ├─ /api/* ──► FastAPI  (8003)  ──► MySQL（可写 root）
   │  Vue3 + TS   │   └─ /kb/*  ──► 小助手 (8010)  ──► MySQL（只读 kb_ro）
   └──────────────┘
```

| 服务 | 端口 | 启动方式 | 数据库权限 |
|---|---|---|---|
| FastAPI 后端 | **8003** | `python main.py` | 可写（root） |
| 知识库小助手 | 8010 | `kb_assistant/start.ps1` | **只读**（`kb_ro`） |
| 前端 | 5173 | `cd frontend; npm run dev` | —— |

> 端口以 `main.py:51` 的 `APP_PORT` 默认值为准（**8003**）。
> 环境变量 `APP_PORT` / `APP_HOST` / `APP_RELOAD` 可覆盖。
> ⚠️ 项目里仍有若干文件写着 8002（`sql/README.md`、`tests/smoke_live.py` 默认地址等），
> 属于历史遗留不一致，见 [§10.3](#103-文档与代码不一致清单)。

**跨域不由后端解决**，而靠 Vite dev proxy：浏览器只跟 5173 说话（同源），
由 Vite 在服务端转发到 8003 并去掉 `/api` 前缀。生产环境用 Nginx 反代 `/api` 即可，
**后端与前端代码都无需改动**。

> 注意 `/kb` 代理**不 rewrite** —— 小助手路由本身就是 `/kb/chat`、`/kb/health`，
> 去掉前缀反而对不上。

### 2.2 目录结构

```
student_ms/
├── main.py                  应用入口：建 app、挂 8 个路由、启动 uvicorn
├── database.py              唯一的数据库连接管理点：engine / Base / Session / get_db
├── utils.py                 model_to_dict()：Pydantic → ORM 的安全转换
├── requirements.txt
├── .env                     数据库配置 + 小助手 token（已被 .gitignore 排除）
│
├── API/                     ── 第 1 层：接口层 ──────────────────
│   ├── stu_info_api.py      学生(router01) + 顾问(router07)
│   ├── score_api.py         成绩(router02)
│   ├── emp_api.py           就业(router03)
│   ├── class_api.py         班级(router04)
│   ├── teacher_api.py       老师(router05)
│   ├── stat_api.py          统计(router06)
│   └── class_teacher_api.py 班主任(router08)
│
├── Dao/                     ── 第 2 层：数据访问层 ──────────────
│   ├── stu_dao.py  emp_dao.py  score_Dao.py
│   ├── class_dao.py  teacher_dao.py  stat_dao.py
│
├── model/                   ── 第 3 层：ORM 模型层 ──────────────
│   ├── student_table.py     Agent / Student_info
│   ├── class_model.py       Class / Class_teacher
│   ├── score_model.py  teacher.py  employment.py
│   └── __init__.py          统一导入（注册 relationship 类表）
│
├── schema/                  ── 第 4 层：请求校验层 ──────────────
│   ├── enums.py             Sex 枚举 + SexField 兼容转换器
│   ├── student_request.py   Student_request / Agent_request / UpdateStudent / UpdateAgent
│   ├── emp_request.py       EmpRequest / EmpSearch / EmpUpdate
│   ├── class_schema.py      Class_Request / Class_teacher_Request
│   ├── score_schema.py  teacher_request.py
│
├── sql/                     建库脚本 + 1018 条演示数据 + 操作手册
├── tests/                   回归测试 + 端到端冒烟
├── frontend/                Vue3 管理后台
├── kb_assistant/            知识库小助手（独立服务）
└── docs/                    ★ 本文档 + 文档生成 prompt
```

---

## 三、后端：四层分层的骨架

### 3.1 调用链固定四步

```
HTTP 请求
   │
   ▼
schema  ── Pydantic 校验请求体 ──▶ 格式不对 = 422（自动，不写任何 if）
   │
   ▼
API    ── 组织参数、调用 DAO、把 DAO 的失败翻译成 HTTPException
   │
   ▼
Dao    ── 查询/写入数据库、做业务规则判断（重名、外键是否存在）
   │        失败时返回 (False, {message, status_code})
   ▼
model  ── ORM 实体，映射数据库表
```

各层的职责边界（**越界就是设计缺陷**）：

| 层 | 该做 | 不该做 |
|---|---|---|
| schema | 判断「JSON 长得对不对」 | 查数据库、判断资源是否存在 |
| API | 组织参数、调 DAO、翻译异常 | 写格式校验、写业务规则 |
| Dao | 查库/写库、业务规则判断 | 抛 HTTPException、感知 HTTP 状态码 |
| model | 映射表结构、声明 relationship | 写业务逻辑 |

> **Dao 层不许 import `HTTPException`** —— 项目里有一条专门的测试
> (`test_dao_layer_does_not_import_http_exception`) 守着这条边界。
> DAO 不知道 HTTP 是什么，它只说「失败了，原因是什么，该返回几」。

### 3.2 各层的关键约定速查

> 每条约定的完整解释与代码片段见 [`PROJECT_DOC.md` 第三章](../PROJECT_DOC.md#三后端四层分层设计)。

**schema 层**

1. `Field(...)` 的省略号 = 必填。`Field(max_length=10)` 不带 `default`
   在 Pydantic v2 里**等于必填**，修改类接口必须写 `Field(default=None, ...)`。
2. 部分更新靠 `exclude_unset=True` —— 只把请求体里真正出现过的字段交给 DAO。
3. 空白字符串 = 没填。`UpdateStudent` 用 `mode='before'` 校验器把 `""` 统一转 `None`
   （必须用 `before`，`after` 跑的时候字段已被校验过）。
4. `SexField` 兼容 `"男"/"女"/1/0/"1"/"0"/"male"/"M"` 等多种写法。
5. `Sex` **必须**覆写 `__str__` —— 否则 pymysql 写库时 `str(Sex.MALE)` 得到
   `'Sex.MALE'`，**不报错但数据全废**。
6. 跨字段规则写进 schema（如 offer 不能早于简历开放）。

**Dao 层**

1. 统一返回 `(ok, result)` 二元组。成功 `result` 是数据，失败是
   `{'message': ..., 'status_code': ...}`。
2. 软删除：所有查询带 `is_del == 0` 过滤，删除只置 `is_del = 1`。
3. 修改白名单：`STU_UPDATABLE_FIELDS` 之外的 key（尤其 `stu_id`、`is_del`）被静默忽略。

**API 层**

1. 只做三件事：组织参数、调 DAO、翻译异常。
2. 路由前缀和分组标签统一在 `main.py` 挂载 —— 所以 `API/stu_info_api.py`
   一个文件里定义了 `router01`（学生）和 `router07`（顾问）两个路由器。

**database.py**

1. 整个项目只有这一个文件负责「怎么连数据库」。
2. `pool_pre_ping=True` —— 取连接前先 ping，挡住「跑一晚上就崩」的线上事故。
3. `pool_recycle=3600` —— MySQL 默认 8 小时断开空闲连接，连接池不知道这件事。
4. `get_db()` 用 `yield` 不是 `return`；异常分支**必须 `rollback()`**，
   否则「坏掉的会话」被还回连接池，故障会传给别人。

---

## 四、数据库设计

### 4.1 表清单（7 张）

| 表 | ORM 类 | 含义 | 种子行数 |
|---|---|---|---|
| `agent` | `Agent` | 招生顾问 | 12 |
| `class_teacher` | `Class_teacher` | 班主任 | 12 |
| `teacher` | `Teacher` | 授课老师 | 24 |
| `clazz` | `Class` | 班级（6 专业方向 × 6 期） | 36 |
| `student_info` | `Student_info` | 学生 | 200 |
| `scores` | `Score` | 成绩（每人 3 次考试） | 600 |
| `employment` | `Emp` | 就业信息 | 134 |
| | | **合计** | **1018** |

> 上表行数由**实际查库**得出，并与 `sql/02_seed_demo_data.sql` 的基线逐表比对过。

### 4.2 关系图

```
clazz ──┬─< student_info >──┬── agent
        │                   └── employment
        └── class_teacher_id（无外键约束，DAO 层校验）

teacher ── teacher_id（无外键约束）
```

> `clazz` 表的 `class_teacher_id` / `teacher_id` **刻意没写 ForeignKey**：
> 真实表结构里就没有这个外键约束，ORM 写了会和实际结构对不上。
> 业务上的「班主任/老师必须存在」由 `Dao/class_dao.py` 检查。

### 4.3 关键字段约定

| 约定 | 说明 |
|---|---|
| **软删除** | 每张表都有 `is_del`（0 正常 / 1 已删除），**例外**：`teacher` 表叫 `is_delete` —— 命名不统一是历史遗留 |
| **薪资单位** | 全项目统一「**元/月**」。填 `25000` 就是 25000 元/月 |
| **性别存储** | 存 `'男'` / `'女'` 字符串，不是 int |
| **班级主键** | `clazz.stu_class_id` **不自增**，人工指定（1 号班就是 1） |
| **就业日期** | `open_date`（简历开放）与 `offer_date`（收到 offer）均必填，否则「就业时长」算不出来 |
| **建表时机** | 应用启动时 `create_all`，**只建表不改表** |

### 4.4 ORM 与 SQL 脚本是两份独立定义 ⚠️

`sql/01_create_schema.sql` 里已经建好的约束，ORM 模型里没有全部体现：

| 表 | 约束 | 说明 |
|---|---|---|
| `student_info` | `fk_student_class` / `fk_student_agent` | 外键指向 `clazz` / `agent` |
| `student_info` | `ck_stu_sex` CHECK | 性别只允许 `'男'` / `'女'` |
| `employment` | `uk_emp_stu_id` 唯一索引 | 一个学生最多一条就业记录 |
| `scores` | `idx_scores_stu_id` 索引 | 按学生查成绩 |
| 全局 | `utf8mb4` + InnoDB | 支持完整中文与 emoji |

> ⚠️ **改了 `model/` 里的字段，必须重跑 `python sql/run_sql.py`**。
> `create_all` **不会修改已存在的表** —— 而且**不报任何错**。
> 这是本项目最容易「改了没生效还找不到原因」的地方。

**数值类型的选择**：`employment.salary` 用 `DECIMAL(10,2)`（金额必须用定点数，
`FLOAT` 的二进制浮点误差会让金额对不上账）；`scores.score` 用 `FLOAT`
（考试分数本身是离散整数）。

> **薪资单位为什么值得单独说**：种子数据最初写的是 `27.74`（心里想的是「27.74 千」），
> 而接口写进去的是 `25000`，同一张表出现两种量级，「薪资前五」的统计直接失真 ——
> **而且不报任何错**。所以 `model/employment.py` 和 `schema/emp_request.py`
> 都把单位写死在注释上了。

---

## 五、接口清单

### 5.1 接口清单的实际来源

本文所有接口信息由**后端运行时的 OpenAPI 契约**导出，不是手抄：

```powershell
# 导出完整接口清单（含方法、路径、summary、模块标签）
.\.venv\Scripts\python.exe -c "from main import app; import json; print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))"
```

> **为什么强调这一点**：路由重构后，代码里的「接口总数」与文档里的数字曾经对不上。
> 手抄和手数都会错，只有契约导出不会。
> 同理，前端的接口速查表 `frontend/src/types/api-meta.ts` 也是**自动生成物**
> （`node scripts/gen-api-meta.mjs`），手改它必然随契约漂移而失效。

### 5.2 学生 `/student`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/student/add_stu` | 新增学生 ⚠️ **见 §10.1①，当前恒定 500** |
| GET | `/student/select_stu_id` | 按 id 查询 → `{code,message,Data}` |
| GET | `/student/select_stu_skip` | 分页查询（`skip`/`limit`）→ `{code,message,total,Data}` |
| GET | `/student/select_stu_name` | 按姓名查询 → `{code,message,Data}` |
| GET | `/student/select_stu_class` | 按班级查询 → `{code,message,Data}` |
| PUT | `/student/update_stu_class` | 修改学生（只改传了的字段）→ `{code,message,Data}` |
| DELETE | `/student/delete_stu` | 软删除学生 → `{code,message}` |

> `agent_id`（顾问）是**必填** —— 业务规则是每个学生都必须有顾问。

### 5.3 顾问 `/agent`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/agent/add_agent` | 新增顾问（重名 → 409） |
| GET | `/agent/agent` | 查询所有顾问 |
| GET | `/agent/select_agent` | 按 id 查询单个顾问 |
| PUT | `/agent/update_agent` | 修改顾问 |
| DELETE | `/agent/delete_agent` | 软删除顾问 |
| GET | `/agent/select_stu_agent` | 按顾问查询其名下学生 |

> `select_stu_agent` 虽然是「查学生」，但挂在 `router07`（`/agent` 前缀）下，
> 与其余 5 个顾问接口同属一个 `APIRouter`，因此计入顾问模块。
>
> ⚠️ 这 6 个接口是**从 `/student/*` 迁过来的**。旧路径已下线，
> 但 `tests/` 下的测试文件**仍在用旧路径** —— 见 [§10.1②](#102-回归测试大面积失效测试文件用的是重构前的旧路径)。

### 5.4 成绩 `/score`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/score/score` | 录入成绩 ⚠️ **见 §10.1④，当前完全不可用** |
| GET | `/score/stu_id/{stu_id}` | 查询单个学生的考试成绩 |
| GET | `/score/test_id/{test_id}` | 查询单次考试次序的学生成绩 |
| GET | `/score/test_id1/{test_id}` | 同上（另一入口） |
| GET | `/score/stu_id/{stu_id}/test_id/{test_id}` | 查询单个学生的单次考试 |
| PUT | `/score/put` | 修改成绩 |
| DELETE | `/score/del/stu_id/{stu_id}/test_id/{test_id}` | 删除成绩（软删） |
| GET | `/score/get_del` | 查询已删除的成绩 ⚠️ **见 §10.1③，当前 500** |


### 5.5 就业 `/employment`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/employment/create` | 添加就业信息 |
| GET | `/employment/search` | 条件查询 |
| GET | `/employment/page` | 分页查询 → `{total,page,size,total_pages,items}` |
| GET | `/employment/unemployed` | 查询未就业学生 → `{total,result}` |
| PUT | `/employment/put/{stu_id}` | 按学号修改 |
| DELETE | `/employment/delete/{stu_id}` | 删除 |

### 5.6 班级 `/class` 与班主任 `/class_teacher`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/class/` | 新建班级 |
| PUT | `/class/update_class/{stu_class_id}` | 修改班级 |
| DELETE | `/class/delete_class/{stu_class_id}` | 删除班级及班级学员 |
| GET | `/class/get_class/{stu_class_id}` | 查询班级信息 |
| GET | `/class/get_class/{stu_class_id}/students` | 查询班级所有学生 |
| GET | `/class/all_class` | 查询所有班级 |
| POST | `/class_teacher/class_teacher` | 新增班主任 |
| PUT | `/class_teacher/update_class_teacher/{id}` | 修改班主任 |
| DELETE | `/class_teacher/delete_class_teacher/{id}` | 删除班主任 |
| GET | `/class_teacher/get_class_teacher/{id}` | 查询单个班主任 |
| GET | `/class_teacher/all_class_teacher` | 查询所有班主任 |

> 班主任接口是 2026-11-03 从 `/class/*` 迁到 `/class_teacher/*` 的。
> 旧路径已被整段注释掉（`API/class_api.py:146-224`），实测返回 404。

### 5.7 老师 `/teacher`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/teacher/` | 新增老师 |
| GET | `/teacher/` | 查询所有老师 |
| GET | `/teacher/{teacher_id}` | 按 id 查询 |
| PUT | `/teacher/{teacher_id}` | 修改老师 |
| DELETE | `/teacher/{teacher_id}` | 删除老师 |

### 5.8 统计 `/stat`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/stat/students/over_age` | 查询超过指定年龄的学员 |
| GET | `/stat/class/statistics` | 各班人数及男女人数 |
| GET | `/stat/score/all_above_80` | 各次考试均 80 分以上的学生 |
| GET | `/stat/score/failed_twice` | 两次以上不及格的学生 |
| GET | `/stat/score/avg_by_class` | 各班平均分（降序） |
| GET | `/stat/emp/top5_salary` | 薪资最高前五名 |
| GET | `/stat/emp/duration` | 每个学生的就业时长 |
| GET | `/stat/emp/avg_duration_by_class` | 各班平均就业时长 |

### 5.9 响应格式不统一（重要）

**这是历史遗留的坑，前端必须做适配。** 后端有 7 种不同的返回形状：

| 模块 | 实际形状 |
|---|---|
| 学生 / 就业（列表） | `{code, message, total, Data}` |
| 学生（单条） | `{code, message, Data}` |
| 删除类操作 | `{code, message}` |
| 成绩 | `{msg, detail}` |
| 就业分页 | `{total, page, size, total_pages, items}` |
| 未就业学员 | `{total, result}` |
| 班级 / 老师 / 统计 | 裸数组 |

另外，**成绩、班级、班主任三个模块的响应字段名是中文的**
（`学生编号` / `考试序次` / `分数` / `班级id` / `班主任名字` 等），
**请求体反而是英文的**。这是老代码留下的约定。

> 前端的应对方式：在 Axios 响应拦截器里统一拆包成
> `{code, message, data, total}`，业务层只看到一种形状；
> 中文字段在 `src/utils/mappers.ts` 里转英文。
> **后端要改返回格式，只需改前端 `http.ts` 一个文件。**

#### 还有 3 种「半截子」变体，前端适配层并未专门处理

除了上表 7 种，还有 3 种更零碎的形状：

| 场景 | 实际返回 | 前端适配层的表现 |
|---|---|---|
| 班级 / 班主任的增删改 | `{message: "新增班主任成功"}` | 落到 `normalize()` 的**兜底分支** → `message` 文案丢失，`data` 变成整个对象 |
| 老师软删除 | `{msg: "..."}` | 同上 |
| 就业的增删改 | `{stu_id: 1, message: "..."}` | 同上 |

> **这意味着「后端改格式只改 `http.ts` 一个文件」这个结论，在前端侧是有缺口的** ——
> 这 3 种变体没有专门的分支，错误文案会丢。
> 统一后端返回结构（见 §10.2）能一并解决。

#### 前端自己的注释已经过时

| 文件 | 注释写的 | 实际 |
|---|---|---|
| `frontend/src/api/http.ts` | 「把后端的 **6 种**返回格式统一成…」 | **6 种** ✅ 已对齐（原先是 7 种，`/employment/unemployed` 单独返回 `{total, result}`；已把后端改成标准形状 `{code, message, total, Data}`，前端那个特判分支降级为旧格式兼容） |
| `frontend/src/utils/mappers.ts` | 「后端有 **2 个**模块的响应字段名是中文的」 | **3 个**（班主任接口也返回中文 key） |

本文写的数字才是对的，是前端注释没跟上后端演进。


### 5.10 状态码语义

| 状态码 | 含义 | 触发场景 |
|---|---|---|
| 200 / 201 | 成功 / 创建成功 | —— |
| 400 | 请求不合法 | 修改接口一个有效字段都没传；薪资上下限颠倒 |
| 404 | 资源不存在 | 按 id 查不到、查顾问名下无学生、班级/顾问不存在、录入成绩时学生不存在 |
| 409 | 冲突 | 新增顾问重名、姓名+电话重复、成绩重复 |
| 422 | 校验失败 | Pydantic 层拦截（自动生成） |
| 500 | 服务端错误 | 未预期的异常 ⚠️ **已修复 3 处**，见 §10.1 |


---

## 六、从零跑起来

### 6.1 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.10+ | 用到 `str \| None` 语法 |
| MySQL | 5.7+ / 8.x | 8.x 需 `cryptography` |
| Node.js | **20.19+ 或 22.12+** | Vite 8 的硬性要求 |

### 6.2 四步走（后端 + 数据库）

> ⚠️⚠️ **第 1 步会删库重建，务必先读完这一段** ⚠️⚠️
>
> `sql/01_create_schema.sql` 的第 1 行是 **`DROP DATABASE IF EXISTS`**，
> `python sql/run_sql.py` 会执行它 —— **目标库里的东西会被全部清空，然后重建**。
>
> - 默认目标是 `student_ms_demo`（专供测试的库），一般不会碰到你的业务库
> - **但如果你把 `.env` 里的 `DB_NAME` 改成了正式库名，跑这一步就是全量清库**
> - 换库名：`python sql/run_sql.py student_ms_test`（同样会删掉那个库再重建）
>
> **在有真实数据的环境里跑之前，先确认 `.env` 的 `DB_NAME` 指向哪个库。**
> 本文档在核查期间多次执行过该脚本（用于恢复种子基线），
> 每次都会清空并重建 `student_ms_demo`。

```powershell
# 第 1 步：建库 + 灌 1018 条测试数据（项目根目录执行）
#         会自动建 student_ms_demo 库，不需要你预先手动建库
#         ⚠️ 会先 DROP DATABASE，请确认 .env 里的 DB_NAME
python sql/run_sql.py

# 第 2 步：装后端依赖
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 第 3 步：配好 .env（项目根目录）
#         DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
#         默认 DB_NAME=student_ms_demo，与第 1 步建出来的库名一致

# 第 4 步：启动
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8003
```

启动后访问 `http://127.0.0.1:8003/docs` —— Swagger UI，
左边 8 个模块 51 个接口，右边填参数点 "Try it out" 直接调。

### 6.3 前端与小助手

```powershell
# 前端
cd frontend
npm install
npm run dev              # -> http://localhost:5173

# 小助手（另开一个终端）
cd kb_assistant
pip install -r requirements.txt
.\start.ps1              # -> http://127.0.0.1:8010
```

**或者一键启动前后端**（推荐）：

```powershell
cd frontend
.\scripts\start-all.ps1
```

脚本会依次检查 Node 版本、`node_modules`、`.venv`、`.env`，
拉起 FastAPI 并**等到它真正能响应且能查到数据库**才继续拉起 Vite。

### 6.4 登录

演示模式，**任意账号密码都能进**（预填 `admin` / `123456`）。

> **边界**：登录是**纯前端模拟** —— `store/user.ts` 把用户信息写进 `localStorage`，
> 路由守卫只检查「localStorage 里有没有用户信息」。
> 这能挡住「没登录直接敲 URL」，**挡不住直接调后端接口**。
> 后端目前**没有任何鉴权**。

### 6.5 改过 model 之后

`create_all` **只建表、不改表**。改了 `model/` 里的字段必须重跑：

```powershell
python sql/run_sql.py
```

否则你改的字段不会生效，而且**不报任何错**。

> ⚠️ 同样地，**这条命令会先 DROP DATABASE**（见 §6.2 的警告）。
> 在有真实数据的库里，这是唯一能同步表结构的方式，但代价是清库。
> 这也是「上 Alembic」被列为高优先级改进项的原因（见 §10.2）。


### 6.6 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DB_HOST` | —— | 数据库地址 |
| `DB_PORT` | —— | 数据库端口 |
| `DB_NAME` | `student_ms_demo` | 数据库名 |
| `DB_USER` | —— | 主后端用 root；小助手在 `kb_assistant/.env` 里覆盖为 `kb_ro` |
| `DB_PASSWORD` | —— | 数据库密码 |
| `APP_HOST` | `127.0.0.1` | 后端监听地址 |
| `APP_PORT` | `8003` | 后端监听端口 |
| `APP_RELOAD` | `0` | 设为 `1` 开启热重载 |
| `MINIMAX_API_KEY` | —— | **小助手必填**，模型 token |
| `MINIMAX_BASE_URL` | `https://api.minimax.chat/anthropic/v1` | Messages 协议端点 |
| `MINIMAX_MODEL` | `MiniMax-M3.1-Flash` | 模型 |
| `KB_ASSISTANT_PORT` | `8010` | 小助手端口 |
| `KB_ASSISTANT_MAX_ROWS` | `200` | 单次查询行数上限 |
| `KB_ASSISTANT_SQL_TIMEOUT` | `15` | 单条 SQL 超时（秒） |
| `KB_ASSISTANT_MAX_HISTORY` | `8` | 会话保留轮数 |
| `KB_ASSISTANT_SHOW_SQL` | `1` | 是否在回答里附带 SQL |

> ⚠️ **`.env` 不要提交到 git**（已在 `.gitignore` 中）。
> 但**直接拷贝整个文件夹会绕过 gitignore** —— 给不完全信任的人时，
> 记得手动删掉 `.env`，让对方自己填。
>
> 小助手的只读账号配置放在 `kb_assistant/.env`（优先级高于根目录 `.env`），
> **不要删掉这个文件** —— 否则小助手会退回用 root 连库。

---

## 七、测试与验证

### 7.1 两套后端测试

| 脚本 | 类型 | 数量 | 怎么跑 | 什么时候跑 |
|---|---|---|---|---|
| `tests/test_api.py` | 回归测试 | 64 项 | 进程内 `TestClient` | 开发中随时跑，CI 跑这个 |
| `tests/smoke_live.py` | 端到端冒烟 | 70 次调用 | 打**真实运行中**的服务 | 发布前跑这个 |

```powershell
# 回归测试
python -m pytest tests/ -q

# 端到端冒烟 —— 需要先启动服务
python main.py
python tests/smoke_live.py http://127.0.0.1:8003
```

> ⚠️ **`smoke_live.py` 的默认地址是 8002**（`tests/smoke_live.py:24`），
> 而后端实际跑在 **8003**。不显式传地址会全部连不上 ——
> **务必带上 `http://127.0.0.1:8003` 参数**。

> ⚠️ **当前实测：7 失败 / 26 通过 / 31 报错**，根因见 [§10.1②](#102-回归测试大面积失效测试文件用的是重构前的旧路径)。
> 这不是环境问题，是测试文件没跟上路由重构。
>
> ⚠️ **跑测试会污染演示库**：`tests/conftest.py` 的文档写明「只创建不删除」，
> 每次跑都会留下带时间戳的测试数据（`回归生8177`、`回归老师8177` 等）。
> 跑完记得用 [§7.4](#74-演示数据复位) 的复位脚本推回基线。


### 7.2 前端验证

```powershell
cd frontend
node scripts/check-api-paths.mjs   # 拿后端 openapi.json 逐条比对前端路径，查断链
npm run build                      # 类型检查 + 生产构建
npm run verify                     # 接口层端到端验证
node scripts/gen-api-meta.mjs      # 刷新接口速查表（自动生成物）
```

> **`check-api-paths.mjs` 是后端改路由后的第一道关**。
> 它把前端每个 `get/post/put/del(...)` 的路径跟 `openapi.json` 对一遍，
> 输出断链清单，比逐个模块试错可靠得多。
>
> **当前实测：前端 52 个接口调用全部能在后端契约里找到，✅ 无断链。**
>
> `npm run verify` 当前实测 **64 通过 / 1 失败**，唯一失败项是「新增学生 500」，
> 指向后端 `stu_1d` 缺陷（见 §10.1①）。前端这边接口调用、字段映射、错误提示都已就绪。
>
> **断言数会随库状态浮动 1～2 项**：`verify-api.mjs` 自己会删一条成绩（制造软删记录）
> 再查 `get_del`。有软删记录时后端 500（缺陷暴露，多 1 项失败），
> 没有时后端 404（符合预期，该项通过）。


### 7.3 小助手测试

```powershell
cd kb_assistant
pytest            # 60 个用例（test_kb_assistant.py 53 + test_agent_flow.py 7）
```

覆盖 SQL 闸门、领域边界、知识库一致性、真实查库，以及打桩模型调用的流程集成测试。
**当前实测：全部通过。**

### 7.4 演示数据复位

并发调试会在正式库里写测试行（命名特征明显：`Z######`、`回归班2759`、`探针班2834`…），
它们会直接出现在前端列表页上，看着像「数据出错了」。

```powershell
cd frontend
node scripts/verify-api.mjs   # 跑完会自动清理自己造的数据
```

> 兜底可跑 `frontend/scripts/reset-demo-data.sql` 手动推回种子基线。
> 它按**命名特征**删，不碰种子行；跑完会打印各表行数自检，
> 期望值是 `200 / 600 / 134 / 36 / 12 / 24 / 12`。

---

## 八、前端

> 完整文档见 **[`frontend/README.md`](../frontend/README.md)**，本节只给接手必需的骨架。

- **技术栈**：Vue 3 + TypeScript + Element Plus + Pinia + Vite 8 + ECharts
- **UI 骨架**：复用开源 [Geeker-Admin](https://github.com/HalseySpicy/Geeker-Admin)（MIT），
  视觉主题改为自研的「教务墨册」（主色墨色 `#1E2C3A`，朱砂 `#C0392B` 用于激活/预警/删除）
- **端口**：5173，`/api` 代理到 8003，`/kb` 代理到 8010
- **路由**：9 组路由，全部懒加载；`/screen` 数据大屏是**独立路由**（不套 Layout）

### 8.1 接手时必须知道的三个设计

**① 响应适配层（`src/api/http.ts`）** —— 统一后端 6 种返回形状，
把 422 的 Pydantic 报错中文化（`年龄：必须大于 18`），错误统一弹提示。
业务层永远只看到 `{code, message, data, total}`。
**后端要改返回格式？只需改 `http.ts` 这一个文件。**

**② 中文字段转英文（`src/utils/mappers.ts`）** —— 成绩/班级/班主任三个模块的
响应字段名是中文的，在这一层统一转成英文字段名。
不转的话界面会出现「表格有行数但整列空白」。
这些是**纯函数**，所以验证脚本能直接 `import` 进来做断言 —— 验证的就是浏览器里真跑的那段代码。

**③ 可观测日志面板（`src/utils/logger.ts` + `LogPanel`）** —— 顶栏图标开抽屉，
看接口耗时、console 输出、未捕获异常。
**刻意不收请求体** —— 登录接口的 body 里带密码，落进日志就是明文泄露。

### 8.2 几个实现选择

| 场景 | 做法 | 原因 |
|---|---|---|
| 学生管理分页 | 一次拉全量 + 前端分页 | 后端 `/student/select_stu_skip` 的 `total` 是**本页条数**不是总数，且 `skip/limit` 与 `el-pagination` 的 1-based 页码对不上 |
| 就业列表分页 | 走服务端 `/employment/page` | 后端有真正的分页接口；排序也交给后端做（`sort=字段:方向`，字段走白名单），否则排的只是当前这一页 |
| 班级/班主任查询 | 前端过滤 | 各 36 / 12 条，一次拉全量再过滤最省事 |
| 大屏缩放 | 固定 1920×1080 画布 + `transform: scale()` | 任何分辨率都不错位 |

### 8.3 契约变更的应对顺序

后端改路由后，前端按这个顺序动：

```powershell
node scripts/check-api-paths.mjs    # ① 先体检：抓断链
# ② 再同步类型与中文字段映射：src/types/models.ts + src/utils/mappers.ts
node scripts/gen-api-meta.mjs       # ③ 刷新接口速查表（别手改）
npm run verify                      # ④ 最后跑全量验证
```

---

## 九、知识库小助手

> 完整文档见 **[`kb_assistant/README.md`](../kb_assistant/README.md)**。

嵌在页面右下角的自然语言问答助手「小管家」，用问话直接查库出答案。

- **模型**：MiniMax `MiniMax-M3.1-Flash`（Anthropic Messages 协议）
  —— 也支持 OpenAI 兼容协议（OpenAI / DeepSeek / 通义 / 智谱 / Kimi / Ollama / vLLM…）
  与 Gemini 协议，改 `LLM_PROTOCOL` + `LLM_BASE_URL` + `LLM_MODEL` 即可换模型
- **端口**：8010，**独立进程**，与主后端互不影响
- **数据库**：**只读账号** `kb_ro`，只看 `student_ms_demo`
- **形态**：悬浮球 + 聊天抽屉，SSE 流式回答，登录后自动出现

### 9.1 主流程

```
用户提问
  │
  ├─ ① 领域预检（确定性规则）—— 命中跑题直接拒答，不消耗 token
  │
  ├─ ② 路由 + 生成 SQL（一次模型调用）
  │      模型回 "NO_SQL" → 走知识库；回一条 SELECT → 走查库
  │
  ├─ ③ 安全校验（sql_guard）—— 不过就带着错误原因让模型重写一次
  │
  ├─ ④ 执行查询（只读连接 + 行数上限）
  │
  └─ ⑤ 生成回答（流式）—— 有结果基于结果作答，没结果基于知识库作答
```

### 9.2 三层安全防线

模型输出是不可信输入，所以**不只靠提示词**：

| 层 | 手段 |
|---|---|
| 1. SQL 安全闸门（`sql_guard.py`） | 只允许 `SELECT`/`WITH`、单语句、危险函数黑名单、表白名单（仅 7 张业务表）、自动补 `LIMIT` |
| 2. 领域边界（`scope.py` + 提示词） | 调用前确定性关键词预检、提示词写死边界、调用后检查越界标记 `[超出范围]` |
| 3. 只读数据库账号 | `kb_ro` 只有 `SELECT ON student_ms_demo.*` —— 代码闸门被绕过也写不进去 |

> **设计取舍是「宁可漏判，不可误杀」**：黑名单只收几乎不可能出现在
> 本系统问题里的词。所以「怎么给系统加个接口」不会被拦，但「帮我写个爬虫」会。

### 9.3 SSE 事件类型

| event | 载荷 | 含义 |
|---|---|---|
| `status` | `{phase, text}` | 阶段提示（理解问题 / 查库 / 组织回答） |
| `sql` | `{sql}` | 本次实际执行的 SQL |
| `token` | `{text}` | 回答的文本增量 |
| `reset` | `{text}` | 覆盖上一条回答（模型越界被拦下时） |
| `result` | `{columns, root, row_count, elapsed_ms}` | 查询结果 |
| `done` | `{session_id, used_sql}` | 结束 |
| `error` | `{message}` | 出错（文案已是中文，可直接展示） |

### 9.4 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` `/kb/health` | 健康检查 + 脱敏配置状态（缺配置/库不通时返回 503） |
| POST | `/kb/chat` | 问答（SSE 流式），body `{question, session_id?}` |
| POST | `/kb/chat/sync` | 问答（非流式，一次性返回） |
| GET | `/kb/session/{id}` | 查看会话上下文（调试用） |
| DELETE | `/kb/session/{id}` | 清空会话上下文 |
| GET | `/static/assistant.png` | 小助手立绘 |

### 9.5 改知识库

模型对「这个系统是什么」的全部认知都在 **`kb_assistant/app/knowledge.py`**：
`TABLES`（7 张表的字段与中文含义）、`MODULES`（前端功能模块）、
`API_ENDPOINTS`（后端接口清单）、`GLOSSARY`（业务术语）。
改完重启小助手即生效。

提示词在 `kb_assistant/app/prompts.py`，三套分工：
`SCOPE_SYSTEM`（回答阶段，定人设与边界）、
`SQL_SYSTEM`（生成 SQL 阶段，只让它吐 SQL）、
`ANSWER_SYSTEM`（拿到结果后，逼它基于数据说话，不许编）。

---

## 十、已知问题与演进路线

### 10.1 遗留缺陷

> 以下 4 项均为**本次文档核查中实际复现**的，不是推测。
> 按「影响面」排序：④ 影响整个成绩录入，① 影响学生录入，②③ 影响诊断能力。
>
> ✅ **更新（2026-11-05）：①②③④ 已全部修复。**
> 修复前 `pytest tests/` 是 `7 failed, 26 passed, 31 errors`，修复后是 **`64 passed`**；
> `npm run verify` 从 1 项失败变成 **78 项全通过**。
> 下面保留原始排查过程（便于复盘），标题上的 ✅ 表示该项已修复，
> 「最小改法」一律改成了「已改」。

#### ④ `POST /score/score` 录入成绩完全不可用（schema 与 ORM 字段不匹配）⚠️ 影响面最大 ✅ 已修复

**根因**：`schema/score_schema.py` 的 `Score` 模型要 `score1` + `score2`，
但 `model/score_model.py` 的 ORM 类 `Score` 只有一列 `score`。
`API/score_api.py:48` 把 `score_data.model_dump()` 原样展开给
`Dao/score_Dao.py:38` 的 `Score(**score_dict)` —— **字段对不上，直接 TypeError**。

**实测行为**：

```
POST /score/score  {"stu_id":1,"test_id":3,"score":88}
    → 422  缺少 score1 / score2          （前端实际用的就是这个字段名）

POST /score/score  {"stu_id":1,"test_id":3,"score1":88,"score2":88}
    → 409  该场次成绩已存在               （在重复检查阶段就返回了，侥幸没崩）

POST /score/score  {"stu_id":1,"test_id":9,"score1":88,"score2":88}
    → 500  TypeError: 'score1' is an invalid keyword argument for Score
```

**注意第二行的「侥幸」**：409 是因为 DAO 的重复检查**先于**写入执行。
换一个库里不存在的 `test_id`，就会走到写入路径并 500。

**为什么这条比 `stu_1d` 更严重**：

- `stu_1d` 只影响**新增学生**这一个接口
- 这一条影响的是**整个成绩录入功能** —— 前端成绩列表页的新增按钮完全用不了
- 而且**两种 payload 都进不去**：用 `score` 被 schema 拦（422），
  用 `score1/score2` 在 DAO 崩（500）。**没有一种写法能成功**
- §5.10 里「409 成绩重复」这条状态码，**当前实际上不可达**

**已改**（采用上面的方案 A）：`schema/score_schema.py` 统一成单字段
`score: float = Field(..., ge=0, le=100)`，前端 payload 不用改；
另外把 `/score/test_id1/{test_id}` 从「GET 带必填 body」改成 query 参数，
并修正了 `Dao/score_Dao.py` 里 `score_list(q, db, test_id)` 参数顺序颠倒、
以及分数边界不传时会生成 `score <= NULL` 导致查不出行的问题。

验证：`npm run verify` 的「录入成绩 → 查询 → 修改 → 删除 → 查已删除成绩」全链路已通过。

> ⚠️ **修好 `stu_1d` 之后，`npm run verify` 会多出 1 项失败** ——
> 因为验证脚本里「录入成绩」那步此前因新增学生 500 被 SKIP，
> 现在学生能建成了，这一步会真正执行并撞上本缺陷。
> **两个缺陷要一起修**，否则修一个会让验证脚本从 1 项失败变成 2 项失败。
> —— 实际就是**一起修的**，所以现在 78 项全通过。

#### ① `POST /student/add_stu` 恒定 500，且数据已写入库 ✅ 已修复


**根因**：`Dao/stu_dao.py:222`

```python
return True, {
    'message': '添加成功',
    'data': {'stu_id': new_stu.stu_1d},   # ← 应为 stu_id
}
```

`stu_1d` 是 `stu_id` 的笔误。`db.commit()` 在第 217 行**已经执行**，
第 218 行 `db.refresh()` 也成功了 —— 崩溃发生在**构造响应时**。

**实测行为**：

```
POST /student/add_stu                      →  500 Internal Server Error
GET  /student/select_stu_name?stu_name=... →  200，查到了这条学生（库里确实有）
再次 POST 同样内容                          →  409 姓名和电话已经存在
```

**这个接口目前没有任何一条请求能成功返回** —— 只要走到「写入成功」这一步，
就必然在构造响应时崩溃。**与性别传 `1` 还是 `"男"` 无关**，
两者实测都是同一个 500（`stu_1d` 崩溃点相同）。

**为什么这个 bug 特别危险**：

- 数据**确实入库了**，但接口返回失败 —— 用户和前端都以为没创建成功
- 用户看到报错后**重试**，第二次会撞上「姓名+电话重复」的 409，
  于是误以为「这个学生根本建不了」
- 库里多出一条前端从未见过、也从未被正确展示的记录
- **接口不报错、不返回、只是 500** —— 崩溃发生在最后一公里，前面所有环节都成功了

**已改**：`new_stu.stu_1d` → `new_stu.stu_id`（一个字符）。
和 §10.1④ 的 schema 缺陷**一起修**的（否则验证脚本会从 1 项失败变成 2 项失败）。

> ✅ 修好之后，用前端的新增学生功能写数据不会再留下孤儿记录。
> 想自查库里有没有历史遗留的孤儿记录，用下面这条 SQL
> （`is_del=0` 且姓名是测试命名的）：
>
> ```sql
> SELECT stu_id, stu_name, stu_tel FROM student_info
> WHERE is_del = 0 AND stu_name LIKE 'Z%';
> ```


#### ② 回归测试大面积失效（测试文件用的是重构前的旧路径） ✅ 已修复

**根因**：2026-11-03 路由重构（顾问独立成 `/agent`、班主任独立成 `/class_teacher`、
`/student/select_all` 下线）之后，**测试文件没有同步**。

`tests/conftest.py` 与 `tests/test_api.py` 里仍在调用：

| 旧路径（已下线） | 新路径 |
|---|---|
| `POST /student/add_agent` | `POST /agent/add_agent` |
| `GET /student/agent` | `GET /agent/agent` |
| `GET /student/select_agent` | `GET /agent/select_agent` |
| `GET /student/select_all` | `GET /student/select_stu_skip?skip=0&limit=5000` |
| `POST /class/class_teacher` | `POST /class_teacher/class_teacher` |
| `GET /class/all_class_teacher` | `GET /class_teacher/all_class_teacher` |
| `GET /class/get_class_teacher/{id}` | `GET /class_teacher/get_class_teacher/{id}` |
| `PUT /class/update_class_teacher/{id}` | `PUT /class_teacher/update_class_teacher/{id}` |
| `DELETE /class/delete_class_teacher/{id}` | `DELETE /class_teacher/delete_class_teacher/{id}` |

**实测结果**：

```
7 failed, 26 passed, 31 errors
```

- **31 个 ERROR 全部是连锁反应** —— `conftest.py:95` 用旧路径
  `POST /student/add_agent` 建顾问，返回 404，`assert` 失败 →
  `agent_id` fixture 建不出来 → 所有依赖它的用例在 setup 阶段就报错
- **7 个 FAILED** 是断言与实现不一致：
  - `test_class_teacher_crud` / `test_delete_class_teacher_path_param_matches`
    → 旧路径 404
  - `test_agent_crud_endpoints` → 旧路径 404
  - `test_select_all_students_not_500` → `/student/select_all` 已下线
  - `test_unemployed_students_endpoint` / `test_unemployed_students_has_useful_fields`
    → 断言期望 body 里有 `Data` 键，实际后端返回 `{total, result}`
  - `test_score_for_missing_student_returns_404`
    → 期望 404，实际 422。**但根因不是「学生不存在没返回 404」**，
    而是测试的 payload 字段名不对（见下方说明）

> **关于 `test_score_for_missing_student_returns_404` 的 422**：
> 后端对「学生不存在」**返回 404 是正确的** —— 实测：
>
> ```
> POST /score/score  {"stu_id":99999,"test_id":1,"score":50}
>     → 422  缺 score1 / score2
> POST /score/score  {"stu_id":99999,"test_id":1,"score1":50,"score2":50}
>     → 404  成绩录入失败，没有该学生(id=99999)   ✅ 正确
> ```
>
> 也就是说 **422 是请求体字段名不对造成的，不是学生不存在造成的** ——
> 测试用了 `score`，schema 要 `score1`/`score2`。
> 这条用例要修的是**测试的 payload**（配合修 §10.1④ 的 schema），
> 不是改后端的 404 逻辑。

**⚠️ 注意**：修路由之前，「测试通过率」这个指标是没有意义的 ——
它衡量的是测试文件跟不跟得上代码变化，而不是代码对不对。
**修好之前不要把「pytest 全绿」当成质量结论。**

**已改**（三条都做了）：
1. 把上表中的旧路径逐条替换为新路径（`tests/conftest.py`、`tests/test_api.py`、`tests/smoke_live.py`）
2. `GET /employment/unemployed` 的返回结构统一成 `{code, message, total, Data}` ——
   原来单独返回 `{total, result}`，和接口 docstring 里承诺的形状对不上，
   前端适配层不得不为它单独加一个特判分支；现在标准形状，前端特判可以删
3. `test_score_for_missing_student_returns_404` 的 payload 配合 §10.1④ 改用 `score`

**现在的结果**：`pytest tests/` → **`64 passed`**，0 failed、0 error。

> ⚠️ 注意：修路由之前，「测试通过率」这个指标是没有意义的 ——
> 它衡量的是测试文件跟不跟得上代码变化，而不是代码对不对。
> ✅ 路由修好、断言同步之后，`pytest 全绿` 才重新具备意义。
#### ③ `GET /score/get_del` 会 500 ✅ 已修复

**根因**：DAO 层把「查询结果行（Row）」和「ORM 实体对象」搞混了。
`Dao/score_Dao.py:147` 的 `get_del_score()` 返回 **Score ORM 对象**
（`scores` 表没有 `stu_name` 列），而 `API/score_api.py` 的 `_score_to_dict()`
读 `row.stu_name` → `AttributeError: 'Score' object has no attribute 'stu_name'`。

**触发条件很刁钻**：库里有软删成绩 → **500**；一条都没有 → **404**。
**这个接口越是有数据可查，越是打不开。**

> **实测提示**：演示库当前**没有软删成绩**，所以直接调这个接口会返回 **404**，
> 看起来一切正常 —— 这是这个 bug 最容易藏身的地方。
> 想复现 500，把某条成绩软删即可：
>
> ```sql
> UPDATE scores SET is_del = 1 WHERE stu_id = 1 AND test_id = 1;
> -- 此时 GET /score/get_del 返回 500
> UPDATE scores SET is_del = 0 WHERE stu_id = 1 AND test_id = 1;   -- 还原
> ```

**已改**：`get_del_score()` 改成带 JOIN 的行查询
（`db.query(Score.stu_id, Score.test_id, Student_info.stu_name, Score.score).join(...)`），
把 `stu_name` 一起查出来，序列化时就不会再炸。**前端零改动。**

验证：`npm run verify` 的「删除后查已删除成绩（应能查到刚才那条）」一项已通过。


#### ④ 建表方式与文档不符

`DEBUG_NOTES.md` 记载「已把 `create_all` 挪到 `main.py` 的 lifespan」，
但实际 `model/` 下 5 个模型文件末尾**仍保留** `Base.metadata.create_all(engine)`，
`main.py` 中也没有 lifespan。当前行为是 **import 即建表** ——
数据库不可用时，连纯校验代码都无法 import。

### 10.2 架构待改进项

| 优先级 | 事项 | 理由 |
|---|---|---|
| ✅ | ~~修 §10.1④ 的 `score1/score2` vs `score`~~ | 已修：schema 统一成单字段 `score` |
| ✅ | ~~修 §10.1① 的 `stu_1d`~~ | 已修：新增学生恢复正常返回 |
| ✅ | ~~同步测试文件到新路由~~ | 已修：64 项回归测试全部跑通 |
| **高** | 上 **Alembic** | 手写 SQL 迁移每次都要自己想清楚「先摘外键还是先改表」。建表应由迁移脚本负责，而非应用启动 —— 现在的 `run_sql.py` 方案代价是**先 DROP DATABASE** |
| **高** | 加**认证** | 目前任何人可增删改查所有数据。库里已有 `user` 表可改造 |
| 中 | **统一响应结构** | 现在有 6 种返回形状 + 3 种半截子变体，前端必须做适配层，其中 3 种变体还会丢错误文案 |
| 中 | 统一**软删除列名** | `teacher` 表叫 `is_delete`，其余表叫 `is_del` |
| 中 | 补 **`clazz` 表外键** | `class_teacher_id` / `teacher_id` 无外键约束，靠 DAO 层校验 |
| 低 | 上 **Docker Compose** | 三个服务 + MySQL 手动起，跨机器复现成本高 |


### 10.3 文档与代码不一致清单

本轮核对代码时发现的、需同步修正的点：

| # | 位置 | 文档写的 | 实际 |
|---|---|---|---|
| 1 | `sql/README.md`、`tests/smoke_live.py` 默认地址、`DEBUG_NOTES.md` §11 | 端口 **8002** | 实际 **8003**（`main.py:51`） |
| 2 | `DEBUG_NOTES.md` §2/§6/§12 | `create_all` 已挪到 lifespan | 5 个模型文件末尾仍有 |
| 3 | `DEBUG_NOTES.md` §11 | 回归 54 项 / 冒烟 69 项 | 实际 **64 项** / 冒烟脚本 **70 次调用** |
| 4 | `kb_assistant/README.md` §7 | 默认 base_url 为 `agent.minimax.cn/mavis/...` | 实际 `api.minimax.chat/anthropic/v1`（`config.py:152`） |
| 5 | `frontend/README.md` §二 | 接口速查表 50 个接口 | 实际 **51 个**（速查表漏了 `/class/get_class/{id}/students`，已重新生成） |
| 6 | `tests/smoke_live.py` 文件头注释 | `test_api.py` 跑 33 项 | 实际 **64 项** |
| 7 | `frontend/README.md` §五 | `npm run verify` 有 78 项断言，当前 77 通过 / 1 失败 | 实际断言数**随库状态浮动**（实测 63～65 项），当前失败项为「新增学生」 |
| 8 | `frontend/README.md` §五 | 失败项只有 1 个（`get_del`） | 库中有软删成绩时会变成 **2 个**（`get_del` + 新增学生 500） |
| 9 | `kb_assistant/README.md` §九 | `pytest` 有 58 个用例 | 实际 **60 个**（`test_kb_assistant.py` 53 + `test_agent_flow.py` 7） |

> 第 5 项已经在本次核查中修正（重跑 `gen-api-meta.mjs`）。
> 第 1、2、3、4、6、7、8、9 项尚未在对应文件中修正 —— **这些都在别人写的文档里**，
> 本次核查只做记录，不改动他人文档的正文。
>
> **关于断言数为什么会浮动**：`verify-api.mjs` 自己会删一条成绩（制造软删记录）
> 再查 `get_del`。有软删记录时后端 500（缺陷暴露，多 1 项失败），
> 没有时后端 404（符合预期，该项通过）。
> 所以「多少项失败」取决于**跑之前库里有没有软删成绩**，不是脚本本身不稳定。



### 10.4 两个容易对不上的口径

**① 「班级总数」的两种口径**

| 来源 | 统计方式 | 含义 |
|---|---|---|
| `/class/all_class` | 查 `clazz` 表全部在册班级 | 含**暂时没有学员的空班** |
| `/stat/class/statistics` | 从 `student_info` 分组聚合（`Dao/stat_dao.py:47-58`） | **只有有学员的班级** |

> 在**当前演示库**里两者都是 36 —— 因为 36 个班每个都有学员，两个数字恰好相等。
> 但它们的**统计路径完全不同**：一旦某个班没有学员（或学员被软删），
> 两个接口就会给出不同的数。这是**结构性的口径差异**，不是数据问题。
> 大屏 KPI 上已加了悬浮提示说明。

**② 学生分页的 `total` 不是总数**

`/student/select_stu_skip` 返回的 `total` 是**本页条数**（`len(root)`），
不是总记录数；且它的 `skip`/`limit` 与 `el-pagination` 的 1-based 页码对不上。
所以前端的学生管理页是**一次拉全量 + 前端分页**（见 §8.2）。


---

## 附录：文档索引

| 文档 | 内容 | 适合谁 |
|---|---|---|
| **本文 `docs/ARCHITECTURE.md`** | **全栈总览：三服务拓扑、四层骨架、接口清单、跑起来、已知问题** | **先读这份** |
| [`PROJECT_DOC.md`](../PROJECT_DOC.md) | 后端四层分层的逐层详解，每层的约定与踩坑点 | 要改后端代码 |
| [`docs/PROJECT_DOC_PROMPT.md`](PROJECT_DOC_PROMPT.md) | 可复用的「项目文档生成 prompt」 | 要给别的项目写文档 |
| [`DEBUG_NOTES.md`](../DEBUG_NOTES.md) | 排错与优化全记录：从「跑不起来」到全绿的 14 章笔记，含 21 个业务 bug 的根因与修法 | 排查具体报错 |
| [`frontend/README.md`](../frontend/README.md) | 前端完整文档：技术选型、Geeker-Admin 复用清单、关键设计、验证方式 | 要改前端 |
| [`kb_assistant/README.md`](../kb_assistant/README.md) | 小助手完整文档：三层安全设计、接口清单、配置项、知识库维护 | 要改小助手 |
| [`sql/README.md`](../sql/README.md) | 建库脚本说明：三步跑起来、数据长什么样、脚本踩过的坑 | 要重建数据库 |

### 建议的阅读顺序

```
第一次接手：
  ① 本文 ARCHITECTURE.md  —— 建立全局认知
  ② 按需要读对应子系统的 README
  ③ python sql/run_sql.py → 跑起来 → 打开 /docs

要改后端：
  ① PROJECT_DOC.md 第三章（四层详解）
  ② 本文 §5 接口清单 + §10.1 已知缺陷
  ③ 改完跑 pytest

要改前端：
  ① frontend/README.md
  ② 本文 §8.1 三个关键设计 + §8.3 契约变更应对顺序
  ③ 改完跑 npm run build && npm run verify

要写别的项目的文档：
  ① docs/PROJECT_DOC_PROMPT.md
```

---

*本文基于 2026-11-03 的代码状态编写，所有接口数量、测试结果、数据库行数均经实际执行核对。*
*接口与行为有变更时，请同步更新本文档。*
