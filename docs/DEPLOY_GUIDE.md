# 学生管理系统 · 上线指引（GitHub 公开仓库 + 云服务器部署）

> 本文档是**操作手册**，按顺序做即可。每一步都给了「为什么」和「怎么验证做对了」。
> 全程约 2～3 小时（不含买服务器、等备案、等证书签发）。

---

## 0. 先看清这个项目的真实形态

在动手之前，你需要知道手里这是个什么东西。这决定了后面所有步骤。

| 层 | 技术 | 端口 | 说明 |
|---|---|---|---|
| 后端 | FastAPI + SQLAlchemy + PyMySQL | 8003 | `main.py` 入口，`import model` 时会自动建表 |
| 数据库 | MySQL 8 | 3306 | 表结构 `sql/01_create_schema.sql`，演示数据 `sql/02_seed_demo_data.sql` |
| 前端 | Vue 3 + TS + Vite + Element Plus | 5173（生产为静态文件） | 走 `/api` 前缀，生产由 Nginx 反代到后端 |
| 小助手 | FastAPI（独立进程） | 8010 | 自然语言 → SQL → 查库 → 回答，**只读账号** `kb_ro` |

**三个关键事实**（决定了部署方案的形状）：

1. **前端是纯静态产物**。`npm run build` 出来的 `dist/` 丢给 Nginx 就行，不需要 Node 常驻。
2. **前端已经写好了反向代理约定**（`frontend/vite.config.ts`）：
   - `/api` → 转发到 `8003`，**并且去掉 `/api` 前缀**（后端真实路径是 `/student/xxx`）
   - `/kb` → 转发到 `8010`，**不前缀**（后端真实路径就是 `/kb/chat`）
   这两条规则**必须原样搬到生产 Nginx**，否则前端全线报错。这是整个部署最容易翻车的地方。
3. **系统目前没有任何鉴权**。后端 API 无登录校验，前端登录页是演示模式（任意账号密码都能进）。
   既然你选了公开仓库 + 部署到公网，**这一条必须先解决**——否则任何人拿到网址就能改你的数据库。见第 3 步。

### 本机环境体检结果（已替你确认）

| 项 | 状态 |
|---|---|
| Git | 2.55.0 ✅ |
| GitHub CLI (`gh`) | 2.103.0 ✅ |
| Docker | 29.8.0 ✅ |
| Node | v26.13.0 ✅（满足 Vite 8 要求） |
| Python | `.venv` 已存在 ✅ |
| Git 全局身份 | `Iphsiibl / iphsiibl@qq.com` ✅ 已配置 |
| 仓库状态 | **尚未 `git init`** ⚠️ |

> ⚠️ **npm 在 PowerShell 里被拦**：报「禁止运行脚本」，因为 `npm.ps1` 撞上执行策略。
> **本机所有 npm 命令请改用 `npm.cmd`**（`npm.cmd run build`）。这不影响服务器上的 Docker 构建。

---

## 1. 第 1 步：先修掉 3 个会「泄漏或报错」的问题

这一步**先于** `git init`。因为一旦提交进历史，敏感内容就很难彻底清干净了。

### 1.1 修 `.gitignore`：前端生产配置被误伤

实测确认的问题：根目录 `.gitignore` 第 3 行 `.env.*` 规则**把 `frontend/.env.production` 和 `frontend/.env.development` 一起忽略了**。

后果很直接：`frontend/.env.production` 里那行 `VITE_API_BASE=/api` 是生产构建的命根子。文件缺失时 Vite 会退化成 `undefined`，前端请求地址全错，页面一个接口都调不通。

修改根目录 `.gitignore`，把这几行：

```gitignore
# 环境变量（含数据库密码、模型 API Key），绝不能提交
.env
.env.*
!.env.example
```

改成：

```gitignore
# 环境变量（含数据库密码、模型 API Key），绝不能提交
.env
.env.*
!.env.example

# 前端的 Vite 配置不是密钥，只是路径前缀，必须提交
# 否则生产构建拿不到 VITE_API_BASE=/api，前端全线崩
!frontend/.env.production
!frontend/.env.development
```

> 顺带一提：`kb_assistant/.env.example` 现在是**能**入库的（第 4 行 `!.env.example` 的取反规则生效了），不用管它。

**验证**（在项目根目录，等 `git init` 之后跑）：

```powershell
git check-ignore -v --no-index frontend/.env.production
```

输出里应该出现 `!frontend/.env.production`（带 `!`），说明规则取反成功。

### 1.2 补 `.env.example`：让别人能跑起来

根目录现在**没有** `.env.example`，但 `.gitignore` 已经预留了 `!.env.example`。新建一个：

```gitignore
# 复制为 .env 后按自己的环境填写。
# .env 已被 .gitignore 忽略，绝不会被提交。

# ---- 数据库 ----
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=student_ms_demo
DB_USER=root
DB_PASSWORD=

# ---- 知识库小助手：模型配置（Anthropic Messages 协议）----
LLM_PROTOCOL=anthropic
LLM_BASE_URL=https://api.minimax.chat/anthropic/v1
LLM_API_KEY=
LLM_MODEL=MiniMax-M3.1-Flash
LLM_TIMEOUT=120
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.3

# ---- 演示数据重置 ----
# 不配 = 重置功能整个关闭（接口返回 404，顶栏不显示按钮）。
# 这是刻意的默认行为：公开部署时忘了配，结果应该是「用不了」而不是「谁都能重置」。
# 配了就多一个「一键回到种子基线」的出口 —— 详见 docs/RESET_GUIDE.md
RESET_TOKEN=

# ---- 小助手服务 ----
KB_ASSISTANT_HOST=127.0.0.1
KB_ASSISTANT_PORT=8010
KB_ASSISTANT_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
KB_ASSISTANT_RELOAD=0
KB_ASSISTANT_LOG_LEVEL=INFO
KB_ASSISTANT_MAX_ROWS=200
KB_ASSISTANT_SQL_TIMEOUT=15
KB_ASSISTANT_MAX_HISTORY=8
KB_ASSISTANT_SHOW_SQL=1
```

