"""
协议适配层的单元测试。

【为什么这层必须测】
    三种协议的差异全在「请求怎么发、响应怎么拆」上。
    拼错一个字段名（system 放错位置、鉴权头写错、流式分片取错字段），
    线上表现是「模型不响应」或者「回答永远是空的」，本地很难看出来。
    所以这里用 httpx.MockTransport 把请求原样抓下来断言。

【不联网】
    全部用 MockTransport 打桩，一个真实请求都不会发出去。

运行：
    cd kb_assistant
    pytest tests/test_llm_protocols.py -q
"""

from __future__ import annotations

import json

import httpx
import pytest

from app import llm
from app.config import Settings, load_settings
from app.llm import LLMError
from app.llm.anthropic import AnthropicClient
from app.llm.gemini import GeminiClient
from app.llm.openai import OpenAICompatibleClient

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
# 配置相关的环境变量（测兼容规则时全部先清干净）
LLM_ENV_KEYS = (
    'LLM_PROTOCOL',
    'LLM_BASE_URL',
    'LLM_API_KEY',
    'LLM_MODEL',
    'LLM_TIMEOUT',
    'LLM_MAX_TOKENS',
    'LLM_TEMPERATURE',
    'LLM_EXTRA_HEADERS',
    'LLM_MODELS',
    'LLM_FALLBACK_MODELS',
    'LLM_PROVIDER',
    'MINIMAX_API_KEY',
    'MINIMAX_BASE_URL',
    'MINIMAX_MODEL',
    'MINIMAX_TIMEOUT',
    'MINIMAX_MAX_TOKENS',
    'MINIMAX_TEMPERATURE',
)


def make_settings(**overrides) -> Settings:
    """造一份测试用的 Settings —— 不走环境变量，结果确定。"""
    base = {
        'protocol': 'anthropic',
        'llm_api_key': 'test-key',
        'llm_base_url': 'https://example.test/v1',
        'llm_model': 'test-model',
        'llm_max_tokens': 512,
        'llm_temperature': 0.3,
    }
    base.update(overrides)
    return Settings(**base)


def sse(*lines: str) -> httpx.Response:
    """把几行 SSE 拼成一个流式响应。"""
    body = ''.join(f'{line}\n\n' for line in lines)
    return httpx.Response(200, text=body, headers={'Content-Type': 'text/event-stream'})


class Capture:
    """记录请求的 MockTransport 包装。"""

    def __init__(self, responder) -> None:
        self.requests: list[httpx.Request] = []
        self._responder = responder

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responder(request)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def body(self, index: int = -1) -> dict:
        return json.loads(self.requests[index].content)


# ===========================================================================
#  OpenAI 兼容协议
# ===========================================================================
class TestOpenAIProtocol:
    """OpenAI 兼容 —— 一套接 OpenAI / DeepSeek / 通义千问 / Ollama 等。"""

    async def test_request_body_and_headers(self):
        """system 必须变成一条 role=system 的消息，插在 messages 最前面。"""
        capture = Capture(lambda request: httpx.Response(
            200, json={'choices': [{'message': {'content': '1 号班有 12 人'}}]},
        ))
        client = OpenAICompatibleClient(
            make_settings(protocol='openai', llm_base_url='https://api.example.com/v1'),
            transport=httpx.MockTransport(capture),
        )

        text = await client.complete(
            [{'role': 'user', 'content': '1 号班有多少学生'}],
            system='你是一个教务数据管家',
            model='gpt-4o-mini',
        )

        assert text == '1 号班有 12 人'
        assert str(capture.last.url) == 'https://api.example.com/v1/chat/completions'
        # 鉴权走 Authorization: Bearer
        assert capture.last.headers['authorization'] == 'Bearer test-key'

        body = capture.body()
        assert body['model'] == 'gpt-4o-mini'
        assert body['messages'][0] == {'role': 'system', 'content': '你是一个教务数据管家'}
        assert body['messages'][1] == {'role': 'user', 'content': '1 号班有多少学生'}
        assert body['max_tokens'] == 512
        assert body['temperature'] == 0.3
        # 非流式请求不能带 stream
        assert 'stream' not in body

    async def test_stream_parses_delta_content(self):
        """流式：取 choices[0].delta.content，遇到 [DONE] 收尾。"""
        capture = Capture(lambda request: sse(
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":"1 号班"}}]}',
            'data: {"choices":[{"delta":{"content":"有 12 人"}}]}',
            'data: [DONE]',
        ))
        client = OpenAICompatibleClient(
            make_settings(protocol='openai'),
            transport=httpx.MockTransport(capture),
        )

        chunks = [
            chunk async for chunk in client.stream(
                [{'role': 'user', 'content': '1 号班有多少学生'}],
                system='你是教务数据管家',
            )
        ]

        assert chunks == ['1 号班', '有 12 人']
        assert capture.body()['stream'] is True
        # system 还是放在 messages 里
        assert capture.body()['messages'][0]['role'] == 'system'

    async def test_extra_headers_are_injected(self):
        """LLM_EXTRA_HEADERS 里的自定义头要真的发出去。"""
        capture = Capture(lambda request: httpx.Response(
            200, json={'choices': [{'message': {'content': '好'}}]},
        ))
        client = OpenAICompatibleClient(
            make_settings(protocol='openai', llm_extra_headers={'X-Title': 'kb-assistant'}),
            transport=httpx.MockTransport(capture),
        )

        await client.complete([{'role': 'user', 'content': 'hi'}])

        assert capture.last.headers['x-title'] == 'kb-assistant'


