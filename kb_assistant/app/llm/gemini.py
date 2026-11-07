"""
Google Gemini —— Generative Language API 的 generateContent。

【协议要点】
    地址    POST {base}/models/{model}:generateContent
            流式用 POST {base}/models/{model}:streamGenerateContent?alt=sse
    鉴权    x-goog-api-key: {API Key}
    请求体  contents[].parts[].text        （assistant 角色要翻成 model）
            systemInstruction.parts[].text （system 放这里）
            generationConfig.maxOutputTokens / temperature
    非流式  candidates[0].content.parts[].text
    流式    data: {"candidates":[{"content":{"parts":[{"text":"..."}]}}]}

【和另两套协议的差别】
    1. 角色名：assistant -> model；
    2. system 不是消息也不是顶层参数，而是 systemInstruction；
    3. 模型 id 拼在 URL 路径里，不在请求体里。

【可用性】
    这套实现是完整可用的（不只是接口预留）。
    但 Gemini 对「systemInstruction 必须是纯文本、消息必须严格 user/model 交替」
    比另两套更严格，历史上把多轮历史原样塞过去偶尔会被拒。
    真遇到这种情况，优先换成 openai 协议接 Gemini 的 OpenAI 兼容端点。
"""

from __future__ import annotations

from typing import Any

from .base import LLMClient, LLMError


class GeminiClient(LLMClient):
    """Gemini generateContent 协议客户端。"""

    protocol = 'gemini'
    display_name = 'Gemini generateContent 协议'

    def endpoint(self, model: str) -> str:
        """generateContent 地址。模型 id 拼在路径里。"""
        return f'{self.settings.llm_base_url.rstrip("/")}/models/{self._model_id(model)}:generateContent'

    def stream_endpoint(self, model: str) -> str:
        """流式地址。加 alt=sse 才会吐 SSE 帧（否则是一大坨 JSON 数组）。"""
        base = f'{self.settings.llm_base_url.rstrip("/")}/models/{self._model_id(model)}'
        return f'{base}:streamGenerateContent?alt=sse'

    def _model_id(self, model: str) -> str:
        """模型 id 去掉 models/ 前缀（用户可能写全了）。"""
        model_id = model.strip()
        if model_id.startswith('models/'):
            model_id = model_id[len('models/'):]
        return model_id

    def auth_headers(self) -> dict[str, str]:
        if not self.settings.llm_api_key:
            raise LLMError(
                '模型服务未配置：请在 .env 中填写 LLM_API_KEY（旧配置 MINIMAX_API_KEY 也认）',
                code='llm_not_configured',
                status_code=500,
            )
        return {'x-goog-api-key': self.settings.llm_api_key}

    def build_payload(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int | None,
        temperature: float | None,
        stream: bool,
        model: str,
    ) -> dict[str, Any]:
        """组装请求体。system 走 systemInstruction，assistant 角色翻成 model。"""
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = message.get('role', 'user')
            gemini_role = 'model' if role == 'assistant' else 'user'
            contents.append({
                'role': gemini_role,
                'parts': [{'text': message.get('content', '')}],
            })

        body: dict[str, Any] = {'contents': contents}

        if system:
            body['systemInstruction'] = {'parts': [{'text': system}]}

        generation_config: dict[str, Any] = {}
        if max_tokens or self.settings.llm_max_tokens:
            generation_config['maxOutputTokens'] = max_tokens or self.settings.llm_max_tokens
        if temperature is not None:
            generation_config['temperature'] = temperature
        if generation_config:
            body['generationConfig'] = generation_config

        return body

    def parse_text(self, data: dict[str, Any]) -> str:
        """正文在 candidates[0].content.parts[].text。"""
        candidates = data.get('candidates') or []
        if not candidates:
            return ''
        content = candidates[0].get('content') or {}
        parts = content.get('parts') or []
        return ''.join(
            part.get('text', '')
            for part in parts
            if isinstance(part, dict)
        )

    def parse_delta(self, data: dict[str, Any]) -> str:
        """流式分片结构和非流式一样，直接复用。"""
        return self.parse_text(data)
