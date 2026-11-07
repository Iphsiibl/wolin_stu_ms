# 知识库小助手「小管家」

> 嵌在学生管理系统右下角的一只女仆助手。
> 用自然语言问它，它自己去数据库查数据、给你答案。

- **模型**：三种协议随便切 —— Anthropic Messages（默认，MiniMax / Claude）、
  OpenAI 兼容（OpenAI / DeepSeek / 通义千问 / 智谱 / Kimi / Ollama / vLLM / LM Studio）、
  Gemini generateContent。改一个环境变量就行
- **数据**：直接查 MySQL `student_ms_demo`，能写 SQL、能统计、能出表格
- **边界**：只聊本系统。天气、股票、写诗这类问题一律礼貌拒绝
- **形态**：悬浮球 + 聊天抽屉，SSE 流式回答，登录后自动出现

**主后端（`main.py` / `API/` / `Dao/`）一行都没改。**
小助手是独立进程、独立端口、独立依赖的旁路服务。

---

## 一、为什么做成独立服务

主后端是业务 CRUD 服务（可写连接、无状态、管的是业务规则），
小助手是「自然语言 → SQL → 查库 → 回答」的旁路，特性完全不同：

| | 主后端 | 小助手 |
|---|---|---|
| 端口 | 8003 | 8010 |
| 数据库权限 | 可写（root） | **只读（`kb_ro`，已配好）** |
| 依赖 | 项目 requirements.txt | kb_assistant/requirements.txt |
| 挂掉的影响 | 整个系统不可用 | 只是问答不能用 |
| 鉴权 | 无（演示模式） | 无（跟主后端一致，走同源代理） |

拆开的好处：主后端不用背 AI 相关的依赖和风险，小助手可以独立升级、
独立部署，也能单独做只读账号的权限收敛。

---

## 二、目录结构

```
kb_assistant/                      ← 本文件夹，整个功能都在这里
├── app/
│   ├── __init__.py
│   ├── main.py                    FastAPI 应用：路由 + SSE + 统一错误响应
│   ├── config.py                  配置中心（唯一读 .env 的地方）
│   ├── llm/                       模型调用层（协议适配）
│   │   ├── __init__.py            对外出口：complete() / stream() / 降级
│   │   ├── base.py                公共基类：请求 / SSE 解析 / 错误翻译
│   │   ├── anthropic.py           Anthropic Messages 协议
│   │   ├── openai.py              OpenAI 兼容协议
│   │   └── gemini.py              Gemini generateContent 协议
│   ├── knowledge.py               知识库：表结构 / 模块 / 接口 / 术语
│   ├── prompts.py                 三套提示词：人设、生成 SQL、组织回答
│   ├── agent.py                   主流程编排
│   ├── sql_guard.py               SQL 安全闸门（只读）
│   ├── scope.py                   领域边界守卫
│   ├── db.py                      只读数据库访问
│   └── sessions.py                多轮会话（内存）
├── tests/
│   ├── test_kb_assistant.py       安全闸门 / 知识库 / 数据库
│   ├── test_agent_flow.py         流程集成测试（模型打桩）
│   ├── test_llm_protocols.py      三种协议的请求组装 / 流式解析 / 降级
│   └── test_api_endpoints.py      HTTP 接口（向后兼容 + 自描述）
├── tools/
│   └── prepare_avatar.py          从三视图精灵图裁头像（纯标准库）
├── static/
│   └── assistant.png              小助手立绘
├── requirements.txt
├── .env.example                   环境变量样例
└── pytest.ini

frontend/src/
├── components/KbAssistant/index.vue   悬浮球 + 聊天抽屉
├── api/kb.ts                          SSE 客户端（fetch + ReadableStream）
├── utils/markdown.ts                  极简 Markdown 渲染
└── assets/kb-assistant.png            头像
```

---

## 三、跑起来

### 1. 装依赖

```bash
# 小助手（和主后端分开装）
pip install -r kb_assistant/requirements.txt
```

### 2. 配 token

**只需要改 `.env` 一处**。项目根目录的 `.env` 里已经有数据库配置了，
补上 token 即可：

```dotenv
# .env（新的写法）
LLM_API_KEY=你的真实token
LLM_MODEL=MiniMax-M3.1-Flash
```

