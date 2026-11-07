"""
HTTP 接口的测试。

【重点验证两件事】
    1. 【向后兼容】前端在用的 /kb/chat、/kb/health、/kb/session/... 一个都不能坏；
    2. 【自描述】新增的 /models、/capabilities 要说清楚服务能干什么。

【不打桩数据库】
    /health 会真的 ping 一下数据库（这里把它打桩掉，
    免得接口测试受本机 MySQL 状态影响）。

运行：
    cd kb_assistant
    pytest tests/test_api_endpoints.py -q
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.main import app


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """一个不依赖 MySQL 的测试客户端。"""
    monkeypatch.setattr('app.main.db.ping', lambda: True)
    return TestClient(app)


@pytest.fixture
def fake_run(monkeypatch):
    """把 agent.run 换掉：只产出固定事件，不调模型。"""
    seen: dict = {}

    async def _fake_run(question, session, model=None):
        seen['question'] = question
        seen['model'] = model
        yield agent.AgentEvent('status', {'phase': 'answering', 'text': '正在组织回答…'})
        yield agent.AgentEvent('token', {'text': '1 号班有 12 人。'})
        yield agent.AgentEvent('done', {'session_id': session.session_id})

    monkeypatch.setattr('app.main.run', _fake_run)
    return seen


# ===========================================================================
#  健康检查
# ===========================================================================
class TestHealth:
    """健康检查要能看出「配没配」，但绝不能把密钥抖出来。"""

    def test_health_reports_protocol_and_model(self, client):
        resp = client.get('/health')

        assert resp.status_code == 200
        body = resp.json()
        assert body['protocol'] == 'anthropic'
        assert body['model']
        assert body['base_url']
        assert body['api_key_configured'] is True
        assert body['supported_protocols'] == ['anthropic', 'openai', 'gemini']

    def test_kb_health_alias_still_works(self, client):
        """前端 /kb/health 走的就是这个别名。"""
        resp = client.get('/kb/health')

        assert resp.status_code == 200
        assert resp.json()['status'] == 'ok'

    def test_health_never_leaks_api_key(self, client):
        from app.config import settings

        resp = client.get('/health')

        assert settings.llm_api_key
        assert settings.llm_api_key not in resp.text
        assert 'api_key' not in resp.json() or resp.json()['api_key_configured'] is True


# ===========================================================================
#  模型列表
# ===========================================================================
class TestModels:
    """GET /models —— 从配置读，不去调远端。"""

    def test_models_shape(self, client):
        resp = client.get('/models')

        assert resp.status_code == 200
        body = resp.json()
        assert body['models'], '至少要有一个模型'
        for item in body['models']:
            assert 'id' in item
            assert 'provider' in item
            assert 'display_name' in item

    def test_default_model_is_marked(self, client):
        from app.config import settings

        body = client.get('/models').json()

        defaults = [item for item in body['models'] if item['default']]
        assert len(defaults) == 1
        assert defaults[0]['id'] == settings.llm_model

    def test_kb_models_alias(self, client):
        assert client.get('/kb/models').status_code == 200


# ===========================================================================
#  能力清单
# ===========================================================================
class TestCapabilities:
    """GET /capabilities —— 让人一眼看懂能干什么。"""

    def test_capabilities_lists_tables_and_readonly(self, client):
        resp = client.get('/capabilities')

        assert resp.status_code == 200
        body = resp.json()
        assert body['read_only'] is True
        assert body['assistant']['name'] == '小管家'

        table_names = {table['name'] for table in body['tables']}
        assert 'student_info' in table_names
        assert 'scores' in table_names
        assert 'employment' in table_names

    def test_capabilities_has_example_questions(self, client):
        body = client.get('/capabilities').json()

        assert body['example_questions']
        assert body['capabilities']
        assert body['limits']['max_rows'] > 0

    def test_kb_capabilities_alias(self, client):
        assert client.get('/kb/capabilities').status_code == 200


# ===========================================================================
#  会话
# ===========================================================================
class TestSessions:
    """GET /sessions、DELETE /sessions/{id}。"""

    def test_list_sessions(self, client):
        resp = client.get('/sessions')

        assert resp.status_code == 200
        body = resp.json()
        assert 'sessions' in body
        assert body['count'] == len(body['sessions'])

    def test_delete_unknown_session(self, client):
        resp = client.delete('/sessions/不存在的会话')

        assert resp.status_code == 200
        assert resp.json()['ok'] is False


# ===========================================================================
#  问答接口（向后兼容）
# ===========================================================================
class TestChatCompatibility:
    """前端在用的路径和响应结构不能变。"""

    def test_kb_chat_stream_still_works(self, client, fake_run):
        resp = client.post('/kb/chat', json={'question': '1 号班有多少学生'})

        assert resp.status_code == 200
        assert resp.headers['content-type'].startswith('text/event-stream')
        assert 'event: token' in resp.text
        assert '1 号班有 12 人' in resp.text
        assert 'event: done' in resp.text

    def test_chat_alias(self, client, fake_run):
        resp = client.post('/chat', json={'question': '1 号班有多少学生'})

        assert resp.status_code == 200
        assert 'event: done' in resp.text

    def test_model_override_is_forwarded(self, client, fake_run):
        client.post('/chat', json={'question': '你好', 'model': 'deepseek-chat'})

        assert fake_run['model'] == 'deepseek-chat'

    def test_model_is_optional(self, client, fake_run):
        client.post('/chat', json={'question': '你好'})

        assert fake_run['model'] is None

    def test_chat_sync_response_shape(self, client, fake_run):
        resp = client.post('/kb/chat/sync', json={'question': '1 号班有多少学生'})

        assert resp.status_code == 200
        body = resp.json()
        # 前端 kb.ts 依赖这几个字段
        for field in ('session_id', 'answer', 'sql', 'result', 'used_sql', 'refused'):
            assert field in body
        assert body['answer'] == '1 号班有 12 人。'

    def test_empty_question_returns_400(self, client):
        """空问题是客户端的错 —— 状态码要语义正确。"""
        resp = client.post('/kb/chat/sync', json={'question': '   '})

        assert resp.status_code == 400
        body = resp.json()
        assert body['code'] == 'invalid_request'
        assert body['message']


# ===========================================================================
#  统一错误响应
# ===========================================================================
class TestErrorResponses:
    """所有错误都是同一个结构：{code, message, detail}。"""

    def test_validation_error_is_structured(self, client):
        resp = client.post('/kb/chat/sync', json={'wrong_field': 'x'})

        assert resp.status_code == 422
        body = resp.json()
        assert body['code'] == 'invalid_request'
        assert body['message']
        assert body['detail']

    def test_unknown_route_is_structured(self, client):
        resp = client.get('/不存在的接口')

        assert resp.status_code == 404
        body = resp.json()
        assert body['code'] == 'http_404'
        assert body['message']

    def test_error_body_has_no_key(self, client):
        from app.config import settings

        resp = client.post('/kb/chat/sync', json={'wrong_field': 'x'})

        assert settings.llm_api_key not in resp.text
