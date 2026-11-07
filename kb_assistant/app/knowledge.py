"""
知识库 —— 小助手对「这个系统是什么」的全部认知。

【包含什么】
    1. 数据库表结构（7 张表、字段中文含义、软删除字段、关联关系）；
    2. 前端功能模块（统计分析 / 学生管理 / 顾问 / 学生成绩 / 就业 / 班级 / 班主任 / 授课老师 / 数据大屏）；
    3. 后端接口清单（模块 + 路径 + 用途）；
    4. 业务术语表（顾问、班主任、班级、结业时长……）。

【为什么要手写而不是自动从数据库读】
    1. 【稳定】information_schema 在不同 MySQL 版本上字段名有出入，
       手写一份可控、可读、可注释；
    2. 【有业务含义】表结构只能告诉模型「有哪些列」，
       而「顾问是负责招生的老师」「employment 是就业去向」这类业务语义
       必须有人写下来，模型才知道怎么回答业务问题；
    3. 【省 token】精选过的结构比 SHOW CREATE TABLE 全量输出短得多。

【表结构怎么保证不过期】
    本文件与 sql/01_create_schema.sql 一一对应。
    改了数据库结构，记得同步改这里 —— 可以在 app/main.py 的 /health 里
    打开 DB_SCHEMA_DRIFT_CHECK 做校验。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    """一个字段。"""

    name: str
    cn: str
    type: str
    note: str = ''

    def render(self) -> str:
        extra = f'  -- {self.note}' if self.note else ''
        return f'{self.name} {self.type}{extra}'


@dataclass(frozen=True)
class Table:
    """一张表。"""

    name: str
    cn: str
    desc: str
    columns: list[Column] = field(default_factory=list)
    # 该表的软删除字段名（没有则为 None）
    soft_delete: str | None = None

    def render(self) -> str:
        lines = [f'-- {self.cn}：{self.desc}', f'CREATE TABLE {self.name} (']
        body = [f'  {c.render()},' for c in self.columns]
        lines.extend(body)
        lines.append(');')
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# 表结构
# ---------------------------------------------------------------------------
TABLES: list[Table] = [
    Table(
        name='student_info',
        cn='学生信息表',
        desc='学员档案主表。成绩表和就业信息表都外键指向它。',
        soft_delete='is_del',
        columns=[
            Column('stu_id', '学生编号', 'INT', '主键'),
            Column('stu_name', '学生姓名', 'VARCHAR(10)'),
            Column('stu_age', '年龄', 'INT'),
            Column('stu_sex', '性别', 'VARCHAR(10)', "取值只有 '男' / '女'"),
            Column('stu_tel', '联系电话', 'VARCHAR(20)'),
            Column('stu_class_id', '所在班级id', 'INT', '外键 -> clazz.stu_class_id'),
            Column('agent_id', '负责招生的顾问id', 'INT', '外键 -> agent.agent_id，可为空（校方直招）'),
            Column('stu_from', '生源地', 'VARCHAR(20)'),
            Column('stu_school', '毕业院校', 'VARCHAR(20)'),
            Column('stu_major', '专业', 'VARCHAR(20)'),
            Column('enroll_date', '入学时间', 'DATETIME'),
            Column('gra_date', '毕业时间', 'DATETIME'),
            Column('edu_bg', '教育背景', 'VARCHAR(20)'),
            Column('is_del', '是否删除', 'INT', '0 未删除，1 已删除'),
        ],
    ),
    Table(
        name='clazz',
        cn='班级表',
        desc='班级是「教学单元」，一个班级配一位班主任和一位授课老师。',
        soft_delete='is_del',
        columns=[
            Column('stu_class_id', '班级编号', 'INT', '主键'),
            Column('class_name', '班级名称', 'VARCHAR(20)'),
            Column('start_date', '开课时间', 'DATE'),
            Column('class_teacher_id', '班主任id', 'INT', '外键 -> class_teacher.class_teacher_id'),
            Column('teacher_id', '授课老师id', 'INT', '外键 -> teacher.teacher_id'),
            Column('is_del', '是否删除', 'INT', '0 未删除，1 已删除'),
        ],
    ),
    Table(
        name='agent',
        cn='顾问表',
        desc='顾问负责招生，按顾问可以查出其招来的学生。表名 agent 是历史沿用，业务上叫「顾问」。',
        soft_delete='is_del',
        columns=[
            Column('agent_id', '顾问编号', 'INT', '主键'),
            Column('agent_name', '顾问姓名', 'VARCHAR(20)'),
            Column('agent_sex', '顾问性别', 'VARCHAR(20)', "取值 '男' / '女'"),
            Column('agent_age', '顾问年龄', 'INT'),
            Column('is_del', '是否删除', 'INT', '0 未删除，1 已删除'),
        ],
    ),
    Table(
        name='class_teacher',
        cn='班主任表',
        desc='班主任负责班级管理，一个班级对应一位班主任。',
        soft_delete='is_del',
        columns=[
            Column('class_teacher_id', '班主任编号', 'INT', '主键'),
            Column('class_teacher_name', '班主任姓名', 'VARCHAR(10)'),
            Column('class_teacher_sex', '班主任性别', 'VARCHAR(1)', "取值 '男' / '女'"),
            Column('is_del', '是否删除', 'INT', '0 未删除，1 已删除'),
        ],
    ),
    Table(
        name='teacher',
        cn='老师表',
        desc='授课老师。注意这张表的软删除字段叫 is_delete，不是 is_del —— 历史遗留。',
        soft_delete='is_delete',
        columns=[
            Column('teacher_id', '老师编号', 'INT', '主键'),
            Column('teacher_name', '老师姓名', 'VARCHAR(20)'),
            Column('teacher_tel', '老师手机号', 'VARCHAR(20)'),
            Column('teacher_job', '老师岗位', 'VARCHAR(20)'),
            Column('is_delete', '是否删除', 'INT', '0 未删除，1 已删除'),
        ],
    ),
    Table(
        name='scores',
        cn='成绩表',
        desc='一行 = 一个学生某一次考试的成绩。每个学生通常有 3 次考试（test_id = 1/2/3）。',
        soft_delete='is_del',
        columns=[
            Column('id', '主键', 'INT', '自增'),
            Column('stu_id', '学生编号', 'INT', '外键 -> student_info.stu_id'),
            Column('test_id', '考试序次', 'INT', '1、2、3 分别代表第几次考试'),
            Column('score', '分数', 'FLOAT', '满分 100，低于 60 视为不及格'),
            Column('is_del', '是否删除', 'INT', '0 未删除，1 已删除'),
        ],
    ),
    Table(
        name='employment',
        cn='就业信息表',
        desc='就业去向。一个学生最多一条就业记录（stu_id 上有唯一索引）。',
        soft_delete='is_del',
        columns=[
            Column('id', '主键', 'INT', '自增'),
            Column('stu_id', '学生编号', 'INT', '外键 -> student_info.stu_id，唯一'),
            Column('open_date', '简历开放日期', 'DATETIME', '进入就业阶段的时间'),
            Column('offer_date', '收到offer日期', 'DATETIME', '拿到 offer 的时间'),
            Column('company', '就业公司', 'VARCHAR(50)'),
            Column('salary', '薪资', 'DECIMAL(10,2)', '单位：元'),
            Column('is_del', '是否删除', 'INT', '0 未删除，1 已删除'),
        ],
    ),
]


# ---------------------------------------------------------------------------
# 前端功能模块
# ---------------------------------------------------------------------------
MODULES: list[tuple[str, str, str]] = [
    ('统计分析', '/stat/analysis', '首页总览（原数据看板已并入这里）：八格册页副表 + 总览/成绩/就业/班级四个分区，另有「进入数据大屏」入口。'),
    ('学生管理', '/student/list', '学员档案的增删改查，支持按姓名、班级、顾问筛选；默认按学号、年龄、入学时间排序。'),
    ('顾问管理', '/student/agent', '招生顾问的档案管理，可反查该顾问招来的学生。'),
    ('学生成绩', '/score/list', '录入与查询成绩，支持按学生、按考试序次查询。'),
    ('就业信息', '/employment/list', '就业去向登记（公司、薪资、offer 时间），含分页与未就业查询；默认按薪资降序。'),
    ('班级列表', '/class/list', '班级档案管理，可查看班级下的全部学员。'),
    ('班主任', '/class/teacher', '班主任档案管理。'),
    ('授课老师', '/teacher/list', '授课老师档案管理。'),
    ('数据大屏', '/screen', '全屏驾驶舱：班级排名、就业去向热力中国地图、薪资区间、待就业名录等。'),
]


# ---------------------------------------------------------------------------
# 后端接口清单（前缀 + 路径 + 用途）
# ---------------------------------------------------------------------------
API_ENDPOINTS: list[tuple[str, str, str]] = [
    ('/student', 'POST /add_stu', '新增学生'),
    ('/student', 'GET /select_stu_id', '按学生 id 查询'),
    ('/student', 'GET /select_stu_skip', '分页查询学生列表'),
    ('/student', 'GET /select_stu_name', '按姓名查询学生'),
    ('/student', 'GET /select_stu_class', '按班级查询学生'),
    ('/student', 'PUT /update_stu_class', '修改学生信息'),
    ('/student', 'DELETE /delete_stu', '删除学生'),
    ('/agent', 'POST /add_agent', '新增顾问'),
    ('/agent', 'GET /agent', '查询所有顾问'),
    ('/agent', 'GET /select_agent', '按 id 查询顾问'),
    ('/agent', 'PUT /update_agent', '修改顾问'),
    ('/agent', 'DELETE /delete_agent', '删除顾问'),
    ('/score', 'POST /score', '录入成绩'),
    ('/score', 'GET /stu_id/{stu_id}', '查询单个学生的考试成绩'),
    ('/score', 'GET /test_id/{test_id}', '查询某次考试的学生成绩'),
    ('/score', 'GET /stu_id/{stu_id}/test_id/{test_id}', '查询某学生某次考试的成绩'),
    ('/score', 'PUT /put', '修改学生成绩'),
    ('/score', 'DELETE /del/stu_id/{stu_id}/test_id/{test_id}', '删除学生成绩'),
    ('/score', 'GET /get_del', '查询已删除的成绩'),
    ('/employment', 'POST /create', '添加就业信息'),
    ('/employment', 'GET /search', '按条件查询就业信息'),
    ('/employment', 'GET /page', '分页查询就业信息'),
    ('/employment', 'GET /unemployed', '查询当前未就业的学生'),
    ('/employment', 'PUT /put/{stu_id}', '按学号修改就业信息'),
    ('/employment', 'DELETE /delete/{stu_id}', '删除就业信息'),
    ('/class', 'POST /', '新建班级'),
    ('/class', 'PUT /update_class/{stu_class_id}', '修改班级'),
    ('/class', 'DELETE /delete_class/{stu_class_id}', '删除班级及班级学员'),
    ('/class', 'GET /get_class/{stu_class_id}', '查询班级信息'),
    ('/class', 'GET /get_class/{stu_class_id}/students', '查询班级全部学员'),
    ('/class', 'GET /all_class', '查询所有班级'),
    ('/class_teacher', 'POST /class_teacher', '新增班主任'),
    ('/class_teacher', 'PUT /update_class_teacher/{id}', '修改班主任'),
    ('/class_teacher', 'DELETE /delete_class_teacher/{id}', '删除班主任'),
    ('/class_teacher', 'GET /get_class_teacher/{id}', '查询班主任'),
    ('/class_teacher', 'GET /all_class_teacher', '查询所有班主任'),
    ('/teacher', 'POST /', '新增老师'),
    ('/teacher', 'GET /{teacher_id}', '按 id 查询老师'),
    ('/teacher', 'GET /', '查询所有老师'),
    ('/teacher', 'PUT /{teacher_id}', '修改老师'),
    ('/teacher', 'DELETE /{teacher_id}', '删除老师'),
    ('/stat', 'GET /students/over_age', '查询超过指定年龄的学员'),
    ('/stat', 'GET /class/statistics', '每个班级的总人数与男女构成'),
    ('/stat', 'GET /score/all_above_80', '每次考试都在 80 分以上的学生'),
    ('/stat', 'GET /score/failed_twice', '有两次以上不及格的学生'),
    ('/stat', 'GET /score/avg_by_class', '各班各次考试的平均分（倒序）'),
    ('/stat', 'GET /emp/top5_salary', '薪资最高的 5 名学生'),
    ('/stat', 'GET /emp/duration', '每个学生的就业时长（offer - 简历开放）'),
    ('/stat', 'GET /emp/avg_duration_by_class', '各班平均就业时长'),
]


# ---------------------------------------------------------------------------
# 业务术语
# ---------------------------------------------------------------------------
GLOSSARY: list[tuple[str, str]] = [
    ('顾问', '负责招生的老师，一个学生可以有一位顾问，也可以没有（校方直招）。代码里表名叫 agent，是历史沿用。'),
    ('班主任', '负责班级日常管理的老师，一个班级对应一位班主任，在 clazz.class_teacher_id 里关联。'),
    ('授课老师', '负责具体课程教学的老师，一个班级对应一位，在 clazz.teacher_id 里关联。'),
    ('班级', '教学单元，编号从 1 开始递增，班级下挂学生（student_info.stu_class_id）。'),
    ('班级名称格式', 'class_name 的实际取值是「专业名 + 序号班」，例如「软件工程1班」「计算机科学1班」'
                    '「网络工程3班」，共 36 个班，全部互不相同。'
                    '★ 关键：班级序号与 stu_class_id 一一对应 —— 第 N 个班就是 stu_class_id = N。'
                    '所以用户说「1 号班」时，应该用 stu_class_id = 1 去查，'
                    '而不是去猜 class_name 等于「1号班」（库里根本没有这个名字）。'),
    ('考试序次', 'test_id，表示第几次考试，一般 1/2/3。成绩表一行 = 一个学生的一次考试。'),
    ('及格线', '60 分。低于 60 分视为不及格。'),
    ('简历开放时间', 'open_date，学生进入就业阶段、简历开始投放的时间。'),
    ('offer 时间', 'offer_date，学生拿到录用意向的时间。'),
    ('就业时长', 'offer_date - open_date，单位一般按天算。'),
    ('软删除', '所有业务表都用 is_del 标记删除（teacher 表是 is_delete），1 表示已删除。统计时默认要过滤掉。'),
]


# ---------------------------------------------------------------------------
# 渲染成给模型看的文本
# ---------------------------------------------------------------------------
def render_schema() -> str:
    """把表结构渲染成给模型看的紧凑 DDL 文本。"""
    return '\n\n'.join(t.render() for t in TABLES)


def render_relations() -> str:
    """表与表之间的关联关系说明。"""
    return '\n'.join([
        'student_info.stu_class_id  -> clazz.stu_class_id      (学生属于班级)',
        'student_info.agent_id     -> agent.agent_id           (学生的招生顾问，可为 NULL)',
        'clazz.class_teacher_id    -> class_teacher.class_teacher_id  (班主任)',
        'clazz.teacher_id          -> teacher.teacher_id       (授课老师)',
        'scores.stu_id             -> student_info.stu_id      (成绩属于学生)',
        'employment.stu_id         -> student_info.stu_id      (就业信息属于学生)',
    ])


def render_modules() -> str:
    """前端功能模块清单。"""
    return '\n'.join(f'- {name}（{path}）：{desc}' for name, path, desc in MODULES)


def render_api() -> str:
    """后端接口清单。"""
    return '\n'.join(f'- {prefix}{path}：{desc}' for prefix, path, desc in API_ENDPOINTS)


def render_glossary() -> str:
    """业务术语表。"""
    return '\n'.join(f'- {term}：{desc}' for term, desc in GLOSSARY)


def render_knowledge() -> str:
    """
    完整的知识库文本 —— 直接塞进系统提示词。

    长度大约 3000 字左右，对 512K 上下文来说可以忽略不计，
    但足以让模型准确理解这个系统的业务语义。
    """
    return f"""# 一、数据库表结构（MySQL，库名 student_ms_demo）

{render_schema()}

# 二、表关联关系

{render_relations()}

# 三、前端功能模块

{render_modules()}

# 四、后端接口清单

{render_api()}

# 五、业务术语

{render_glossary()}
"""