> 老的写法 `MINIMAX_API_KEY` / `MINIMAX_MODEL` **照样能用** ——
> 新的 `LLM_*` 没配时会自动回退到旧的 `MINIMAX_*`，再回退到内置默认值。
> 所以老的 `.env` 一行不改也能继续跑。
>
> 也可以在 `kb_assistant/.env` 里单独放（优先级更高），样例见
> `kb_assistant/.env.example`。**不要把 token 提交进 git** ——
> 根目录的 `.env` 已经在 `.gitignore` 里了。
>
> `kb_assistant/.env` 里已经放好了只读数据库账号的凭据（`DB_USER=kb_ro`），
> **不要删掉这个文件**，否则小助手会退回用 root 连库。
> 只想补 token 的话，在根目录 `.env` 加 `LLM_API_KEY` 就够了 —— 不用动这两个文件。

### 3. 起三个服务

```bash
# ① 主后端（原有，端口 8003）
python main.py

# ② 小助手（新增，端口 8010）
cd kb_assistant
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010

# ③ 前端（端口 5173）
cd frontend
npm run dev
```

浏览器打开 http://localhost:5173 ，登录 admin / 123456 ，
右下角就出现小管家了。

> 前端已经把 `/kb` 代理到 `127.0.0.1:8010`（见 `frontend/vite.config.ts`），
> 所以浏览器只跟同源打交道，不会碰 CORS。生产环境用 Nginx 把 `/kb` 反代过去即可。

---

## 四、怎么用

点右下角的小管家 → 打开抽屉 → 输入问题。

**能问的：**

| 类型 | 例子 |
|---|---|
| 业务数据 | `1 号班有多少学生` `就业薪资最高的 5 个学生是谁` |
| 统计口径 | `哪些学生有两次以上不及格` `各班平均分是多少` |
| 系统结构 | `数据库里有哪些表` `顾问和班主任有什么区别` |
| 功能用法 | `这个系统有哪些模块` `成绩接口在哪个路径` |

**不能问的**（会被拦下并礼貌拒绝）：天气、新闻、股票、写诗、写通用代码、
医疗法律咨询等等。

回答里会附一张「本次查询」的折叠卡片，能看到**实际执行的 SQL** 和
**查询结果表格**（最多 20 行）—— 方便你核对数据是怎么来的。

---

## 五、安全设计

模型输出是不可信输入，所以有**三层**防线，不只靠提示词。

### 第 1 层：SQL 安全闸门（`sql_guard.py`）

模型生成的 SQL 要过四道检查才能执行：

1. **只允许 `SELECT` / `WITH`** —— `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`/`TRUNCATE` 一律拒绝
2. **单语句** —— 含分号就拒（防止 `SELECT 1; DROP TABLE ...` 拼接）
3. **危险函数黑名单** —— `LOAD_FILE`、`INTO OUTFILE`、`BENCHMARK`、`SLEEP` 等
4. **表白名单** —— 只允许查本项目的 7 张业务表，`mysql.user`、`information_schema` 这些一律拒绝

另外自动补 `LIMIT`（默认上限 200 行），注释会先被剥掉再检查关键字。

### 第 2 层：领域边界（`scope.py` + 提示词）

- **调用前**：确定性关键词规则，明显跑题的问题直接拒答 —— 省一次 token，也更稳
- **提示词里**：写死领域边界，要求越界时输出固定标记 `[超出范围]`
- **调用后**：检查回答里有没有越界标记，有就整段换成拒答话术

> 设计取舍是**宁可漏判，不可误杀**：黑名单只收几乎不可能出现在
> 本系统问题里的词。所以「怎么给系统加个接口」不会被拦，
> 但「帮我写个爬虫」会。

### 第 3 层：只读数据库账号（已配置）

小助手用的是**独立的只读 MySQL 账号**，不是 root。

```
kb_ro@localhost   GRANT USAGE ON *.*                            -- 没有全局权限
                   GRANT SELECT ON `student_ms_demo`.*           -- 只能读本库
```

这样即使代码里的 SQL 闸门被绕过，数据库这层也写不进去 —— 两道防线互相独立。

**为什么账号配置放在 `kb_assistant/.env` 而不是根目录的 `.env`：**
根目录 `.env` 里的 `DB_USER=root` 是**主后端**在用的。
如果把小助手的 `DB_USER` 也改成 `kb_ro`，主后端就失去了写权限，
整个系统的新增/修改/删除全挂。
所以 `kb_assistant/.env` 单独放小助天的只读凭据，**只影响小助手**。

