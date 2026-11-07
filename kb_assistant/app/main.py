"""
知识库小助手服务 —— 独立 FastAPI 应用。

【为什么要独立成一个服务】
    主后端（main.py / API/ / Dao/）是业务 CRUD 服务，一行都不用改。
    小助手是旁路服务：独立进程、独立端口（默认 8010）、独立依赖。
    前端通过 Vite 代理 /kb -> 127.0.0.1:8010 访问它。

【接口】
    GET    /health          健康检查 + 脱敏配置状态
    GET    /models          可用模型列表（从配置读）
    GET    /capabilities    小助手能做什么（查哪些表、典型问法）
    GET    /sessions        当前会话列表
    DELETE /sessions/{id}   删除某个会话
    GET    /                服务信息
    POST   /chat            问答（SSE 流式），body: {question, session_id?, model?}
    POST   /chat/sync       问答（非流式，一次性返回），body 同上
    DELETE /session/{id}    清空某个会话的上下文

    【/kb 前缀是同一批路由的别名】
    前端走 Vite 代理 /kb -> 127.0.0.1:8010（不 rewrite），
    所以 /kb/chat、/kb/health 这些必须一直在。
    两条路径共用同一个处理函数，行为完全一致。

【SSE 事件类型】
    status  阶段提示（正在理解问题 / 正在查库 / 正在组织回答…）
    sql     本次实际执行的 SQL
    token   回答的文本增量
    reset   覆盖上一条回答（比如模型越界被拦下）
    result  查询结果（列名 + 行），前端可渲染小表格
    done    结束，附带 session_id
    error   出错

【错误响应】
    统一结构：{"code": "...", "message": "中文说明", "detail": "..."}
    状态码语义：鉴权失败 401/403、模型不存在 404、限流 429、超时 504、
                上游异常 502、参数错误 422、内部错误 500。
    message 是给人看的中文，前端可以直接展示。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .agent import run
from .config import KB_DIR, SUPPORTED_PROTOCOLS, settings
from .db import db
from .knowledge import GLOSSARY, MODULES, TABLES
from .llm import LLMError
from .prompts import ASSISTANT_NAME, ASSISTANT_TITLE
from .sessions import sessions

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv('KB_ASSISTANT_LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('kb_assistant')


# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------
app = FastAPI(
    title=f'学生管理系统 · {ASSISTANT_NAME}（{ASSISTANT_TITLE}）',
    description='基于本地数据库的自然语言问答服务，支持 Anthropic / OpenAI 兼容 / Gemini 三种模型协议',
    version='2.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# 小助手的形象资源（全身立绘）。
# 前端另外打包了一份头像（frontend/src/assets/kb-assistant.png），
# 这里这份是给「只想调接口」的人用的，比如直接拿去做其他客户端。
STATIC_DIR = KB_DIR / 'static'
if STATIC_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    """问答请求。"""

    question: str = Field(..., description='用户想问的问题')
    session_id: str | None = Field(default=None, description='会话 id，不传则新建')
    model: str | None = Field(default=None, description='临时指定模型，不传则用配置的默认模型')


class ChatResponse(BaseModel):
    """非流式问答响应。"""

    session_id: str
    answer: str
    sql: str | None = None
    result: dict | None = None
    used_sql: bool = False
    refused: bool = False


# ---------------------------------------------------------------------------
# 统一错误响应
# ---------------------------------------------------------------------------
def _error_payload(code: str, message: str, detail: Any = '') -> dict:
    """统一的错误体。message 是给人看的中文，绝不含密钥。"""
    return {'code': code, 'message': message, 'detail': detail}


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    """模型调用失败 -> 结构化错误 + 语义正确的状态码。"""
    logger.warning('模型调用失败（%s）：%s', exc.code, exc.message)
    return JSONResponse(
        _error_payload(exc.code, exc.message, exc.detail),
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """参数不合法 -> 422 + 结构化错误。"""
    detail = [
        {
            'field': '.'.join(str(part) for part in err.get('loc', [])),
            'message': err.get('msg', ''),
            'type': err.get('type', ''),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        _error_payload('invalid_request', '请求参数不合法，请检查后重试', detail),
        status_code=422,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """404 / 405 之类也统一成同一个结构。"""
    messages = {
        404: '接口不存在，请对照 /docs 里的接口清单检查路径',
        405: '请求方法不对，请对照 /docs 里的接口清单检查',
    }
    message = messages.get(exc.status_code) or (exc.detail if isinstance(exc.detail, str) else '请求处理失败')
    return JSONResponse(
        _error_payload(f'http_{exc.status_code}', message, exc.detail if not isinstance(exc.detail, str) else ''),
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：任何没接住的异常都不许把内部细节抖给调用方。"""
    logger.exception('未捕获异常：%s', type(exc).__name__)
    return JSONResponse(
        _error_payload('internal_error', '服务内部错误，请稍后再试'),
        status_code=500,
    )


