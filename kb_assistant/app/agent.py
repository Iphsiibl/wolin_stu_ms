"""
问答编排 —— 小助手的主流程。

【完整流程】
    用户提问
      │
      ├─ ① 领域预检（确定性规则）
      │     命中跑题 → 直接返回友好拒答，不消耗 token
      │
      ├─ ② 路由 + 生成 SQL（一次模型调用）
      │     模型要么回 "NO_SQL"（知识库能答），要么回一条 SELECT
      │
      ├─ ③ 安全校验（sql_guard）
      │     不过就带着错误原因让模型重写一次（自纠错）
      │
      ├─ ④ 执行查询（只读连接 + 行数上限）
      │
      └─ ⑤ 生成回答（流式）
            有查询结果 → 基于结果作答
            没查询结果 → 基于知识库作答
            回答里带越界标记 → 换成统一拒答话术

【为什么要「路由 + 生成 SQL」合成一次调用】
    拆成两次会让知识类问题（"这个系统有哪些模块？"）白白多跑一次模型；
    合在一起的话，知识类问题只要一次额外调用就能开始流式输出答案。

【和模型协议解耦】
    这一层只调用 llm.complete() / llm.stream()，
    完全不知道底下走的是 Anthropic、OpenAI 兼容还是 Gemini 协议。
    换协议只是改 .env 里的 LLM_PROTOCOL，这个文件一行都不用动。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from . import scope
from .config import settings
from .db import QueryResult, db
from .llm import LLMError, complete, stream
from .prompts import ANSWER_SYSTEM, NO_SQL_ANSWER, SCOPE_SYSTEM, SQL_SYSTEM
from .sessions import Session
from .sql_guard import SqlRejected, extract_sql, validate

logger = logging.getLogger('kb_assistant.agent')

# 模型判断「不用查库」时输出的标记
NO_SQL_MARKER = 'NO_SQL'


@dataclass
class AgentEvent:
    """一个流式事件。event 是类型，data 是载荷。"""

    event: str
    data: dict = field(default_factory=dict)

    def to_sse(self) -> str:
        """序列化成 SSE 帧。"""
        payload = json.dumps(self.data, ensure_ascii=False, default=str)
        return f'event: {self.event}\ndata: {payload}\n\n'


def _format_result(result: QueryResult) -> str:
    """把查询结果渲染成给模型看的文本。"""
    if not result.ok:
        return f'查询执行失败：{result.error}'

    if not result.rows:
        return '查询结果：0 行（没有查到符合条件的记录）'

    lines = [
        f'查询结果：共 {result.row_count} 行，用时 {result.elapsed_ms}ms',
        '',
        '| ' + ' | '.join(result.columns) + ' |',
        '| ' + ' | '.join('---' for _ in result.columns) + ' |',
    ]
    for row in result.rows[:100]:
        cells = []
        for col in result.columns:
            value = row.get(col)
            if value is None:
                cells.append('NULL')
            elif isinstance(value, float):
                cells.append(f'{value:g}')
            else:
                cells.append(str(value))
        lines.append('| ' + ' | '.join(cells) + ' |')

    if result.row_count > 100:
        lines.append(f'（以上只列出了前 100 行，实际共 {result.row_count} 行）')

    return '\n'.join(lines)


async def _generate_sql(
    question: str,
    history: list[dict[str, str]],
    model: str | None = None,
) -> str:
    """
    调用模型做「路由 + 生成 SQL」。

    返回值有两种可能：
      - 'NO_SQL'   —— 这个问题用知识库就能答
      - 一条 SQL    —— 需要查库
    """
    messages: list[dict[str, str]] = []
    if history:
        messages.extend(history)
    messages.append({'role': 'user', 'content': question})

    raw = await complete(
        messages,
        system=SQL_SYSTEM,
        max_tokens=1200,
        temperature=0.1,
        model=model,
    )
    return raw.strip()


async def _repair_sql(
    question: str,
    rejected_sql: str,
    reason: str,
    history: list[dict[str, str]],
    model: str | None = None,
) -> str:
    """SQL 没通过安全校验时，让模型看着错误原因重写一次。"""
    messages: list[dict[str, str]] = []
    if history:
        messages.extend(history)
    messages.append({'role': 'user', 'content': question})
    messages.append({
        'role': 'assistant',
        'content': f'我生成的 SQL 是：\n{rejected_sql}',
    })
    messages.append({
        'role': 'user',
        'content': (
            f'这个 SQL 没有通过安全校验：{reason}\n'
            '请重新输出一条合规的 SELECT 语句（只输出 SQL，不要解释）。'
        ),
    })

    return (await complete(
        messages,
        system=SQL_SYSTEM,
        max_tokens=1200,
        temperature=0.1,
        model=model,
    )).strip()


def _build_answer_messages(
    question: str,
    history: list[dict[str, str]],
    sql: str | None,
    result: QueryResult | None,
) -> list[dict[str, str]]:
    """组装最终回答阶段的 Messages。"""
    messages: list[dict[str, str]] = []
    if history:
        messages.extend(history)

    if sql and result is not None:
        context = (
            f'【用户问题】\n{question}\n\n'
            f'【已执行的 SQL】\n{sql}\n\n'
            f'【查询结果】\n{_format_result(result)}'
        )
    else:
        context = f'【用户问题】\n{question}'

    messages.append({'role': 'user', 'content': context})
    return messages


async def run(
    question: str,
    session: Session,
    model: str | None = None,
) -> AsyncIterator[AgentEvent]:
    """
    主流程。产出 AgentEvent 流。

    调用方（main.py）负责把事件编码成 SSE 发给前端。
    model 不传就用配置里的默认模型；传了则临时换模型（接口层的 model 覆盖）。
    """
    question = (question or '').strip()

    # ---- ① 领域预检 ----
    reason = scope.precheck(question)
    if reason:
        logger.info('范围拦截（%s）：%s', reason, question[:60])
        yield AgentEvent('status', {'phase': 'refused', 'text': '这个问题不在我的职责范围内'})
        yield AgentEvent('token', {'text': scope.refusal(reason)})
        yield AgentEvent('done', {'session_id': session.session_id, 'refused': True})
        return

    if not question:
        yield AgentEvent('error', {
            'message': '请输入你想了解的内容',
            'code': 'invalid_request',
            'status_code': 400,
        })
        yield AgentEvent('done', {'session_id': session.session_id})
        return

    history = session.history(settings.max_history_turns)

    # ---- ② 路由 + 生成 SQL ----
    try:
        raw = await _generate_sql(question, history, model=model)
    except LLMError as exc:
        logger.warning('模型调用失败：%s', exc)
        yield AgentEvent('error', {
            'message': exc.message,
            'code': exc.code,
            'status_code': exc.status_code,
            'detail': exc.detail,
        })
        yield AgentEvent('done', {'session_id': session.session_id})
        return

    sql: str | None = None
    result: QueryResult | None = None

    if raw.upper().startswith(NO_SQL_MARKER):
        # 知识库分支：不需要查库
        logger.info('走知识库分支：%s', question[:60])
        yield AgentEvent('status', {'phase': 'answering', 'text': '正在查阅系统知识库…'})
    else:
        # 数据分支：生成 SQL → 校验 → 执行
        yield AgentEvent('status', {'phase': 'sql', 'text': '正在理解问题并生成查询…'})

        try:
            candidate = extract_sql(raw)
            sql = validate(candidate, settings.max_rows)
        except SqlRejected as exc:
            logger.warning('SQL 安全校验未通过：%s（原始：%s）', exc, raw[:120])
            # 自纠错一次：把错误原因喂回模型
            try:
                repaired = await _repair_sql(question, raw[:500], str(exc), history, model=model)
                candidate = extract_sql(repaired)
                sql = validate(candidate, settings.max_rows)
            except (SqlRejected, LLMError) as exc2:
                logger.warning('SQL 重写后仍不合规：%s', exc2)
                yield AgentEvent('status', {'phase': 'fallback', 'text': '没能生成合适的查询，改用知识库回答'})
                sql = None

        if sql:
            yield AgentEvent('sql', {'sql': sql})
            yield AgentEvent('status', {'phase': 'querying', 'text': '正在查询数据库…'})
            result = db.run_sql(sql, settings.max_rows)
            if not result.ok:
                logger.warning('查询失败：%s', result.error)
                yield AgentEvent('status', {'phase': 'query_failed', 'text': '查询没成功，改用知识库回答'})
                result = None

    # ---- ⑤ 生成回答（流式） ----
    yield AgentEvent('status', {'phase': 'answering', 'text': '正在组织回答…'})

    messages = _build_answer_messages(question, history, sql, result)
    system = ANSWER_SYSTEM if result is not None else SCOPE_SYSTEM

    collected: list[str] = []
    try:
        async for delta in stream(
            messages,
            system=system,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            model=model,
        ):
            collected.append(delta)
            yield AgentEvent('token', {'text': delta})
    except LLMError as exc:
        logger.warning('流式回答失败：%s', exc)
        # 已经吐了一部分内容就不要再补错误提示，避免和半截回答打架
        if not collected:
            yield AgentEvent('error', {
                'message': exc.message,
                'code': exc.code,
                'status_code': exc.status_code,
                'detail': exc.detail,
            })
            yield AgentEvent('done', {'session_id': session.session_id})
            return

    answer = ''.join(collected).strip()

    # ---- 越界兜底 ----
    if scope.is_out_of_scope_answer(answer):
        answer = scope.refusal()
        yield AgentEvent('reset', {'text': answer})

    if not answer:
        answer = NO_SQL_ANSWER
        yield AgentEvent('reset', {'text': answer})

    # ---- 写回会话 ----
    session.add('user', question)
    session.add('assistant', answer)

    # ---- 附带查询结果给前端（可选，用于渲染小表格）----
    if result is not None and settings.show_sql:
        yield AgentEvent('result', result.to_dict())

    yield AgentEvent('done', {
        'session_id': session.session_id,
        'used_sql': sql is not None,
    })