# ===========================================================================
#  Anthropic Messages 协议
# ===========================================================================
class TestAnthropicProtocol:
    """Anthropic Messages —— 现有实现，行为不能变。"""

    async def test_request_body_and_headers(self):
        """system 走顶层参数，鉴权走 x-api-key。"""
        capture = Capture(lambda request: httpx.Response(
            200, json={'content': [{'type': 'text', 'text': '1 号班有 12 人'}]},
        ))
        client = AnthropicClient(
            make_settings(llm_base_url='https://api.example.com/anthropic/v1'),
            transport=httpx.MockTransport(capture),
        )

        text = await client.complete(
            [{'role': 'user', 'content': '1 号班有多少学生'}],
            system='你是一个教务数据管家',
            model='MiniMax-M3.1-Flash',
        )

        assert text == '1 号班有 12 人'
        assert str(capture.last.url) == 'https://api.example.com/anthropic/v1/messages'
        assert capture.last.headers['x-api-key'] == 'test-key'
        assert capture.last.headers['anthropic-version'] == '2023-06-01'

        body = capture.body()
        assert body['model'] == 'MiniMax-M3.1-Flash'
        assert body['max_tokens'] == 512
        # system 必须是顶层参数，不能塞进 messages
        assert body['system'] == '你是一个教务数据管家'
        assert all(m['role'] != 'system' for m in body['messages'])

    async def test_stream_parses_content_block_delta(self):
        """流式：content_block_delta -> delta.text_delta -> text。"""
        capture = Capture(lambda request: sse(
            'event: message_start',
            'data: {"type":"message_start","message":{"id":"1"}}',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"1 号班"}}',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"有 12 人"}}',
            'data: {"type":"message_stop"}',
        ))
        client = AnthropicClient(
            make_settings(),
            transport=httpx.MockTransport(capture),
        )

        chunks = [
            chunk async for chunk in client.stream(
                [{'role': 'user', 'content': '1 号班有多少学生'}],
                system='你是教务数据管家',
            )
        ]

        assert chunks == ['1 号班', '有 12 人']
        assert capture.body()['stream'] is True

    async def test_ignores_non_text_deltas(self):
        """非文本分片（ping、thinking）不能被当成正文吐出来。"""
        capture = Capture(lambda request: sse(
            'data: {"type":"ping"}',
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text"}}',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"答案"}}',
        ))
        client = AnthropicClient(make_settings(), transport=httpx.MockTransport(capture))

        chunks = [
            chunk async for chunk in client.stream([{'role': 'user', 'content': 'hi'}])
        ]

        assert chunks == ['答案']