> 加载顺序：`config.py` 先读根目录 `.env`，再用 `kb_assistant/.env` 覆盖。
> 根目录 `.gitignore` 里的 `.env` 规则对任意层级都生效，这个文件不会被提交。

**实测行为（已验证）：**

| 操作 | 结果 |
|---|---|
| `SELECT`（本库任意表） | ✅ 正常 |
| `INSERT` / `UPDATE` / `DELETE` | ❌ MySQL error 1142 |
| `DROP` / `ALTER` / `CREATE` / `TRUNCATE` | ❌ MySQL error 1142 |
| 读 `mysql.user` | ❌ MySQL error 1142 |
| 读 `information_schema` | ✅ 可读，但**只看到 student_ms_demo 的 7 张表**（MySQL 8 按权限自动收窄） |

**换环境 / 重建账号时用这段 SQL：**

```sql
CREATE USER 'kb_ro'@'localhost' IDENTIFIED BY '你的密码';
CREATE USER 'kb_ro'@'127.0.0.1' IDENTIFIED BY '你的密码';
GRANT SELECT ON student_ms_demo.* TO 'kb_ro'@'localhost';
GRANT SELECT ON student_ms_demo.* TO 'kb_ro'@'127.0.0.1';
FLUSH PRIVILEGES;
```

> 密码里如果有 `@` `%` `#` 这些字符也没关系 —— `db.py` 用
> `sqlalchemy.engine.URL.create()` 构造连接串，会自动做转义。
> （用字符串拼接的话，密码里的 `@` 会被当成主机名分隔符，连接直接失败。）


### SQL 不合规时的自纠错

模型第一次生成的 SQL 没过校验，会把**错误原因**喂回给模型让它重写一次。
还是不过，就退回知识库回答 —— 不会把错误暴露给用户，更不会执行。

---

## 六、接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` `/kb/health` | 健康检查 + 脱敏配置状态 |
| GET | `/models` `/kb/models` | 可用模型列表（从配置读） |
| GET | `/capabilities` `/kb/capabilities` | 小管家能做什么（查哪些表、典型问法） |
| GET | `/sessions` `/kb/sessions` | 当前会话列表 |
| DELETE | `/sessions/{id}` | 删掉某个会话（连上下文一起） |
| POST | `/chat` `/kb/chat` | 问答（SSE 流式），body `{question, session_id?, model?}` |
| POST | `/chat/sync` `/kb/chat/sync` | 问答（非流式，一次性返回） |
| GET | `/kb/session/{id}` | 查看会话上下文（调试用） |
| DELETE | `/kb/session/{id}` | 只清空上下文，会话本身留着 |
| GET | `/static/assistant.png` | 小助手立绘 |

> `/kb` 前缀是同一批路由的别名。前端走 Vite 代理 `/kb -> 127.0.0.1:8010`
> 且**不 rewrite**，所以 `/kb/chat`、`/kb/health` 这些必须一直在 ——
> 两条路径共用同一个处理函数，行为完全一致。

**SSE 事件类型：**

| event | 载荷 | 含义 |
|---|---|---|
| `status` | `{phase, text}` | 阶段提示（正在理解问题 / 正在查库 / 正在组织回答） |
| `sql` | `{sql}` | 本次实际执行的 SQL |
| `token` | `{text}` | 回答的文本增量 |
| `reset` | `{text}` | 覆盖上一条回答（模型越界被拦下时） |
| `result` | `{columns, rows, row_count, elapsed_ms}` | 查询结果 |
| `done` | `{session_id, used_sql}` | 结束 |
| `error` | `{message, code, status_code}` | 出错（文案已是中文，可直接展示） |

**统一错误响应：**

所有错误都是同一个结构，`message` 是能直接展示给用户的中文：

```json
{ "code": "llm_timeout", "message": "模型服务响应超时，请稍后再试", "detail": "" }
```

| 情况 | code | HTTP |
|---|---|---|
| 参数不合法 | `invalid_request` | 422 |
| 上游鉴权失败 | `llm_unauthorized` / `llm_forbidden` | 401 / 403 |
| 模型不存在 | `llm_model_not_found` | 404 |
| 限流 | `llm_rate_limited` | 429 |
| 超时 | `llm_timeout` | 504 |
| 上游 5xx | `llm_unavailable` | 502 |
| 其它 | `llm_error` / `internal_error` | 502 / 500 |

