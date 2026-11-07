# 数据库脚本说明

这个文件夹里是**从零建一个完整数据库 + 灌入 1018 条类真实测试数据**的全部脚本。

---

## 一、这个文件夹里有什么

| 文件 | 作用 |
|---|---|
| `01_create_schema.sql` | 建库 + 建 7 张表（含外键、唯一约束、CHECK 约束、索引） |
| `02_seed_demo_data.sql` | 插入 1018 条类真实数据（200 个学生） |
| `run_sql.py` | 一键执行上面两个文件（**推荐用这个**） |

---

## 二、三步跑起来

### 第 1 步：建库 + 灌数据

在**项目根目录**（不是 `sql/` 目录）打开终端，执行：

```powershell
python sql/run_sql.py
```

你会看到：

```
======================================================================
目标数据库: student_ms_demo
======================================================================

>>> 执行 01_create_schema.sql（18 条语句）...
    [ 1] ok            DROP DATABASE IF EXISTS `student_ms_demo`
    ...
    ✓ 01_create_schema.sql 完成

>>> 执行 02_seed_demo_data.sql（27 条语句）...
    [ 4] 写入    12 行   INSERT INTO `agent` ...
    ...
    ✓ 02_seed_demo_data.sql 完成

======================================================================
student_ms_demo 建好了，数据统计：
======================================================================
    agent               12 行
    class_teacher       12 行
    clazz               36 行
    employment         134 行
    scores             600 行
    student_info       200 行
    teacher             24 行
    合计              1018 行
```

> **为什么不用 `mysql < xxx.sql`？**
> 那是 Linux / macOS 的 bash 语法，Windows 的 PowerShell 不支持。
> `run_sql.py` 就是为了绕开这个限制写的。
> （如果你用 Navicat / MySQL Workbench，可以直接打开 .sql 文件点"运行"，效果一样。）

### 第 2 步：把项目指向这个库

打开项目根目录的 `.env`，找到 `DB_NAME` 这一行，改成：

```ini
DB_NAME=student_ms_demo
```

> ⚠️ 改之前记得把原值 `student_ms` 记下来，那是你的老库。

### 第 3 步：启动服务

```powershell
python main.py
```

然后打开浏览器：**http://127.0.0.1:8002/docs**

这是 FastAPI 自动生成的接口文档，左边是 6 大模块共 50 个接口，
右边填个参数点"Try it out"就能直接调。

> **其实不跑第 1 步也能启动。**
> 每个模型文件末尾都有 `Base.metadata.create_all(engine)`，
> 启动服务时会自动把 7 张表建出来（表不存在才建，不会动已有数据）。
>
> 跑 `run_sql.py` 的价值在于：它还会**灌入 1018 条演示数据**，
> 并且保证表结构和 `01_create_schema.sql` **完全一致**。
> 改过 `model` 里的字段之后，也建议重跑一次 ——
> 因为 `create_all` 不会修改已经存在的表。

---

## 三、数据长什么样

| 表 | 行数 | 说明 |
|---|---|---|
| `agent`（顾问） | 12 | 业务上的"顾问"角色，负责招学生 |
| `class_teacher`（班主任） | 12 | |
| `teacher`（老师） | 24 | 授课老师 |
| `clazz`（班级） | 36 | 6 个专业方向 × 6 期 |
| `student_info`（学生） | **200** | ← 你要的"至少 200 条"就是这批 |
| `scores`（成绩） | 600 | 每个学生 3 次考试 |
| `employment`（就业） | 134 | 约 65% 的学生已就业 |

**数据是"像真的"，不是 111 / 222 / 333：**

