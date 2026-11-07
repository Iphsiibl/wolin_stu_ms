# 排错与优化笔记

> 记录这次从「跑不起来」到「69 项接口冒烟 + 54 项回归测试全绿」的全过程。
> 每一条都是：现象 → 根因 → 修法 → 你以后该怎么避免。

---

## 目录

- [0. 一句话总结](#0-一句话总结)
- [1. 第一步：让它跑起来](#1-第一步让它跑起来)
- [2. 第二个坑：import 就建表，把真正的错误藏起来了](#2-第二个坑import-就建表把真正的错误藏起来了)
- [3. 第三个坑：create_all 只建表、不改表](#3-第三个坑create_all-只建表不改表)
- [4. 业务 Bug 清单（21 个）](#4-业务-bug-清单21-个)
- [5. 两个隐蔽的坑](#5-两个隐蔽的坑)
- [6. 架构优化](#6-架构优化)
- [7. 新增功能](#7-新增功能)
- [8. 本轮：合入学生模块 + 三层架构大改](#8-本轮合入学生模块--三层架构大改)
- [9. 第二轮：顾问改名 + 建库脚本 + 清理](#9-第二轮顾问改名--建库脚本--清理)
- [10. 第三轮：薪资单位 + employment 表被删 + 新接口](#10-第三轮薪资单位--employment-表被删--新接口)
- [11. 怎么跑](#11-怎么跑)
- [12. 我改了什么（文件清单）](#12-我改了什么文件清单)
- [13. 下一步该做什么](#13-下一步该做什么)
- [14. 第四轮：update_stu_class 改成「只改用户传了的字段」](#14-第四轮update_stu_class-改成只改用户传了的字段)

---

## 0. 一句话总结

你的项目**分层是对的**（API / Dao / model / schema 四层清晰），问题出在**边界没对齐**：
数据库结构、ORM 模型、Pydantic 校验、HTTP 语义，四个地方各自按自己的理解写，最后对不上。

调试这类问题的正确顺序是**从下往上**：

```
能启动  →  能连库  →  表结构和模型一致  →  单个接口正确  →  全部接口正确
```

绝大多数人卡住是因为跳过了中间三步，直接在第 4 步改业务代码。

---

## 1. 第一步：让它跑起来

### 1.1 依赖没装

```
ModuleNotFoundError: No module named 'pymysql'
```

环境里只有 `pydantic` 和 `uvicorn`，`fastapi` / `sqlalchemy` / `pymysql` / `python-dotenv` 都没有。

```powershell
pip install fastapi "sqlalchemy>=2.0" pymysql python-dotenv cryptography
```

> **教训**：项目根目录必须有一份 `requirements.txt`。它不只是给别人看的，
> 也是**你三个月后还能把环境装起来**的唯一依据。凭记忆敲依赖，早晚敲错。

### 1.2 `.env` 里的库名是错的

```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (1049, "Unknown database 'school_system'")
```

`.env` 写的是 `school_system`，但 MySQL 里根本没有这个库。

```
ai0923  day3homework  day4homework  demo  happy_moon_day
information_schema  mysql  performance_schema
school_db  student_ms  sys  test_employment  other_school
```

两个候选：

| 库 | 表 | 判断 |
|---|---|---|
| `other_school` | `employee`, `student_assessment`, `student_attendance`, `student_basic_info`, `student_employment` | **另一个项目**，表结构完全对不上 |
| `student_ms` | `clazz`, `employment`, `scores`, `student_info`, `user` | **就是这个项目**，表名和你的 ORM 模型一一对应 |

`.env` 改成 `DB_NAME=student_ms`。

> **教训**：`.env` 不要提交到 git（建 `.gitignore`），但要在 README 里写清楚
> 「需要先建哪个库、导入哪个 SQL 文件」。现在这个项目的表结构全靠 `create_all`
> 现场生成，换台机器就全乱了 —— 这是后面第 3 节要解决的。

---

## 2. 第二个坑：import 就建表，把真正的错误藏起来了

你的每个 `model/*.py` 末尾都有这么一行：

```python
Base.metadata.create_all(engine)
```

问题在于它写在**模块顶层**。于是：

```
import model.teacher
   └─> Base.metadata.create_all(engine)
          └─> 立刻连数据库
                 └─> 数据库不通 → ImportError: 1045 Access denied
```

结果就是：**你根本看不到真正的错误**，只看到一个 `ImportError`，
而真正的原因（密码错了 / MySQL 没启动 / 库名写错）被埋在最底下。

这行代码还带来一个更隐蔽的坏处：它让**每一个 model 文件都依赖数据库可用**，
连 `python -c "from schema.student_request import Student_request"` 这种纯校验代码都跑不了。

**修法**：把建表挪到服务启动时。

```python
# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(engine)
        logger.info('数据库表结构检查完成')
    except Exception:
        logger.exception('初始化数据库表结构失败，数据库相关接口将不可用')
    yield
```

```python
app = FastAPI(title='学生管理系统 API', lifespan=lifespan)
```

现在建表失败只是打一条日志，**服务照样起来**，其它不依赖数据库的接口照常工作，
报错也变成了真正的原因。

> **教训**：
> - 模块顶层只放「定义」，不放「动作」。建表、发请求、写文件这些有副作用的
>   事情，放进函数里，由明确的入口调用。
> - **导入一个模块不应该产生副作用**。这是 Python 里很硬的一条经验。

---

## 3. 第三个坑：create_all 只建表、不改表

这是整个项目最深的坑，也是最值得你记住的一个。

`create_all` 的语义是「**表不存在就建出来**」，它**从来不会修改已存在的表**。

所以当你的模型改了字段之后，数据库里的老表还是老结构 —— 除非你手动 `ALTER`。

我对比了 ORM 声明和数据库实际结构，发现两处漂移：

### `clazz` 表

| | ORM 声明 | 数据库实际 |
|---|---|---|
| 主键 | `stu_class_id` | `class_id` ❌ |
| `start_date` | 有 | **没有** ❌ |
| `class_teacher_id` | 有 | **没有** ❌ |
| `teacher_id` | 有 | **没有** ❌ |
| `is_del` | 有 | **没有** ❌ |

### `employment` 表

| | ORM 声明 | 数据库实际 |
|---|---|---|
| `id`（自增主键） | 有 | **没有** ❌ |
| `stu_id` | 普通列 | 主键 ❌ |

**漂移的直接后果**（这些 500 都是这么来的）：

- `SELECT ... FROM clazz` → `Unknown column 'clazz.start_date'`
- `SELECT ... FROM employment` → `Unknown column 'employment.id'`
- 班级模块里凡是碰 `start_date` / `teacher_id` / `is_del` 的查询全部报错

### 迁移脚本

放在 `migrations/` 下，每个文件一步，都带注释：

| 文件 | 干了什么 |
|---|---|
| `001_align_schema_to_models.sql` | `clazz` 主键改名 + 补 4 列；`student_info.stu_id` 改自增；`employment` 加自增主键 + 唯一索引；`scores.is_del` 补默认值 + 建索引；`agent.agent_age` 改 int |
| `002_sex_to_varchar.sql` | `stu_sex` 改字符串 + 加 CHECK 约束 |
| `003_add_agent_id_to_student.sql` | `student_info` 加 `agent_id` + 索引 + 外键 |
| `004_add_class_teacher_sex.sql` | `class_teacher` 加 `class_teacher_sex` |
| `run_migration.py` | 迁移执行器 |
| `verify_migrations.py` | **迁移演练工具**（见 3.1） |

```powershell
python migrations/run_migration.py migrations/001_align_schema_to_models.sql
```

### 3.1 迁移脚本必须演练 —— 而且我踩了一个大坑

写完迁移脚本，**别直接往正式库上跑**。我为此写了个 `verify_migrations.py`：

1. 造一个临时库，把「迁移前」的真实表结构还原进去
2. 用子进程把迁移脚本从头跑一遍
3. 和线上库**逐列比对**（列名 / 类型 / 可空 / 键）
4. 跑完自动删掉临时库

```powershell
python migrations/verify_migrations.py
```

**它当场抓出了一个致命设计缺陷。** 我原来的迁移脚本第一行是：

```sql
USE `student_ms`;
```

这行**硬编码了目标库**。执行器明明连的是临时库，被这一行一切，
**整个迁移实际跑在了正式库上**！

当时正式库已经是新结构，所以那些语句全部"无害地失败"了
（`Unknown column 'class_id'`、`Duplicate column 'start_date'`……），
纯属侥幸没造成破坏。如果正式库当时还是旧结构，这一轮"演练"
就等于在正式库上跑了一遍半成品迁移。

**修正**：迁移脚本里**不写 `USE xxx`**，目标库完全由执行器在连接时决定。
改完之后演练一次通过：

```
[一致] clazz  (6 列)
[一致] student_info  (12 列)
[一致] employment  (7 列)
[一致] scores  (5 列)
[一致] agent  (4 列)
验证通过 —— 迁移脚本可以从旧结构一把跑到目标结构。
```

> **教训**：
> - 迁移脚本是**一次性、不可逆**的操作，和业务代码完全不是一回事。
>   业务代码跑错了改代码就行，迁移脚本跑错了可能要把库恢复回去。
> - 凡是会**改变持久化状态**的脚本，都应该能先在一次性环境上完整跑一遍。
> - 脚本里写死库名，是把"在哪执行"这个决策从调用方抢走了 —— 原则是
>   **调用方决定目标，脚本只描述变更**。

> 顺手记一个 MySQL 的坑（迁移时我踩了两次）：
> **被外键引用的列不能直接改**，哪怕改的是「被引用方」。
> 正确顺序永远是：**摘外键 → 改结构 → 装回外键**。
> 另外 `ALTER TABLE ... DROP PRIMARY KEY` 和 `ADD COLUMN ... AUTO_INCREMENT`
> 不能写在同一条语句里，必须拆开 —— MySQL 会报
> `there can be only one auto column and it must be defined as a key`。

### 备份

改动前先 dump 一份，别裸奔：

```powershell
mysqldump -h localhost -P 3306 -u root -p --default-character-set=utf8mb4 `
  --databases student_ms --result-file=backup_student_ms_before_migration.sql
```

> 备份文件属于**一次性产物**，迁移验证通过后就可以删掉了（它还会在 `.gitignore` 里）。
> 但在删之前，先确认新库的数据确实没丢 —— 这次迁移后原有 5 个学生、
> 3 个班级、3 条就业信息全部完好。

> **教训**：`create_all` 是开发期的便利，**不是迁移方案**。
> 真正的项目要用 **Alembic**：
> ```powershell
> pip install alembic
> alembic init migrations
> alembic revision --autogenerate -m "add class start_date"
> alembic upgrade head
> ```
> 它会自动 diff 你的模型和数据库，生成 `ALTER TABLE` 语句，还能版本回滚。
> 你现在手写的这些 SQL，其实就是 Alembic 会替你自动生成的东西。

---

## 4. 业务 Bug 清单（21 + 12 个）

### 学生模块

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | 1 号班的学生加不进去 | `stu_class_id: int = Field(..., gt=1)`，`gt` 是严格大于，1 号班被排除。而库里实实在在有 1 号班 | 改成 `ge=1` |
| 2 | 只改一个字段也 422 | `stu_name: str \| None = Field(max_length=10)` **没写默认值**。Pydantic v2 里 `Field()` 不带 default 时默认值是 `PydanticUndefined`，字段变必填 | 全部改成 `Field(default=None, ...)` |
| 3 | 接口叫 `update_stu_class`，却改不了班级 | `UpdateStudent` 里压根没有 `stu_class_id`（也没有 `stu_age`） | 补上这两个字段 |
| 4 | 删不存在的学生返回 422 | 「人根本不存在」应该是 404，422 的语义是「格式没问题但处理不了」 | 改用 `NotFoundError` → 404 |
| 5 | `delete_stu` 参数是 `str` | 数据库里 `stu_id` 是 int 主键，靠 MySQL 隐式转换才能对上，还可能让索引失效 | 改成 `int` |
| 6 | `query_stu_class` 参数没类型标注 | FastAPI 只能按字符串处理 | 改成 `stu_class_id: int` |
| 7 | GET 接口里 `db.rollback()` | GET 不改数据，回滚没有语义；而且真正的回滚应该由 `get_db` 统一负责 | 删掉 |

### 就业模块（坏得最彻底的一块）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 8 | `/employment/search` 永远 500 | `get_emp_filter` 里写的是 `if not class_name:` —— **条件写反了**。`not class_name` 在「用户没传班级」时成立，于是每次都去过滤 `stu_class_name == None`，而这个字段**在模型里根本不存在** → `AttributeError` | 改成 `if class_name:`，班级名改从 `clazz.class_name` 取 |
| 9 | `/employment/page` 500 | `_emp_to_dict` 里用了 `e.student.stu_class_name` —— 同一个不存在的字段 | 显式 join `clazz` 取 `class_name` |
| 10 | 按性别筛永远查不到 | `stu_sex` 有**三种表示**：模型是 `int`、接口是 `SexEnum('男'/'女')`、统计代码里也是字符串。库里存 int，查询传字符串 → 匹配不上 | 统一成字符串存储（见第 5 节） |
| 11 | 薪资上下限颠倒 → 500 | API 层靠**比对错误文案**来区分 400 和 500：<br>`if data == '薪资下限不能大于薪资上限': raise HTTPException(400, data)`<br>文案一改，状态码就悄悄错位 | DAO 把该用的状态码一起带回来（见 8.1） |
| 12 | `create_emp` 里有 `print(ok, msg)` | 调试残留，上线后会把用户数据打进日志 | 删掉 |

### 班级 / 班主任模块

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 13 | 班级更新时班主任校验形同虚设 | `put_class` 里查的是 `Class_teacher` 表，过滤的却是 **`Class.is_del`** —— 拼出一句多表 JOIN 的废话 SQL，而且根本没起到「排除已删除班主任」的作用 | 改成 `Class_teacher.is_del == 0` |
| 14 | 班级创建永远失败 | `class_teacher` 表**没有任何接口能写数据**，但新建班级又要求班主任必须存在 —— 模块之间死锁 | 补齐班主任 CRUD（见第 7 节） |
| 15 | 创建班级失败时状态码还是 200 | `if obj: return result else: return result` —— 两个分支都 `return`，body 里写着「创建失败」但 HTTP 码是 200，前端只能靠猜 body | 失败走异常 → 409 / 404 |

### 老师模块

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 16 | 启动时 Pydantic 警告 `orm_mode has been renamed to from_attributes` | Pydantic v2 改了名，`class Config: orm_mode = True` **被直接忽略** | 改成 `model_config = ConfigDict(from_attributes=True)` |
| 17 | 一个老师教 3 个班，列表里出现 3 条 | `outerjoin(Class)` 后把每一行都塞进列表 | 先查老师（1 条 SQL）+ 再查班级归属（1 条 SQL），内存里拼，共 2 条 SQL，无 N+1 |
| 18 | `update_teacher` 会有 DeprecationWarning | 用了 Pydantic v1 的 `.dict(exclude_unset=True)` | 改成 `.model_dump(exclude_unset=True)` |
| 19 | `teacher_tel: str = Field(None, ...)` | 类型标成 `str` 却拿 `None` 当默认值，自相矛盾 | 改成 `str \| None = Field(default=None, ...)` |

### 统计模块

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 20 | 「男生数」和「女生数」**永远相等** | `case((Student_info.stu_sex == '男', 1))` 拿字符串比 **int 列**，MySQL 隐式把 `'男'` 转成 `0`，于是两个条件都等价于 `stu_sex = 0` | 统一成字符串存储后，条件自然正确（见第 5 节） |
| 21 | `EmpRequest.open_date / offer_date` 必填 | `stat_dao` 的注释写着「offer_date 和 open_date 不是必填的」，统计接口还专门过滤掉没有这两个值的行 —— 一度按"以代码为准"改成了可选 | **最终按业务决定改回必填**：就业时长是这个系统的核心指标，缺了日期一端就统计不出来。现在从数据入口就卡住，不完整的记录根本产生不出来（见 7.5） |

### 第 8 节新增的 12 个（合入你改过的学生模块时发现）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 22 | 同时改顾问的姓名和年龄，只有姓名生效 | `update_agent1` 里 `db.commit()` 和 `return True` **缩进在 for 循环里面**，第一个字段处理完就提交返回了 | `commit` / `return` 挪到循环外面 |
| 23 | 「查询全部学生」少了一批人 | `.join(Agent)` 是 **INNER JOIN**，没有顾问（`agent_id` 为 NULL）的学生被整行过滤 | 改 `joinedload(Student_info.agent)` |
| 24 | 删除顾问失败时返回的是一段字符串、状态码 200 | `return '删除失败,无匹配顾问id'` | 改成 `raise HTTPException(404, ...)` |
| 25 | 查顾问失败提示"无匹配学生编号" | 复制粘贴留下的文案 | 改文案 |
| 26 | 顾问改不了 | 根本没有"修改顾问"的接口和请求模型 | 补 `UpdateAgent` schema + `/student/update_agent` |
| 27 | 顾问删不了 | 根本没有"删除顾问"的接口 | 补 `/student/delete_agent`（软删除） |
| 28 | 顾问删不掉会被外键挡住 | `student_info.agent_id` 外键指向 `agent.agent_id` | 改成软删除（`is_del=1`），不动行 |
| 29 | 可以建出两个同名顾问 | 没有唯一性校验 | 加重名检查 → 409 |
| 30 | 同一个人能重复建档 | 没做"姓名 + 电话"重复检查 | 加 → 409 |
| 31 | `stu_age` / `agent_age` 声明成 `String` | 接口传 int，存进 varchar，统计时还得再转一次类型 | 改成 `Integer` |
| 32 | `import` 这个模块就会连数据库建表 | `Base.metadata.create_all(engine)` 写在 model 文件末尾，数据库密码错 / MySQL 没启动全都变成一句 `Access denied` | 建表挪到 `main.py` 的 lifespan |

另外还有一个**我自己写出来的** bug（编号 33），记在 [8.6](#86-本轮抓到的真-bug我自己写的)：
批量改架构时 `select_stu_name` 漏写 `return True, rows`，接口层解包 list 直接 500。
现在有两条"架构约定"测试专门盯住这类错误。

---

## 5. 两个隐蔽的坑

### 5.1 `pymysql` 会把你的枚举写成 `'Sex.MALE'`

这个坑太隐蔽了，**不报错，只污染数据**，值得单独讲。

```python
class Sex(str, Enum):
    MALE = "男"
    FEMALE = "女"
```

`Sex` 继承 `str`，所以 `Sex.MALE == "男"` 成立，看起来一切正常。
但 Python 3.10 里 `str(Sex.MALE)` 返回的是 **`'Sex.MALE'`**，不是 `'男'`。

而 pymysql 写参数时正好会调 `str()`：

```python
# pymysql/converters.py
def escape_str(value, mapping=None) -> str:
    return "'" + escape_string(str(value)) + "'"
```

于是性别这一列会被写成字符串 **`Sex.MALE`** —— 接口返回 201，数据库也不报错，
但数据全废了，而且要等到你写统计查询才发现。

**修法**（一行）：

```python
class Sex(str, Enum):
    MALE = "男"
    FEMALE = "女"

    def __str__(self) -> str:
        return self.value
```

> **教训**：
> - 继承 `str` 的枚举一定要覆写 `__str__`。
> - 更根本的做法是：**枚举值和数据库列类型保持一致**，别让业务代码猜。

### 5.2 静态路由会被动态路由抢走

FastAPI 按**注册顺序**匹配路由。

```python
@router04.get('/teacher')          # 先注册
@router04.get('/{stu_class_id}')   # 后注册
```

如果顺序反了，请求 `/class/teacher` 会先撞上 `/{stu_class_id}`，
然后因为 `"teacher"` 转不成 int 而返回 422。

**规则**：静态路径永远注册在动态路径前面。

> 顺带一提：`GET /class/{stu_class_id}` 里的 `stu_class_id` 是 int，
> 而 `GET /teacher/{teacher_id}` 是 int，但 `GET /student/select_stu_name` 是 str ——
> 同一批接口里路径参数类型不统一，容易出这种问题。

### 5.3 性别到底存 0/1 还是 '男'/'女'

我问了之后你选了**存字符串**，这个选择其实更贴合你原本的代码意图：

| 位置 | 原本的写法 |
|---|---|
| `schema/student_request.py` | `Student_request2.stu_sex : str` |
| `schema/emp_request.py` | `SexEnum(str, Enum)` = `男`/`女` |
| `Dao/stat_dao.py` | `case((Student_info.stu_sex == '男', 1))` |

**三处都写的是字符串，只有数据库存了 int** —— 是数据库跑偏了，不是代码跑偏了。
所以 `002_sex_to_varchar.sql` 把列改回 `varchar(10)`，并加了一条 CHECK 约束：

```sql
ALTER TABLE `student_info`
  ADD CONSTRAINT `ck_stu_sex` CHECK (`stu_sex` IS NULL OR `stu_sex` IN ('男', '女'));
```

> **把业务规则下沉到数据库**是这一条约束的价值：以前脏数据要等统计查询时才发现，
> 现在在**写进去的那一刻**就被挡下。适合放 CHECK 的还有：分数 0~100、年龄 >= 0、枚举取值。

**一个需要你确认的假设**：迁移脚本把老数据按 `1 → 男`、`0 → 女` 转换。
如果你本来的约定相反，把 `002_sex_to_varchar.sql` 里的 CASE 两行对调，
清空该列再重跑一次即可。

---

## 6. 架构优化

> ⚠️ **本节已被第 8 节取代。**
> 6.1 介绍的是"自定义异常体系（`exceptions.py`）"那套方案，
> 本轮按你的要求改成了 **DAO 返回 `(ok, result)` + 接口层 `raise HTTPException`**，
> `exceptions.py` 已删除。请以 [8.1](#81-最终的三层约定) 为准。
> 这里保留 6.1 是为了让你看清"为什么中间试过另一条路、最后又换回来了"。

### 6.1 错误处理：从 `(ok, msg)` 二元组到异常（已废弃，见 8.1）

**原来的写法**（你 `emp_api.py` 里的原话）：

```python
ok, msg = add_emp(db, emp_dict)
if ok:
    return {'message': msg}
else:
    raise HTTPException(422, msg)
```

三个问题：

1. 一个布尔值把**业务失败**（学生不存在）和**系统故障**（数据库炸了）混在了一起
2. 想区分 400 和 500，只能靠比对错误文案 —— 文案一改，状态码就悄悄错位
3. 每个接口都要写一遍 `if not ok: raise`，样板代码一大片

**现在的写法**：

```python
# exceptions.py
class BizError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class NotFoundError(BizError):    # 404
class ConflictError(BizError):    # 409
class UnprocessableError(BizError):  # 422
```

```python
# Dao/emp_dao.py
def add_emp(db, emp_dict):
    if not student:
        raise NotFoundError('学生学籍不存在，不能添加就业信息。')
    if emp:
        raise ConflictError('该学生就业信息已经存在，不能重复添加。')
```

```python
# API/emp_api.py —— 干净了
@router03.post("/create", status_code=201)
def create_emp(emp: EmpRequest, db: Session = Depends(get_db)):
    return add_emp(db, model_to_dict(emp))
```

```python
# main.py —— 全局翻译
@app.exception_handler(BizError)
async def handle_biz_error(request: Request, exc: BizError):
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.message})
```

> **顺带解决了一个大问题**：DAO 里那些
> `except Exception as e: print(e); return False, 'xxx'`
> 全部删掉了。
>
> 这些 `try/except` 有两个坏处：
> 1. **把真正的错误藏起来了** —— 线上只看到「查询失败，请稍后重试」，看不到堆栈
> 2. **每个函数都是同一套样板**，重复了 20 多遍
>
> 现在：意料之外的异常直接往上冒，由全局处理器统一记日志 + 返回 500；
> 业务错误用 `BizError` 精确表达。**每个 DAO 只需要写它真正的业务逻辑。**

### 6.2 `print` → `logging`

原来项目里散着十几处 `print`。`print` 的问题：

- 没有级别（info / warning / error），没法过滤
- 没有时间戳，出问题不知道是哪一次请求
- 写死了只能打到 stdout，没法落文件
- `print(e)` 只有一行异常消息，**没有堆栈**

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
)
logger = logging.getLogger(__name__)
logger.exception('修改就业信息失败')   # 自动带上完整堆栈
```

### 6.3 数据库连接池

```python
engine = create_engine(
    url,
    pool_size=5,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={'charset': 'utf8mb4'},
)
```

**`pool_pre_ping=True` 一定要加**：MySQL 默认 8 小时空闲断连，
之后第一个请求必然报 `MySQL server has gone away`。
这是线上最常见的「跑了一晚上就崩」的原因，而它的报错完全看不出是连接池的问题。

### 6.4 `get_db` 补上 rollback

```python
def get_db():
    db = Session()
    try:
        yield db
    except Exception:
        db.rollback()   # 少了它，事务失败的 Session 会被连接池复用给下一个人
        raise
    finally:
        db.close()
```

一次 `IntegrityError` 之后，这个 Session 就处于「事务已失败」状态，
后续任何操作都会报 `PendingRollbackError` —— 而这个 Session 还在连接池里。

### 6.5 返回字段显式化

以前直接 `return ORM对象`，字段由数据库决定。
现在每个模块有自己的 `_xxx_to_dict()`，明确列出返回哪些字段：

- `is_del` 这种内部字段不会漏给前端
- 以后给表加字段，不会莫名其妙多返给前端一个字段
- 前端的响应结构是稳定的

### 6.6 避免 N+1 查询

```python
# 改之前：每个学生查一次班级
for emp in rows:
    class_name = emp.student.stu_class_name   # ← 每行一次 SELECT

# 改之后：一次 join 查完
query = (
    db.query(*_EMP_COLUMNS)
    .join(Student_info, Emp.stu_id == Student_info.stu_id)
    .join(Class, Student_info.stu_class_id == Class.stu_class_id)
)
```

> **N+1 查询**是 ORM 最经典的性能坑：
> 列表里有 100 条数据，接口就发 101 条 SQL。
> 判断方法：看接口的 SQL 日志条数是不是随数据量线性增长。

---

## 7. 新增功能

### 7.1 班级 / 班主任模块（按你改版后的路由）

补班主任接口是因为它是一个**功能死锁**：`class_teacher` 表没有任何接口能写，
但新建班级又要求班主任必须存在 —— 班级模块根本走不通。

最终路由（你定的命名风格，全部改成"动词_资源"的显式路径）：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/class/` | 新建班级 → 201 |
| PUT | `/class/update_class/{id}` | 修改班级 |
| DELETE | `/class/delete_class/{id}` | 删除班级（连带软删学员） |
| GET | `/class/get_class/{id}` | 查询单个班级 |
| GET | `/class/all_class` | 查询所有班级 |
| POST | `/class/class_teacher` | 新增班主任 → 201 |
| PUT | `/class/update_class_teacher/{id}` | 修改班主任 |
| DELETE | `/class/delete_class_teacher/{id}` | 删除班主任 |
| GET | `/class/get_class_teacher/{id}` | 查询单个班主任 |
| GET | `/class/all_class_teacher` | 查询所有班主任 |

**改成显式路径顺带解决了一个老问题**：原来有 `GET /class/{stu_class_id}` 这种
"裸参数"路由，任何静态路径都得注册在它前面，
否则 `/class/teacher` 会先撞上它然后因为转不成 int 而 422
（见 5.2）。现在没有裸参数路由了，顺序问题自然消失。

另外补了 `class_teacher_sex`（班主任性别）字段：
模型、校验、接口都带上，数据库加了一列 `class_teacher_sex VARCHAR(1)`
（迁移脚本 `004_add_class_teacher_sex.sql`）。

### 7.2 健康检查 `GET /health`

```json
{"status": "ok", "database": "ok"}
```

只看进程活着没有意义，**顺便探一下数据库通不通**才算有效。
数据库挂了返回 503。

### 7.3 顾问关联（`student_info.agent_id`）

原始模型里有一行被注释掉的 `# agent_id = Column(Integer)`，
`Agent` 模型、`/student/add_agent` 接口、`Agent_request` 校验都在，
**唯独学生表和顾问表之间的关联没接通** —— 这条业务链路是断的。

补齐后：

| 改动 | 说明 |
|---|---|
| `migrations/003_add_agent_id_to_student.sql` | 加列 + 索引 + 外键（`ON DELETE SET NULL`） |
| `model/student_table.py` | `Student_info.agent_id` 外键 + `agent` 关系；`Agent.students` 反向关系 |
| `schema/student_request.py` | `Student_request.agent_id` / `UpdateStudent.agent_id`（都可空） |
| `Dao/stu_dao.py` | 写入前校验顾问存在；`joinedload` 预取顾问 |
| `API/stu_info_api.py` | 输出 `agent_id` + `agent_name` |

**设计取舍**：

1. **列可空** —— 不是每个学生都有顾问（也可能是校方直招），
   所以不对已有数据做任何改动，老学生的 `agent_id` 就是 `NULL`。
2. **写入前校验顾问存在** —— 数据库有外键兜底，但外键报错是 `1452`
   这种天书一样的数字；在 DAO 层先拦一道，返回「顾问不存在(id=99999)」。
3. **`ON DELETE SET NULL`** —— 顾问被物理删除时，学生的 `agent_id` 自动置空，
   而不是卡住删除操作。

**顺带补的两个接口**（光加字段是不够用的）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/student/agent` | 查询所有顾问 —— 前端要选顾问，得先能拿到列表 |
| GET | `/student/select_stu_agent?agent_id=` | 按顾问查学生（这个顾问招来的学生） |

**一个容易踩的坑：N+1 查询**

序列化时要输出 `agent_name`，如果直接写 `row.agent.agent_name`，
SQLAlchemy 会对**每一行**都懒加载一次顾问 —— 列表 100 条就是 101 条 SQL。

解法是在 DAO 查询里加 `joinedload`：

```python
db.query(Student_info)
  .filter(Student_info.is_del == 0)
  .options(joinedload(Student_info.agent))   # 一次 JOIN 带出顾问
  .all()
```

> **判断 N+1 的方法**：看接口的 SQL 日志条数是不是随数据量线性增长。

### 7.4 其它

- `GET /student/select_stu_skip` 现在会返回 `total` 字段
- `PUT /score/put` 原来返回 `{"detail": true}`（布尔值塞在 detail 里），现在返回真实成绩数据
- `GET /teacher/` 的返回里，`stu_class_ids` 是一个**数组**（原来是一条记录一个班，重复）

### 7.5 就业日期改必填 + 顺序校验

`EmpRequest` 的 `open_date`（简历开放时间）和 `offer_date`（收到 offer 时间）
**改回必填**，并新增一条业务规则：**offer 不能早于 open**。

```python
class EmpRequest(BaseModel):
    open_date: datetime = Field(..., description='简历开放时间')
    offer_date: datetime = Field(..., description='收到offer时间')

    @model_validator(mode='after')
    def check_date_order(self):
        if self.offer_date < self.open_date:
            raise ValueError('收到offer的时间不能早于简历开放时间')
        return self
```

**为什么加顺序校验**：这两个日期既然都必填了，它们的先后关系就是一条明确的
业务规则。与其等统计接口算出「负数时长」再去排查，不如在入口就拦掉。
（`stat_dao.seconds_to_dhms` 里那个 `negative` 分支就是为这种异常数据准备的。）

**更新接口的校验放在 DAO 层**：

```python
# Dao/emp_dao.py —— update_emp
for field, value in emp_dict.items():
    if value is not None:
        setattr(emp, field, value)

# 这里才比得了：更新可能只传了其中一个日期，
# 必须拿库里另一个日期来比，才知道顺序对不对
if emp.open_date and emp.offer_date and emp.offer_date < emp.open_date:
    db.rollback()
    raise BizError('收到offer的时间不能早于简历开放时间')
```

> **schema 只能校验「传进来的字段之间」的关系**；
> 只要有一方来自数据库，校验就必须下沉到 DAO —— 那里才拿得到完整的数据。

**对存量数据无影响**：迁移前库里 `employment` 的 `open_date` / `offer_date`
**0 行为 NULL**，所以改成必填后没有任何历史记录会被卡住。

### 7.6 班级模块改版：合入你的版本时修掉的 5 个 Bug

你改版后的 `class_api.py` / `class_dao.py` / `class_model.py` / `class_schema.py`
已经整体并入项目（DAO 保留你原来的 `(ok, message)` 返回约定，没改成 BizError），
只修了下面这些真 bug：

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | `DELETE /class/delete_class_teacher/5` **永远 422** | 路径是 `{class_teacher_id}`，函数参数却写成 `teacher_id`。FastAPI 找不到路径参数，就把 `teacher_id` 当成**必填的 query 参数**，于是报 `{"loc": ["query", "teacher_id"], "msg": "Field required"}` | 参数名改成 `class_teacher_id`，和路径一致 |
| 2 | 查班主任不存在时提示"**班级**不存在" | 复制粘贴留下的 | 改成"班主任不存在" |
| 3 | `get_all_class_teacher` 里有一句空的 `print()` | 调试残留 | 删掉 |
| 4 | `from sqlalchemy import null` 没用到 | 无用导入 | 删掉 |
| 5 | `put_class` 校验班主任时过滤了 `Class.is_del` | 查 `Class_teacher` 表却过滤 `Class` 表字段，SQL 多出无意义 JOIN，且没起到"排除已删除班主任"的作用 | 改成 `Class_teacher.is_del == 0` |

另外把"失败时返回 200 + body 里写着失败信息"改成了抛 `HTTPException`（422），
和这个模块里删除接口的写法保持一致。

> **关于路径参数名这件事，值得单独记一笔**：
> FastAPI 靠**函数参数名**去匹配路径里的 `{xxx}`。
> 两边对不上时，它不会报错，而是把路径参数当成"没人认领"，
> 同时把函数参数降级成必填 query 参数 ——
> 结果就是接口永远 422，而且报错信息指向 query 而不是 path，很容易查不到根因。
>
> **规矩**：路径里的 `{名字}` 和函数参数名**必须一模一样**。

### 7.7 一次真实的翻车现场

`migrations/004_add_class_teacher_sex.sql` 是我新建的迁移脚本，
写的时候手滑带了一行 `USE \`student_ms\`;` —— 正是 3.1 节刚讲完不能写的东西。

所幸这次目标库恰好就是 `student_ms`，`USE` 和执行器的连接指向同一个库，
所以没造成任何破坏。但这正是 3.1 那个演练工具存在的意义：
**危险的操作必须在一次性环境上演练**，不能靠"这次刚好没事"。

（写完我把那行删掉了，脚本里不再有 `USE`。）

---

## 8. 本轮：合入学生模块 + 三层架构大改

这一轮你提了三件事：

1. 你自己改了 4 个学生模块的文件（`student_table.py` / `stu_info_api.py` / `stu_dao.py` / `request.py`），
   要合进项目、debug、并把缺的业务处理补上；
2. 架构要调整成 **DAO 层只返回业务结果，接口层负责抛 HTTP 异常**；
3. 整个项目加上详细注释，照顾新手阅读；
4. 约束：**改 bug 时尽量用文件里已经有的基础 FastAPI 写法**（`raise HTTPException`）。

### 8.1 最终的三层约定

```
schema 层   校验 JSON 长什么样         不合格 -> 422
   ↓
Dao 层      查库/写库，只返回业务结果    (ok, result)
   ↓
API 层      把失败翻译成 HTTP 异常      raise HTTPException(...)
```

**DAO 层统一返回 `(ok, result)`：**

| 情况 | `ok` | `result` |
|---|---|---|
| 成功 | `True` | 业务数据（dict / list / ORM 对象） |
| 失败 | `False` | `{'message': '提示语', 'status_code': 404}` |

接口层每个接口都长这样（全程只用 FastAPI 最基础的那个东西）：

```python
ok, result = add_stu(db, stu_dict)
if not ok:
    raise HTTPException(status_code=result['status_code'], detail=result['message'])
return result
```

`status_code` 放在 DAO 返回的失败结果里，而不是让接口层去比对错误文案 ——
比对文案是个陷阱：文案一改，状态码就悄悄错位，而且最难发现。

**为什么 DAO 不直接 `raise HTTPException`？**

HTTP 是传输层的事，DAO 关心的是业务。把两层分开，
这个 DAO 将来被定时任务、Excel 导入脚本复用时不用装 FastAPI。

**为什么 DAO 不再 `try/except` 吞异常？**

你原来的写法每个函数都包一层 `except: print(e); return False`。
真实报错（数据库断连、字段不存在）会被一句"操作失败"盖住，线上根本查不出是哪行炸的。

现在的规矩：

- 业务规则不满足 → `return (False, {'message': ..., 'status_code': ...})`
- 数据库真的炸了 → 异常直接往上冒，由 `main.py` 里的全局 `Exception` 处理器记完整堆栈 + 返回 500

**`exceptions.py` 已删除。** 上一轮我加的 `BizError / NotFoundError / ConflictError / UnprocessableError`
那套自定义异常体系，正是你这次明确不要的东西 —— 全项目现在只用 FastAPI 自带的 `HTTPException`。

### 8.2 你的 4 个文件，逐个修了什么

#### `student_table.py`（model 层）

| 问题 | 现象 | 修法 |
|---|---|---|
| `stu_age = Column(String(20))` | 接口传 int 进来，存进 varchar，统计时还要再做类型转换 | 改 `Integer` |
| `agent_age = Column(String(20))` | 同上 | 改 `Integer` |
| 少了 `stu_tel` | 你加的业务规则没地方存 | 补 `Column(String(20))` |
| `Agent` 少了 `is_del` | 顾问没法软删除 | 补 `Column(Integer, default=0)` |
| `stu_class_id` 没了外键 | ORM 和真实表结构对不上 | 补 `ForeignKey('clazz.stu_class_id')` |
| 缺 `Student_info.agent` / `.clazz` | 查学生带不出顾问名 / 班级名 | 补 relationship |
| 顶层 `Base.metadata.create_all(engine)` | import 就连库建表，真错误被掩盖 | 删掉，建表挪到 `main.py` 的 lifespan |
| `import null` / 多余 import | — | 清理 |

#### `request.py`（= 项目的 `schema/student_request.py`）

| 问题 | 现象 | 修法 |
|---|---|---|
| `stu_sex: int` | 数据库存的是字符串，int 写进去变成 `'1'`，和统计口径对不上 | 改用 `SexField`（接受 男/女/1/0） |
| `UpdateStudent` 字段没有 `default=None` | Pydantic v2 里 `Field(max_length=10)` = **必填**，改一个名字也要全传 | 每个字段补 `default=None` |
| `UpdateStudent` 少了 4 个字段 | 改不了年龄、班级、顾问、电话 | 补 `stu_age` / `stu_class_id` / `agent_id` / `stu_tel` |
| `Student_request2` | 全项目无人使用，且 `stu_sex: str` 和别处不一致 | 删（死代码 + 误导） |
| 没有"修改顾问"的模型 | 顾问录错了改不了 | 新增 `UpdateAgent`（全字段可选） |

#### `stu_dao.py`

| 问题 | 现象 | 修法 |
|---|---|---|
| **`update_agent1` 的 `commit()` / `return` 缩进在 for 循环里面** | 同时改姓名和年龄 → 只有姓名生效，年龄被丢掉，而且完全看不出来 | 挪到循环外面 |
| `setattr(result, i, k)` 没有白名单 | 请求里多传一个字段就 setattr 一个不存在的属性；传 `is_del` 就能改软删除标记 | 加白名单 `AGENT_UPDATABLE_FIELDS` / `STU_UPDATABLE_FIELDS` |
| `.join(Agent)` 是 **INNER JOIN** | 没有顾问（`agent_id` 为 NULL）的老学生**整行消失** | 改 `joinedload(Student_info.agent)` |
| `try/except` + `print` | 真报错被盖住 | 去掉，异常往上冒 |
| 缺顾问的唯一性校验 | 可以建出两个同名顾问 | 加重名检查 → 409 |
| `add_stu` 没做"姓名 + 电话"重复检查 | 同一个人能重复建档 | 加 → 409 |

#### `stu_info_api.py`

| 问题 | 现象 | 修法 |
|---|---|---|
| `delete_agent` 失败时 `return '删除失败...'` | 返回的是一段**字符串**，HTTP 状态码还是 200 | 改成 `raise HTTPException(404, ...)` |
| `select_agent` 文案是"无匹配学生编号" | 明明查的是顾问 | 改文案 |
| `print(stu_dict)` | 调试残留，会把用户数据打进日志 | 删 |
| `query_stu_id` / `query_stu_class` 缺类型标注 | FastAPI 按字符串处理，靠 MySQL 隐式转换 | 补 `int` |
| `delete_stu1(stu_id: str)` | 主键是 int，传字符串靠隐式转换 | 改 `int` |

### 8.3 新增的接口

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/student/select_agent?agent_id=` | 按 id 查单个顾问 |
| PUT | `/student/update_agent?agent_id=` | 修改顾问 |
| DELETE | `/student/delete_agent?agent_id=` | 删除顾问（软删除） |
| GET | `/student/select_all` | 查询全部学生（原来被 INNER JOIN 吃掉了一部分） |

### 8.4 数据库改动

迁移 `005_add_stu_tel_and_agent_is_del.sql`：

```sql
ALTER TABLE student_info ADD COLUMN stu_tel VARCHAR(20) NULL COMMENT '学生联系电话';
ALTER TABLE agent       ADD COLUMN is_del INT DEFAULT 0 COMMENT '是否删除：0未删除，1已删除';
```

两列都允许为 NULL / 有默认值 —— 加一列不能把老数据搞坏。

### 8.5 两个我替你拍板的地方（你要改回来很容易）

**① `stu_tel` 我做成了【必填】**（跟着你附件里的写法）。

理由：这是新增字段，新建学生时要求填电话很合理；
而且"姓名 + 电话"当唯一标识，电话比名字稳定。

影响：所有新增学生的调用方必须带 `stu_tel`，格式必须是 11 位手机号
（`^1[3-9]\d{9}$`），否则 422。

想改成选填？把 `schema/student_request.py` 里的
`stu_tel: str = Field(..., pattern=...)` 改成
`stu_tel: str | None = Field(default=None, pattern=...)` 就行，
DAO 层不用动（它用的是 `.get('stu_tel')`）。

**② `agent_id` 原本我保持【选填】，你后来定了"每个学生都必须有顾问"，已改成必填。**

改的地方见 [9.2](#92-顾问改成必填)。

（留个记录：这一条在"选填"和"必填"之间的取舍，
决定了要不要在 DAO 层区分"没传"和"传了但不存在的顾问"，
以及测试里那条 `test_create_student_without_agent_is_allowed` 要不要反过来。）

### 8.6 本轮抓到的真 bug（我自己写的）

改造完跑冒烟测试，`GET /student/select_stu_name` 返回 **500**。

原因：批量改 DAO 的时候，`select_stu_name` 漏写了一行 `return True, rows`，
函数返回的是一个 **list** 而不是二元组。接口层执行
`ok, rows = select_stu_name(...)` 时，解包 list 抛 `ValueError` → 500。

**这类错不写测试根本发现不了**（函数能正常调用，只是返回的东西不对）。
所以我补了两条"架构约定"测试：

```python
# 1. 每个 DAO 函数都必须返回 (ok, result)
#    （用 inspect.getsource 扫一遍全部 50 个 DAO 函数）

# 2. DAO 层不许出现 HTTPException
#    （用 ast 解析代码，注释里提到不算）
```

第一条当场就把 `select_stu_name` 抓了出来。

**教训**：批量改架构时，"逐个函数检查返回值"比"跑一遍看看"可靠得多。
接口测试只能覆盖你想到的调用路径，结构测试覆盖的是**全部**函数。

### 8.7 全项目注释

每个文件现在都有：

- **文件头 docstring**：这个文件是干什么的、属于哪一层、有什么约定；
- **函数 docstring**：做什么、失败时返回什么、踩过什么坑；
- **行内注释**：只在"不看代码就猜不出为什么"的地方写。

注释的风格是**讲道理**而不是复述代码。
比如不会写 `# 查数据库`，而是写：

> 为什么这里用 `joinedload` 而不是 `join`：
> `join` 是 INNER JOIN，没有顾问的学生会被整行过滤掉，
> 库里正好有这么一批老学生，一查就"消失"了。

---

## 9. 第二轮：顾问改名 + 建库脚本 + 清理

这一轮你提了三件事：

1. **"代理（agent）"这个角色，在业务上叫"顾问"**；
2. 写好**建库 SQL** + **至少 200 条类真实数据**的 SQL，自己拿来测整个项目；
3. **删除不必要的文件**（"我是小白，我也看不懂"）。

### 9.1 顾问改名

全项目 **102 处"代理"** 改成了"顾问"，涉及 15 个文件。

**只改中文文案，代码标识符一律不动**：

| 东西 | 改没改 | 为什么 |
|---|---|---|
| 接口提示语、注释、文档、Swagger 标题 | ✅ 改成"顾问" | 这是给人看的 |
| Python 类名 `Agent` | ❌ 保留 | 类名跟表名 `agent` 对应，改了要动一串 import |
| 数据库表名 `agent` | ❌ 保留 | 改名要写迁移脚本，风险大 |
| 字段名 `agent_id` | ❌ 保留 | 同上，而且它是外键，改名要连带改索引和约束 |

**改的时候差点改错一个地方**，值得单独说：

`model/employment.py` 里有一句"独立的**代理主键** id"。
这里的"代理"是数据库术语 **surrogate key**（代理键 = 用一个没有业务含义的自增列当主键），
跟招生代理一点关系都没有。批量替换时如果直接全局替换，
就会把它改成"顾问主键" —— 一个彻底看不懂的词。

所以替换规则是**按顺序**的：

```python
('招生代理（顾问）', '顾问'),   # 括号重复
('招生代理 / 顾问',  '顾问'),   # 斜杠重复
('代理主键',          '自增主键'),  # ← 数据库术语，不能动成"顾问主键"
('招生代理',          '顾问'),
('代理',              '顾问'),
```

### 9.2 顾问改成【必填】

你后来补充了一条业务规则：**每个学生都要有顾问**。

这一条把之前的设计推翻了一部分 —— 原来 `agent_id` 是选填的
（理由是"可能有校方直招的学生"）。现在改成必填：

```python
# schema/student_request.py
agent_id: int = Field(..., ge=1, description='顾问id')
```

连带改了 3 个地方：

1. **DAO 的存在性校验**：`agent_id` 为 `None` 现在直接报错"必须指定负责招生的顾问id"；
2. **修改学生的校验**：只有【真的传了】 `agent_id` 才检查 ——
   因为"修改"是部分更新，没传表示"这个字段不动"，不是"清空顾问"；
3. **测试**：原来那条 `test_create_student_without_agent_is_allowed`
   （允许不传顾问）反过来了，改成 `test_create_student_without_agent_returns_422`。

### 9.3 建库脚本 + 1018 条测试数据

新建了 `sql/` 文件夹：

| 文件 | 作用 |
|---|---|
| `01_create_schema.sql` | 建库 + 建 7 张表（含外键/唯一约束/CHECK/索引） |
| `02_seed_demo_data.sql` | 1018 条类真实数据 |
| `run_sql.py` | 一键执行（因为 PowerShell 不支持 `mysql < x.sql`） |
| `README.md` | 三步操作手册 |

**数据规模**：

| 表 | 行数 | 说明 |
|---|---|---|
| `agent`（顾问） | 12 | 每个学生都有归属顾问 |
| `class_teacher`（班主任） | 12 | |
| `teacher`（老师） | 24 | |
| `clazz`（班级） | 36 | 6 个专业方向 × 6 期 |
| `student_info`（学生） | **200** | |
| `scores`（成绩） | 600 | 每个学生 3 次考试 |
| `employment`（就业） | 134 | offer 时间一定晚于简历开放时间 |

数据"像真的"：真实中文名（2~3 字）、11 位手机号（全局不重复）、
31 个省市、34 所真实高校、38 个真实专业、成绩围绕基准分浮动。

#### 这里踩了两个"不报错但没生效"的坑

**坑 1：整文件一次性执行，后面的 INSERT 被静默跳过。**

一开始用 `client_flag=CLIENT.MULTI_STATEMENTS` 想一把梭。
结果每条 INSERT 都报"成功"，但查出来 **0 行**。

原因：文件中间有 `SET NAMES utf8mb4;`，它会改变连接字符集，
PyMySQL 解析后面的结果包时对不上，后面的语句就没被执行。
**全程不报任何错。**

修法：自己写了个 `split_sql_statements()`，把文件拆成一条条执行。
拆分时要跳过引号和注释里的分号：

```python
if ch in ("'", '"', '`'):      # 引号里的分号不能切
if ch == '-' and nxt == '-':   # 行注释里的分号不能切
if ch == '/' and nxt == '*':   # 块注释里的分号不能切
```

**坑 2：忘了 `commit()`，数据全部回滚。**

PyMySQL 默认 `autocommit=False`。不提交的话，连接一关闭事务就回滚 ——
表现同样是"每条 INSERT 显示写入 N 行，换个连接查却是 0 行"。

而且**我的诊断脚本一开始也踩了这个坑**：它是在同一个连接里查的，
所以能看到未提交的数据，误以为没问题。
**换连接查才是真相。**

这两个坑的共同点 —— **不报错**。所以现在的 `run_sql.py` 会逐条打印影响行数，
跑完还会**重新连一次库**统计总行数给你看（而不是相信过程输出）。

### 9.4 删掉了什么

| 删掉 | 为什么 |
|---|---|
| `migrations/` 整个目录 | 5 个补丁迁移 + 执行器 + 演练工具。新建库用 `sql/` 里的脚本就够了；老库已经修好了，以后也不需要再打补丁 |
| `.idea/` 保留 | PyCharm 会用 |
| `DEBUG_NOTES.md` 保留 | 这是你的学习笔记 |

还有 6 个临时脚本（`_tmp_*.py`，用来批量改名、生成数据、诊断问题）也一并删了。

### 9.5 验证结果

- **demo 库表结构 vs 线上库：7 张表逐列一致** ✅
- **pytest 57 项全绿** ✅
- **端到端冒烟 70 项全绿**（跑在 200 名真实学生的库上）✅

---

## 10. 第三轮：薪资单位 + employment 表被删 + 新接口

### 薪资单位统一成"元"

你发现 demo 库里有"31.94"和"上万"两种量级 —— 查下来是**种子数据的 bug**：

生成器里写的是 `random.uniform(6.5, 32.0)`，心里想的是"6.5千 ~ 32千"，
但这个数字直接存进了 `comment` 标注"单位：元"的列，**差了 1000 倍**。

之所以没被发现，是因为它和另一个接口（冒烟测试）写进去的 `25000` 混在了一张表里。

修完：

```
demo 库   min=6530.00  max=31940.00  avg=19109.18
老库      min=12345.00 max=100000.00 avg=19727.03
```

**教训：单位不能靠人记。** 现在三处都写死了：

| 位置 | 写法 |
|---|---|
| `model/employment.py` | 注释 + `comment='薪资，单位：元/月'` |
| `schema/emp_request.py` | `description='薪资，单位：元/月'` |
| `sql/02_seed_demo_data.sql` | 文件头专门有一段"单位约定" |

### employment 表被删 → "薪资前五"变成空列表

你反馈"薪资最高的前五名学生，运行没有结果"。查下来：

```
binlog: pos=649860  use `student_ms_demo`; DROP TABLE `employment`
binlog: pos=650096  use `student_ms_demo`; CREATE TABLE employment ( id INTEGER NOT NULL ... AUTO_INCREMENT ... )
```

**第一行**：employment 表被外部 DROP 掉了（不是我干的，binlog 里就这一条）。
**第二行**：你 11:33 启动服务时，`main.py` 的 `create_all` 悄悄给它建了一张**新的空表**。

而这张新表是按 ORM 模型生成的，和原来那张**结构不一样**：

| | 原来的表（`sql/01_create_schema.sql`） | create_all 补的表 |
|---|---|---|
| `stu_id` | `NOT NULL` | `DEFAULT NULL` |
| 唯一索引 | `uk_emp_stu_id`（一个学生一条就业） | **没了** |
| 外键 | `fk_emp_student` + `ON DELETE CASCADE` | `employment_ibfk_1`，**级联没了** |
| `is_del` | `DEFAULT 0` | `DEFAULT NULL` |

所以 `top5_salary` 查出来是 `[]` —— 而**全程不报任何错**。

**这暴露了 `create_all` 的三个特性**（现在写进 `main.py` 的注释了）：

1. 它**只会建不存在的表**，永远不会修改已存在的表；
2. 它**不会删表**，但反过来说：谁手动 DROP 了一张表，它就会悄悄补一张结构不同的空表；
3. 所以**表结构的唯一权威是 `sql/01_create_schema.sql`**。
   库出问题时正确做法是重跑 `python sql/run_sql.py`（DROP + CREATE + 灌数据），
   而不是指望服务启动时"自动修"。

排查手法（这次定位靠它）：MySQL 的 binlog 是 `ROW` 格式且已开启，
`SHOW BINLOG EVENTS` 能直接看到"谁在什么时候 DROP 了哪张表"。

### 新接口：查询当前未就业的学生

```
GET /employment/unemployed
```

返回格式和学生模块一致：`{'code', 'message', 'total', 'Data'}`。

**SQL 是这里最容易写错的地方：**

```python
.outerjoin(
    Emp,
    and_(Emp.stu_id == Student_info.stu_id, Emp.is_del == 0),
)
.filter(Student_info.is_del == 0, Emp.id.is_(None))
```

- 用 `outerjoin`（LEFT JOIN）而不是 `NOT IN (SELECT stu_id FROM employment)` ——
  后者在 stu_id 里有 NULL 时会整个查不出东西（SQL 的经典坑）；
- JOIN 条件里带上 `Emp.is_del == 0` ——
  这样"就业记录被软删除"的学生也会算成未就业，符合直觉。
  如果只写 `Emp.stu_id == Student_info.stu_id`，那条软删的记录照样 JOIN 上，人就被误判成"已就业"；
- `Emp.id.is_(None)` 表示"没 JOIN 上" = 没有未删除的就业记录。

配套加了 3 条回归测试，其中一条专门盯上面那个 `is_del` 的坑。

---

## 11. 怎么跑

```powershell
# 1. 装依赖
pip install -r requirements.txt

# 2. 配好 .env（DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD）

# 3. 建库 + 灌 1018 条测试数据（会自动建 student_ms_demo）
python sql/run_sql.py

#    然后把 .env 里的 DB_NAME 改成 student_ms_demo

# 4. 起服务
python main.py
#    或者：python -m uvicorn main:app --reload --port 8002

# 5. 打开接口文档
#    http://127.0.0.1:8002/docs
```

**测试**：

```powershell
# 回归测试（54 项，进程内 TestClient，CI 里跑这个）
python -m pytest tests/ -q

# 端到端冒烟（69 项，打真实运行中的服务，发布前跑这个）
#   先启动服务：python main.py
python tests/smoke_live.py
```

两个测试脚本都用**带时间戳的唯一命名**造数据，所以可以反复执行，不会互相打架。

> 想跑冒烟测试但不想改 `.env`？可以临时指定：
> ```powershell
> $env:DB_NAME='student_ms_demo'
> python -m uvicorn main:app --port 8003
> python tests/smoke_live.py http://127.0.0.1:8003
> ```

---

## 12. 我改了什么（文件清单）

### 新增

| 文件 | 作用 |
|---|---|
| `schema/enums.py` | 全局 `Sex` 枚举（含 `1/0` 兼容、`__str__` 覆写） |
| `utils.py` | `model_to_dict()`：Pydantic 模型 → ORM 可用的 dict |
| `sql/` | 建库脚本 + 1018 条测试数据 + 一键执行器 + 操作手册 |
| `tests/conftest.py`、`tests/test_api.py` | 54 项回归测试 |
| `tests/smoke_live.py` | 69 项端到端冒烟（打真实服务） |
| `requirements.txt` | 依赖清单 |
| `.gitignore` | 忽略 `.env` / 缓存 / 备份文件 |

### 重写

`database.py`、`main.py`、`schema/*.py`（7 个）、
`model/*.py`（6 个）、`Dao/*.py`（6 个）、`API/*.py`（6 个）

### 删除

- `exceptions.py` —— 上一轮加的自定义异常体系（`BizError` 等）。
  本轮按你的要求改回"接口层直接 `raise HTTPException`"，这套东西就没有存在意义了。
- `migrations/` 整个目录 —— 5 个补丁迁移 + 执行器 + 演练工具。
  新建库用 `sql/01_create_schema.sql` 就够了；
  老库已经修好并验证过，以后也不需要再打补丁。
- `schema/student_request.py` 里的 `Student_request2` —— 全项目无人使用，且字段类型是错的
  （`stu_sex: str` 和其它地方不一致），留着只会误导人。
- 调试过程中的一次性产物：`__pycache__/`、`.pytest_cache/`、
  迁移前的数据库备份 dump（迁移已验证通过、数据完好，留着只会误导人）。
- 6 个临时脚本 `_tmp_*.py`（批量改名、生成种子数据、诊断问题用的）。

### 数据库

5 张表结构对齐 + 1 个 CHECK 约束 + 3 个索引 + **新增 2 列**
（`student_info.stu_tel`、`agent.is_del`）。**原有数据全部保留**。

另外新建了一个专供测试的库 **`student_ms_demo`**：
7 张表结构与线上库**逐列一致**，装了 1018 条类真实数据。

---

## 13. 下一步该做什么

按性价比排序：

### 13.1 上 Alembic（优先级最高）

手写 SQL 迁移的问题：加字段、改字段、删字段，每次都要自己想清楚
「先摘外键还是先改表」。Alembic 会自动 diff：

```powershell
pip install alembic
alembic init migrations
# 改完 model 之后
alembic revision --autogenerate -m "描述这次改动"
alembic upgrade head
```

同时把 `model/*.py` 里的 `create_all` 和 `main.py` lifespan 里的建表都删掉 ——
**建表应该由迁移脚本负责，不是由应用启动负责**。

### 13.2 加认证

现在任何人都能增删改查所有数据。至少加个登录 + Token：

```python
from fastapi.security import OAuth2PasswordBearer
```

`user` 表已经在库里了（`id` / `name` / `email`），可以改成真正的用户表。

### 13.3 统一响应结构

现在有的接口返回 `{'msg': ...}`，有的返回 `{'message': ...}`，有的返回裸数组，
有的返回 `{'code': 200, 'message': ..., 'Data': ...}`。

建议统一成：

```json
{"code": 0, "message": "ok", "data": {...}}
```

配合 `response_model` 声明，Swagger 文档也会自动变准。

### 13.4 补 Alembic + pytest 的 CI

每次提交前自动跑一遍 `pytest`，比上线后才发现问题便宜太多。

### 13.5 其它可以打磨的地方

- **`select_stu_name` / `class_name` 用模糊匹配**：现在是精确等于，搜索体验差。
  改成 `like(f"%{x}%")` 即可（`company` 已经是模糊匹配了，风格不统一）。
- **`scores` 表加唯一约束** `(stu_id, test_id)`：现在重复录入靠应用层检查，
  并发下仍可能插两条。
- **`student_info.stu_class_id` 建索引**：外键列不建索引，关联查询会全表扫。
  （`clazz` 表建的时候 MySQL 自动加了 `KEY fk_student_class`，但
  `scores.stu_id` 之前没有，这次补上了。）
- **分页接口统一**：只有 `/employment/page` 有完整分页，
  `/student/select_stu_skip` 是手写的 skip/limit，可以统一成同一个分页模型。
- **`teacher_job` / `edu_bg` 建字典表**：现在都是自由文本，
  `edu_bg` 的筛选只能精确等于字符串，写错一个字就查不到。

---

## 14. 第四轮：`update_stu_class` 改成「只改用户传了的字段」

需求：**用户传了值才去改；没传的、传的是默认值（空值）的，一律不动。**

### 14.1 先说清楚：老代码其实已经能"只改一个字段"

`UpdateStudent` 的字段全是 `default=None`，DAO 里又有 `if value is not None` 的过滤，
所以只传 `{"stu_school": "新大学"}`，其它 11 个字段确实不会被覆盖。
**但有三个洞，而且前两个比"改不改字段"本身更要命。**

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | 前端整表单提交直接 422 | 表单里用户没碰过的输入框提交上来是 `""`，而 `stu_tel` 有手机号正则、`stu_age` 是 int、`stu_sex` 是枚举 —— 空字符串全部校验失败 | schema 层加 `mode='before'` 校验器，把空白字符串统一转成 `None` |
| 2 | 空 body `{}` 返回 200「更新成功」 | 数据库其实一个字节都没动 | DAO 层判定"一个有效字段都没有"→ 400 |
| 3 | 传 `stu_name: ""` 会真的把姓名清空 | DAO 只过滤 `None`，空字符串被当成合法值写进了库 | 空字符串和 `None` 一样算"没填"，跳过 |

第 1 条最要命：**用户明明只想改个学校，整个请求却挂了，一个字段都改不了。**
以前没暴露，是因为前端一直只提交"改过的字段"，从没提交过整张表单。

### 14.2 现在的三层分工

```
schema 层  把"空值"统一成一种东西
            "" / "   " / null  ->  None（校验之前就转，所以不会被正则拦成 422）
            没传的 key          ->  压根不出现在结果里

API 层     用 model_dump(exclude_unset=True) 交给 DAO
            请求 {"stu_school": "新大学"}
              -> DAO 收到 {'stu_school': '新大学'}      就这一个 key
              -> 其它 11 个字段根本不会进到 DAO 面前

DAO 层     三道关筛出真正要写的字段
            1. 在白名单里（防 is_del / stu_id 被改掉）
            2. 值不是空的（None / "" / "   " 都跳过）
            3. 有业务约束的单独校验（班级 / 顾问是否存在）
            一个都没剩下 -> 400「没有需要更新的字段」
```

### 14.3 三个你可能想问的问题

**Q：`exclude_unset=True` 和 `if value is not None` 有什么区别？**

前者决定"这个 key 在不在字典里"，后者决定"这个值要不要写进库"。
以前只有后者，所以"用户没传"和"用户显式传了 null"被混为一谈。
加上 `exclude_unset=True` 之后，DAO 拿到的是**用户真正提过的字段**，
"提过但给了空值"和"压根没提"在 DAO 眼里是两件事，都能正确处理。

**Q：`null` 能不能用来清空某个字段？**

**不能。** 在这个接口里 `null` = "这个字段我没什么要改的"。
想清空字段目前没有支持的写法 —— 这是有意留的坑，见下面 14.4。

**Q：`stu_age: 0` 算空吗？**

不算。`0` 和 `False` 是有意义的业务值，`stu_age=0` 会被 `gt=18` 当成
"你填错了年龄"直接 422 —— 这是"填错"，不是"没填"，不该被静默跳过。

### 14.4 留的一个坑（需要时再开）

现在**没有办法通过这个接口把某个字段置空**（比如把 `stu_major` 清成 NULL）。
原因是要区分"用户想清空"和"用户没填"，光看 JSON 里的 `null` 区分不了。
如果以后真需要，两个做法：

1. 加一个显式开关字段，比如 `{"stu_major": null, "__clear__": ["stu_major"]}`；
2. 换用 PATCH 语义，把"清空"改成传 `""` 并在 DAO 里单独处理。

现在先不选，因为业务上还没这个需求 —— 但要知道它在那儿。

### 14.5 改动的文件

| 文件 | 改了什么 |
|---|---|
| `utils.py` | `model_to_dict()` 加 `exclude_unset` 参数（默认 `False`，**不影响任何现有调用方**） |
| `schema/student_request.py` | `UpdateStudent` 加 `_blank_to_none` 前置校验器 |
| `Dao/stu_dao.py` | `update_stu_info()` 重写成三道关筛选 + 空更新返回 400；新增 `_is_blank()` |
| `API/stu_info_api.py` | 改用 `model_to_dict(stu_info, exclude_unset=True)` |
| `tests/test_api.py` | 新增 6 条回归测试（只改传了的字段 / 空串 / null / 空 body / 全空值 / 白名单） |

### 14.6 现在的行为对照表

| 请求体 | 改之前 | 改之后 |
|---|---|---|
| `{"stu_school": "新大学"}` | 200，只改学校 | 200，只改学校（不变） |
| `{"stu_school": "新大学", "stu_tel": ""}` | **422** | 200，只改学校，手机号不动 |
| `{"stu_school": "新大学", "stu_major": null}` | 200，只改学校 | 200，只改学校（不变） |
| `{"stu_name": ""}` | **200，姓名被清空** | 400，没有可更新的字段 |
| `{}` | **200「更新成功」（其实啥也没改）** | 400，没有可更新的字段 |
| `{"stu_class_id": 99999}` | 404 班级不存在 | 404 班级不存在（不变） |
| `{"is_del": 1, "stu_id": 999}` | 200，危险字段被忽略 | 200，危险字段被忽略（不变） |

---

## 附：排查这类问题的通用流程

下次再遇到「跑不起来」，按这个顺序走，别跳步：

```
1. python -c "import main"
   └─ 报错在 import 阶段 → 是依赖 / 配置 / 顶层副作用问题
   └─ 报错在运行阶段   → 进第 2 步

2. python -c "import 数据库驱动; 连一下"
   └─ 连不上 → 检查 .env、MySQL 服务、端口、认证方式

3. 把 ORM 模型和 SHOW CREATE TABLE 的结果对一遍
   └─ 对不上 → 表结构漂移，写迁移脚本（先备份！）

4. 起服务，先打一个最简单的 GET 接口
   └─ 通了 → 逐个模块打，失败的就地查

5. 写一个覆盖全接口的冒烟脚本，一次性跑完
   └─ 比"改一个跑一个"快得多
```

**两个最有用的习惯**：

1. **先把项目跑起来再改代码。** 跑不起来的时候改代码，你分不清
   「是我改坏了」还是「本来就坏的」。
2. **一次跑完所有接口，而不是修一个报一个。** 我这次第一轮冒烟就抓出了 9 个
   状态码问题 + 4 个 500，如果一个一个修，来回得跑十几轮。

祝进度顺利。有具体哪个点想深挖，随时说。