> 密钥绝不会出现在错误体、`/health` 或日志里 —— 只有「配没配」这个布尔值。

**几个返回结构示例：**

```jsonc
// GET /health
{
  "status": "ok",
  "assistant": { "name": "小管家", "title": "教务数据管家" },
  "protocol": "anthropic",
  "model": "MiniMax-M3.1-Flash",
  "base_url": "https://api.minimax.chat/anthropic/v1",
  "api_key_configured": true,
  "supported_protocols": ["anthropic", "openai", "gemini"],
  "config": { /* 完整版：provider、config_sources、warnings… */ },
  "database_connected": true,
  "missing_config": []
}

// GET /models
{
  "protocol": "anthropic",
  "provider": "minimax",
  "provider_display_name": "MiniMax",
  "default_model": "MiniMax-M3.1-Flash",
  "fallback_models": [],
  "models": [
    { "id": "MiniMax-M3.1-Flash", "provider": "minimax", "display_name": "MiniMax M3.1 Flash", "default": true }
  ]
}

// GET /capabilities
{
  "assistant": { "name": "小管家", "title": "教务数据管家" },
  "read_only": true,
  "database": { "name": "student_ms_demo", "user": "kb_ro", "host": "localhost", "port": 3306 },
  "tables": [ { "name": "student_info", "display_name": "学生信息表", "description": "…", "soft_delete_column": "is_del" } ],
  "modules": [ { "name": "统计分析", "path": "/stat/analysis", "description": "…" } ],
  "glossary": [ { "term": "顾问", "meaning": "…" } ],
  "example_questions": ["1 号班有多少学生？", "…"],
  "capabilities": ["业务数据查询：…", "…"],
  "not_supported": ["非本系统的话题…", "任何写操作…"],
  "limits": { "max_rows": 200, "max_history_turns": 8, "sql_timeout_seconds": 15.0 },
  "protocol": { "protocol": "anthropic", "display_name": "MiniMax", "model": "MiniMax-M3.1-Flash", "supported_protocols": ["anthropic", "openai", "gemini"] }
}
```

---

## 七、模型协议适配层

`app/llm/` 是一个独立的适配层。三种协议各一个类，
上层（`agent.py`）只认 `complete()` / `stream()` 两个方法，
**完全不知道底下是哪套协议**。换协议 = 改一个环境变量，业务代码一行不动。

| | `anthropic`（默认） | `openai` | `gemini` |
|---|---|---|---|
| 请求地址 | `POST {base}/messages` | `POST {base}/chat/completions` | `POST {base}/models/{model}:generateContent` |
| 鉴权头 | `x-api-key` + `anthropic-version: 2023-06-01` | `Authorization: Bearer {key}` | `x-goog-api-key` |
| system 放哪 | **顶层参数** `body.system` | messages 里一条 `role=system` | `systemInstruction.parts[0].text` |
| 角色名 | `user` / `assistant` | `user` / `assistant` / `system` | `user` / **`model`** |
| 模型 id 在哪 | 请求体 `model` | 请求体 `model` | **URL 路径里** |
| 非流式正文 | `content[].text` | `choices[0].message.content` | `candidates[0].content.parts[].text` |
| 流式增量 | `content_block_delta` → `delta.text` | `choices[0].delta.content` | `candidates[0].content.parts[].text` |
| 流式结束标记 | 无（靠 `message_stop`） | `data: [DONE]` | 无 |

**OpenAI 兼容协议一套接全家** —— OpenAI / DeepSeek / 通义千问 / 智谱 / Kimi /
Ollama(`/v1`) / vLLM / LM Studio 都提供 `/chat/completions`，换个 `base_url` 就行。

**降级：** `LLM_FALLBACK_MODELS` 里配了备选模型时，主模型遇到**可重试**的错误
（超时 / 限流 / 上游 5xx / 连不上）会自动换下一个模型重试。
鉴权失败、参数错误这种配置问题**不降级** —— 换模型也救不回来，直接报错更快。
流式已经吐过内容时也不降级 —— 半截回答再接另一段只会更乱。

---

## 八、配置项

全部在 `.env`（或 `kb_assistant/.env`），详见 `kb_assistant/.env.example`。

### 模型配置