> **为什么 `.env` 这么写是安全的**：`.env` 和 `.env.*` 都在忽略列表里，只有 `.env.example` 被显式放行。
> 记住一条铁律：**`.env.example` 里只能出现假值**，真密码和真 Key 永远只进 `.env`。

### 1.3 【公开仓库必做】演示数据说明

`sql/02_seed_demo_data.sql` 里的 1014+ 条数据是 **AI 生成的模拟数据**，不来自任何真实学生。
但它有两个"看起来太真"的地方，公开仓库里建议处理一下：

- 224 行含**真实格式的手机号**（`17208944474`、`18799207667` …）
- 学生姓名是**真实中文姓名**（`李家怡`、`邓强东`、`范浩` …），毕业院校是**真实高校**（西安交通大学、浙江大学 …）

**风险不在法律，而在于「看起来像真的」**——公开后可能被误当成真实学生信息传播。
原则：**保留数据的结构关系，但让值一眼看出是假的**。

替换规则（保持字段格式不变，只换值）：

| 字段 | 现状 | 改成 |
|---|---|---|
| `stu_tel` / `teacher_tel` | 真实格式手机号 | `13800138000` ~ `13800138300`（连续，明显是测试号） |
| `stu_name` | 真实姓名 | `学生001` ~ `学生200`（保留长度约束） |
| `agent_name` / `class_teacher_name` / `teacher_name` | 真实姓名 | `顾问01` ~ `顾问12`、`班主任01` ~、`教师01` ~ |
| `stu_school` | 真实高校 | `示例大学01` ~ `示例大学10` |
| `company` | 真实企业名 | `示例科技01` ~ `示例科技20` |
| `stu_from` / `stu_major` | 真实省市/专业 | 真实值**可保留**（省份和专业名本身不指向个人） |

**执行方式**：建议写个一次性 Python 脚本跑映射表，别手工改 1000 多行。改完后务必验证：

```powershell
# 改完后跑这个，手机号应该一个都不剩
Select-String -Path sql/02_seed_demo_data.sql -Pattern '1[3-9]\d{9}' | Measure-Object | Select-Object -ExpandProperty Count
```

**期望输出：`0`**。

> **不想改数据也行的替代方案**：在 `sql/02_seed_demo_data.sql` 顶部加一行说明，
> 明确告诉读者「本文件为 AI 生成的模拟数据，与真实个人无关」。
> 这比逐行改值省事得多，对绝大多数场景也够用。
>
> ⚠️ 但**手机号建议还是换掉**——随机生成的手机号有概率撞上真实在用的号码，
> 公开后可能有人打过去，属于给陌生人添麻烦。

> ✅ **截图已处理**：`frontend/docs/screenshots/` 已整个删除，
> `frontend/README.md` 里的图片引用也一并改成了文字描述。
> 需要看界面效果请本地跑 `node scripts/capture-screenshots.mjs` 现场生成。

### 1.4 【公开仓库必做】处理文档里的本机路径

只找到 1 处，在 `frontend/README.md:171`：

```
cd <项目根目录>    # 换成你自己机器上的路径，例如 D:\work\student_ms
```

这个是占位示例，**不是真实路径**，留着无妨。但你顺手确认一下 `PROJECT_DOC.md`、`DEBUG_NOTES.md`、`docs/ARCHITECTURE.md`——我已全量扫过，**没有**残留本机绝对路径，手机号也是 0 命中。这三份文档可以放心公开。

### 1.5 补 LICENSE（公开仓库的硬性要求）

根目录现在没有 LICENSE。公开仓库**必须**有许可证，否则别人默认「保留所有权利」，等于不授权。