# ---------------------------------------------------------------------------
# 基础接口
# ---------------------------------------------------------------------------
@app.get('/', tags=['基础'])
async def index() -> dict:
    """服务信息。"""
    return {
        'service': f'学生管理系统 · {ASSISTANT_NAME}',
        'assistant': {'name': ASSISTANT_NAME, 'title': ASSISTANT_TITLE},
        'protocol': settings.protocol,
        'provider': settings.provider_display_name,
        'model': settings.llm_model,
        'docs': '/docs',
        'endpoints': [
            'GET  /health',
            'GET  /models',
            'GET  /capabilities',
            'GET  /sessions',
            'POST /chat          (SSE 流式)',
            'POST /chat/sync     (非流式)',
            'DELETE /sessions/{session_id}',
            'DELETE /session/{session_id}   (只清上下文)',
        ],
    }


@app.get('/health', tags=['基础'])
@app.get('/kb/health', tags=['基础'])
async def health() -> JSONResponse:
    """
    健康检查。

    顺便做「配置体检」：token 没配、数据库连不上，都在这里报出来，
    不用等用户提问才发现问题。

    【脱敏保证】
        只返回「配没配」，绝不返回 token、密码本身。
    """
    missing = settings.missing()
    db_alive = db.ping()
    healthy = not missing and db_alive

    config = settings.health()
    payload = {
        'status': 'ok' if healthy else 'degraded',
        'assistant': {'name': ASSISTANT_NAME, 'title': ASSISTANT_TITLE},
        # 常用的几项直接摊在顶层，方便一眼看到（config 里还有完整版）
        'protocol': config['protocol'],
        'model': config['model'],
        'base_url': config['base_url'],
        'api_key_configured': config['api_key_configured'],
        'supported_protocols': config['supported_protocols'],
        'config': config,
        'database_connected': db_alive,
        'missing_config': missing,
    }
    if missing:
        payload['hint'] = (
            '请在项目根目录 .env 或 kb_assistant/.env 中补齐：' + '、'.join(missing)
        )
    if not db_alive:
        payload['hint'] = '数据库连接失败，请检查 MySQL 是否启动、.env 里的 DB_* 配置是否正确'
    if config.get('warnings'):
        payload['hint'] = '；'.join(config['warnings'])

    return JSONResponse(payload, status_code=200 if healthy else 503)


@app.get('/models', tags=['模型'])
@app.get('/kb/models', tags=['模型'])
async def list_models() -> dict:
    """
    可用模型列表（从配置读，不去调远端）。

    LLM_MODELS 没配时，只返回当前默认模型。
    """
    return {
        'protocol': settings.protocol,
        'provider': settings.provider,
        'provider_display_name': settings.provider_display_name,
        'default_model': settings.llm_model,
        'fallback_models': list(settings.llm_fallback_models),
        'models': [
            {
                'id': model_id,
                'provider': settings.provider,
                'display_name': display_name,
                'default': model_id == settings.llm_model,
            }
            for model_id, display_name in settings.llm_models.items()
        ],
    }