# ===========================================================================
#  Gemini generateContent 协议
# ===========================================================================
class TestGeminiProtocol:
    """Gemini —— contents / systemInstruction / 模型 id 拼在路径里。"""

    async def test_request_body_and_headers(self):
        capture = Capture(lambda request: httpx.Response(
            200, json={'candidates': [{'content': {'parts': [{'text': '1 号班有 12 人'}]}}]},
        ))
        client = GeminiClient(
            make_settings(protocol='gemini', llm_base_url='https://generativelanguage.googleapis.com/v1beta'),
            transport=httpx.MockTransport(capture),
        )

        text = await client.complete(
            [
                {'role': 'user', 'content': '1 号班有多少学生'},
                {'role': 'assistant', 'content': '你问的是 1 号班'},
            ],
            system='你是一个教务数据管家',
            model='gemini-2.0-flash',
        )

        assert text == '1 号班有 12 人'
        assert str(capture.last.url) == (
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'
        )
        assert capture.last.headers['x-goog-api-key'] == 'test-key'

        body = capture.body()
        # assistant 角色要翻成 model
        assert body['contents'][0] == {'role': 'user', 'parts': [{'text': '1 号班有多少学生'}]}
        assert body['contents'][1] == {'role': 'model', 'parts': [{'text': '你问的是 1 号班'}]}
        # system 走 systemInstruction
        assert body['systemInstruction'] == {'parts': [{'text': '你是一个教务数据管家'}]}
        assert body['generationConfig']['maxOutputTokens'] == 512
        assert body['generationConfig']['temperature'] == 0.3
        # 模型 id 在路径里，不在请求体里
        assert 'model' not in body

    async def test_stream_uses_stream_generate_content(self):
        capture = Capture(lambda request: sse(
            'data: {"candidates":[{"content":{"parts":[{"text":"1 号班"}]}}]}',
            'data: {"candidates":[{"content":{"parts":[{"text":"有 12 人"}]}}]}',
        ))
        client = GeminiClient(
            make_settings(protocol='gemini'),
            transport=httpx.MockTransport(capture),
        )

        chunks = [
            chunk async for chunk in client.stream([{'role': 'user', 'content': '1 号班有多少学生'}])
        ]

        assert chunks == ['1 号班', '有 12 人']
        assert str(capture.last.url).endswith(':streamGenerateContent?alt=sse')


# ===========================================================================
#  协议选择
# ===========================================================================
class TestProtocolSelection:
    """LLM_PROTOCOL 决定用哪套客户端。"""

    def test_build_client_picks_right_class(self):
        assert isinstance(llm.build_client(make_settings(protocol='anthropic')), AnthropicClient)
        assert isinstance(llm.build_client(make_settings(protocol='openai')), OpenAICompatibleClient)
        assert isinstance(llm.build_client(make_settings(protocol='gemini')), GeminiClient)

    def test_unknown_protocol_raises_clear_error(self):
        with pytest.raises(LLMError) as excinfo:
            llm.build_client(make_settings(protocol='llama-cpp'))
        assert excinfo.value.code == 'llm_unsupported_protocol'
        assert 'anthropic' in excinfo.value.message

    def test_default_protocol_is_anthropic(self):
        """老配置一行不改，行为必须和以前一致。"""
        assert make_settings().protocol == 'anthropic'

    def test_model_chain_order(self):
        settings = make_settings(llm_model='main', llm_fallback_models=('b', 'c'))
        assert llm.model_chain(settings) == ['main', 'b', 'c']
        # 临时指定模型时，它当主模型，降级模型照样跟着
        assert llm.model_chain(settings, model='temp') == ['temp', 'b', 'c']


# ===========================================================================
#  降级逻辑
# ===========================================================================
class TestFallback:
    """主模型挂了自动换备选模型。"""

    def _patch(self, monkeypatch, settings, transport):
        """让 llm.complete / llm.stream 用上打了桩的客户端。"""
        monkeypatch.setattr(llm, 'global_settings', settings)
        monkeypatch.setattr(
            llm,
            'build_client',
            lambda *args, **kwargs: OpenAICompatibleClient(settings, transport=transport),
        )

    async def test_falls_back_when_server_error(self, monkeypatch):
        calls: list[str] = []

        def responder(request: httpx.Request) -> httpx.Response:
            model = json.loads(request.content)['model']
            calls.append(model)
            if model == 'primary-model':
                return httpx.Response(500, json={'error': {'message': 'boom'}})
            return httpx.Response(200, json={'choices': [{'message': {'content': '备选模型的答案'}}]})

        settings = make_settings(
            protocol='openai',
            llm_model='primary-model',
            llm_fallback_models=('backup-model',),
        )
        self._patch(monkeypatch, settings, httpx.MockTransport(responder))

        text = await llm.complete([{'role': 'user', 'content': 'hi'}])

        assert text == '备选模型的答案'
        assert calls == ['primary-model', 'backup-model']

    async def test_does_not_fall_back_on_auth_error(self, monkeypatch):
        """鉴权失败是配置问题，换模型也救不回来 —— 不该白跑一次。"""
        calls: list[str] = []

        def responder(request: httpx.Request) -> httpx.Response:
            calls.append(json.loads(request.content)['model'])
            return httpx.Response(401, json={'error': {'message': 'invalid api key'}})

        settings = make_settings(
            protocol='openai',
            llm_model='primary-model',
            llm_fallback_models=('backup-model',),
        )
        self._patch(monkeypatch, settings, httpx.MockTransport(responder))

        with pytest.raises(LLMError) as excinfo:
            await llm.complete([{'role': 'user', 'content': 'hi'}])

        assert excinfo.value.code == 'llm_unauthorized'
        assert excinfo.value.status_code == 401
        assert calls == ['primary-model']

    async def test_stream_falls_back_before_first_chunk(self, monkeypatch):
        """还没吐过内容时可以降级重来。"""
        calls: list[str] = []

        def responder(request: httpx.Request) -> httpx.Response:
            model = json.loads(request.content)['model']
            calls.append(model)
            if model == 'primary-model':
                return httpx.Response(503, json={'error': 'unavailable'})
            return sse('data: {"choices":[{"delta":{"content":"备选模型的答案"}}]}')

        settings = make_settings(
            protocol='openai',
            llm_model='primary-model',
            llm_fallback_models=('backup-model',),
        )
        self._patch(monkeypatch, settings, httpx.MockTransport(responder))

        chunks = [chunk async for chunk in llm.stream([{'role': 'user', 'content': 'hi'}])]

        assert chunks == ['备选模型的答案']
        assert calls == ['primary-model', 'backup-model']

    async def test_stream_does_not_fall_back_after_first_chunk(self, monkeypatch):
        """已经吐了一半再降级只会更乱 —— 直接把错误抛出去。"""
        calls: list[str] = []

        def responder(request: httpx.Request) -> httpx.Response:
            calls.append(json.loads(request.content)['model'])

            async def broken_stream():
                chunk = 'data: {"choices":[{"delta":{"content":"说到一半"}}]}\n\n'
                yield chunk.encode('utf-8')
                raise httpx.ReadTimeout('连接中途断了', request=request)

            return httpx.Response(200, content=broken_stream())

        settings = make_settings(
            protocol='openai',
            llm_model='primary-model',
            llm_fallback_models=('backup-model',),
        )
        self._patch(monkeypatch, settings, httpx.MockTransport(responder))

        chunks = []
        with pytest.raises(LLMError):
            async for chunk in llm.stream([{'role': 'user', 'content': 'hi'}]):
                chunks.append(chunk)

        # 半截内容确实吐出来了，而且没有再试备选模型
        assert chunks == ['说到一半']
        assert calls == ['primary-model']