| 变量 | 默认值 | 旧变量（仍兼容） | 说明 |
|---|---|---|---|
| `LLM_PROTOCOL` | `anthropic` | — | 协议：`anthropic` / `openai` / `gemini` |
| `LLM_BASE_URL` | 按协议给（anthropic 是 `https://api.minimax.chat/anthropic/v1`） | `MINIMAX_BASE_URL` | 服务端点 |
| `LLM_API_KEY` | — | `MINIMAX_API_KEY` | **必填**，模型 token |
| `LLM_MODEL` | 按协议给（anthropic 是 `MiniMax-M3.1-Flash`） | `MINIMAX_MODEL` | 模型 |
| `LLM_TIMEOUT` | `120` | `MINIMAX_TIMEOUT` | 单次请求超时（秒） |
| `LLM_MAX_TOKENS` | `2048` | `MINIMAX_MAX_TOKENS` | 单次回复上限 |
| `LLM_TEMPERATURE` | `0.3` | `MINIMAX_TEMPERATURE` | 采样温度 |
| `LLM_EXTRA_HEADERS` | 空 | — | 自定义请求头（JSON 字符串） |
| `LLM_MODELS` | 空 | — | 可用模型列表，逗号分隔，可写 `id=显示名` |
| `LLM_FALLBACK_MODELS` | 空 | — | 降级模型，逗号分隔 |
| `LLM_PROVIDER` | 按 base_url 自动猜 | — | 服务商标识，只影响显示 |

**兼容规则（重要）：** 每个模型配置都按
`LLM_xxx` → `MINIMAX_xxx` → 内置默认值 三步取。
所以**老的 `.env` 一行不改也能继续跑**。
`GET /health` 里的 `config_sources` 会告诉你每个值最终来自哪个变量：

```json
"config_sources": {
  "protocol": "默认值",
  "base_url": "MINIMAX_BASE_URL",
  "api_key": "MINIMAX_API_KEY",
  "model": "MINIMAX_MODEL"
}
```

> 换协议的时候记得**同时改 `LLM_MODEL`** —— 否则模型名还沿用旧的 `MINIMAX_MODEL`。
> 这种情况下 `/health` 的 `warnings` 里会提醒你。

### 服务与业务配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `KB_ASSISTANT_HOST` / `KB_ASSISTANT_PORT` | `127.0.0.1` / `8010` | 服务地址 |
| `KB_ASSISTANT_MAX_ROWS` | `200` | 单次查询行数上限 |
| `KB_ASSISTANT_SQL_TIMEOUT` | `15` | 单条 SQL 超时（秒） |
| `KB_ASSISTANT_MAX_HISTORY` | `8` | 会话保留轮数 |
| `KB_ASSISTANT_SHOW_SQL` | `1` | 是否在回答里附带 SQL |

数据库配置（`DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`）
沿用根目录 `.env` 里已有的，不用重复配。

**唯一例外**：`DB_USER` / `DB_PASSWORD` 已在 `kb_assistant/.env` 里
覆盖成只读账号 `kb_ro`（详见「安全设计 → 第 3 层」）。
所以小助手用只读身份连库，主后端仍然用 root —— 两边互不影响。

---

## 九、改知识库

模型对「这个系统是什么」的全部认知都在一个文件里：
**`kb_assistant/app/knowledge.py`**。

改完直接重启小助手就生效。里面分五块：

- `TABLES` —— 7 张表的字段、中文含义、软删除字段
- `MODULES` —— 前端功能模块和路径
- `API_ENDPOINTS` —— 后端接口清单
- `GLOSSARY` —— 业务术语（顾问、班主任、就业时长……）

> 改了数据库表结构，记得同步改这里 —— 测试里有一条
> `test_soft_delete_column_exists` 会检查软删除字段是否真的存在。

提示词在 `kb_assistant/app/prompts.py`，改人设、改语气、改输出格式都在那儿。

---

## 十、测试

```bash
cd kb_assistant
pytest            # 114 个用例
```

覆盖四块：

- `test_kb_assistant.py` —— SQL 闸门（写操作、危险函数、非白名单表、多语句、
  注释绕过、CTE）、领域边界（该拦的拦住、该放行的放行）、知识库一致性、真实查库
- `test_agent_flow.py` —— 流程集成测试，模型调用打桩，
  但**真的去查 MySQL**：走 SQL、查库、流式作答、危险 SQL 被拦后重写、
  越界标记被替换、多轮上下文
