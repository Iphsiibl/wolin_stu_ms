"""
OpenAI 兼容协议 —— 一套打天下。

【协议要点】
    地址    POST {base}/chat/completions
    鉴权    Authorization: Bearer {API Key}
    请求体  system 作为一条 role=system 的消息【插在最前面】
    非流式  choices[0].message.content
    流式    data: {"choices":[{"delta":{"content":"..."}}]}，结尾 data: [DONE]

【谁在用这套】
    OpenAI、DeepSeek、通义千问（DashScope 的 compatible-mode）、
    智谱 GLM、Kimi（Moonshot）、Ollama(/v1)、vLLM、LM Studio、
    以及各种「OpenAI 兼容」网关 —— 它们都提供 /chat/completions。

    换句话说：只要 base_url 换一下，同一份代码就能接上面所有家。

【和 Anthropic 协议最容易踩的坑】
    system 的位置。这里必须放进 messages 里当一条 role=system 的消息，
    放顶层网关不认。
"""

from __future__ import annotations

from typing import Any

from .base import LLMClient, LLMError


class OpenAICompatibleClient(LLMClient):
    """OpenAI 兼容协议客户端（chat/completions）。"""

    protocol = 'openai'
    display_name = 'OpenAI 兼容协议'

    def endpoint(self, model: str) -> str:
        """chat/completions 地址。baseURL 末尾有没有 / 都能正确拼接。"""
        return f'{self.settings.llm_base_url.rstrip("/")}/chat/completions'

    def auth_headers(self) -> dict[str, str]:
        if not self.settings.llm_api_key:
            raise LLMError(
                '模型服务未配置：请在 .env 中填写 LLM_API_KEY（旧配置 MINIMAX_API_KEY 也认）',
                code='llm_not_configured',
                status_code=500,
            )
        return {'Authorization': f'Bearer {self.settings.llm_api_key}'}

    def build_payload(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int | None,
        temperature: float | None,
        stream: bool,
        model: str,
    ) -> dict[str, Any]:
        """组装请求体。system 变成一条 role=system 的消息，插在最前面。"""
        payload_messages: list[dict[str, str]] = []
        if system:
            payload_messages.append({'role': 'system', 'content': system})
        payload_messages.extend(messages)

        body: dict[str, Any] = {
            'model': model,
            'messages': payload_messages,
            'max_tokens': max_tokens or self.settings.llm_max_tokens,
        }
        if temperature is not None:
            body['temperature'] = temperature
        if stream:
            body['stream'] = True
        return body

    def parse_text(self, data: dict[str, Any]) -> str:
        """正文在 choices[0].message.content。"""
        choices = data.get('choices') or []
        if not choices:
            return ''
        message = choices[0].get('message') or {}
        content = message.get('content')
        # 少数网关把 content 拆成 [{'type': 'text', 'text': '...'}] 数组
        if isinstance(content, list):
            return ''.join(
                part.get('text', '')
                for part in content
                if isinstance(part, dict)
            )
        return content or ''

    def parse_delta(self, data: dict[str, Any]) -> str:
        """流式分片：choices[0].delta.content。"""
        choices = data.get('choices') or []
        if not choices:
            return ''
        delta = choices[0].get('delta') or {}
        if not isinstance(delta, dict):
            return ''
        return delta.get('content') or ''
