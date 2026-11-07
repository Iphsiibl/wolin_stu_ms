"""
模型调用层 —— 对上层只暴露统一的 complete() / stream()。

【设计目标】
    agent.py 只认「给我一组消息，吐一段文本」这一件事，
    完全不需要知道底下是 Anthropic、OpenAI 兼容还是 Gemini 协议。
    换协议 = 改一个环境变量 LLM_PROTOCOL，业务代码一行不动。

【对外接口】
    complete(messages, system=None, ...)  一次性拿到完整回复
    stream(messages, system=None, ...)    流式拿回复，逐段 yield 文本增量

【协议注册表】
    anthropic -> AnthropicClient        Messages 协议（MiniMax / Anthropic 官方）
    openai    -> OpenAICompatibleClient chat/completions（OpenAI / DeepSeek / 通义千问 /
                智谱 / Kimi / Ollama(/v1) / vLLM / LM Studio）
    gemini    -> GeminiClient            generateContent（Google Gemini）

【降级】
    LLM_FALLBACK_MODELS 里配了备选模型时，主模型遇到可重试的错误
    （超时 / 限流 / 服务端 5xx / 连不上）会自动换下一个模型重试。
    鉴权失败、参数错误这种【配置问题】不降级 —— 换模型也救不回来，
    直接报错更快。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..config import SUPPORTED_PROTOCOLS, Settings, settings as global_settings
from .anthropic import AnthropicClient
from .base import LLMClient, LLMError
from .gemini import GeminiClient
from .openai import OpenAICompatibleClient

logger = logging.getLogger('kb_assistant.llm')

__all__ = [
    'LLMError',
    'LLMClient',
    'AnthropicClient',
    'OpenAICompatibleClient',
    'GeminiClient',
    'PROTOCOL_CLIENTS',
    'SUPPORTED_PROTOCOLS',
    'build_client',
    'model_chain',
    'complete',
    'stream',
]

# 协议 -> 客户端类。注册表在这里，加协议只改这一处
PROTOCOL_CLIENTS: dict[str, type[LLMClient]] = {
    'anthropic': AnthropicClient,
    'openai': OpenAICompatibleClient,
    'gemini': GeminiClient,
}


def build_client(
    settings: Settings | None = None,
    transport: object | None = None,
) -> LLMClient:
    """按协议创建客户端。协议不认识就报错，不猜。"""
    cfg = settings or global_settings
    client_cls = PROTOCOL_CLIENTS.get(cfg.protocol)
    if client_cls is None:
        raise LLMError(
            f'不支持的模型协议：{cfg.protocol}（可选：{"、".join(SUPPORTED_PROTOCOLS)}）',
            code='llm_unsupported_protocol',
            status_code=500,
        )
    return client_cls(cfg, transport=transport)


def model_chain(
    settings: Settings | None = None,
    model: str | None = None,
) -> list[str]:
    """
    要依次尝试的模型列表：主模型 + 降级模型。

    model 不为空（接口层临时指定）时用它当主模型，降级模型照样跟着。
    """
    cfg = settings or global_settings
    chain: list[str] = [(model or cfg.llm_model).strip()]
    for fallback in cfg.llm_fallback_models:
        if fallback and fallback not in chain:
            chain.append(fallback)
    return chain


async def complete(
    messages: list[dict[str, str]],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    model: str | None = None,
) -> str:
    """一次性拿到完整回复（用于生成 SQL 这种内部步骤）。"""
    client = build_client()
    chain = model_chain(model=model)
    last_error: LLMError | None = None

    for index, current in enumerate(chain):
        try:
            return await client.complete(
                messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model=current,
            )
        except LLMError as exc:
            last_error = exc
            if not exc.retryable or index == len(chain) - 1:
                raise
            logger.warning(
                '模型 %s 调用失败（%s），降级到 %s 重试',
                current, exc.code, chain[index + 1],
            )

    raise last_error or LLMError('模型调用失败', code='llm_error', status_code=502)


async def stream(
    messages: list[dict[str, str]],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    model: str | None = None,
) -> AsyncIterator[str]:
    """流式拿到回复，逐段 yield 文本增量（用于边生成边显示）。"""
    client = build_client()
    chain = model_chain(model=model)
    last_error: LLMError | None = None

    for index, current in enumerate(chain):
        emitted = False
        try:
            async for delta in client.stream(
                messages,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                model=current,
            ):
                emitted = True
                yield delta
            return
        except LLMError as exc:
            last_error = exc
            # 已经吐过内容就不降级了 —— 半截回答再接另一段只会更糟
            if emitted or not exc.retryable or index == len(chain) - 1:
                raise
            logger.warning(
                '模型 %s 流式调用失败（%s），降级到 %s 重试',
                current, exc.code, chain[index + 1],
            )

    raise last_error or LLMError('模型调用失败', code='llm_error', status_code=502)
