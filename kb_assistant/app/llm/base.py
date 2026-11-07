"""
模型客户端的公共基类 —— 协议差异只体现在几个钩子方法里。

【为什么要抽基类】
    三种协议（Anthropic / OpenAI 兼容 / Gemini）的差异只有五件事：
      1. 请求地址怎么拼；
      2. 请求头怎么带鉴权；
      3. 请求体怎么装（system 放顶层还是当一条 system 消息）；
      4. 非流式响应里正文在哪个字段；
      5. 流式分片里文本增量在哪个字段。
    其余的（发请求、判状态码、解析 SSE 行、把错误翻成人话）完全一样，
    所以这些放在基类里，子类只写上面五件事。

【对上层（agent.py）的承诺】
    只要实现 complete() 和 stream()，上层就完全不需要知道底下是哪套协议。
    换协议 = 改一个环境变量 LLM_PROTOCOL，代码一行不动。
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..config import Settings

logger = logging.getLogger('kb_assistant.llm')


class LLMError(RuntimeError):
    """
    调用模型失败。

    message 是可以直接展示给用户的中文说明；
    code / status_code 给上层做结构化错误响应用；
    retryable 决定要不要触发降级模型。
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = 'llm_error',
        status_code: int = 502,
        detail: str = '',
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        """转成给前端看的结构化错误（不含任何密钥）。"""
        return {'code': self.code, 'message': self.message, 'detail': self.detail}

    def __str__(self) -> str:
        return self.message


def _extract_error_detail(text: str) -> str:
    """从错误响应体里挖出最有用的那一行（网关的错误格式五花八门）。"""
    raw = (text or '').strip()
    if not raw:
        return ''
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:400]
    if isinstance(data, dict):
        err = data.get('error')
        if isinstance(err, dict):
            message = err.get('message') or err.get('status') or ''
            if message:
                return str(message)[:400]
        if isinstance(err, str):
            return err[:400]
        for key in ('message', 'detail', 'msg'):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value[:400]
    return raw[:400]