@app.get('/capabilities', tags=['基础'])
@app.get('/kb/capabilities', tags=['基础'])
async def capabilities() -> dict:
    """
    小管家能做什么。

    让人一眼看懂：能查哪些表、是不是只读、能怎么问。
    """
    return {
        'assistant': {'name': ASSISTANT_NAME, 'title': ASSISTANT_TITLE},
        'summary': (
            f'{ASSISTANT_NAME}是本系统的教务数据管家，'
            '用自然语言提问，它自己去数据库查数据并给出带 SQL 的答案。'
        ),
        'read_only': True,
        'database': {
            'name': settings.db_name,
            'user': settings.db_user,
            'host': settings.db_host,
            'port': settings.db_port,
        },
        'tables': [
            {
                'name': table.name,
                'display_name': table.cn,
                'description': table.desc,
                'soft_delete_column': table.soft_delete,
            }
            for table in TABLES
        ],
        'modules': [
            {'name': name, 'path': path, 'description': desc}
            for name, path, desc in MODULES
        ],
        'glossary': [
            {'term': term, 'meaning': meaning}
            for term, meaning in GLOSSARY
        ],
        'example_questions': [
            '1 号班有多少学生？',
            '就业薪资最高的 5 个学生是谁？',
            '哪些学生有两次以上不及格？',
            '各班平均分是多少？',
            '顾问和班主任有什么区别？',
            '这个系统有哪些功能模块？',
            '数据库里有哪些表，字段都是干什么的？',
        ],
        'capabilities': [
            '业务数据查询：学员档案、班级、老师 / 班主任 / 顾问、成绩、就业去向',
            '统计分析：人数、平均分、及格率、薪资分布等',
            '系统结构解答：有哪些表、字段含义、表之间怎么关联',
            '功能用法解答：有哪些菜单、某个页面能做什么、某个接口是干什么的',
            '业务流程解答：顾问和班主任的区别、就业时长怎么算、软删除是什么意思',
        ],
        'not_supported': [
            '非本系统的话题（天气、新闻、股票、写诗等）会被直接拒绝',
            '任何写操作 —— 模型只能生成 SELECT，数据库连接本身也是只读账号',
        ],
        'limits': {
            'max_rows': settings.max_rows,
            'max_history_turns': settings.max_history_turns,
            'sql_timeout_seconds': settings.sql_timeout,
        },
        'protocol': {
            'protocol': settings.protocol,
            'display_name': settings.provider_display_name,
            'model': settings.llm_model,
            'supported_protocols': list(SUPPORTED_PROTOCOLS),
        },
    }


# ---------------------------------------------------------------------------
# 会话接口
# ---------------------------------------------------------------------------
def _session_summaries() -> list[dict]:
    """
    会话列表。

    sessions.py 不在本次改动的范围内，所以这里只读地拿它内部的仓库，
    不做任何写入 —— 拿不到就返回空列表，不能让 /sessions 把服务搞挂。
    """
    store = getattr(sessions, '_sessions', None)
    if store is None:
        return []
    try:
        items = list(store.values())
    except Exception:  # noqa: BLE001 —— 列表接口不该把服务搞挂
        return []

    summaries: list[dict] = []
    for session in items:
        last = session.turns[-1].content if session.turns else ''
        summaries.append({
            'session_id': session.session_id,
            'turns': len(session.turns),
            'created_at': session.created_at,
            'updated_at': session.updated_at,
            'last_message': last[:100],
        })
    summaries.sort(key=lambda item: item['updated_at'], reverse=True)
    return summaries


@app.get('/sessions', tags=['会话'])
@app.get('/kb/sessions', tags=['会话'])
async def list_sessions() -> dict:
    """当前活跃的会话列表（按最后活动时间排序）。"""
    summaries = _session_summaries()
    return {'sessions': summaries, 'count': len(summaries)}


@app.delete('/sessions/{session_id}', tags=['会话'])
@app.delete('/kb/sessions/{session_id}', tags=['会话'])
async def delete_session(session_id: str) -> dict:
    """彻底删掉一个会话（上下文一起没了）。"""
    ok = sessions.delete(session_id)
    return {
        'ok': ok,
        'session_id': session_id,
        'message': '会话已删除' if ok else '会话不存在',
    }


