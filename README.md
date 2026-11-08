# 学生管理系统

一套前后端分离的学员管理系统。后端 FastAPI + MySQL，前端 Vue 3 + Element Plus，
外加一个「用自然语言查库」的知识库小助手。

支持学生、成绩、就业、班级、班主任、授课老师、招生顾问七个业务模块的完整增删改查，
带统计分析看板和数据大屏。

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.10+ | 跑 FastAPI 后端 |
| Node.js | **20.19+ 或 22.12+** | Vite 8 的硬性要求，版本低了会报一堆看不懂的错 |
| MySQL | 5.7+ / 8.x | 数据源 |

### 四步跑起来

```powershell
# 第 1 步：建库 + 灌 1018 条演示数据（自动建 student_ms_demo 库）
python sql/run_sql.py

# 第 2 步：装后端依赖
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 第 3 步：填数据库配置
copy .env.example .env      # Windows
# 然后编辑 .env 里的 DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD

# 第 4 步：装前端依赖 + 启动
cd frontend
npm install
.\scripts\start-all.ps1
```

打开 <http://localhost:5173>。

**登录是演示模式**，任意账号密码都能进（预填 `admin` / `123456`）。

> 也可以分两个终端手动启动：
> ```powershell
> # 终端 1 —— 后端（项目根目录）
> .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8003
>
> # 终端 2 —— 前端
> cd frontend && npm install && npm run dev
> ```

### Docker 一键部署

```bash
cp .env.example .env      # 填 DB_PASSWORD / LLM_API_KEY / RESET_TOKEN
docker compose up -d
```


---

## 技术栈

| 层 | 选型 | 版本 |
|---|---|---|
| 后端框架 | FastAPI | 0.162 |
| ORM | SQLAlchemy | 2.1 |
| 数据库 | MySQL | 8.x |
| 前端框架 | Vue 3（`<script setup>`） | 3.5 |
| 语言 | TypeScript | 6.0 |
| 组件库 | Element Plus | 2.14 |
| 状态管理 | Pinia | 4.1 |
| 图表 | ECharts + vue-echarts | 6.1 |
| 构建 | Vite | 8.3 |
| UI 模板 | [Geeker-Admin](https://github.com/HalseySpicy/Geeker-Admin)（MIT） | — |

---

## 目录结构

```
.
├── main.py                 后端入口，FastAPI 应用 + 路由注册
├── database.py             数据库连接与会话管理（唯一管"怎么连库"的文件）
├── API/                    接口层：8 个业务模块 + 1 个数据重置
├── Dao/                    数据访问层：SQL 都在这层
├── model/                  ORM 实体（import 时自动建表）
├── schema/                 Pydantic 请求/响应模型
├── utils/
│   └── reset_service.py    演示数据重置的核心逻辑
├── sql/
│   ├── 01_create_schema.sql   建库 + 建 7 张表（含外键、CHECK、索引）
│   ├── 02_seed_demo_data.sql  1018 条模拟演示数据
│   └── run_sql.py             一键执行上面两个
├── kb_assistant/           知识库小助手（独立进程，独立端口）
├── frontend/               Vue 3 前端
├── tests/                  pytest 测试
├── docs/
│   ├── DEPLOY_GUIDE.md     上线指引
│   ├── RESET_GUIDE.md      数据重置机制说明
│   └── ARCHITECTURE.md     架构详解
└── docker-compose.yml      生产编排
```

---

## 核心设计

### 前后端分离，跨域由反向代理解决

前端开发走 Vite 代理，生产走 Nginx 反代，**后端代码一行都不用改**（不用加 CORS 中间件）。
两条代理规则必须严格对应：

| 前缀 | 转发到 | 前缀处理 |
|---|---|---|
| `/api` | 后端 `:8003` | **去掉** `/api`（后端真实路径是 `/student/xxx`） |
| `/kb` | 小助手 `:8010` | **保留** `/kb`（后端真实路径就是 `/kb/chat`） |

### 响应适配层（`frontend/src/api/http.ts`）

后端各模块历史上返回格式不统一（有 7 种形状），适配层在 Axios 拦截器里统一拆包，
业务层永远只看到一种形状 `{code, message, data, total}`。
**后端改返回格式，只需要改这一个文件。**

### 演示数据一键重置

部署到公网后，被人软删了、改坏了字段值、塞了垃圾行，都能一键恢复。
三道安全闸门：口令 + 确认短语 + **未配置即关闭**（默认行为是安全的那个）。
每次操作写审计日志。详见 **[docs/RESET_GUIDE.md](docs/RESET_GUIDE.md)**。

### 小助手用只读账号

小助手会执行大模型生成的 SQL，所以它连的是**只有 SELECT 权限**的独立账号 `kb_ro`，
和主后端的可写账号隔离。数据库权限是第一层防护，代码里的 `sql_guard.py` 是第二层。

---

## 验证

```powershell
cd frontend
npm run build      # 类型检查 + 生产构建，必须零错误
npm run verify     # 接口层端到端验证
node scripts/check-api-paths.mjs   # 拿后端 openapi.json 逐条比对前端接口路径
```

```powershell
# 后端
pytest
```

---

## 文档

| 文档 | 内容 |
|---|---|
| [docs/DEPLOY_GUIDE.md](docs/DEPLOY_GUIDE.md) | 上线指引：GitHub 公开仓库 + 云服务器 Docker 部署 |
| [docs/RESET_GUIDE.md](docs/RESET_GUIDE.md) | 演示数据重置机制 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构详解 |
| [frontend/README.md](frontend/README.md) | 前端完整文档 |
| [kb_assistant/README.md](kb_assistant/README.md) | 小助手完整文档 |
| [PROJECT_DOC.md](PROJECT_DOC.md) | 项目总文档 |

---

## 数据说明

`sql/02_seed_demo_data.sql` 里的 **1018 条数据全部是模拟生成的**，不来自任何真实个人。
姓名、手机号、院校、公司名都是程序生成的示意值。

---

## 许可证

[MIT](LICENSE)

前端界面骨架移植自 [Geeker-Admin](https://github.com/HalseySpicy/Geeker-Admin)（MIT，Copyright (c) 2022 Halsey）。