- `test_llm_protocols.py` —— 三种协议的请求体组装、流式分片解析、
  协议选择、降级逻辑、错误码映射、配置兼容。**全部用 httpx.MockTransport 打桩，
  一个真实请求都不发**；配置兼容那组把 `LLM_*` / `MINIMAX_*` 全清干净后重跑
  `load_settings()`，验证老的 `.env` 照样生效
- `test_api_endpoints.py` —— HTTP 接口：老路径（`/kb/chat`、`/kb/health`）不能坏、
  新接口（`/models`、`/capabilities`、`/sessions`）要对、
  错误响应要统一、密钥不能出现在响应里

---

## 十一、常见问题

**小助手右下角是灰的 / 标着「!」**
`/kb/health` 返回 503。先看具体缺哪一项：
- `missing_config` 里有 `LLM_API_KEY` → 去 `.env` 填 token
  （老的 `MINIMAX_API_KEY` 也认，但建议改成新写法）
- `database_connected` 是 `false` → 数据库连不上，检查 MySQL 是否启动

**数据库连不上，提示 `Access denied for user 'kb_ro'`**
只读账号没建或者密码对不上。重新执行「安全设计 → 第 3 层」里那段 SQL，
并确认 `kb_assistant/.env` 里的 `DB_PASSWORD` 和建号时用的一致。

**小助手能连库，但主后端说没权限**
说明有人把根目录 `.env` 的 `DB_USER` 改成了 `kb_ro`。
改回 `root` —— 只读凭据应该只放在 `kb_assistant/.env` 里。

**点了没反应 / 一直转圈**
小助手服务没起。先 `curl http://127.0.0.1:8010/health` 确认。

**回答说「没查到相关记录」**
可能是筛选条件太窄，或者统计时没过滤软删除。换个问法，
或者直接看「本次查询」卡片里的 SQL 核对一下。

**想换个模型**
改 `.env` 里的 `LLM_MODEL`。M3 / M2.7 也都能用。

**想换个服务商 / 换套协议**
改 `LLM_PROTOCOL` + `LLM_BASE_URL` + `LLM_MODEL`（见「模型协议适配层」）。
只换模型不换协议的话，`LLM_MODEL` 改一个名字就行。
换协议时记得 `LLM_MODEL` 也要一起改 —— 否则会沿用旧的模型名，
`/health` 的 `warnings` 会提醒你。

**某个模型一直超时 / 报 5xx**
配 `LLM_FALLBACK_MODELS=备用模型1,备用模型2`，
主模型遇到可重试的错误会自动降级。

**会话能跨页面保留吗**
可以，会话 id 存在服务端内存里，前端刷新后仍然带着同一个 id 继续聊。
服务重启则清空（上下文不落盘）。

---

## 十二、关于开源项目

开发前先 survey 了一轮公开的 GitHub 项目，结论是**没有能直接套用的**，
主要卡在这几点：

| 项目 | 为什么不直接用 |
|---|---|
| [HuanMoovo/campus-agent](https://github.com/HuanMoovo/campus-agent) | 最接近的一个（Electron + Vue3 + FastAPI 的校园问答），但它是完整桌面应用，自带独立知识库体系和前端架构，和本项目的 Geeker-Admin 布局完全不是一套东西 |
| [KagaribiDev/queryforge](https://github.com/KagaribiDev/queryforge) | Text-to-SQL 做得不错，但依赖 LangGraph + Redis + Qdrant + Elasticsearch + bge-large 向量服务，7 张表 1000 行数据的场景扛不起这套重型基建；且无开源许可证 |
| [austinLorenzMccoy/sql-query-generator](https://github.com/austinLorenzMccoy/sql-query-generator) | FastAPI + Groq，够轻，但只做 text-to-SQL，没有领域边界约束，也没有多轮会话 |

不过这几个项目的**设计思路被吸收进来了**：

- queryforge 的「元数据驱动 + SQL 校验与自动修正」→ 本项目的
  `knowledge.py`（结构化元数据）+ `sql_guard` 校验不通过时喂回错误让模型重写
- queryforge 的「无结果兜底节点」→ 本项目的「没查到就直说，不编数据」
- campus-agent 的「SSE 流式 + 会话历史」→ 本项目的 `/kb/chat` 与 `sessions.py`

所以最终方案是：**借鉴模式，按本项目栈重写**。

---

## 十三、许可与素材

- 代码：随本项目走
- 小助手形象：用户提供的三视图精灵图裁切而成，
  裁切脚本见 `kb_assistant/tools/prepare_avatar.py`（纯标准库，无第三方依赖）
