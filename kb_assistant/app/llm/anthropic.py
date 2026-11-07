"""
Anthropic Messages 协议。

【协议要点】
    地址    POST {base}/messages
    鉴权    x-api-key: {API Key}      + anthropic-version: 2023-06-01
    请求体  system 是【顶层参数】，不是 role=system 的消息
    非流式  content[].text（type == 'text' 的块）
    流式    data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}

【谁在用这套】
    MiniMax 开放平台（api.minimax.chat/anthropic/v1）、
    Anthropic 官方（api.anthropic.com/v1）、
    以及各种号称「Anthropic 兼容」的网关。

【和 OpenAI 协议最容易踩的坑】
    system 的位置。OpenAI 是 messages 里插一条 role=system，
    这里必须放顶层 —— 放进 messages 里网关会直接报 400。
"""

from __future__ import annotations

from typing import Any

from .base import LLMClient, LLMError


class AnthropicClient(LLMClient):
    """Anthropic Messages 协议客户端（现有实现，行为保持不变）。"""

    protocol = 'anthropic'
    display_name = 'Anthropic Messages 协议'

    def endpoint(self, model: str) -> str:
        """Messages 接口地址。baseURL 末尾有没有 / 都能正确拼接。"""
        return f'{self.settings.llm_base_url.rstrip("/")}/messages'

    def auth_headers(self) -> dict[str, str]:
        if not self.settings.llm_api_key:
            raise LLMError(
                '模型服务未配置：请在 .env 中填写 LLM_API_KEY（旧配置 MINIMAX_API_KEY 也认）',
                code='llm_not_configured',
                status_code=500,
            )
        return {
            'x-api-key': self.settings.llm_api_key,
            'anthropic-version': '2023-06-01',
        }

    def build_payload(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int | None,
        temperature: float | None,
        stream: bool,
        model: str,
    ) -> dict[str, Any]:
        """组装请求体。system 走顶层参数（Messages 协议的要求）。"""
        body: dict[str, Any] = {
            'model': model,
            'max_tokens': max_tokens or self.settings.llm_max_tokens,
            'messages': messages,
        }
        if system:
            body['system'] = system
        if temperature is not None:
            body['temperature'] = temperature
        if stream:
            body['stream'] = True
        return body

    def parse_text(self, data: dict[str, Any]) -> str:
        """正文在 content 数组里，type == 'text' 的块才是正文。"""
        return ''.join(
            block.get('text', '')
            for block in data.get('content', [])
            if isinstance(block, dict) and block.get('type') == 'text'
        )

    def parse_delta(self, data: dict[str, Any]) -> str:
        """流式分片：content_block_delta -> delta.text_delta -> text。"""
        if data.get('type') != 'content_block_delta':
            return ''
        delta = data.get('delta') or {}
        if not isinstance(delta, dict) or delta.get('type') != 'text_delta':
            return ''
        return delta.get('text') or ''