- 学生姓名：随机组合的真实中文名（2~3 字）
- 手机号：1 开头 11 位，全局不重复
- 生源地：31 个省市
- 毕业院校：34 所真实高校
- 专业：38 个真实专业
- **每个学生都有归属顾问**（符合业务规则）
- 成绩：围绕一个基准分上下浮动，不是纯随机
- 就业：offer 时间一定晚于简历开放时间（符合"收到offer不能早于简历开放"的校验）
- **薪资单位统一是「元/月」**（不是千元、不是万元）。一条记录长这样：
  `('1', 1, '2025-06-09 00:00:00', '2025-11-06 00:00:00', '百度', 27740.00, 0)`
  —— 那个 `27740.00` 就是 27740 元/月。
  手工加数据时别写成 `27.74`（那会变成"月薪 27 块 7 毛"），也别写成 `27.74 万`。

> 这里踩过一个坑值得记：种子数据最初写的是 `27.74`（心里想的是"27.74 千"），
> 而接口写进去的是 `25000`，同一张表里出现了两种量级，
> "薪资前五"的统计直接失真 —— 而且**不报任何错**。
> 所以 `model/employment.py` 和 `schema/emp_request.py` 里都把单位写死在注释上了。

想看看效果，随便调几个接口：

```
GET /student/select_stu_skip?skip=0&limit=10    分页查学生（带顾问名）
GET /student/select_all                        查全部 200 个学生
GET /student/agent                             查 12 个顾问
GET /stat/class/statistics                     班级人数 + 男女比例
GET /stat/emp/top5_salary                      薪资前五
GET /stat/emp/duration                         就业时长
GET /employment/page?page=1&size=10            就业信息分页
```

---

## 四、几个要注意的地方

### ① 脚本会先删库重建

`01_create_schema.sql` 第 1 行是 `DROP DATABASE IF EXISTS`，
所以**目标库里的东西会被全部清空**。

默认目标是 `student_ms_demo`（一个全新的专供测试的库），
不会碰到你的 `student_ms`。但如果你把库名改成 `student_ms`，就会把老数据清掉！

### ② 想换个库名

```powershell
python sql/run_sql.py student_ms_test
```

或者直接改 `01_create_schema.sql` 里的两处 `student_ms_demo`
（`CREATE DATABASE` 和 `USE` 各一处），再改 `02_seed_demo_data.sql` 里的 `USE`。

### ③ 为什么 `01_create_schema.sql` 里有 `USE`，而以前的迁移脚本里没有？

不矛盾，是两回事：

- **迁移脚本**（给已经在跑的旧库打补丁用）：绝不能写 `USE`，
  因为执行器已经连好了目标库，写了 `USE` 会覆盖掉执行器的选择，
  演练时就等于在正式库上跑了。
- **本文件**（从零建库用）：`CREATE DATABASE` 之后必须 `USE` 一下，
  才知道后面的 `CREATE TABLE` 建到哪个库里去。

### ④ `run_sql.py` 里踩过的两个坑（都写进注释了）

1. **不能整文件一次性执行。**
   试过 `client_flag=MULTI_STATEMENTS`，文件中间的 `SET NAMES utf8mb4`
   会改变连接字符集，PyMySQL 解析后面的结果包时对不上，
   后面的 INSERT 被**静默跳过**—— 不报错，但一行数据都没插进去。
   所以改成用 `split_sql_statements()` 一条一条执行。

2. **必须 `commit()`。**
   PyMySQL 默认 `autocommit=False`，不提交的话连接一关闭就回滚。
   表现同样是"每条 INSERT 都显示成功，但查出来是 0 行"。

这两个坑的共同点：**都不报错**。所以脚本会逐条打印影响行数，
跑完还会重新连一次库统计总行数给你看。

---

## 五、想再加点数据？

直接在 `02_seed_demo_data.sql` 里照着格式加几行就行，比如给顾问表加一条：

```sql
INSERT INTO `agent` (`agent_id`, `agent_name`, `agent_sex`, `agent_age`, `is_del`) VALUES
    ('13', '张三', '男', 30, 0);
```

加完重新跑 `python sql/run_sql.py` 就行（会重建整个库）。
