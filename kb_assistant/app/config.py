"""
配置中心 —— 本模块是整个知识库小助手【唯一】读取敏感信息的地方。

【设计原则】
    1. 模型 token、数据库密码，一律【不写死在代码里】，只从 .env 读。
    2. 项目根目录的 .env 是主配置源（数据库连接信息已经在那里了），
       kb_assistant/.env 作为【本地覆盖】文件存在时优先级更高。
    3. 启动时做一次「体检」：关键配置缺失就给出明确的中文提示，
       而不是等到用户问了一句才报一个看不懂的 500。

【模型配置：新的 LLM_* 和旧的 MINIMAX_* 共存】
    早期只对接 MiniMax，配置项全是 MINIMAX_* 前缀。
    现在支持三种协议（anthropic / openai / gemini），配置项统一成 LLM_* 前缀。

    【向后兼容规则 —— 老的 .env 一行不改也能继续跑】
        每个模型配置都按下面三步取：
            LLM_xxx（新）  ->  MINIMAX_xxx（旧）  ->  内置默认值
        例：老 .env 里只写了 MINIMAX_API_KEY，效果等同于写了 LLM_API_KEY。
        health() 里的 config_sources 会告诉你每个值最终来自哪个环境变量。

【为什么密钥只在这里读】
    只有本模块 import os.environ 拿密钥，其它模块一律通过 settings.xxx 拿。
    这样「密钥会不会被打进日志」只需要在一个文件里检查一遍。
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

logger = logging.getLogger('kb_assistant.config')

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
# config.py -> app -> kb_assistant -> 项目根目录
APP_DIR = Path(__file__).resolve().parent
KB_DIR = APP_DIR.parent
PROJECT_ROOT = KB_DIR.parent

# 项目根目录的 .env（主配置源，含数据库连接信息）
ROOT_ENV = PROJECT_ROOT / '.env'
# 小助手自己的 .env（本地覆盖，优先级更高，通常用来放模型 token）
LOCAL_ENV = KB_DIR / '.env'

# 加载顺序：先根目录，再用本地覆盖（override=True 让本地值赢）
load_dotenv(ROOT_ENV, override=False)
load_dotenv(LOCAL_ENV, override=True)


# ---------------------------------------------------------------------------
# 协议常量
# ---------------------------------------------------------------------------
# 小助手支持的模型协议。LLM_PROTOCOL 只能是这三个之一。
SUPPORTED_PROTOCOLS: tuple[str, ...] = ('anthropic', 'openai', 'gemini')

# 协议的中文说明，用于 /health、/capabilities 自描述
PROTOCOL_DISPLAY_NAMES: dict[str, str] = {
    'anthropic': 'Anthropic Messages 协议',
    'openai': 'OpenAI 兼容协议',
    'gemini': 'Gemini generateContent 协议',
}

# 各协议的默认端点 —— 只在 LLM_BASE_URL / MINIMAX_BASE_URL 都没配时才用
DEFAULT_BASE_URLS: dict[str, str] = {
    'anthropic': 'https://api.minimax.chat/anthropic/v1',
    'openai': 'https://api.openai.com/v1',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta',
}

# 各协议的默认模型 —— 同上，只在新旧都没配时兜底
DEFAULT_MODELS: dict[str, str] = {
    'anthropic': 'MiniMax-M3.1-Flash',
    'openai': 'gpt-4o-mini',
    'gemini': 'gemini-2.0-flash',
}


# ---------------------------------------------------------------------------
# 服务商识别
# ---------------------------------------------------------------------------
# 按 base_url 的主机名猜「这是谁家的服务」。
# 猜出来只是给 /health、/models 用来显示名字，不影响实际请求。
_PROVIDER_BY_HOST: dict[str, tuple[str, str]] = {
    'api.minimax.chat': ('minimax', 'MiniMax'),
    'api.minimaxi.com': ('minimax', 'MiniMax'),
    'agent.minimax.cn': ('minimax', 'MiniMax'),
    'api.openai.com': ('openai', 'OpenAI'),
    'api.deepseek.com': ('deepseek', 'DeepSeek'),
    'dashscope.aliyuncs.com': ('qwen', '通义千问'),
    'open.bigmodel.cn': ('zhipu', '智谱 AI'),
    'api.moonshot.cn': ('kimi', 'Moonshot Kimi'),
    'generativelanguage.googleapis.com': ('gemini', 'Google Gemini'),
    'api.anthropic.com': ('anthropic', 'Anthropic Claude'),
}

# 本地部署的常见端口
_PROVIDER_BY_PORT: dict[int, tuple[str, str]] = {
    11434: ('ollama', 'Ollama 本地模型'),
    8000: ('vllm', 'vLLM 本地模型'),
    1234: ('lmstudio', 'LM Studio 本地模型'),
}

# 协议兜底
_PROVIDER_BY_PROTOCOL: dict[str, tuple[str, str]] = {
    'anthropic': ('anthropic', 'Anthropic 兼容服务'),
    'openai': ('openai', 'OpenAI 兼容服务'),
    'gemini': ('gemini', 'Google Gemini'),
}

# provider id -> 中文显示名
PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    'minimax': 'MiniMax',
    'openai': 'OpenAI',
    'deepseek': 'DeepSeek',
    'qwen': '通义千问',
    'zhipu': '智谱 AI',
    'kimi': 'Moonshot Kimi',
    'gemini': 'Google Gemini',
    'anthropic': 'Anthropic Claude',
    'ollama': 'Ollama 本地模型',
    'vllm': 'vLLM 本地模型',
    'lmstudio': 'LM Studio 本地模型',
    'local': '本地模型服务',
    'custom': '自定义模型服务',
}

# 常见模型 id -> 人类可读的名字（认不出来就走通用美化规则）
_KNOWN_MODEL_NAMES: dict[str, str] = {
    'MiniMax-M3.1-Flash': 'MiniMax M3.1 Flash',
    'MiniMax-M2.7': 'MiniMax M2.7',
    'gpt-4o': 'GPT-4o',
    'gpt-4o-mini': 'GPT-4o mini',
    'gpt-4.1': 'GPT-4.1',
    'deepseek-chat': 'DeepSeek Chat',
    'deepseek-reasoner': 'DeepSeek Reasoner',
    'qwen-plus': '通义千问 Plus',
    'qwen-max': '通义千问 Max',
    'glm-4-plus': '智谱 GLM-4 Plus',
    'glm-4-air': '智谱 GLM-4 Air',
    'moonshot-v1-8k': 'Moonshot v1 8k',
    'gemini-2.0-flash': 'Gemini 2.0 Flash',
    'gemini-1.5-pro': 'Gemini 1.5 Pro',
}


# ---------------------------------------------------------------------------
# 读环境变量的小工具
# ---------------------------------------------------------------------------
def _env(key: str, default: str = '') -> str:
    """读环境变量并去掉首尾空白（.env 里手滑多打一个空格是很常见的事）。"""
    return (os.getenv(key) or default).strip()


def _env_int(key: str, default: int) -> int:
    """读整型环境变量，值不合法时退回默认值，而不是让服务起不来。"""
    raw = _env(key)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key).lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _env_first(*keys: str, default: str = '') -> tuple[str, str]:
    """
    按优先级读环境变量，返回 (值, 来源变量名)。

    第一个「非空」的值胜出 —— 这就是 LLM_* -> MINIMAX_* -> 默认值 的兼容规则。
    来源变量名会记进 config_sources，/health 会返回它，方便排查「到底哪条配置生效了」。
    """
    for key in keys:
        value = _env(key)
        if value:
            return value, key
    return default, ''


def _env_first_int(*keys: str, default: int) -> tuple[int, str]:
    """_env_first 的整型版。值不合法就当没配，继续往下找。"""
    for key in keys:
        raw = _env(key)
        if not raw:
            continue
        try:
            return int(raw), key
        except ValueError:
            logger.warning('环境变量 %s 的值 %r 不是整数，已忽略', key, raw)
    return default, ''


def _env_first_float(*keys: str, default: float) -> tuple[float, str]:
    """_env_first 的浮点版。值不合法就当没配，继续往下找。"""
    for key in keys:
        raw = _env(key)
        if not raw:
            continue
        try:
            return float(raw), key
        except ValueError:
            logger.warning('环境变量 %s 的值 %r 不是数字，已忽略', key, raw)
    return default, ''


# ---------------------------------------------------------------------------
# 值解析
# ---------------------------------------------------------------------------
def pretty_model_name(model_id: str) -> str:
    """把模型 id 变成一个人类可读的名字（认不出来就做个通用美化）。"""
    if model_id in _KNOWN_MODEL_NAMES:
        return _KNOWN_MODEL_NAMES[model_id]
    text = model_id.replace('-', ' ').replace('_', ' ').strip()
    # camelCase 拆开：DeepSeekChat -> DeepSeek Chat
    text = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # 全小写的顺手首字母大写：other-model -> Other Model
    if text and text == text.lower():
        text = ' '.join(word.capitalize() for word in text.split(' '))
    return text


def parse_model_list(raw: str) -> dict[str, str]:
    """
    解析 LLM_MODELS / LLM_FALLBACK_MODELS。

    【格式】
        逗号分隔，每一项可以是：
            模型id                 —— 显示名用 pretty_model_name() 自动生成
            模型id=显示名          —— 显示名自己写
        例：LLM_MODELS=MiniMax-M3.1-Flash,deepseek-chat=DeepSeek V3
    """
    result: dict[str, str] = {}
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        model_id, _, display = item.partition('=')
        model_id = model_id.strip()
        display = display.strip()
        if model_id:
            result[model_id] = display or pretty_model_name(model_id)
    return result


def parse_extra_headers(raw: str) -> tuple[dict[str, str], list[str]]:
    """
    解析 LLM_EXTRA_HEADERS（JSON 字符串）。

    【格式】
        {"X-Title": "kb-assistant", "HTTP-Referer": "https://example.com"}

    解析不了不算致命错误 —— 返回空字典 + 一条警告，服务照常起来。
    """
    if not raw:
        return {}, []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}, ['LLM_EXTRA_HEADERS 不是合法的 JSON，已忽略（示例：{"X-Title": "kb-assistant"}）']
    if not isinstance(data, dict):
        return {}, ['LLM_EXTRA_HEADERS 必须是一个 JSON 对象（键值对），已忽略']
    return {str(k): str(v) for k, v in data.items()}, []


def infer_provider(base_url: str, protocol: str) -> tuple[str, str]:
    """根据 base_url 猜服务商，返回 (provider id, 中文显示名)。"""
    try:
        parsed = urlparse(base_url)
        host = (parsed.hostname or '').lower()
        port = parsed.port
    except ValueError:
        host, port = '', None

    if host in _PROVIDER_BY_HOST:
        return _PROVIDER_BY_HOST[host]

    if host in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
        if port in _PROVIDER_BY_PORT:
            return _PROVIDER_BY_PORT[port]
        return ('local', '本地模型服务')

    return _PROVIDER_BY_PROTOCOL.get(protocol, ('custom', '自定义模型服务'))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    """小助手的全部运行配置。"""

    # ---- 模型协议 ----
    # anthropic / openai / gemini，决定请求怎么发
    protocol: str = 'anthropic'
    # 服务商标识（minimax / openai / deepseek / ollama …），只用于展示
    provider: str = 'minimax'
    # 服务商中文名，/health 和 /models 里显示
    provider_display_name: str = 'MiniMax'

    # ---- 模型连接 ----
    # token：只从环境变量读，代码里不出现、也不打日志
    llm_api_key: str = ''
    # 服务端点。默认按协议给；也可以用 MINIMAX_BASE_URL 兼容旧配置
    llm_base_url: str = 'https://api.minimax.chat/anthropic/v1'
    # 当前使用的模型
    llm_model: str = 'MiniMax-M3.1-Flash'
    # 单次请求超时（秒）。流式回答留得久一点
    llm_timeout: float = 120.0
    # 单次回复的最大 token 数
    llm_max_tokens: int = 2048
    # 采样温度：问答场景 0.3 足够稳定，又不至于像 0 那样呆板
    llm_temperature: float = 0.3
    # 额外请求头（LLM_EXTRA_HEADERS），给需要自定义头的网关用
    llm_extra_headers: dict[str, str] = field(default_factory=dict)
    # 可用模型列表：模型 id -> 显示名。默认模型永远排在第一个
    llm_models: dict[str, str] = field(default_factory=dict)
    # 主模型失败时的降级模型（按顺序尝试）
    llm_fallback_models: tuple[str, ...] = ()

    # ---- 数据库 ----
    db_host: str = 'localhost'
    db_port: int = 3306
    db_user: str = 'root'
    db_password: str = ''
    db_name: str = 'student_ms_demo'

    # ---- 服务自身 ----
    host: str = '127.0.0.1'
    port: int = 8010
    # 允许跨域的来源（前端 dev server 走 Vite 代理时其实用不到，留着方便调试）
    cors_origins: tuple[str, ...] = field(default_factory=lambda: ('http://localhost:5173', 'http://127.0.0.1:5173'))

    # ---- 业务行为 ----
    # 单次查询最多返回多少行（SQL 没写 LIMIT 时自动补）
    max_rows: int = 200
    # 单条 SQL 的执行超时（秒）
    sql_timeout: float = 15.0
    # 会话里最多保留多少轮对话历史
    max_history_turns: int = 8
    # 是否在回答里附带执行的 SQL（方便用户核对）
    show_sql: bool = True

    # ---- 自描述信息 ----
    # 每个配置最终来自哪个环境变量（'默认值' 表示没配，用的内置默认）
    config_sources: dict[str, str] = field(default_factory=dict)
    # 不致命但值得提醒的问题（协议不匹配、extra headers 格式错误等）
    warnings: tuple[str, ...] = ()

    # ---- 体检 ----
    def missing(self) -> list[str]:
        """返回缺失的关键配置项名称列表（为空说明配置齐全）。"""
        missing: list[str] = []
        if self.protocol not in SUPPORTED_PROTOCOLS:
            missing.append('LLM_PROTOCOL')
        if not self.llm_api_key:
            missing.append('LLM_API_KEY')
        if not self.db_password:
            missing.append('DB_PASSWORD')
        return missing

    def health(self) -> dict:
        """给 /health 接口用的脱敏状态快照（绝不返回 token 和密码）。"""
        return {
            'protocol': self.protocol,
            'protocol_display_name': PROTOCOL_DISPLAY_NAMES.get(self.protocol, self.protocol),
            'provider': self.provider,
            'provider_display_name': self.provider_display_name,
            'model': self.llm_model,
            'base_url': self.llm_base_url,
            'api_key_configured': bool(self.llm_api_key),
            'supported_protocols': list(SUPPORTED_PROTOCOLS),
            'database': f'{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}',
            'database_password_configured': bool(self.db_password),
            'max_rows': self.max_rows,
            'fallback_models': list(self.llm_fallback_models),
            'missing_config': self.missing(),
            'config_sources': dict(self.config_sources),
            'warnings': list(self.warnings),
        }


def load_settings() -> Settings:
    """
    从环境变量装配 Settings。

    【兼容规则】
        每个模型配置都按 LLM_xxx -> MINIMAX_xxx -> 内置默认值 的顺序取，
        并把「最终来自哪个变量」记进 config_sources，/health 会返回它。
    """
    protocol, protocol_src = _env_first('LLM_PROTOCOL', default='anthropic')
    protocol = protocol.lower()

    base_url, base_src = _env_first(
        'LLM_BASE_URL',
        'MINIMAX_BASE_URL',
        default=DEFAULT_BASE_URLS.get(protocol, DEFAULT_BASE_URLS['anthropic']),
    )
    api_key, key_src = _env_first('LLM_API_KEY', 'MINIMAX_API_KEY')
    model, model_src = _env_first(
        'LLM_MODEL',
        'MINIMAX_MODEL',
        default=DEFAULT_MODELS.get(protocol, DEFAULT_MODELS['anthropic']),
    )
    timeout, timeout_src = _env_first_float('LLM_TIMEOUT', 'MINIMAX_TIMEOUT', default=120.0)
    max_tokens, max_tokens_src = _env_first_int('LLM_MAX_TOKENS', 'MINIMAX_MAX_TOKENS', default=2048)
    temperature, temperature_src = _env_first_float('LLM_TEMPERATURE', 'MINIMAX_TEMPERATURE', default=0.3)

    extra_headers, header_warnings = parse_extra_headers(_env('LLM_EXTRA_HEADERS'))

    # ---- 服务商 ----
    provider_override, _ = _env_first('LLM_PROVIDER')
    if provider_override:
        provider = provider_override.strip().lower()
        provider_display_name = PROVIDER_DISPLAY_NAMES.get(provider, provider)
    else:
        provider, provider_display_name = infer_provider(base_url, protocol)

    # ---- 模型列表（默认模型排第一）----
    configured_models = parse_model_list(_env('LLM_MODELS'))
    model_list: dict[str, str] = {model: configured_models.get(model) or pretty_model_name(model)}
    for model_id, display in configured_models.items():
        if model_id != model:
            model_list[model_id] = display

    # ---- 降级模型 ----
    fallback_models: list[str] = []
    for item in _env('LLM_FALLBACK_MODELS').split(','):
        item = item.strip()
        if not item:
            continue
        fallback_id = item.partition('=')[0].strip()
        if fallback_id and fallback_id not in fallback_models:
            fallback_models.append(fallback_id)

    # ---- 警告 ----
    warnings: list[str] = list(header_warnings)
    if protocol not in SUPPORTED_PROTOCOLS:
        warnings.append(
            f'LLM_PROTOCOL={protocol} 不是受支持的协议（可选：{"、".join(SUPPORTED_PROTOCOLS)}）'
        )
    if protocol != 'anthropic' and model_src.startswith('MINIMAX'):
        warnings.append(
            f'协议已切到 {protocol}，但模型还沿用旧的 {model_src}={model}，建议显式配置 LLM_MODEL'
        )

    config_sources = {
        'protocol': protocol_src or '默认值',
        'base_url': base_src or '默认值',
        'api_key': key_src or '未配置',
        'model': model_src or '默认值',
        'timeout': timeout_src or '默认值',
        'max_tokens': max_tokens_src or '默认值',
        'temperature': temperature_src or '默认值',
    }

    origins = _env('KB_ASSISTANT_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
    return Settings(
        protocol=protocol,
        provider=provider,
        provider_display_name=provider_display_name,
        llm_api_key=api_key,
        llm_base_url=base_url,
        llm_model=model,
        llm_timeout=timeout,
        llm_max_tokens=max_tokens,
        llm_temperature=temperature,
        llm_extra_headers=extra_headers,
        llm_models=model_list,
        llm_fallback_models=tuple(fallback_models),
        db_host=_env('DB_HOST', 'localhost'),
        db_port=_env_int('DB_PORT', 3306),
        db_user=_env('DB_USER', 'root'),
        db_password=_env('DB_PASSWORD'),
        db_name=_env('DB_NAME', 'student_ms_demo'),
        host=_env('KB_ASSISTANT_HOST', '127.0.0.1'),
        port=_env_int('KB_ASSISTANT_PORT', 8010),
        cors_origins=tuple(o.strip() for o in origins.split(',') if o.strip()),
        max_rows=_env_int('KB_ASSISTANT_MAX_ROWS', 200),
        sql_timeout=_env_float('KB_ASSISTANT_SQL_TIMEOUT', 15.0),
        max_history_turns=_env_int('KB_ASSISTANT_MAX_HISTORY', 8),
        show_sql=_env_bool('KB_ASSISTANT_SHOW_SQL', True),
        config_sources=config_sources,
        warnings=tuple(warnings),
    )


settings = load_settings()
