"""
演示数据重置服务 —— 把数据库恢复到「种子基线」。

====================================================================
【为什么需要这个模块？】
====================================================================
这个系统部署到公网后，任何拿到网址的人都能增删改数据。而你可能：

    · 被人手滑删了学生/成绩（软删除，is_del=1）
    · 被人改坏了某个字段（比如把学生 1 的院校改成 'string'）
    · 被人插入了大量测试垃圾行

前两种情况，光靠 `frontend/scripts/reset-demo-data.sql` 救不回来 ——
它只按「命名特征」删多余的行，对「被改值」的种子行无能为力。
所以这里做的是【彻底重建】：删表重建 + 重新灌种子，保证 100% 回到初始状态。

====================================================================
【为什么不用现成的 sql/run_sql.py？】
====================================================================
run_sql.py 走的是「DROP DATABASE + CREATE DATABASE」，这会：
    1. 删掉整个库 —— 包括 SQLite/MySQL 之外的所有东西
    2. 让后端连接池里的连接全部失效（库被重建了）
    3. 在 Docker 里更麻烦：MySQL 容器初始化脚本只跑一次

这里改成【只重建表、不动库】：
    DROP TABLE ... → CREATE TABLE ... → INSERT 种子
库还在、连接还在，只是表被换了一遍。对在线服务友好得多。

====================================================================
【安全性：三重闸门】
====================================================================
1. 口令校验 —— 必须带正确的 RESET_TOKEN（从环境变量读，绝不写死）
2. 确认短语 —— 必须传 confirm='RESET'，防误触
3. 审计日志 —— 每次重置记录时间、来源 IP、操作人

而且：没有配置 RESET_TOKEN 时，这个接口【直接关闭】（返回 404），
不是「空口令也能过」。这是公开部署场景下必须有的默认行为。

====================================================================
【幂等性】
====================================================================
重复执行任意多次，结果完全一样 —— 每次都从种子文件重建。
"""

import io
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger('reset_service')

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
# utils/reset_service.py -> utils -> 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / 'sql'

# 要依次执行的脚本（顺序不能变：先建表，后灌数据）
SEED_FILES = ['01_create_schema.sql', '02_seed_demo_data.sql']

# 审计日志文件（放在 logs/ 下，与 kb_assistant/logs/ 同一套约定）
LOG_DIR = PROJECT_ROOT / 'logs'
AUDIT_LOG = LOG_DIR / 'reset-audit.log'

# ---------------------------------------------------------------------------
# 基线自检值：种子跑完后各表应该有多少行
# 与 sql/02_seed_demo_data.sql 实际内容核对过（合计 1018 行）
# ---------------------------------------------------------------------------
BASELINE_COUNTS: Dict[str, int] = {
    'agent': 12,
    'class_teacher': 12,
    'teacher': 24,
    'clazz': 36,
    'student_info': 200,
    'scores': 600,
    'employment': 134,
}

# 种子文件里的默认库名。重建表时不涉及 USE 语句，但要防止
# 01_create_schema.sql 里的 DROP DATABASE 顺手把库删了。
_SEED_DB_NAME = 'student_ms_demo'

# 允许重建的表（白名单，杜绝误删系统表）
_ALLOWED_TABLES = set(BASELINE_COUNTS.keys())


