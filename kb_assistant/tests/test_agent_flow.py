"""
问答流程的集成测试（模型调用被打桩）。

【为什么打桩】
    真实调用模型要花钱、要网络、结果还不确定。
    但流程本身（路由 -> 校验 -> 查库 -> 流式作答）必须稳定可测，
    所以把 app.agent 里的 complete / stream 两个函数换掉，
    剩下���全走真实代码路径 —— 真的去查 MySQL。

运行：
    cd kb_assistant
    pytest -q
"""

from __future__ import annotations

import pytest

from app import agent
from app.sessions import Session


async def _collect(gen) -> list[agent.AgentEvent]:
    """把事件流收集成列表。"""
    return [event async for event in gen]


@pytest.fixture
def session() -> Session:
    return Session(session_id='test-session')


class TestAgentFlow:
    """主流程。"""

    @pytest.mark.asyncio
    async def test_data_question_runs_sql_and_answers(self, session, monkeypatch):
        """问一个数据问题：应该生成 SQL、查库、流式吐答案。"""

        async def fake_complete(messages, **kwargs):
            return 'SELECT class_name, COUNT(*) AS c FROM student_info s JOIN clazz c ON s.stu_class_id = c.stu_class_id WHERE s.is_del = 0 GROUP BY class_name LIMIT 10'

        async def fake_stream(messages, **kwargs):
            for piece in ['1 号班有 ', '12 ', '名学生。']:
                yield piece

        monkeypatch.setattr(agent, 'complete', fake_complete)
        monkeypatch.setattr(agent, 'stream', fake_stream)

        events = await _collect(agent.run('1 号班有多少学生', session))

        types = [e.event for e in events]
        assert 'sql' in types, '应该产出 SQL 事件'
        assert 'token' in types, '应该产出回答增量'
        assert types[-1] == 'done'

        # 回答内容被拼起来了
        answer = ''.join(e.data['text'] for e in events if e.event == 'token')
        assert '1 号班有 12 名学生' in answer

        # 会话记住了这一轮
        assert len(session.turns) == 2
        assert session.turns[0].role == 'user'

    @pytest.mark.asyncio
    async def test_out_of_scope_never_calls_model(self, session, monkeypatch):
        """跑题问题：直接拒答，一次模型都不调。"""
        called = False

        async def fake_complete(messages, **kwargs):
            nonlocal called
            called = True
            return 'SELECT 1'

        async def fake_stream(messages, **kwargs):
            nonlocal called
            called = True
            yield 'x'

        monkeypatch.setattr(agent, 'complete', fake_complete)
        monkeypatch.setattr(agent, 'stream', fake_stream)

        events = await _collect(agent.run('今天天气怎么样', session))

        assert called is False, '跑题问题不应该调用模型'
        assert events[0].event == 'status'
        assert events[0].data.get('phase') == 'refused'

        answer = ''.join(e.data['text'] for e in events if e.event == 'token')
        assert '学生管理系统' in answer

    @pytest.mark.asyncio
    async def test_knowledge_question_skips_database(self, session, monkeypatch):
        """知识库能答的问题：不查库，直接作答。"""

        async def fake_complete(messages, **kwargs):
            return 'NO_SQL'

        async def fake_stream(messages, **kwargs):
            yield '这个系统有 9 个功能模块。'

        monkeypatch.setattr(agent, 'complete', fake_complete)
        monkeypatch.setattr(agent, 'stream', fake_stream)

        events = await _collect(agent.run('这个系统有哪些功能模块', session))

        assert all(e.event != 'sql' for e in events), '不该产出 SQL 事件'
        answer = ''.join(e.data['text'] for e in events if e.event == 'token')
        assert '9 个功能模块' in answer

    @pytest.mark.asyncio
    async def test_dangerous_sql_is_blocked_and_repaired(self, session, monkeypatch):
        """
        模型第一次生成了危险 SQL（UPDATE）。

        期望：第一次被 sql_guard 拦下 -> 带着错误原因重写 -> 第二次合规 -> 正常查库。
        """
        replies = [
            "UPDATE student_info SET stu_name = 'x' WHERE stu_id = 1",
            'SELECT stu_name FROM student_info WHERE is_del = 0 LIMIT 5',
        ]
        calls = {'n': 0}

        async def fake_complete(messages, **kwargs):
            index = min(calls['n'], len(replies) - 1)
            calls['n'] += 1
            return replies[index]

        async def fake_stream(messages, **kwargs):
            yield '查到 5 名学生。'

        monkeypatch.setattr(agent, 'complete', fake_complete)
        monkeypatch.setattr(agent, 'stream', fake_stream)

        events = await _collect(agent.run('随便看看学生', session))

        sql_events = [e for e in events if e.event == 'sql']
        assert len(sql_events) == 1, '应该只产出一条通过校验的 SQL'
        assert sql_events[0].data['sql'].upper().startswith('SELECT')
        assert 'UPDATE' not in sql_events[0].data['sql'].upper()

    @pytest.mark.asyncio
    async def test_model_error_is_reported_gracefully(self, session, monkeypatch):
        """模型报错：不能崩，要给用户一条能看懂的话。"""
        from app.llm import LLMError

        async def fake_complete(messages, **kwargs):
            raise LLMError('模型服务鉴权失败：MINIMAX_API_KEY 无效或已过期')

        async def fake_stream(messages, **kwargs):
            yield ''

        monkeypatch.setattr(agent, 'complete', fake_complete)
        monkeypatch.setattr(agent, 'stream', fake_stream)

        events = await _collect(agent.run('1 号班有多少学生', session))

        errors = [e for e in events if e.event == 'error']
        assert len(errors) == 1
        assert '鉴权失败' in errors[0].data['message']
        assert events[-1].event == 'done'

    @pytest.mark.asyncio
    async def test_out_of_scope_marker_in_answer_is_replaced(self, session, monkeypatch):
        """模型自己输出了越界标记：整段换成拒答话术。"""

        async def fake_complete(messages, **kwargs):
            return 'NO_SQL'

        async def fake_stream(messages, **kwargs):
            yield '[超出范围]'

        monkeypatch.setattr(agent, 'complete', fake_complete)
        monkeypatch.setattr(agent, 'stream', fake_stream)

        events = await _collect(agent.run('随便聊聊', session))

        resets = [e for e in events if e.event == 'reset']
        assert len(resets) == 1
        assert '学生管理系统' in resets[0].data['text']

    @pytest.mark.asyncio
    async def test_history_is_carried_to_next_turn(self, session, monkeypatch):
        """第二轮问「那他们的成绩呢」，历史要带进去。"""
        seen: list[list[dict]] = []

        async def fake_complete(messages, **kwargs):
            seen.append(messages)
            return 'NO_SQL'

        async def fake_stream(messages, **kwargs):
            yield '好的。'

        monkeypatch.setattr(agent, 'complete', fake_complete)
        monkeypatch.setattr(agent, 'stream', fake_stream)

        await _collect(agent.run('1 号班有多少学生', session))
        await _collect(agent.run('那他们的成绩呢', session))

        # 第二轮的 messages 里有第一轮的问答
        second = seen[-1]
        assert len(second) >= 3
        assert second[0]['role'] == 'user'
        assert '1 号班有多少学生' in second[0]['content']