# ---------------------------------------------------------------------------
# 问答接口
# ---------------------------------------------------------------------------
@app.post('/kb/chat', tags=['问答'])
@app.post('/chat', tags=['问答'])
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """
    问答（SSE 流式）。

    浏览器用 fetch + ReadableStream 读这个接口，
    逐个事件渲染出来（阶段提示 → SQL → 回答增量 → 结果 → 结束）。

    请求体多了一个可选的 model 字段，可以临时换一个模型问这次。
    """
    session = sessions.get_or_create(req.session_id)

    async def event_source():
        """把 AgentEvent 流编码成 SSE 帧。"""
        try:
            async for event in run(req.question, session, model=req.model):
                yield event.to_sse()
        except LLMError as exc:
            logger.warning('流式问答异常：%s', exc)
            yield _error_event(exc.message, exc.code, exc.status_code)
        except Exception as exc:  # noqa: BLE001 —— 兜底，别让连接裸奔断开
            logger.exception('流式问答未捕获异常')
            yield _error_event(f'服务内部错误：{exc}', 'internal_error', 500)

    return StreamingResponse(
        event_source(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            # 关掉 Nginx 的缓冲，否则流式会被攒成一坨最后才吐出来
            'X-Accel-Buffering': 'no',
        },
    )


@app.post('/kb/chat/sync', response_model=None, tags=['问答'])
@app.post('/chat/sync', response_model=None, tags=['问答'])
async def chat_sync(req: ChatRequest) -> ChatResponse | JSONResponse:
    """
    问答（非流式）。

    一次性返回完整答案，适合脚本调用和自动化测试。
    内部复用的还是同一套编排逻辑。

    出错时返回结构化错误体（code / message / detail）和语义正确的状态码。
    """
    session = sessions.get_or_create(req.session_id)

    answer_parts: list[str] = []
    sql: str | None = None
    result: dict | None = None
    used_sql = False
    refused = False
    error: dict | None = None

    async for event in run(req.question, session, model=req.model):
        if event.event == 'token':
            answer_parts.append(event.data.get('text', ''))
        elif event.event == 'reset':
            answer_parts = [event.data.get('text', '')]
        elif event.event == 'sql':
            sql = event.data.get('sql')
            used_sql = True
        elif event.event == 'result':
            result = event.data
        elif event.event == 'error':
            error = event.data
        elif event.event == 'done':
            refused = bool(event.data.get('refused'))

    if error:
        return JSONResponse(
            _error_payload(
                error.get('code', 'llm_error'),
                error.get('message', '服务出错了'),
                error.get('detail', ''),
            ),
            status_code=int(error.get('status_code') or 502),
        )

    return ChatResponse(
        session_id=session.session_id,
        answer=''.join(answer_parts).strip(),
        sql=sql,
        result=result,
        used_sql=used_sql,
        refused=refused,
    )


@app.delete('/kb/session/{session_id}', tags=['问答'])
async def clear_session(session_id: str) -> dict:
    """清空某个会话的对话上下文（数据本身不受影响）。"""
    ok = sessions.clear(session_id)
    return {'ok': ok, 'session_id': session_id, 'message': '上下文已清空' if ok else '会话不存在'}


@app.get('/kb/session/{session_id}', tags=['问答'])
async def get_session(session_id: str) -> dict:
    """查看某个会话的上下文（调试用）。"""
    session = sessions.get_or_create(session_id)
    return {
        'session_id': session.session_id,
        'turns': len(session.turns),
        'history': [{'role': t.role, 'content': t.content} for t in session.turns],
    }


def _error_event(message: str, code: str = 'llm_error', status_code: int = 502) -> str:
    """构造一个 error 事件的 SSE 帧。"""
    import json

    payload = json.dumps(
        {'message': message, 'code': code, 'status_code': status_code},
        ensure_ascii=False,
    )
    return f'event: error\ndata: {payload}\n\n'


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import uvicorn

    missing = settings.missing()
    if missing:
        logger.warning('配置不完整：%s —— 请在 .env 中补齐后重启', '、'.join(missing))
    else:
        logger.info(
            '模型 %s（%s / %s）已就绪',
            settings.llm_model, settings.protocol, settings.provider_display_name,
        )
    for warning in settings.warnings:
        logger.warning('配置提醒：%s', warning)

    uvicorn.run(
        'app.main:app',
        host=settings.host,
        port=settings.port,
        reload=os.getenv('KB_ASSISTANT_RELOAD', '0') == '1',
    )