class LLMClient(ABC):
    """
    模型客户端基类。

    子类必须实现 5 个钩子（endpoint / auth_headers / build_payload /
    parse_text / parse_delta），其余逻辑全部共用。
    """

    #: 协议标识，和 LLM_PROTOCOL 的取值一一对应
    protocol: str = ''
    #: 协议的中文说明，用于 /health、/capabilities 自描述
    display_name: str = ''

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        # transport 只在测试里用（httpx.MockTransport），线上是 None
        self._transport = transport

    # -------------------------------------------------------------------------
    # 子类要实现的钩子
    # -------------------------------------------------------------------------
    @abstractmethod
    def endpoint(self, model: str) -> str:
        """非流式请求的完整地址。"""

    @abstractmethod
    def auth_headers(self) -> dict[str, str]:
        """带鉴权的请求头。"""

    @abstractmethod
    def build_payload(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int | None,
        temperature: float | None,
        stream: bool,
        model: str,
    ) -> dict[str, Any]:
        """组装请求体。"""

    @abstractmethod
    def parse_text(self, data: dict[str, Any]) -> str:
        """从非流式响应里取出正文。"""

    @abstractmethod
    def parse_delta(self, data: dict[str, Any]) -> str:
        """从流式分片里取出文本增量（取不到就返回空串）。"""

    # -------------------------------------------------------------------------
    # 可以按需覆盖的钩子
    # -------------------------------------------------------------------------
    def stream_endpoint(self, model: str) -> str:
        """流式请求的完整地址。默认和非流式一样。"""
        return self.endpoint(model)

    # -------------------------------------------------------------------------
    # 基类共用的实现
    # -------------------------------------------------------------------------
    def resolve_model(self, model: str | None) -> str:
        """没指定模型就用配置里的默认模型。"""
        return (model or self.settings.llm_model).strip()

    def resolve_temperature(self, temperature: float | None) -> float:
        """没指定温度就用配置里的默认温度（LLM_TEMPERATURE / MINIMAX_TEMPERATURE）。"""
        if temperature is not None:
            return temperature
        return self.settings.llm_temperature

    def headers(self) -> dict[str, str]:
        """完整请求头：内容类型 + 鉴权 + LLM_EXTRA_HEADERS 自定义头。"""
        headers = {'Content-Type': 'application/json'}
        headers.update(self.auth_headers())
        # 自定义头放最后：允许覆盖 Content-Type 以外的任何头
        headers.update(self.settings.llm_extra_headers)
        return headers

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.settings.llm_timeout, transport=self._transport)

    def raise_for_status(self, status: int, text: str, model: str | None = None) -> None:
        """
        把网关的错误翻译成人话 + 结构化错误码。

        状态码语义：
            401/403 -> 鉴权失败   404 -> 模型不存在
            429     -> 限流       504 -> 超时      5xx -> 上游挂了
        """
        detail = _extract_error_detail(text)
        model_name = model or self.settings.llm_model

        if status in (401, 403):
            raise LLMError(
                '模型服务鉴权失败：API Key 无效、已过期，或没有该模型的权限'
                '（请检查 .env 里的 LLM_API_KEY，旧配置 MINIMAX_API_KEY 也认）',
                code='llm_unauthorized' if status == 401 else 'llm_forbidden',
                status_code=401 if status == 401 else 403,
                detail=detail,
            )
        if status == 404:
            raise LLMError(
                f'模型 {model_name} 不存在，或当前账号无权访问这个模型',
                code='llm_model_not_found',
                status_code=404,
                detail=detail,
            )
        if status == 429:
            raise LLMError(
                '模型服务限流了，请稍后再试',
                code='llm_rate_limited',
                status_code=429,
                detail=detail,
                retryable=True,
            )
        if status >= 500:
            raise LLMError(
                '模型服务暂时不可用，请稍后再试',
                code='llm_unavailable',
                status_code=502,
                detail=detail,
                retryable=True,
            )
        raise LLMError(
            f'模型服务返回异常（HTTP {status}）：{detail}',
            code='llm_error',
            status_code=502,
            detail=detail,
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        """一次性拿到完整回复（用于生成 SQL 这种内部步骤）。"""
        current_model = self.resolve_model(model)
        url = self.endpoint(current_model)
        payload = self.build_payload(
            messages, system, max_tokens, self.resolve_temperature(temperature), False, current_model,
        )
        headers = self.headers()

        async with self._new_client() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise LLMError(
                    '模型服务响应超时，请稍后再试',
                    code='llm_timeout',
                    status_code=504,
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(
                    f'无法连接模型服务：{exc}',
                    code='llm_unreachable',
                    status_code=502,
                    retryable=True,
                ) from exc

        if resp.status_code != 200:
            self.raise_for_status(resp.status_code, resp.text, current_model)

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMError(
                '模型服务返回了无法解析的内容',
                code='llm_bad_response',
                status_code=502,
            ) from exc

        return self.parse_text(data).strip()

    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """流式拿到回复，逐段 yield 文本增量（用于边生成边显示）。"""
        current_model = self.resolve_model(model)
        url = self.stream_endpoint(current_model)
        payload = self.build_payload(
            messages, system, max_tokens, self.resolve_temperature(temperature), True, current_model,
        )
        headers = self.headers()

        async with self._new_client() as client:
            try:
                async with client.stream('POST', url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        self.raise_for_status(resp.status_code, resp.text, current_model)

                    async for line in resp.aiter_lines():
                        raw = self._sse_payload(line)
                        if raw is None:
                            # 空行 / 注释行 / 非 data 行 —— 跳过
                            continue
                        if raw == '[DONE]':
                            # OpenAI 协议用 [DONE] 表示流结束
                            break
                        text = self._parse_sse_payload(raw)
                        if text:
                            yield text
            except httpx.TimeoutException as exc:
                raise LLMError(
                    '模型服务响应超时，请稍后再试',
                    code='llm_timeout',
                    status_code=504,
                    retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(
                    f'无法连接模型服务：{exc}',
                    code='llm_unreachable',
                    status_code=502,
                    retryable=True,
                ) from exc

    def _sse_payload(self, line: str) -> str | None:
        """
        从一行 SSE 里取出 data 部分。

        返回 None 表示「这行不用管」（空行、注释心跳、event: 行）。
        """
        line = (line or '').strip()
        if not line or line.startswith(':'):
            return None
        if not line.startswith('data:'):
            return None
        return line[5:].strip()

    def _parse_sse_payload(self, raw: str) -> str:
        """
        解析一行 SSE 的 data 部分，取出文本增量。

        三种协议都用 `data: {...}` 的形式传分片，所以这一段是共用的；
        差异只在 JSON 里面字段的位置 —— 那是 parse_delta() 的事。
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return ''
        if not isinstance(data, dict):
            return ''
        return self.parse_delta(data)