你的前端复用了 [Geeker-Admin](https://github.com/HalseySpicy/Geeker-Admin)（MIT），所以用 MIT 最一致。新建 `LICENSE`：

```
MIT License

Copyright (c) 2026 Iphsiibl

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> 顺带在 README 里注明前端基于 Geeker-Admin 移植（MIT），保留原作者署名——你的 `frontend/README.md` 第 28-30 行已经写了，保持就好。

### 1.6 补根目录 README.md

现在根目录没有 README，GitHub 仓库首页会空空荡荡，很难看也不专业。至少写清楚：项目是什么、技术栈、怎么跑起来（本地/生产）、目录结构、许可证。内容可以从 `PROJECT_DOC.md` 和 `frontend/README.md` 提炼。

---

## 2. 第 2 步：补上 Dockerfile 与编排文件

项目里目前**完全没有** Docker 相关文件，需要新建 4 个。

### 2.1 部署文件清单（**已创建，可直接用**）

以下 4 个文件已经在项目根目录，**内容已按实测调优过，不需要再改**：

| 文件 | 作用 | 实测结果 |
|---|---|---|
| `Dockerfile.backend` | 主后端 + 小助手共用镜像 | 329 MB |
| `Dockerfile.frontend` | 前端构建 + Nginx 运行（两阶段） | **77.6 MB**（运行层不含 Node） |
| `nginx.conf` | 生产反代配置 | 容器 healthy，四条链路全 200 |
| `.dockerignore` | 防止密钥进镜像 | 实测镜像里**无 `.env`**、有 `.env.example` |
| `docker-compose.yml` | 四服务编排 + 内存限制 | 内存合计 **265 MiB** |

#### `Dockerfile.backend` 要点

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Shanghai
WORKDIR /app
# 先装依赖，利用层缓存（改源码不会触发重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
COPY . .
RUN mkdir -p /app/logs          # 审计日志目录
EXPOSE 8003 8010
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

> ⚠️ **`--host 0.0.0.0`，不是 `127.0.0.1`**。容器内绑 127.0.0.1 会导致外部完全连不上，
> 这是最常见的翻车原因。小助手在 compose 里用 `command` 覆盖成
> `uvicorn kb_assistant.app.main:app --host 0.0.0.0 --port 8010`。

> 💡 **两个服务共用一个镜像**：主后端和 kb_assistant 的依赖只差一个 `httpx`
> （主后端 `requirements.txt` 里本来就有），拆两个镜像要维护两份 Dockerfile。

#### `Dockerfile.frontend` 要点

```dockerfile
# 构建阶段
FROM node:22-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

# 运行阶段（不含 Node、不含 node_modules、不含源码）
FROM nginx:1.27-alpine
COPY frontend/.env.production /app/.env.production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

> ⚠️ **两阶段构建不是可选项**：单阶段镜像会带上 Node 和 node_modules，体积 1GB+。
> 两阶段后只有 **77.6 MB**，服务器拉取和启动都快得多。
>
> ⚠️ **`npm ci` 而不是 `npm install`**：`npm ci` 严格按 lock 文件装精确版本，可复现；
> `npm install` 可能悄悄升级依赖，导致「昨天能构建今天不能」。
> 实测 `npm ci` 在 400 MB 内存下就能跑完。
>
> ⚠️ **必须 COPY `frontend/.env.production`**：那行 `VITE_API_BASE=/api` 是生产构建的命根子。
> 这也是为什么第 1 步要修 `.gitignore`（它原本被误伤了）。

### 2.3 `nginx.conf`（生产反代，**实测踩过两个坑**）

> ⚠️ **坑 1：启动时解析不到后端主机名**
>
> 直觉写法 `proxy_pass http://backend:8003/;` 会让 Nginx 在**启动时**就把
> `backend` 解析成 IP 并固化。但容器刚起来时 Docker 内嵌 DNS 还没写好这条记录，
> Nginx 直接报错退出：
>
> ```
> nginx: [emerg] host not found in upstream "backend"
> ```
>
> 而且 `restart: unless-stopped` **救不回来**——它会一直重启。
> `depends_on` 只保证启动**顺序**，不保证 DNS 记录已生成。
>
> **解法**：写成变量 `$backend_upstream`，配合 `resolver` 延迟到请求时才解析。

> ⚠️ **坑 2：变量形式下 `proxy_pass` 不做 URI 前缀替换**（更隐蔽）
>
> 写成 `proxy_pass http://$backend_upstream:8003/;` 看着像静态写法那样
> "末尾斜杠 = 去掉 `/api` 前缀"，**实际上请求会被转成 `GET /`**，路径全丢。
> 后端日志里能直接看到：
>
> ```
> INFO: 172.18.0.5 - "GET / HTTP/1.1" 404 Not Found
> ```
>
> **解法**：路径处理用**显式 `rewrite`**，`proxy_pass` 不带 URI 部分。
> 语义完全确定，不依赖 `proxy_pass` 的隐式替换规则。

> ⚠️ **坑 3：`set` 指令的位置**
> `resolver` 和 `set` 必须写在 `server` / `location` 块**内部**，
> 写在 `server` 外面会报 `"set" directive is not allowed here`。

**实测验证**：改成下面这样之后，后端日志收到的是正确的路径，四条链路全部 HTTP 200：

```
INFO: 172.18.0.5 - "GET /student/select_stu_skip?skip=0&limit=3 HTTP/1.1" 200 OK
INFO: 172.18.0.5 - "GET /reset/status HTTP/1.1" 200 OK
```

```nginx
server {
    listen 80;
    server_name _;

    # Docker 内嵌 DNS，延迟解析
    # 【注意】resolver 和 set 必须写在 server / location 块内部
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $backend_upstream backend;
    set $kb_upstream kb;

    root /usr/share/nginx/html;
    index index.html;

    # ---------- 前端静态资源 ----------
    location / {
        # SPA history 路由兜底。
        # 少了这行，直接访问 /student 或刷新页面会 404 —— Vue Router 用的是 history 模式。
        try_files $uri $uri/ /index.html;
    }

    # ---------- 主后端 ----------
    location /api/ {
        # 显式去掉 /api 前缀：/api/student/xxx -> /student/xxx
        rewrite ^/api/(.*)$ /$1 break;

        # 【不带】URI 部分，配合上面的 rewrite，路径不会被二次处理
        proxy_pass http://$backend_upstream:8003;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # ---------- 知识库小助手 ----------
    location /kb/ {
        # 【不 rewrite】保留 /kb 前缀 —— 后端路由本来就是 /kb/chat
        proxy_pass http://$kb_upstream:8010;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # 小助手是 SSE 流式返回。
        # 缓冲不开的话，模型生成的回答会一直卡着不出来（要等缓冲满了才吐），
        # 表现为「小助手一直转圈」。
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;

        # 大模型响应慢，超时给足
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

> **`/api` 去前缀、`/kb` 不去前缀** —— 这两条必须和 `frontend/vite.config.ts`
> 的 dev proxy 逐字对应（那边有注释说明）。搞反了就是两个模块一起 404。
> `proxy_buffering off` 是 SSE 的命门，漏了它小助手会「一直转圈直到超时」。

### 2.4 `.dockerignore`（**必须建**）

```dockerignore
# ---- 密钥与配置 ----
.env
.env.*
!.env.example
kb_assistant/.env

# ---- Python ----
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/

# ---- 前端 ----
frontend/node_modules/
frontend/dist/
frontend/.runtime/

# ---- 日志 ----
logs/
kb_assistant/logs/
*.log

# ---- Git / IDE / 文档 / 测试 ----
.git/
.idea/
.vscode/
*.md
docs/
tests/
```

> ⚠️ **`.env` 那一行至关重要**。没有它，`docker build` 会把数据库密码和
> MiniMax Key 打进镜像层——**镜像一旦推到 Docker Hub 或公开 registry，
> 密钥就永久泄漏了，删 commit 也救不回来**。
>
> 养成习惯：**镜像里绝不含密钥，密钥一律运行时通过环境变量注入**。
>
> ✅ **已实测验证**：构建出的后端镜像里 `/app/.env` 不存在，
> 而 `/app/kb_assistant/.env.example` 在（样例该保留）。

### 2.5 `docker-compose.yml`（**已创建**）

完整内容在项目根目录 `docker-compose.yml`。四个服务的关键配置：

| 服务 | 端口映射 | 内存上限 | 依赖 |
|---|---|---|---|
| `db` | **无**（仅内网） | 600 MiB | - |
| `backend` | **无**（仅内网） | 350 MiB | `db` healthy |
| `kb` | **无**（仅内网） | 300 MiB | `db` healthy |
| `frontend` | `80:80` | 100 MiB | `backend`, `kb` |

**四个关键设计：**

1. **只有 `frontend` 映射端口**。公网上只暴露 Nginx 一个入口，
   后端、小助手、MySQL 全部待在内网。攻击者拿不到后端直连地址，也扫不到 3306。

2. **`mem_limit` 必配**。MySQL 默认按物理内存 50% 分配缓冲池，
   2G 机器 = 1G，加上其它进程容易触发 OOM。compose 里同时限制了
   `--innodb-buffer-pool-size=128M` 和 `--max-connections=50`。

3. **`depends_on` + `condition: service_healthy`**。
   主后端 `import model` 时会触发 `create_all(engine)`，启动就要连库建表。
   MySQL 没就绪就起后端，它会直接崩溃。

4. **小助手用 `kb_ro` 只读账号**。它会去执行 LLM 生成的 SQL，
   用 root 的话一条被诱导的 `UPDATE` 就能改正式数据。
   见 2.6。

### 2.6 给小助手建只读账号

小助手会去执行 LLM 生成的 SQL。**如果它用 root 账号，一条被诱导的 `UPDATE` 就能改你的正式数据**——AI 生成 SQL 的攻击面必须靠数据库权限兜住。

在服务器上执行（进 MySQL 容器）：

```bash
docker exec -it stu-ms-db mysql -uroot -p"$DB_PASSWORD" <<'SQL'
CREATE USER IF NOT EXISTS 'kb_ro'@'%' IDENTIFIED BY '换成你的只读密码';
GRANT SELECT ON ${DB_NAME}.* TO 'kb_ro'@'%';
FLUSH PRIVILEGES;
SQL
```

> 注意 `kb_ro`@`%` 的 `%`——容器内网访问来自 Docker 网桥，不是 `localhost`，
> 写成 `'kb_ro'@'localhost'` 会连不上。
> 项目自带 `kb_assistant/app/sql_guard.py` 做只读闸门，是第二层防护；数据库权限是第一层。两层都要有。

---

## 3. 第 3 步：上线前必须解决鉴权问题 ⚠️

**这一步是本指南里唯一的「阻塞项」，请不要跳过。**

现状核查结果：

- 后端 `API/` 下**所有**接口都没有任何鉴权装饰器（已全量搜索 `Depends`/`get_current_user`/`HTTPBearer`/`Authorization`，零命中）
- 前端登录页是**纯演示模式**，任意账号密码都能进，`localStorage` 存个 `stu_ms_user` 就完事
- 小助手同样无鉴权

**如果就这么部署到公网**：任何人都能
1. 直接调 `DELETE /student/delete_stu/{id}` 删你的学生数据；
2. 直接调 `POST /score/...` 篡改成绩；
3. **反复调 `/kb/chat` 烧你的 MiniMax 额度**——这是会真金白银花钱的；
4. 把你库里的学生信息全导走。

### 三个可选方案（按工作量从小到大）

**方案 A：Nginx 层加 Basic Auth（推荐，最快，30 分钟）**

在 Nginx 前面套一层密码。不改任何后端代码：

```nginx
server {
    # ... 原有 location 块不变 ...

    auth_basic           "Student MS";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

生成密码文件（服务器上执行）：

```bash
docker exec stu-ms-frontend htpasswd -cB /etc/nginx/.htpasswd admin
# 交互式输入密码
```

**方案 B：只允许特定 IP 访问**

在云服务器安全组里，只放行你办公网/家宽的 IP。最简单，但换网络就用不了了。

**方案 C：后端加真鉴权（最正规，工作量最大）**

引入 JWT 或 session 中间件，改动 `main.py` 加依赖、给 50+ 个接口加 `Depends`。改动面大，建议**先上 A 保住安全，后续再迭代**。

### 我的建议

**先用方案 A 上线**。它是「不改一行业务代码」就能拿到实效的方案——公开仓库的代码里不需要包含任何密钥或账号，密码放在服务器的 Nginx 容器里。

> 另外提醒：公开仓库意味着**代码是公开的**。任何鉴权方案都不能依赖「代码保密」，只能靠**服务器上的配置**。这正是方案 A 天然满足的。

---

## 4. 第 4 步：本地初始化 Git 并推送到 GitHub

### 4.1 初始化与首次提交

在项目根目录执行：

```powershell
git init
git add -A
git status          # ← 关键：逐行确认没有 .env、没有 node_modules、没有 .venv
```

**`git status` 的输出你要亲眼看一遍。** 预期看到：

```
A  .env.example
A  .gitignore
A  LICENSE
A  README.md
A  API/...
A  Dao/...
A  model/...
A  sql/...
A  frontend/src/...
A  frontend/.env.production      ← 确认它在
A  frontend/package-lock.json
```

**必须确认不在列表里的**（出现任何一项都要停下处理）：

- `.env` ← **数据库密码 + MiniMax Key**
- `kb_assistant/.env` ← 小助手本地覆盖配置
- `frontend/node_modules/`（几十万文件）
- `frontend/dist/`
- `.venv/`
- `__pycache__/`
- `*.log`、`kb_assistant/logs/`
- `frontend/.runtime/`（含本机绝对路径）

> 稳妥起见，提交前跑一次「密钥扫描」：
> ```powershell
> git diff --cached | Select-String -Pattern '(password|api_key|secret|token)\s*[:=]\s*["'']?[A-Za-z0-9_\-]{12,}'
> ```
> 命中的每一行都要人工确认是不是假值。

确认无误后：

```powershell
git commit -m "feat: 学生管理系统 v1 —— FastAPI + Vue3 + 知识库小助手

- 后端: FastAPI + SQLAlchemy + MySQL, 8 个业务模块
- 前端: Vue3 + TS + Element Plus + Vite, 响应式适配
- 小助手: 自然语言查库, 只读账号隔离
- 一键重置: 口令保护 + 审计日志, 演示数据随时回到种子基线
- 含 1018 条模拟演示数据与完整文档"
```

### 4.2 推送到 GitHub（用 gh CLI，一条命令）

```powershell
gh auth login
# 选 GitHub.com → HTTPS → 浏览器登录

gh repo create wolin-stu-ms --public --source=. --remote=origin --push --description "学生管理系统：FastAPI + Vue3 + MySQL，含自然语言查库小助手"
```

`--public` 直接建公开仓库（按你选的方案）。想先建私有、确认无误后再改公开：

```powershell
gh repo create wolin-stu-ms --private --source=. --remote=origin --push
# 确认没问题后，一条命令转公开：
gh repo edit --visibility public
```

**验证**：

```powershell
gh repo view --web        # 打开浏览器看仓库首页
gh secret list            # 确认没有误传任何 secret
```

### 4.3 仓库上线后立刻检查

打开 GitHub 仓库页面，肉眼确认：

1. 搜索框搜 `password` → **没有**命中真实密码
2. 搜索框搜 `sk-` 或 `MINIMAX_API_KEY` → 只有**变量名**，没有**值**
3. 首页 README 正常显示
4. `sql/02_seed_demo_data.sql` 打开，手机号已换成测试号（或顶部已声明是模拟数据）

---

## 5. 第 5 步：服务器准备

### 5.0 【实测结论】2 核 2G 的服务器能不能跑？

**能，而且余量很充裕。** 以下数据来自在 Docker 里**真实跑起来**的完整栈实测
（不是估算）：

| 容器 | 实测内存 | 配置的上限 |
|---|---|---|
| `stu-ms-db`（MySQL 8） | **155 MiB** | 600 MiB |
| `stu-ms-backend`（FastAPI） | **58 MiB** | 350 MiB |
| `stu-ms-kb`（小助手） | **51 MiB** | 300 MiB |
| `stu-ms-frontend`（Nginx） | **14 MiB** | 100 MiB |
| **合计（空闲）** | **≈ 278 MiB** | 1350 MiB |
| **合计（50 并发压测后）** | **≈ 657 MiB** | — |

也就是说：**四个服务空闲时只用了 2GB 里的约 14%**，
压测峰值也只到三分之一。

其它实测数据：

- **零 OOM、零异常重启**（`OOMKilled=false`，`RestartCount=0`）
- **50 并发请求耗时 616 ms**，压测后内存从 278 MiB 涨到 657 MiB（数据库缓冲池预热，属正常）
- **Docker 重启后数据完整保留**（数据卷持久化正常）
- **数据库初始化成功**：200 学生 / 600 成绩 / 134 就业 / 36 班级 / 12 班主任 / 24 老师 / 12 顾问 = **1018 行**
- **重置接口端到端可用**：错误口令 401、正确口令 200
- **前端镜像构建下限 350 MiB**（见下节，这是最大的坑）
- **前端镜像体积 77.6 MiB**（多阶段构建，运行层不含 Node）
- **安全检查通过**：镜像内无 `.env`、无 `kb_assistant/.env`、无个人邮箱；有 `.env.example`

> ⚠️ **但必须显式设置内存上限**，否则 MySQL 默认会按「物理内存的 50%」分配
> InnoDB 缓冲池（2G 机器 = 1G），加上连接池和 Python 进程，
> 很容易触发 OOM Killer 把容器杀掉。`docker-compose.yml` 里已经配好了
> `mem_limit` 和 `--innodb-buffer-pool-size=128M`，**照着用就行**。

#### ⚠️ 最大的坑：在服务器上构建镜像

| 操作 | 内存需求 | 2G 机器 |
|---|---|---|
| **运行时**（跑起来） | ≈ 265 MiB | ✅ 毫无压力 |
| **构建时**（`docker compose build`） | **至少 350 MiB**，实测 350m 可过 | ✅ 能做，但要小心 |

前端构建要跑 Node + Vite + `vue-tsc`，内存消耗比运行时高一个量级。
**实测 350 MiB 就能完整构建成功**（含 `npm ci` + `vue-tsc` 类型检查 + `vite build`）。

但构建时如果 MySQL 也在跑，会叠加占用。所以推荐：

**方案 A（推荐）：在本地构建好，服务器只拉取运行**

```powershell
# 本地（内存充足）
docker compose build
docker save -o stu-ms-images.tar stu-ms-2g-test-backend stu-ms-2g-test-frontend
# 上传到服务器后
docker load -i stu-ms-images.tar
```

**方案 B：服务器上构建，但先停掉数据库**

```bash
docker compose stop db
docker compose build
docker compose up -d
```

**方案 C：给服务器加 Swap（2G 机器强烈建议）**

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
free -h   # 确认 Swap 已生效
```

> Swap 不能代替内存，但它能让你在构建时不被 OOM 直接杀掉。
> 有了 2G Swap，即使构建峰值超了，也是变慢而不是崩。

#### 2 核够用吗？

够。这个项目的负载特点：

- 前端是静态文件，由 Nginx 直接返回，**不占 CPU**
- 后端是 IO 密集（查 MySQL），不是 CPU 密集
- 只有小助手调大模型时是**等网络**，不吃 CPU

实测压测时 4 个容器的 CPU 占用都在 **1% 以下**。

> 💡 **如果这台机器还要跑别的东西**，建议升到 **2 核 4G**：
> 多留 2G 给构建过程和其他服务，内存宽裕很多。
> 只跑这个系统的话，**2 核 2G 完全够**。

### 5.1 买服务器

**推荐配置**（国内阿里云/腾讯云轻量应用服务器即可）：

| 项 | 建议 | 说明 |
|---|---|---|
| CPU / 内存 | 2 核 2G 起步，**建议 2 核 4G** | MySQL + 2 个 FastAPI + Nginx + 构建前端 |
| 系统 | Ubuntu 22.04 / 24.04 LTS | Docker 生态最顺 |
| 带宽 | 3～5 Mbps 起 | 静态资源为主，够用 |
| 硬盘 | 40G+ | 前端构建需要空间 |
| 地区 | 就近（国内选国内） | 国内访问快；小助手调 MiniMax 也快 |

> **预算参考**：轻量应用服务器 2核4G 通常 ¥100～200/年，首年常有促销。
>
> ⚠️ **如果服务器在中国大陆**：用域名直接访问 80/443 端口，**必须先完成 ICP 备案**（约 1～3 周）。
> 想跳过备案，两个选择：① 买**香港/海外**节点；② 继续用 `http://IP:80` 访问，备案后再上域名。
> 备案是硬性要求，不备案用域名访问会被拦截。

### 5.2 装 Docker

```bash
ssh root@你的服务器IP

# 换源（国内机器必做，否则拉镜像极慢）
apt update && apt install -y apt-transport-https ca-certificates curl gnupg
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

docker --version && docker compose version
```

### 5.3 安全组：只开 22 / 80 / 443

在云服务商控制台配安全组入方向规则：

| 端口 | 协议 | 源 | 用途 |
|---|---|---|---|
| 22 | TCP | **你的 IP**（或 0.0.0.0/0） | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP（后续跳 HTTPS） |
| 443 | TCP | 0.0.0.0/0 | HTTPS |

**3306 / 8003 / 8010 一律不开** —— 数据库根本不映射到宿主机，后端和小助手也只在 Docker 内网。

---

## 6. 第 6 步：拉代码、配置密钥、启动

### 6.1 拉代码

```bash
git clone https://github.com/你的用户名/wolin-stu-ms.git
cd wolin-stu-ms
```

### 6.2 创建服务器端 `.env`（**唯一存放真实密钥的地方**）

```bash
cp .env.example .env
nano .env
```

填入：

```ini
DB_HOST=db
DB_PORT=3306
DB_NAME=student_ms_demo
DB_USER=root
DB_PASSWORD=换成强密码

# 小助手只读账号（先用 root 跑通，再按 2.6 建 kb_ro）
KB_DB_USER=root
KB_DB_PASSWORD=换成强密码

LLM_PROTOCOL=anthropic
LLM_BASE_URL=https://api.minimax.chat/anthropic/v1
LLM_API_KEY=你的真实MiniMaxKey
LLM_MODEL=MiniMax-M3.1-Flash
```

```bash
chmod 600 .env    # 只有属主可读
```

> ⚠️ 这个 `.env` 在**服务器上**，由 `.gitignore` 保护，**永远不会进 Git**。这是整套流程的安全基石。

### 6.3 构建并启动

```bash
docker compose build
docker compose up -d
docker compose ps          # 看四个容器是否都 Up
```

**首次启动时**，MySQL 容器会自动执行 `/docker-entrypoint-initdb.d/` 里的两个 SQL：建表 + 灌 1018 条演示数据。

> ⚠️ **`/docker-entrypoint-initdb.d/` 只在数据卷为空时执行一次。** 以后改 SQL 不会重新跑。
> 需要重灌数据时：`docker compose down -v`（**会删数据卷，慎用**）再 `up -d`。

> ⚠️ **实测踩过的字符集坑（已修复）**
>
> Docker 里首次初始化曾报：
>
> ```
> ERROR 3819 (HY000) at line 156: Check constraint 'ck_stu_sex' is violated.
> ```
>
> 现象极具迷惑性：种子数据里的性别值**明明全是 男/女**，
> 但 200 条学生数据**一条都插不进去**。表结构里能看到乱码：
>
> ```
> CONSTRAINT `ck_stu_sex` CHECK (((`stu_sex` is null) or (`stu_sex` in (_latin1'?',_latin1'?'))))
> ```
>
> **根因**：建表语句里的 CHECK 约束含中文常量 `'男'` / `'女'`。
> MySQL 执行 SQL 文件时，连接字符集由**客户端**决定。
> 本地用 Navicat / PyMySQL(utf8mb4) 执行都正常，
> 但 Docker 的 initdb 用的是 mysql 客户端默认字符集，把中文常量按 `_latin1` 存了进去。
>
> **关键点**：`/docker-entrypoint-initdb.d/` 里**每个文件是独立进程**，
> 所以 `02_seed_demo_data.sql` 里的 `SET NAMES utf8mb4` **不会**影响 `01_create_schema.sql`。
> 每个建表/灌数据的 SQL 文件都必须**自己**声明字符集。
>
> ✅ **已修复**：`sql/01_create_schema.sql` 开头已加上 `SET NAMES utf8mb4;`。
> 修复后约束变成 `_utf8mb4`，数据正常灌入（200 学生 / 600 成绩 / 134 就业）。
>
> 💡 **你本机的数据库没受影响**——它是用 PyMySQL(utf8mb4) 建的，约束本来就是对的。

### 6.4 验证四个服务

```bash
# 1) 数据库
docker compose logs db | tail -20
docker exec -it stu-ms-db mysql -uroot -p"$DB_PASSWORD" -e "USE student_ms_demo; SELECT COUNT(*) FROM student_info;"
#    期望：200

# 2) 主后端
curl http://127.0.0.1/api/student/select_stu_skip?skip=0
#    期望：JSON 数组

# 3) 小助手
curl http://127.0.0.1/kb/health
#    期望：JSON，含 "status": "ok"，且 config_sources 显示 LLM_API_KEY 来自环境变量

# 4) 前端
curl -I http://127.0.0.1/
#    期望：HTTP/1.1 200 OK

# 5) 重置功能（如果配了 RESET_TOKEN）
curl http://127.0.0.1/api/reset/status
#    期望：{"enabled": true, ...}
#    没配的话是 {"enabled": false, ...} —— 这是正常的
```

浏览器打开 `http://服务器IP/`，登录 `admin` / `123456`，逐页点一遍。

### 6.5 「别人删了我的数据」怎么救

系统**内置了一键重置**：登录后台，顶栏右侧有个 ⟲ 按钮，点开输入口令 + 确认短语 `RESET`，
就能把数据库恢复到种子基线（1018 行）。

前提是服务器 `.env` 里配了 `RESET_TOKEN`：

```bash
# 生成一个强口令
openssl rand -base64 24

# 写进服务器上的 .env
echo "RESET_TOKEN=把上面那串填进来" >> .env
docker compose up -d
```

> **不配也能上线**，只是没有这个按钮。配了就多一道「数据被搞乱」的保险。
>
> 三道安全闸门、口令校验、审计日志的完整说明见 **[`docs/RESET_GUIDE.md`](RESET_GUIDE.md)**。

---

## 7. 第 7 步：域名与 HTTPS

### 7.1 域名解析

给域名加一条 A 记录，指向服务器公网 IP。国内还需完成 **ICP 备案**才能正常访问。

### 7.2 申请证书

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d 你的域名 -d www.你的域名 --agree-tos -m 你的邮箱
```

Certbot 会自动改写 Nginx 配置、加上证书路径、配置 80→443 跳转。

> Docker 里的 Nginx 由容器托管，Certbot 改的是**宿主机**的 Nginx，两者不是一套。
> **两种做法**（选一）：
> - **简单版（推荐先跑通）**：宿主机 Nginx 作入口 → `proxy_pass http://127.0.0.1:80`（转给 Docker 里的 Nginx）。证书在宿主机，配置简单。
> - **规范版**：把证书挂载进容器，容器内 Nginx 直接用。

验证续期：

```bash
certbot renew --dry-run
```

### 7.3 生产环境小改：后端连的是容器里的 MySQL

如果用了宿主机 Nginx 反代 Docker，**后端无需改动**——它连的是 `db` 这个容器，仍然走 Docker 内网。只有反向代理那一层的位置变了。

---

## 8. 第 8 步：日常运维

### 8.1 常用命令

```bash
docker compose ps                       # 看状态
docker compose logs -f backend          # 看后端日志（Ctrl+C 退出跟随）
docker compose logs -f kb               # 看小助手日志
docker compose restart backend           # 重启单个服务
docker compose up -d --build            # 改完代码后重新构建部署
docker compose down                     # 停止（保留数据）
```

### 8.2 数据备份（必做）

数据库在 Docker 卷里，**服务器坏了数据就没了**。写个备份脚本：

```bash
cat > /opt/backup-stu-ms.sh <<'EOF'
#!/bin/bash
BACKUP_DIR=/opt/stu-ms-backups
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
docker exec stu-ms-db mysqldump -uroot -p"$DB_PASSWORD" \
  --single-transaction --routines --triggers student_ms_demo \
  | gzip > "$BACKUP_DIR/stu_ms_$STAMP.sql.gz"
# 只保留最近 30 份
ls -t "$BACKUP_DIR"/*.sql.gz | tail -n +31 | xargs -r rm --
EOF
chmod +x /opt/backup-stu-ms.sh
```

挂到 crontab，每天凌晨 3 点跑：

```bash
crontab -e
# 加一行
0 3 * * * /opt/backup-stu-ms.sh >> /var/log/stu-ms-backup.log 2>&1
```

> `mysqldump` 加 `--single-transaction` 才能在 InnoDB 上做到**不锁表**的一致性备份。

### 8.3 更新上线流程

以后改了代码，完整流程：

```bash
# 本地
git add -A && git commit -m "..." && git push

# 服务器
cd wolin-stu-ms
git pull
docker compose up -d --build
```

---

## 9. 最终检查清单

上线前逐项打勾：

**安全**
- [ ] `.env` 不在任何一次提交里（`git log --all --full-history -- .env` 应无输出）
- [ ] 演示数据已处理（手机号换成测试号，或至少在文件顶部声明是模拟数据）
- [ ] 截图已删除（`frontend/docs/screenshots/` 已移除，README 引用已改成文字）
- [ ] 小助手用 `kb_ro` 只读账号，不是 root
- [ ] Nginx 已加 Basic Auth 或已限制访问 IP
- [ ] 服务器 `.env` 权限 600
- [ ] 安全组只开 22/80/443

**数据自愈**
- [ ] 服务器 `.env` 里配了 `RESET_TOKEN`（否则「别人删了数据」没有一键恢复的出口）
- [ ] `curl http://域名/api/reset/status` 返回 `enabled: true`
- [ ] 审计日志目录已挂载到宿主机（`./logs:/app/logs`），容器重建不丢日志

**Docker**
- [ ] `docker compose ps` 四个容器都是 Up，frontend 是 healthy
- [ ] `docker compose logs db` 里**没有** `Check constraint ... is violated`
- [ ] 数据库行数正确：`student_info=200 scores=600 employment=134`
- [ ] `docker compose logs backend | grep 'GET /'` 能看到 `/student/xxx` 而不是 `GET /`
- [ ] 镜像里没有密钥：`docker run --rm --entrypoint sh <backend镜像> -c "ls /app/.env"` 应报「不存在」
- [ ] `docker stats` 内存合计 < 800 MiB

**功能**
- [ ] `/api/xxx` 反代正常（路径前缀已去掉）
- [ ] `/kb/chat` 反代正常（路径前缀保留，SSE 不缓冲）
- [ ] 小助手能正常问答
- [ ] 前端刷新不白屏（SPA 兜底生效）
- [ ] 全部页面逐个点过

**仓库**
- [ ] README.md 存在且完整
- [ ] LICENSE 存在
- [ ] `.env.example` 存在且**只有假值**
- [ ] `frontend/.env.production` 已提交

**运维**
- [ ] 备份脚本已配 crontab
- [ ] 证书自动续期已验证（`certbot renew --dry-run`）

---

## 10. 常见问题速查

| 现象 | 原因 | 解决 |
|---|---|---|
| 容器起不来，日志 `Can't connect to MySQL` | MySQL 还没就绪 | `depends_on` 配 `condition: service_healthy` |
| 容器起不来，外部连不上 | uvicorn 绑了 127.0.0.1 | 改 `--host 0.0.0.0` |
| 前端 404，接口全挂 | Nginx 没去掉 `/api` 前缀 | `proxy_pass http://backend:8003/;` 末尾斜杠不能少 |
| 小助手 404 | Nginx 错误地去掉了 `/kb` 前缀 | `proxy_pass http://kb:8010;` **不带**末尾斜杠 |
| 小助手一直转圈 | SSE 被缓冲 | 加 `proxy_buffering off;` |
| 前端刷新页面白屏 | 缺 SPA 兜底 | 加 `try_files $uri $uri/ /index.html;` |
| 小助手答不了 | Key 没生效 | `curl /kb/health` 看 `config_sources` |
| 本机 `npm` 报「禁止运行脚本」 | PowerShell 执行策略 | 改用 `npm.cmd` |
| 改了 SQL 但没生效 | initdb 只跑一次 | `docker compose down -v && docker compose up -d`（**删数据**）|
| MySQL 初始化报 `ck_stu_sex is violated` | 建表时连接字符集不对，中文常量被存成 latin1 | `sql/01_create_schema.sql` 开头加 `SET NAMES utf8mb4;`（**已修复**）|
| Nginx 反复重启，日志 `host not found in upstream` | 启动时 DNS 还没就绪 | 用变量形式 upstream + resolver（**已修复**）|
| Nginx 反复重启，日志 `"set" directive is not allowed here` | `set` 写在了 server 块外面 | 把 `resolver` / `set` 移进 server 块内部（**已修复**）|
| 前端接口全 404，后端日志显示 `GET /` | 变量形式 proxy_pass 不做前缀替换 | 用显式 `rewrite ^/api/(.*)$ /$1 break;`（**已修复**）|
| `kb_ro` 连不上 | 授权 host 写错 | 用 `'kb_ro'@'%'`，不是 `'localhost'` |
| 顶栏没有 ⟲ 重置按钮 | 服务器没配 `RESET_TOKEN` | 这是设计意图（功能默认关闭）。配置后重启：`docker compose up -d` |
| 点重置返回 404 | 同上，功能未启用 | 同上 |
| 点重置返回 401 | 口令不对 | 检查服务器 `.env` 里的 `RESET_TOKEN` |
| 审计日志找不到 | 容器没挂载 `logs/` 目录 | compose 里加 `- ./logs:/app/logs`，然后 `mkdir -p logs` |

---

## 附：执行顺序速览

```
第 1 步  修 .gitignore + 补 .env.example + 处理演示数据 + 补 LICENSE/README  ← 本地
第 2 步  写 Dockerfile ×2 + nginx.conf + .dockerignore + compose.yml     ← 本地
第 3 步  加鉴权（Nginx Basic Auth 最快）                                  ← 本地/服务器
第 4 步  git init → 检查 git status → commit → gh repo create --public    ← 本地
第 5 步  买服务器 → 装 Docker → 配安全组                                 ← 服务器
第 6 步  clone → 建 .env（含 RESET_TOKEN）→ docker compose up -d → 验证   ← 服务器
第 7 步  域名解析 + ICP 备案 + certbot HTTPS                             ← 服务器
第 8 步  备份脚本 + crontab + 更新流程                                    ← 服务器
```

**顺序有讲究**：数据处理必须在第 4 步（提交）之前完成；
鉴权必须在第 6 步（上线）之前完成；
`RESET_TOKEN` 也要在第 6 步配好（否则线上没有一键恢复的出口）；
备份必须在第 7 步（拿到域名）之后、正式放流量之前配好。

---

*文档生成时间：2026-11-06 ｜ 项目版本：wolin_stu_ms_v1*
*本指引基于对项目实际代码的核查（配置、依赖、路由、gitignore 实际行为、截图内容）*