# ===========================================================================
#  错误映射
# ===========================================================================
class TestErrorMapping:
    """网关的错误要翻成【能给人看的中文】+ 语义正确的状态码。"""

    @pytest.mark.parametrize(
        ('status', 'expected_code', 'expected_status'),
        [
            (401, 'llm_unauthorized', 401),
            (403, 'llm_forbidden', 403),
            (404, 'llm_model_not_found', 404),
            (429, 'llm_rate_limited', 429),
            (500, 'llm_unavailable', 502),
            (503, 'llm_unavailable', 502),
        ],
    )
    async def test_status_maps_to_code(self, status, expected_code, expected_status):
        client = AnthropicClient(
            make_settings(),
            transport=httpx.MockTransport(lambda request: httpx.Response(status, json={'error': 'x'})),
        )

        with pytest.raises(LLMError) as excinfo:
            await client.complete([{'role': 'user', 'content': 'hi'}])

        assert excinfo.value.code == expected_code
        assert excinfo.value.status_code == expected_status
        # 中文说明
        assert excinfo.value.message
        assert excinfo.value.message != expected_code

    async def test_timeout_maps_to_504(self):
        def responder(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout('模拟超时', request=request)

        client = AnthropicClient(make_settings(), transport=httpx.MockTransport(responder))

        with pytest.raises(LLMError) as excinfo:
            await client.complete([{'role': 'user', 'content': 'hi'}])

        assert excinfo.value.code == 'llm_timeout'
        assert excinfo.value.status_code == 504
        assert excinfo.value.retryable is True

    async def test_missing_api_key_raises_clear_error(self):
        client = AnthropicClient(make_settings(llm_api_key=''))

        with pytest.raises(LLMError) as excinfo:
            await client.complete([{'role': 'user', 'content': 'hi'}])

        assert excinfo.value.code == 'llm_not_configured'
        assert 'LLM_API_KEY' in excinfo.value.message

    async def test_error_message_never_contains_api_key(self):
        """密钥绝不能出现在异常信息里。"""
        client = AnthropicClient(
            make_settings(llm_api_key='super-secret-key'),
            transport=httpx.MockTransport(lambda request: httpx.Response(500, text='boom')),
        )

        with pytest.raises(LLMError) as excinfo:
            await client.complete([{'role': 'user', 'content': 'hi'}])

        assert 'super-secret-key' not in str(excinfo.value)
        assert 'super-secret-key' not in excinfo.value.detail


# ===========================================================================
#  配置兼容
# ===========================================================================
class TestConfigCompatibility:
    """老的 MINIMAX_* 配置一行不改也得能用。"""

    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)

    def test_legacy_minimax_env_still_works(self, monkeypatch):
        """只配旧的 MINIMAX_* —— 新的 LLM_* 全部走回退。"""
        monkeypatch.setenv('MINIMAX_API_KEY', 'legacy-key')
        monkeypatch.setenv('MINIMAX_BASE_URL', 'https://legacy.test/anthropic/v1')
        monkeypatch.setenv('MINIMAX_MODEL', 'legacy-model')
        monkeypatch.setenv('MINIMAX_TIMEOUT', '42')
        monkeypatch.setenv('MINIMAX_MAX_TOKENS', '1234')
        monkeypatch.setenv('MINIMAX_TEMPERATURE', '0.7')

        settings = load_settings()

        assert settings.protocol == 'anthropic'
        assert settings.llm_api_key == 'legacy-key'
        assert settings.llm_base_url == 'https://legacy.test/anthropic/v1'
        assert settings.llm_model == 'legacy-model'
        assert settings.llm_timeout == 42
        assert settings.llm_max_tokens == 1234
        assert settings.llm_temperature == 0.7
        # 来源要能看出来
        assert settings.config_sources['api_key'] == 'MINIMAX_API_KEY'
        assert settings.config_sources['model'] == 'MINIMAX_MODEL'

    def test_new_llm_env_wins_over_legacy(self, monkeypatch):
        """新旧都配了，新的优先。"""
        monkeypatch.setenv('LLM_API_KEY', 'new-key')
        monkeypatch.setenv('MINIMAX_API_KEY', 'legacy-key')
        monkeypatch.setenv('LLM_MODEL', 'new-model')
        monkeypatch.setenv('MINIMAX_MODEL', 'legacy-model')

        settings = load_settings()

        assert settings.llm_api_key == 'new-key'
        assert settings.llm_model == 'new-model'
        assert settings.config_sources['api_key'] == 'LLM_API_KEY'

    def test_protocol_switch_keeps_legacy_model_but_warns(self, monkeypatch):
        """换协议了但模型还是旧配置 —— 要提醒一句。"""
        monkeypatch.setenv('LLM_PROTOCOL', 'openai')
        monkeypatch.setenv('MINIMAX_MODEL', 'MiniMax-M3.1-Flash')

        settings = load_settings()

        assert settings.protocol == 'openai'
        assert settings.llm_model == 'MiniMax-M3.1-Flash'
        assert any('LLM_MODEL' in warning for warning in settings.warnings)

    def test_unknown_protocol_is_reported(self, monkeypatch):
        monkeypatch.setenv('LLM_PROTOCOL', 'llama-cpp')

        settings = load_settings()

        assert 'LLM_PROTOCOL' in settings.missing()
        assert any('llama-cpp' in warning for warning in settings.warnings)

    def test_extra_headers_parsed(self, monkeypatch):
        monkeypatch.setenv('LLM_EXTRA_HEADERS', '{"X-Title": "kb-assistant"}')

        settings = load_settings()

        assert settings.llm_extra_headers == {'X-Title': 'kb-assistant'}

    def test_invalid_extra_headers_do_not_break_startup(self, monkeypatch):
        """格式写错了不能让服务起不来 —— 忽略掉 + 记一条警告。"""
        monkeypatch.setenv('LLM_EXTRA_HEADERS', 'not-json')

        settings = load_settings()

        assert settings.llm_extra_headers == {}
        assert any('LLM_EXTRA_HEADERS' in warning for warning in settings.warnings)

    def test_models_and_fallbacks_parsed(self, monkeypatch):
        monkeypatch.setenv('LLM_MODEL', 'main-model')
        monkeypatch.setenv('LLM_MODELS', 'main-model=主力模型,other-model')
        monkeypatch.setenv('LLM_FALLBACK_MODELS', 'backup-model,another-model=备用')

        settings = load_settings()

        # 默认模型永远排第一
        assert list(settings.llm_models)[0] == 'main-model'
        assert settings.llm_models['main-model'] == '主力模型'
        assert settings.llm_models['other-model'] == 'Other Model'
        assert settings.llm_fallback_models == ('backup-model', 'another-model')

    def test_missing_reports_llm_api_key(self):
        settings = load_settings()

        assert 'LLM_API_KEY' in settings.missing()

    def test_health_never_leaks_key(self, monkeypatch):
        monkeypatch.setenv('LLM_API_KEY', 'super-secret-key')

        settings = load_settings()
        health = settings.health()

        assert health['api_key_configured'] is True
        assert 'super-secret-key' not in json.dumps(health, ensure_ascii=False)