# =======================================================================
# 一、SQL 拆分
# =======================================================================
def split_sql_statements(sql_text: str):
    """
    把一个 .sql 文件拆成一条条独立语句。

    【为什么要自己拆？】
    让 PyMySQL 一次执行整个文件（client_flag=MULTI_STATEMENTS），
    文件中间的 `SET NAMES utf8mb4;` 会改变连接字符集，
    PyMySQL 解析后面的结果包时对不上，后面的 INSERT 会被【静默跳过】 ——
    不报错，但数据一行都没插进去。这种「不报错但没生效」最坑，
    所以改成一条一条执行。

    拆分时必须跳过这些地方里的分号，否则会切错：
        '字符串里的分号;'      —— 单引号
        "字符串里的分号;"      —— 双引号
        `表名;`                —— 反引号
        -- 行注释里的分号;     —— 双减号注释
        /* 块注释里的分号; */  —— 块注释
    """
    statements = []
    buf = []
    i = 0
    n = len(sql_text)

    while i < n:
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < n else ''

        # ---- 注释 ----
        if ch == '-' and nxt == '-':
            while i < n and sql_text[i] != '\n':
                i += 1
            continue

        if ch == '/' and nxt == '*':
            end = sql_text.find('*/', i + 2)
            i = n if end == -1 else end + 2
            continue

        # ---- 引号 ----
        if ch in ("'", '"', '`'):
            quote = ch
            buf.append(ch)
            i += 1
            while i < n:
                buf.append(sql_text[i])
                if sql_text[i] == '\\' and i + 1 < n:
                    i += 1
                    buf.append(sql_text[i])
                    i += 1
                    continue
                if sql_text[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        # ---- 分号：一条语句结束 ----
        if ch == ';':
            stmt = ''.join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    # 文件最后可能有一条不带分号的语句
    tail = ''.join(buf).strip()
    if tail:
        statements.append(tail)

    return statements


# =======================================================================
# 二、口令校验
# =======================================================================
def get_reset_token() -> Optional[str]:
    """
    从环境变量读重置口令。

    没有配置 = 接口关闭（不是空口令放行）。
    这个默认行为很重要：公开部署时如果忘了配 RESET_TOKEN，
    结果应该是「重置功能用不了」，而不是「任何人都能重置」。
    """
    token = os.getenv('RESET_TOKEN', '').strip()
    return token or None


def is_reset_enabled() -> bool:
    """重置功能是否可用（有没有配口令）。"""
    return get_reset_token() is not None


def verify_token(provided: Optional[str]) -> bool:
    """校验口令。用常量时间比较，避免计时侧信道。"""
    expected = get_reset_token()
    if not expected:
        return False
    if not provided:
        return False
    # secrets.compare_digest 做的是常量时间比较
    import secrets
    return secrets.compare_digest(str(provided), expected)


# =======================================================================
# 三、审计日志
# =======================================================================
def write_audit(entry: Dict[str, Any]) -> None:
    """
    把一次重置操作写进审计日志文件。

    【为什么单独写文件而不是只用 logging？】
    logging 的输出可能被容器日志轮转、可能被日志级别过滤掉。
    审计日志要【独立留存、不能丢】，所以直接写文件（追加模式）。

    日志里【不记录口令本身】，只记操作人和来源 IP。
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = (
            f"[{stamp}] "
            f"action={entry.get('action')} "
            f"result={entry.get('result')} "
            f"operator={entry.get('operator')} "
            f"ip={entry.get('ip')} "
            f"client={entry.get('client')} "
            f"duration_ms={entry.get('duration_ms')} "
            f"detail={entry.get('detail')}\n"
        )
        with io.open(AUDIT_LOG, 'a', encoding='utf-8') as f:
            f.write(line)
    except OSError as e:
        # 审计写失败不能把重置流程搞崩，但必须让人知道
        logger.error('审计日志写入失败: %s', e)


# =======================================================================
# 四、重建
# =======================================================================
def _drop_and_recreate_tables(db: Session) -> None:
    """
    删掉 7 张业务表再按种子脚本重建。

    【为什么删表重建，而不是 DELETE FROM？】
    DELETE FROM 只能清数据，改坏了的【表结构】（比如某列被加了默认值）
    修不回来；而且 AUTO_INCREMENT 计数器不会归零，
    重置后新加的学生会从 601 号开始，很怪。
    删表重建能保证结构、数据、自增计数器全部回到初始状态。

    【外键的处理】
    必须先关掉外键检查，否则 DROP 顺序不对会报错。
    建完表再打开。
    """
    # 先关外键检查（表之间有外键，drop 顺序错了会失败）
    db.execute(text('SET FOREIGN_KEY_CHECKS = 0'))

    for table in _ALLOWED_TABLES:
        # 表名来自白名单常量，不接受外部输入 —— 不存在 SQL 注入面
        db.execute(text(f'DROP TABLE IF EXISTS `{table}`'))

    db.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
    db.commit()


def _run_seed_statements(db: Session) -> Dict[str, int]:
    r"""
    执行种子脚本，把 1018 条数据灌回去。

    种子脚本里的 USE 语句和 DROP DATABASE 这两句必须跳过 ——
    我们的目标是【重建表】，不是重建库。
    """
    executed = 0

    for filename in SEED_FILES:
        path = SQL_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f'找不到种子文件: {path}')

        with io.open(path, 'r', encoding='utf-8') as f:
            sql_text = f.read()

        for stmt in split_sql_statements(sql_text):
            head = stmt.split('\n')[0][:60]
            # 跳过库级语句：我们只重建表，不碰库
            if re.match(r'^\s*(USE\s|DROP\s+DATABASE|CREATE\s+DATABASE)', stmt, re.IGNORECASE):
                logger.info('跳过库级语句: %s', head)
                continue

            try:
                db.execute(text(stmt))
                executed += 1
            except Exception as e:
                db.rollback()
                raise RuntimeError(
                    f'执行种子文件 {filename} 失败于语句「{head}」: {e}'
                ) from e

    db.commit()
    return {'executed_statements': executed}


def _count_rows(db: Session) -> Dict[str, int]:
    """统计各表行数，用于重置后的自检。"""
    counts = {}
    for table in _ALLOWED_TABLES:
        result = db.execute(text(f'SELECT COUNT(*) FROM `{table}`'))
        counts[table] = int(result.scalar() or 0)
    return counts


def _verify_baseline(counts: Dict[str, int]) -> Dict[str, bool]:
    """对照基线值自检，返回每个表是否达标。"""
    return {
        table: counts.get(table) == expected
        for table, expected in BASELINE_COUNTS.items()
    }


def reset_to_baseline(db: Session) -> Dict[str, Any]:
    """
    把数据库彻底恢复到种子基线。

    返回：
        {
            'ok': True/False,
            'message': '...',
            'counts': {表名: 行数},
            'baseline_check': {表名: 是否达标},
            'all_match': True/False,
        }
    """
    started = datetime.now()

    try:
        logger.info('开始重建演示数据 ...')
        _drop_and_recreate_tables(db)
        _run_seed_statements(db)

        counts = _count_rows(db)
        checks = _verify_baseline(counts)
        all_match = all(checks.values())

        duration_ms = int((datetime.now() - started).total_seconds() * 1000)

        if all_match:
            message = '重置成功，数据库已恢复到种子基线。'
            logger.info(message)
        else:
            mismatched = [t for t, ok in checks.items() if not ok]
            message = f'重置已执行，但以下表行数与基线不符: {", ".join(mismatched)}'
            logger.warning(message)

        return {
            'ok': all_match,
            'message': message,
            'counts': counts,
            'baseline_check': checks,
            'all_match': all_match,
            'duration_ms': duration_ms,
        }

    except Exception as e:
        db.rollback()
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        logger.exception('重置失败')
        return {
            'ok': False,
            'message': f'重置失败: {e}',
            'counts': {},
            'baseline_check': {},
            'all_match': False,
            'duration_ms': duration_ms,
        }


def get_baseline_info() -> Dict[str, Any]:
    """
    读一下当前库的各表行数（不改动任何东西）。

    给前端「重置」弹窗做展示用：让用户在按下去之前，
    先看清楚现在库里有多少行，重置后会变成多少行。
    """
    from database import Session as SessionFactory

    db = SessionFactory()
    try:
        counts = _count_rows(db)
        return {
            'current_counts': counts,
            'baseline_counts': dict(BASELINE_COUNTS),
            'total_current': sum(counts.values()),
            'total_baseline': sum(BASELINE_COUNTS.values()),
            'is_at_baseline': counts == dict(BASELINE_COUNTS),
        }
    finally:
        db.close()
