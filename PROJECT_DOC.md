# 学生管理系统 · 项目开发文档

> **📌 这是后端四层分层的「详版」。** 全栈总览（三服务拓扑、前端、小助手、
> 从零跑起来、已知缺陷）见 **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**。
>
> 两份文档的分工：本文讲透**后端每一层的约定与踩过的坑**；
> `ARCHITECTURE.md` 讲**整个系统怎么拼起来、现在有哪些已知问题**。
> 建议先读 `ARCHITECTURE.md`，再按需回到本文。

> 一套前后端分离的学生管理系统。后端 FastAPI + SQLAlchemy 2.0 + MySQL，
> 分四层（API / Dao / model / schema），51 个接口覆盖学生、成绩、就业、
> 班级、班主任、老师、顾问、统计 8 个模块。
>
> **本文以 FastAPI 后端为主体。** 前端（`frontend/`）与知识库小助手
> （`kb_assistant/`）为他人所写，本文档只给出必要篇幅的说明和启动方式，
> 详细文档见各自目录下的 README。

---

## 目录

- [一、项目概述](#一项目概述)
- [二、整体架构](#二整体架构)
- [三、后端：四层分层设计](#三后端四层分层设计)
- [四、数据库设计](#四数据库设计)
- [五、接口清单](#五接口清单)
- [六、从零跑起来](#六从零跑起来)
- [七、测试](#七测试)
- [八、前端](#八前端简要说明)
- [九、知识库小助手](#九知识库小助手简要说明)
- [十、已知问题与演进路线](#十已知问题与演进路线)
- [附录：配套文档索引](#附录配套文档索引)

---

## 一、项目概述

### 1.1 是什么

面向培训机构的学生管理系统，管理学生的**基本信息、成绩、就业去向**三类数据，
并在此之上提供班级、老师、顾问等组织维度与统计分析。

### 1.2 核心功能

| 模块     | 说明                    | 接口数    |
| ------ | --------------------- | ------ |
| 学生信息   | 学生增删改查、分页、按姓名/班级检索    | 7      |
| 顾问     | 招生顾问维护，重名拦截、按顾问检索学生   | 6      |
| 成绩     | 三次考试成绩录入与统计           | 8      |
| 就业     | 就业信息录入、检索、分页、未就业查询    | 6      |
| 班级     | 班级维护、班级学生查询           | 6      |
| 班主任    | 班主任维护                 | 5      |
| 老师     | 授课老师维护                | 5      |
| 统计分析   | 人数/男女比/平均分/薪资排名/就业时长等 | 8      |
| **合计** |                       | **51** |

### 1.3 技术选型

| 层      | 选型             | 版本           | 为什么                                                      |
| ------ | -------------- | ------------ | -------------------------------------------------------- |
| Web 框架 | FastAPI        | ≥0.110       | 自动生成 OpenAPI 文档，参数声明即校验，原生 async                         |
| ORM    | SQLAlchemy     | ≥2.0         | 2.0 的 `Session` 事务模型比 1.4 清晰，`select()` 风格更现代            |
| 数据库    | MySQL          | 5.7+ / 8.x   | 教学项目常规选型；8.x 需 `cryptography` 支撑 `caching_sha2_password` |
| 校验     | Pydantic       | ≥2.6         | v2 的 `model_validator` 让"部分更新"这类规则能写进 schema 层           |
| 驱动     | PyMySQL        | ≥1.1         | 纯 Python，无需编译                                            |
| 服务     | Uvicorn        | ≥0.27        | FastAPI 官方推荐 ASGI 服务器                                    |
| 测试     | pytest + httpx | ≥8.0 / ≥0.27 | `TestClient` 走进程内全链路；`httpx` 打真实服务                       |

### 1.4 运行环境

- Python 3.10+（用到 `str | None` 语法）
- MySQL 5.7+ / 8.x
- Node.js 20.19+ / 22.12+（仅前端需要）
- 依赖清单见 `requirements.txt`

---

## 二、整体架构

### 2.1 三个服务

```
        浏览器
          │
          ▼
   ┌──────────────┐   Vite dev server (5173)
   │   frontend   │   ├─ /api/* ──► FastAPI  (8003)  ──► MySQL
   │  Vue3 + TS   │   └─ /kb/*  ──► 小助手 (8010)  ──► MySQL（只读）
   └──────────────┘
```

| 服务 | 端口 | 启动方式 | 数据库权限 |
|---|---|---|---|
| FastAPI 后端 | **8003** | `python main.py` | 可写（root） |
| 知识库小助手 | 8010 | `kb_assistant/start.ps1` | 只读（`kb_ro`） |
| 前端 | 5173 | `cd frontend; npm run dev` | —— |

> 端口以 `main.py:51` 的 `APP_PORT` 默认值为准（8003）。
> 环境变量 `APP_PORT` / `APP_HOST` / `APP_RELOAD` 可覆盖。

**跨域不由后端解决**，而是靠 Vite dev proxy：浏览器只跟 5173 说话（同源），
由 Vite 在服务端转发到 8003 并去掉 `/api` 前缀。生产环境用 Nginx 反代 `/api` 即可，
后端与前端代码都无需改动（见 `frontend/vite.config.ts`）。

### 2.2 后端目录结构

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
├── frontend/                Vue3 管理后台（他人编写）
└── kb_assistant/            知识库小助手（他人编写）
```

---

## 三、后端：四层分层设计

这是本项目的核心。**每个接口的调用链固定是四步**：

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

### 3.1 第 4 层：schema（请求校验）

**职责**：只做一件事 —— 判断"前端传来的 JSON 长得对不对"。
放在这一层的收益是：DAO 拿到的永远是干净数据，且错误提示由 FastAPI
统一生成，Swagger 文档自动带上字段说明。

**关键约定一：`Field(...)` 的省略号 = 必填**

```python
stu_name: str = Field(..., max_length=10, description='学生姓名')        # 必填
stu_tel:  str | None = Field(default=None, max_length=20, ...)           # 选填
```

> ⚠️ **Pydantic v2 的坑**：`Field(max_length=10)` 不带 `default`，
> 默认值是 `PydanticUndefined`，字段会被当成**必填**。
> 「只改一个名字」也会被 422 拦下：
> `{"type": "missing", "loc": ["body", "stu_from"], "msg": "Field required"}`。
> 修改类接口必须写成 `Field(default=None, ...)`。

**关键约定二：部分更新靠 `exclude_unset`**

修改类接口（`UpdateStudent` / `UpdateAgent` / `EmpUpdate`）所有字段都是
`default=None`。接口层用 `model_to_dict(model, exclude_unset=True)`，
只把**请求体里真正出现过**的字段交给 DAO，没传的字段一个都不动。

**关键约定三：空白字符串 = 没填**

前端表单里用户没碰过的输入框提交上来是 `""` 而不是 `null`。
`UpdateStudent` 用一个 `mode='before'` 的校验器把空白串统一转成 `None`：

```python
@model_validator(mode='before')
@classmethod
def _blank_to_none(cls, data):
    if not isinstance(data, dict):
        return data
    return {k: (None if isinstance(v, str) and not v.strip() else v)
            for k, v in data.items()}
```

必须用 `mode='before'` —— `after` 跑的时候字段已校验过，空串早被 `pattern` 拦成 422 了。

**关键约定四：`SexField` 兼容历史写法**

`schema/enums.py` 里 `Sex` 继承 `str`，值是 `'男'` / `'女'`。
`SexField = Annotated[Sex, BeforeValidator(_to_sex)]` 让一个字段同时接受
`"男" / "女" / 1 / 0 / "1" / "0" / "male" / "M"` 等多种写法，内部统一成枚举。

> `Sex` **必须**覆写 `__str__`。Python 3.10 中 `str(Sex.MALE)` 返回
> `'Sex.MALE'`，而 pymysql 写库前会做 `str(value)`，于是性别列会被写成
> 字符串 `'Sex.MALE'` —— **不报错，但数据全废**。

**关键约定五：跨字段规则写进 schema**

```python
# schema/emp_request.py
@model_validator(mode='after')
def check_date_order(self):
    if self.offer_date < self.open_date:
        raise ValueError('收到offer的时间不能早于简历开放时间')
```

offer 早于简历开放是业务上不可能的数据，在入口就拦掉，
好过等统计接口算出负数时长才发现。

### 3.2 第 3 层：model（ORM 模型）

7 张表对应 7 个 ORM 类。**每个模型文件末尾都有 `Base.metadata.create_all(engine)`**，
所以启动服务时表会自动建好，不必手动执行 DDL。

`model/__init__.py` 集中导入所有模型，原因是 SQLAlchemy 的 `relationship()`
认的是**类名字符串**（如 `relationship("Class", ...)`），必须先在类注册表里登记。

> ⚠️ **导入顺序不能随便调**。因为每个文件末尾都会 `create_all`，
> 而建表有先后顺序：被外键引用的表必须先建。
> 当前顺序 `class_model → student_table → score_model → teacher → employment`
> 依据的是：`clazz` ← `student_info`，`agent` ← `student_info`，`student_info` ← `employment`。
> 把 `student_table` 提前会直接 `NoReferencedTableError`。

### 3.3 第 2 层：Dao（数据访问）

**统一返回约定**：每个函数返回 `(ok, result)` 二元组。

```python
ok, result = add_agent(db, model_to_dict(agent_data))
if not ok:
    raise HTTPException(status_code=result['status_code'], detail=result['message'])
```

- 成功：`result` 是数据（ORM 对象或 dict）
- 失败：`result` 是 `{'message': '...', 'status_code': 409}`，接口层直接翻译成 HTTP 异常

DAO 层负责**业务规则**而非格式校验：顾问/班级是否真实存在、重名拦截、
软删除过滤（`is_del == 0`）、修改字段白名单。

**软删除**：所有查询都要带 `is_del == 0` 过滤。删除接口只置 `is_del = 1`，
不做物理删除。

**修改白名单**（`Dao/stu_dao.py`）：

```python
STU_UPDATABLE_FIELDS = {
    'stu_name', 'stu_from', 'stu_school', 'stu_major',
    'enroll_date', 'gra_date', 'edu_bg', 'stu_sex',
    'stu_age', 'stu_class_id', 'agent_id', 'stu_tel',
}
```

白名单之外的 key（尤其是 `stu_id`、`is_del`）会被静默忽略，
避免前端传脏字段直接改到主键或软删标记上。

### 3.4 第 1 层：API（接口层）

**职责边界**：只做三件事 —— 组织参数、调用 DAO、翻译异常。
**不写业务判断**（那是 Dao 的事），**不写格式校验**（那是 schema 的事）。

路由前缀和分组标签统一在 `main.py` 挂载：

```python
app.include_router(router01, prefix='/student', tags=['学生基本信息接口'])
app.include_router(router07, prefix='/agent',   tags=['顾问信息管理'])
```

所以 `API/stu_info_api.py` 里同一个文件定义了 `router01`（学生）和
`router07`（顾问）两个路由器。

### 3.5 database.py：唯一的连接管理点

整个项目只有这一个文件负责"怎么连数据库"：

| 对象 | 作用 |
|---|---|
| `engine` | 连接池。`pool_size=5`、`pool_recycle=3600`、`pool_pre_ping=True` |
| `Base` | 所有 ORM 模型的基类 |
| `Session` | 会话工厂 |
| `get_db()` | FastAPI 依赖，每请求一个 Session |

**两个必须记住的配置**：

- `pool_pre_ping=True` —— 取连接前先 ping 一下，服务器已断开就自动换一条。
  这一条能挡掉绝大多数"服务跑了一晚上就崩"的线上事故。
- `pool_recycle=3600` —— MySQL 默认 8 小时后断开空闲连接，
  而连接池不知道这件事。

**`get_db()` 用 `yield` 而不是 `return`**：FastAPI 会在响应发出去之后，
再执行 `yield` 之后的部分来关连接。

**异常分支必须 `rollback()`**：否则一个"坏掉的会话"会被还回连接池，
下一个人拿到它照样报错 —— 故障会莫名其妙地传给别人。

### 3.6 utils.py：Pydantic → ORM 的安全转换

```python
def model_to_dict(model: BaseModel, exclude_unset: bool = False) -> dict:
    data = model.model_dump(exclude_unset=exclude_unset)
    return {
        key: (value.value if isinstance(value, Enum) else value)
        for key, value in data.items()
    }
```

**为什么要拆 Enum**：直接 `model_dump()` 拿到的是枚举成员本身（`Sex.MALE`）
而不是 `'男'`。`Enum` 虽继承 `str`，但某些序列化路径会把它打印成 `'Sex.MALE'`，
写进数据库就成了脏数据。

**`exclude_unset` 两种模式的区别**：

| 模式 | 前端传 `{"stu_school": "新大学"}` 的结果 | 用在哪 |
|---|---|---|
| `False`（默认） | 12 个 key，没填的是 `None` | 新增接口（字段本应全必填，少传应被 schema 挡成 422） |
| `True` | 只有 1 个 key | 修改接口（只改用户真传了的） |

---

## 四、数据库设计

### 4.1 表清单（7 张）

| 表 | ORM 类 | 含义 | 行数（演示库） |
|---|---|---|---|
| `agent` | `Agent` | 招生顾问 | 12 |
| `class_teacher` | `Class_teacher` | 班主任 | 12 |
| `teacher` | `Teacher` | 授课老师 | 24 |
| `clazz` | `Class` | 班级（6 专业方向 × 6 期） | 36 |
| `student_info` | `Student_info` | 学生 | 200 |
| `scores` | `Score` | 成绩（每人 3 次考试） | 600 |
| `employment` | `Emp` | 就业信息 | 134 |
| | | **合计** | **1018** |

### 4.2 关系图

```
clazz ──┬─< student_info >──┬── agent
        │                   └── employment
        └── class_teacher_id（无外键约束，DAO 层校验）

teacher ── teacher_id（无外键约束）
```

> `clazz` 表的 `class_teacher_id` / `teacher_id` **刻意没写 ForeignKey**：
> 真实表结构里就没有这个外键约束，ORM 写了会和实际结构对不上。
> 业务上的"班主任/老师必须存在"由 `Dao/class_dao.py` 检查。

### 4.3 关键字段约定

| 约定 | 说明 |
|---|---|
| **软删除** | 每张表都有 `is_del`（0 正常 / 1 已删除），**例外**：`teacher` 表叫 `is_delete` —— 命名不统一是历史遗留 |
| **薪资单位** | 全项目统一「**元/月**」。填 `25000` 就是 25000 元/月 |
| **性别存储** | 存 `'男'` / `'女'` 字符串，不是 int。与 `Sex` 枚举一一对应 |
| **班级主键** | `clazz.stu_class_id` **不自增**，人工指定（1 号班就是 1） |
| **就业日期** | `open_date`（简历开放）与 `offer_date`（收到 offer）均为必填，否则「就业时长」指标算不出来 |
| **建表时机** | 应用启动时 `create_all`，**只建表不改表**。改了 `model/` 的字段必须重跑 `sql/run_sql.py` |

### 4.4 数据库层约束

`sql/01_create_schema.sql` 里已经建好的约束（ORM 模型里没有全部体现）：

| 表              | 约束                                      | 说明                        |
| -------------- | --------------------------------------- | ------------------------- |
| `student_info` | `fk_student_class` / `fk_student_agent` | 外键指向 `clazz` / `agent`    |
| `student_info` | `ck_stu_sex` CHECK                      | 性别只允许 `'男'` / `'女'`，防止脏数据 |
| `employment`   | `uk_emp_stu_id` 唯一索引                    | 一个学生最多一条就业记录              |
| `scores`       | `idx_scores_stu_id` 索引                  | 按学生查成绩                    |
| 全局             | `utf8mb4` + InnoDB                      | 支持完整中文与 emoji             |

**数值类型的选择**：

- `employment.salary` 用 `DECIMAL(10,2)` —— 金额必须用定点数，
  `FLOAT` 的二进制浮点误差会让金额对不上账。
- `scores.score` 用 `FLOAT` —— 考试分数本身是离散整数，用浮点存储足够。

> ⚠️ ORM 模型 (`model/`) 与 SQL 脚本 (`sql/01_create_schema.sql`) 是**两份独立定义**。
> 改了模型字段后，必须重跑 `sql/run_sql.py` 让库结构跟上，
> 否则 `create_all` 不会修改已存在的表 —— **而且不报任何错**。

> **薪资单位为什么值得单独说**：种子数据最初写的是 `27.74`（心里想的是"27.74 千"），
> 而接口写进去的是 `25000`，同一张表出现两种量级，"薪资前五"的统计直接失真 ——
> **而且不报任何错**。所以 `model/employment.py` 和 `schema/emp_request.py`
> 都把单位写死在注释上了。

---

## 五、接口清单

> 完整交互式文档：启动服务后访问 `http://127.0.0.1:8003/docs`（Swagger UI）。

### 5.1 学生 `/student`

| 方法 | 路径 | 说明 | 成功返回 |
|---|---|---|---|
| POST | `/student/add_stu` | 新增学生 | 201 |
| GET | `/student/select_stu_id` | 按 id 查询 | `{code,message,Data}` |
| GET | `/student/select_stu_skip` | 分页查询（`skip`/`limit`） | `{code,message,total,Data}` |
| GET | `/student/select_stu_name` | 按姓名查询 | `{code,message,Data}` |
| GET | `/student/select_stu_class` | 按班级查询 | `{code,message,Data}` |
| PUT | `/student/update_stu_class` | 修改学生（只改传了的字段） | `{code,message,Data}` |
| DELETE | `/student/delete_stu` | 软删除学生 | `{code,message}` |

### 5.2 顾问 `/agent`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/agent/add_agent` | 新增顾问（重名 → 409） |
| GET | `/agent/agent` | 查询所有顾问 |
| GET | `/agent/select_agent` | 按 id 查询单个顾问 |
| PUT | `/agent/update_agent` | 修改顾问 |
| DELETE | `/agent/delete_agent` | 软删除顾问 |
| GET | `/agent/select_stu_agent` | 按顾问查询其名下学生 |

> `select_stu_agent` 虽然是"查学生"，但它挂在 `router07`（`/agent` 前缀）下，
> 与其余 5 个顾问接口同属一个 `APIRouter`，因此计入顾问模块而非学生模块。

### 5.3 成绩 `/score`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/score/score` | 录入成绩 |
| GET | `/score/stu_id/{stu_id}` | 查询单个学生的考试成绩 |
| GET | `/score/test_id/{test_id}` | 查询单次考试次序的学生成绩 |
| GET | `/score/test_id1/{test_id}` | 同上（另一入口） |
| GET | `/score/stu_id/{stu_id}/test_id/{test_id}` | 查询单个学生的单次考试 |
| PUT | `/score/put` | 修改成绩 |
| DELETE | `/score/del/stu_id/{stu_id}/test_id/{test_id}` | 删除成绩 |
| GET | `/score/get_del` | 查询已删除的成绩 ⚠️ **见第十节** |

### 5.4 就业 `/employment`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/employment/create` | 添加就业信息 |
| GET | `/employment/search` | 条件查询 |
| GET | `/employment/page` | 分页查询 |
| GET | `/employment/unemployed` | 查询未就业学生 |
| PUT | `/employment/put/{stu_id}` | 按学号修改 |
| DELETE | `/employment/delete/{stu_id}` | 删除 |

### 5.5 班级 `/class` 与班主任 `/class_teacher`

| 方法     | 路径                                         | 说明        |
| ------ | ------------------------------------------ | --------- |
| POST   | `/class/`                                  | 新建班级      |
| PUT    | `/class/update_class/{stu_class_id}`       | 修改班级      |
| DELETE | `/class/delete_class/{stu_class_id}`       | 删除班级及班级学员 |
| GET    | `/class/get_class/{stu_class_id}`          | 查询班级信息    |
| GET    | `/class/get_class/{stu_class_id}/students` | 查询班级所有学生  |
| GET    | `/class/all_class`                         | 查询所有班级    |
| POST   | `/class_teacher/class_teacher`             | 新增班主任     |
| PUT    | `/class_teacher/update_class_teacher/{id}` | 修改班主任     |
| DELETE | `/class_teacher/delete_class_teacher/{id}` | 删除班主任     |
| GET    | `/class_teacher/get_class_teacher/{id}`    | 查询单个班主任   |
| GET    | `/class_teacher/all_class_teacher`         | 查询所有班主任   |

### 5.6 老师 `/teacher`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/teacher/` | 新增老师 |
| GET | `/teacher/` | 查询所有老师 |
| GET | `/teacher/{teacher_id}` | 按 id 查询 |
| PUT | `/teacher/{teacher_id}` | 修改老师 |
| DELETE | `/teacher/{teacher_id}` | 删除老师 |

### 5.7 统计 `/stat`

| 方法  | 路径                                | 说明              |
| --- | --------------------------------- | --------------- |
| GET | `/stat/students/over_age`         | 查询超过指定年龄的学员     |
| GET | `/stat/class/statistics`          | 各班人数及男女人数       |
| GET | `/stat/score/all_above_80`        | 各次考试均 80 分以上的学生 |
| GET | `/stat/score/failed_twice`        | 两次以上不及格的学生      |
| GET | `/stat/score/avg_by_class`        | 各班平均分（降序）       |
| GET | `/stat/emp/top5_salary`           | 薪资最高前五名         |
| GET | `/stat/emp/duration`              | 每个学生的就业时长       |
| GET | `/stat/emp/avg_duration_by_class` | 各班平均就业时长        |

### 5.8 响应格式不统一（重要）

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

另外，**成绩和班级、班主任三个模块的响应字段名是中文的**
（`学生编号` / `考试序次` / `分数` / `班级id` / `班主任名字` 等），
请求体反而是英文的。这是老代码留下的约定。

> 前端的应对方式：在 Axios 响应拦截器里统一拆包成
> `{code, message, data, total}`，业务层只看到一种形状；
> 中文字段在 `src/utils/mappers.ts` 里转英文。
> **后端要改返回格式，只需改前端 `http.ts` 一个文件。**

### 5.9 状态码语义

| 状态码 | 含义 | 触发场景 |
|---|---|---|
| 200 / 201 | 成功 / 创建成功 | —— |
| 400 | 请求不合法 | 修改接口一个有效字段都没传 |
| 404 | 资源不存在 | 按 id 查不到、查顾问名下无学生 |
| 409 | 冲突 | 新增顾问重名 |
| 422 | 校验失败 | Pydantic 层拦截（自动生成） |
| 500 | 服务端错误 | 未预期的异常 |

---

## 六、从零跑起来

### 6.1 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.10+ | 用到 `str \| None` 语法 |
| MySQL | 5.7+ / 8.x | 8.x 需 `cryptography` |
| Node.js | 20.19+ 或 22.12+ | 仅前端需要，Vite 8 的硬性要求 |

### 6.2 四步走

```powershell
# 第 1 步：建库 + 灌 1018 条测试数据（项目根目录执行）
#         会自动建 student_ms_demo 库，不需要你预先手动建库
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

### 6.3 改过 model 之后

`create_all` **只建表、不改表**。改了 `model/` 里的字段必须重跑：

```powershell
python sql/run_sql.py
```

否则你改的字段不会生效，而且**不报任何错**。

### 6.4 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DB_HOST` | —— | 数据库地址 |
| `DB_PORT` | —— | 数据库端口 |
| `DB_NAME` | —— | 数据库名，应为 `student_ms_demo` |
| `DB_USER` | —— | 数据库账号 |
| `DB_PASSWORD` | —— | 数据库密码 |
| `APP_HOST` | `127.0.0.1` | 后端监听地址 |
| `APP_PORT` | `8003` | 后端监听端口 |
| `APP_RELOAD` | `0` | 设为 `1` 开启热重载 |

> `.env` **不要提交到 git**（已在 `.gitignore` 中）。
> 但**直接拷贝整个文件夹会绕过 gitignore** —— 给不完全信任的人时，
> 记得手动删掉 `.env`，让对方自己填。

---

## 七、测试

### 7.1 两套测试，跑的时机不同

| 脚本 | 类型 | 数量 | 怎么跑 | 什么时候跑 |
|---|---|---|---|---|
| `tests/test_api.py` | 回归测试 | **64** 项 | 进程内 `TestClient`，不起服务 | 开发中随时跑，CI 跑这个 |
| `tests/smoke_live.py` | 端到端冒烟 | **65** 项 | 打**真实运行中**的服务 | 发布前跑这个 |

```powershell
# 回归测试（64 项）
python -m pytest tests/ -q

# 端到端冒烟（65 项）—— 需要先启动服务
python main.py
python tests/smoke_live.py http://127.0.0.1:8003
```

### 7.2 设计要点

- **造数据用带时间戳的唯一命名**（`测试学生{STAMP}`），
  所以可以反复执行，不会互相打架，也不会撞上已有数据。
- 冒烟测试覆盖**写接口的完整生命周期**：
  创建 → 查询 → 修改 → 删除。
- 错误路径也在测：重复顾问 → 409、不存在的 id → 404、软删后查询 → 404。

### 7.3 前端验证脚本

前端另有一套端到端验证（见 `frontend/README.md`）：

```powershell
cd frontend
node scripts/check-api-paths.mjs   # 拿后端 openapi.json 逐条比对前端路径，查断链
npm run build                      # 类型检查 + 生产构建
npm run verify                     # 接口层端到端验证
```

> **后端改过路由之后，先跑 `check-api-paths.mjs`** ——
> 它会把前端每个 `get/post/put/del(...)` 的路径跟 `openapi.json` 对一遍，
> 输出断链清单，比逐个模块试错可靠得多。

---

## 八、前端（简要说明）

> 他人编写，本文档只给必要信息。完整文档见 **`frontend/README.md`**。

- **技术栈**：Vue 3 + TypeScript + Element Plus + Pinia + Vite 8
- **UI 骨架**：复用开源 [Geeker-Admin](https://github.com/HalseySpicy/Geeker-Admin)（MIT）
- **端口**：5173，`/api` 代理到 8003，`/kb` 代理到 8010
- **登录**：演示模式，任意账号密码可进，预填 `admin` / `123456`

**一键启动（前后端一起）**：

```powershell
cd frontend
.\scripts\start-all.ps1
```

脚本会依次检查 Node 版本、`node_modules`、`.venv`、`.env`，
拉起 FastAPI 并**等到它真正能响应且能查到数据库**才继续拉起 Vite。

**接手时需要知道的两个设计**：

1. **响应适配层**（`src/api/http.ts`）—— 统一后端 6 种返回形状，
   并把 422 的 Pydantic 报错中文化。
2. **中文字段转英文**（`src/utils/mappers.ts`）—— 成绩/班级/班主任三个模块
   的响应字段名是中文的，在这一层统一转成英文字段名。
   不转的话界面会出现「表格有行数但整列空白」。

---

## 九、知识库小助手（简要说明）

> 他人编写，本文档只给必要信息。完整文档见 **`kb_assistant/README.md`**。

嵌在页面右下角的自然语言问答助手，用问话直接查库出答案。

- **模型**：MiniMax `MiniMax-M3.1-Flash`（Anthropic Messages 协议）
- **端口**：8010，**独立进程**，与主后端互不影响
- **数据库**：**只读账号** `kb_ro`，只看 `student_ms_demo`
- **安全**：三层防线 —— SQL 只读闸门（禁写操作/危险函数/表白名单）、
  领域边界守卫、只读数据库账号
- **形态**：悬浮球 + 聊天抽屉，SSE 流式回答，登录后自动出现

**启动**：

```powershell
cd kb_assistant
.\start.ps1
```

**依赖**：`kb_assistant/requirements.txt`（与主后端分开装）。
**配置**：在根目录 `.env` 补 `MINIMAX_API_KEY` 即可。

---

## 十、已知问题与演进路线

### 10.1 遗留缺陷

**① `GET /score/get_del` 会 500** ✅ **已修复**

根因：DAO 层把「查询结果行（Row）」和「ORM 实体对象」搞混了。
`Dao/score_Dao.py` 的 `get_del_score()` 返回 **Score ORM 对象**
（`scores` 表没有 `stu_name` 列），而 `API/score_api.py` 的 `_score_to_dict()`
读 `row.stu_name` → `AttributeError: 'Score' object has no attribute 'stu_name'`。

触发条件很刁钻：库里有软删成绩 → **500**；一条都没有 → **404**。
**这个接口越是有数据可查，越是打不开。**

已改：`get_del_score()` 改成和其余查询一样的写法 ——
显式列出需要的列并 `JOIN` 学生表把 `stu_name` 一起查出来。
验证：`npm run verify` 的「删除后查已删除成绩」一项已通过。

**② `POST /student/add_stu` 恒定 500，且数据已写入库** ✅ **已修复**

根因：`Dao/stu_dao.py` 构造响应时写成了 `new_stu.stu_1d`（`stu_id` 的笔误）。
`db.commit()` 早已执行、数据也进了库，崩溃发生在**构造响应**这一步 ——
所以用户和前端都以为没创建成功，重试又撞上「姓名+电话重复」的 409，
库里多出一条前端从未见过的孤儿记录。

已改：`new_stu.stu_1d` → `new_stu.stu_id`。

**③ 成绩录入完全不可用** ✅ **已修复**

根因：`schema/score_schema.py` 要 `score1` + `score2` 两个字段，
而 ORM（`model/score_model.py`）和数据库表 `scores` 都只有**一列** `score`。
于是传 `{"score": 88}` 被 schema 拦成 422，传 `{"score1":..,"score2":..}` 在 DAO 崩成 500
——**两种写法都进不去**，整个成绩录入功能不可用。

已改：schema 统一成单字段 `score`（与 ORM、数据库、前端 payload 三方一致），
另外把 `/score/test_id1/{test_id}` 从「GET 带必填 body」改成 query 参数，
并修正了 DAO 里 `score_list(q, db, test_id)` 参数顺序颠倒的问题。

**④ 建表方式与文档不符**（未修）

`DEBUG_NOTES.md` 记载「已把 `create_all` 挪到 `main.py` 的 lifespan」，
但实际 `model/` 下 5 个模型文件末尾**仍保留** `Base.metadata.create_all(engine)`，
`main.py` 中也没有 lifespan。当前行为是 **import 即建表** ——
数据库不可用时，连纯校验代码都无法 import。

### 10.2 架构待改进项

| 优先级 | 事项                   | 理由                                                               |
| --- | -------------------- | ---------------------------------------------------------------- |
| 高   | 上 **Alembic**        | 手写 SQL 迁移每次都要自己想清楚"先摘外键还是先改表"。Alembic 能自动 diff。建表应由迁移脚本负责，而非应用启动 |
| 高   | 加**认证**              | 目前任何人可增删改查所有数据。库里已有 `user` 表可改造                                  |
| 中   | **统一响应结构**           | 现在有 6 种返回形状，前端必须做适配层。统一成 `{code, message, data}` 后适配层可删          |
| 中   | 统一**软删除列名**          | `teacher` 表叫 `is_delete`，其余表叫 `is_del`                           |
| 中   | 补 **`clazz` 表外键**    | `class_teacher_id` / `teacher_id` 无外键约束，靠 DAO 层校验                |
| 低   | 上 **Docker Compose** | 三个服务 + MySQL 手动起，跨机器复现成本高                                        |

### 10.3 已知文档不一致

本轮核对代码时发现的、需同步修正的点：

| # | 位置 | 文档写的 | 实际 |
|---|---|---|---|
| 1 | `DEBUG_NOTES.md` §11、`sql/README.md`、`sql/run_sql.py`、`tests/smoke_live.py` | 端口 **8002** | 实际 **8003**（`main.py:51`） |
| 2 | `DEBUG_NOTES.md` §2/§6/§12 | `create_all` 已挪到 lifespan | 5 个模型文件末尾仍有 |
| 3 | `DEBUG_NOTES.md` §11 | 回归 54 项 / 冒烟 69 项 | 实际 **64** 项 / **65** 项 |
| 4 | `kb_assistant/README.md` §7 | 默认 base_url 为 `agent.minimax.cn/mavis/...` | 实际 `api.minimax.chat/anthropic/v1`（`config.py:152`） |

---

## 附录：配套文档索引

| 文档 | 内容 |
|---|---|
| `DEBUG_NOTES.md` | 排错与优化全记录：从"跑不起来"到全绿的 14 章笔记，含 21 个业务 bug 的根因与修法 |
| `frontend/README.md` | 前端完整文档：技术选型、Geeker-Admin 复用清单、两个关键设计、验证方式 |
| `kb_assistant/README.md` | 小助手完整文档：三层安全设计、接口清单、配置项、知识库维护 |
| `sql/README.md` | 建库脚本说明：三步跑起来、数据长什么样、脚本踩过的坑 |

---

*文档基于 2026-11-03 的代码状态编写。接口与行为有变更时，请同步更新本文档。*
