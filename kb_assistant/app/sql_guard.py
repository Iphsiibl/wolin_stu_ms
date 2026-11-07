"""
SQL 安全闸门 —— 小助手【只能】读，不能写。

【为什么需要这一层】
    模型的输出是不可信输入。即使系统提示词已经要求「只生成 SELECT」，
    也必须有一道【代码级】的兜底：
      - 万一模型被诱导生成了 UPDATE / DROP；
      - 万一用户把 SQL 直接贴进对话框（提示注入）；
      - 万一模型生成了 INTO OUTFILE / LOAD_FILE 这类能落盘、能读文件的语句。

【这一层做四件事】
    1. 提取 SQL（兼容 ```sql 代码块和裸 SQL 两种写法）；
    2. 关键词黑名单：任何写操作 / DDL / 危险函数直接拒绝；
    3. 表白名单：只允许查本项目的 7 张业务表；
    4. 补 LIMIT：不给上限的查询会拖垮数据库。

【注意】
    这里的校验是「黑名单 + 白名单」双保险。
    单靠黑名单永远不够（SQL 语法太灵活），所以白名单才是真正的那道门。
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 本项目允许查询的表（与 sql/01_create_schema.sql 保持一致）
# ---------------------------------------------------------------------------
ALLOWED_TABLES: frozenset[str] = frozenset({
    'agent',
    'class_teacher',
    'clazz',
    'employment',
    'scores',
    'student_info',
    'teacher',
})

# ---------------------------------------------------------------------------
# 禁用关键词
# ---------------------------------------------------------------------------
# 写操作 / DDL —— 出现在任何位置都拒绝
_FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    'insert', 'update', 'delete', 'replace', 'merge', 'upsert',
    'drop', 'alter', 'truncate', 'create', 'rename', 'comment',
    'grant', 'revoke', 'call', 'execute', 'prepare', 'deallocate',
    'lock', 'unlock', 'set', 'commit', 'rollback', 'begin', 'savepoint',
    'handler', 'load', 'outfile', 'dumpfile', 'into',
)

# 危险函数 —— 能读文件、能发包、能执行系统命令
_FORBIDDEN_FUNCTIONS: tuple[str, ...] = (
    'load_file', 'sys_exec', 'sys_eval', 'benchmark', 'sleep',
    'get_lock', 'release_lock', 'master_pos_wait', 'source',
)

# 单条语句里禁止出现分号（防止「SELECT ...; DROP TABLE ...」拼接）
_STATEMENT_SPLIT = re.compile(r';')

# 代码块提取
_FENCE_RE = re.compile(r'```(?:sql)?\s*(.*?)```', re.DOTALL | re.IGNORECASE)

# 表名提取：FROM / JOIN 后面的标识符
_TABLE_RE = re.compile(
    r'\b(?:from|join)\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?',
    re.IGNORECASE,
)

# CTE 名字提取：WITH xxx AS ( ... )，以及 , yyy AS ( ... )
# 这些名字不是物理表，是查询内部定义的临时结果集，必须放行。
_CTE_RE = re.compile(
    r'(?:\bwith\b|,)\s*`?([a-zA-Z_][a-zA-Z0-9_]*)`?\s+as\s*\(',
    re.IGNORECASE,
)

# 顶层 LIMIT 检测（只看括号外的 LIMIT）
_LIMIT_RE = re.compile(r'\blimit\s+\d+', re.IGNORECASE)


class SqlRejected(Exception):
    """SQL 没通过安全校验。message 是给用户看的中文原因。"""


def extract_sql(text: str) -> str:
    """
    从模型的输出里把 SQL 抠出来。

    兼容两种情况：
      1. 模型用 ```sql ... ``` 包起来；
      2. 模型直接输出一行裸 SQL。

    抠不出来就抛 SqlRejected。
    """
    if not text or not text.strip():
        raise SqlRejected('模型没有生成 SQL')

    candidates: list[str] = []
    for block in _FENCE_RE.findall(text):
        if block.strip():
            candidates.append(block.strip())

    if not candidates:
        stripped = text.strip()
        # 裸 SQL：整段看起来像一条语句就整段用
        if re.match(r'^\s*(select|with)\b', stripped, re.IGNORECASE):
            candidates.append(stripped)
        else:
            # 也可能是一段说明文字后面跟着 SQL，取第一个 SELECT 开头的片段
            match = re.search(r'((?:select|with)\b.*)', stripped, re.IGNORECASE | re.DOTALL)
            if match:
                candidates.append(match.group(1).strip())

    if not candidates:
        raise SqlRejected('模型没有生成可执行的 SQL')

    # 取最长的那个候选：通常是包含完整语句的那段
    return max(candidates, key=len).strip()


def _strip_sql_comments(sql: str) -> str:
    """去掉行注释和块注释，避免注释里藏关键字绕过检查。"""
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    sql = re.sub(r'(?:--|#)[^\n]*', ' ', sql)
    return sql


def _flatten(sql: str) -> str:
    """把 SQL 压成一行小写，方便做关键字匹配（消除换行带来的绕过）。"""
    return re.sub(r'\s+', ' ', sql).strip().lower()


def _check_tables(sql: str) -> None:
    """检查 SQL 里出现的表是否都在白名单里。"""
    # 先把 CTE 名字收集起来：它们是查询内部定义的别名，不是物理表
    cte_names = {name.lower() for name in _CTE_RE.findall(sql)}

    for table in _TABLE_RE.findall(sql):
        name = table.lower()
        if name in ALLOWED_TABLES:
            continue
        # CTE 别名 —— 放行
        if name in cte_names:
            continue
        raise SqlRejected(f'不允许查询表 {table}：小助手只能访问本系统的业务表')


def _check_forbidden(sql: str) -> None:
    """检查禁用关键字和危险函数。"""
    flat = _flatten(sql)

    # 关键词要用「词边界」匹配，避免 stu_id 里的 'set' 之类误伤。
    # 先把标识符里的下划线换成空格再匹配，更稳。
    normalized = flat.replace('_', ' ')

    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf'\b{keyword}\b', normalized):
            raise SqlRejected(f'检测到被禁止的 SQL 关键字「{keyword}」：小助手只能执行只读查询')

    for func in _FORBIDDEN_FUNCTIONS:
        if re.search(rf'\b{func}\s*\(', flat):
            raise SqlRejected(f'检测到被禁止的 SQL 函数「{func}」')


def ensure_limit(sql: str, max_rows: int) -> str:
    """确保 SQL 带 LIMIT；没有就补一个上限。"""
    # 去掉末尾分号再判断
    body = sql.rstrip().rstrip(';').strip()
    if _LIMIT_RE.search(body):
        return body
    return f'{body} LIMIT {max_rows}'


def validate(sql: str, max_rows: int = 200) -> str:
    """
    完整校验一条 SQL，通过则返回【规范化后的安全 SQL】。

    校验顺序（短路，出错立刻抛）：
        1. 非空
        2. 必须以 SELECT / WITH 开头
        3. 不能有多条语句（分号）
        4. 不能有禁用关键字 / 危险函数
        5. 表必须在白名单内
        6. 补 LIMIT

    返回值可以直接丢给数据库执行。
    """
    if not sql or not sql.strip():
        raise SqlRejected('SQL 为空')

    cleaned = _strip_sql_comments(sql).strip()
    if not cleaned:
        raise SqlRejected('SQL 为空')

    # ---- 2. 只允许 SELECT / WITH ----
    if not re.match(r'^\s*(select|with)\b', cleaned, re.IGNORECASE):
        verb = cleaned.split()[0] if cleaned.split() else '未知'
        raise SqlRejected(f'只允许执行 SELECT 查询，收到的是「{verb}」')

    # ---- 3. 单语句 ----
    if _STATEMENT_SPLIT.search(cleaned.rstrip(';')):
        raise SqlRejected('只允许执行单条 SELECT 语句')

    # ---- 4. 禁用关键字 / 函数 ----
    _check_forbidden(cleaned)

    # ---- 5. 表白名单 ----
    _check_tables(cleaned)

    # ---- 6. LIMIT ----
    return ensure_limit(cleaned, max_rows)
