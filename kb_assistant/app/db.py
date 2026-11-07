"""
数据库访问层 —— 小助手【只读】地连 MySQL。

【为什么不复用主项目的 database.py】
    1. 主后端是 CRUD 服务，用的是可写连接；
       小助手只允许读，用同一个引擎容易在失误时写进库；
    2. 主后端代码一行都不该被这个功能牵动（用户明确要求）；
    3. 这里要加【语句级超时】和【行数上限】，主后端没有这层管控。

【建议】
    正式部署时，强烈建议给小助手单独开一个【只读】的 MySQL 账号：
        CREATE USER 'kb_ro'@'%' IDENTIFIED BY '...';
        GRANT SELECT ON student_ms_demo.* TO 'kb_ro'@'%';
    把这个账号写进 .env 的 DB_USER / DB_PASSWORD 即可。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL

from .config import settings


@dataclass
class QueryResult:
    """一次查询的结果。"""

    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    elapsed_ms: int = 0
    truncated: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            'columns': self.columns,
            'rows': self.rows,
            'row_count': self.row_count,
            'elapsed_ms': self.elapsed_ms,
            'truncated': self.truncated,
        }


class Database:
    """只读数据库访问器（惰性连接）。"""

    def __init__(self) -> None:
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        """
        惰性创建连接池。

        注意 create_engine 本身不连库，只有真正执行查询时才连，
        所以数据库没起来时这个模块照样能 import。
        """
        if self._engine is None:
            # 【为什么用 URL.create 而不是拼字符串】
            #   密码里如果有 @ % / # 这些字符，字符串拼出来的 URL 会被
            #   SQLAlchemy 解析错 —— 密码变成主机名的一部分，连接直接失败。
            #   URL.create() 会自动做百分号转义，密码随便取都行。
            url = URL.create(
                drivername='mysql+pymysql',
                username=settings.db_user,
                password=settings.db_password,
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                query={'charset': 'utf8mb4'},
            )
            self._engine = create_engine(
                url,
                pool_size=3,
                pool_recycle=1800,
                pool_pre_ping=True,
                connect_args={
                    'charset': 'utf8mb4',
                    # 单条 SQL 超时，防止一条没有 LIMIT 的查询把连接占死
                    'read_timeout': int(settings.sql_timeout),
                    'write_timeout': int(settings.sql_timeout),
                },
            )
        return self._engine

    def ping(self) -> bool:
        """探活：能不能连上库。"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return True
        except Exception:
            return False

    def run_sql(self, sql: str, max_rows: int | None = None) -> QueryResult:
        """
        执行一条【已经通过 sql_guard 校验】的 SELECT。

        返回值里的 rows 是 [{列名: 值}, ...] 的形式，
        直接序列化成 JSON 交给模型读。
        """
        limit = max_rows or settings.max_rows
        started = time.perf_counter()
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = list(result.keys())
                fetched = result.fetchall()
                # 双保险：即便 SQL 里写了很大的 LIMIT，这里也只放行 limit 行
                truncated = len(fetched) > limit
                rows = [dict(zip(columns, row)) for row in fetched[:limit]]
        except Exception as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            return QueryResult(
                error=self._friendly_error(exc),
                elapsed_ms=elapsed,
            )

        elapsed = int((time.perf_counter() - started) * 1000)
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed_ms=elapsed,
            truncated=truncated,
        )

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        """把数据库异常翻译成用户看得懂的话。"""
        text = str(exc)
        mapping = [
            ('Unknown column', 'SQL 里用了不存在的字段'),
            ('doesn\'t exist', 'SQL 里用了不存在的表或字段'),
            ('You have an error in your SQL syntax', 'SQL 语法有误'),
            ('ambiguous', 'SQL 里字段引用有歧义，需要加上表名前缀'),
            ('Lost connection', '数据库连接中断'),
        ]
        for needle, friendly in mapping:
            if needle in text:
                return f'{friendly}（{text[:160]}）'
        return f'查询执行失败：{text[:200]}'


db = Database()
