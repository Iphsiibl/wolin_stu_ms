# 学生管理系统 · 前端

一套与 FastAPI 后端**完全分离**的管理后台前端。后端代码一行未改，跨域问题由前端开发代理 / 生产 Nginx 反代解决。

---

## 一、技术栈

| 层次    | 选型                      | 版本            | 为什么                                    |
| ----- | ----------------------- | ------------- | -------------------------------------- |
| 框架    | Vue 3（`<script setup>`） | 3.5.44        | 模板语法 `{{ }}` 与熟悉的 Jinja2 心智模型一致，上手成本最低 |
| 语言    | TypeScript              | 6.0.3         | 接口字段能在编译期被校验，后端改字段会直接报错而不是白屏           |
| 组件库   | Element Plus            | 2.14.7        | 企业中后台 CRUD 的事实标准，中文文档最全                |
| 状态管理  | Pinia                   | 4.1.0         | 比 Vuex 样板代码少一大半                        |
| 路由    | Vue Router 4            | 4.6.4         | 官方标配，支持懒加载与路由守卫                        |
| HTTP  | Axios                   | 1.21.0        | 拦截器是本次适配层能收敛复杂度的关键                     |
| 图表    | ECharts + vue-echarts   | 6.1.0 / 8.3.2 | 统计看板需要折线/柱状/饼图，ECharts 覆盖最全            |
| 构建    | Vite                    | 8.3.5         | 冷启动毫秒级，dev proxy 天然解决跨域                |
| 类型检查  | vue-tsc                 | 3.3.13        | `npm run build` 会先跑它，类型错误直接挡住构建        |
| UI 模板 | **Geeker-Admin**（MIT）   | -             | 直接复用其布局骨架 / ProTable / 样式层，详见下一节       |

> 为什么不是 React + Ant Design？Ant Design 6 在视觉精致度与国际化生态上确实更强，
> 但 Element Plus 更贴合国内中后台 CRUD 场景，中文社区与文档密度更高，
> 且 Vue 的模板语法对 Python 开发者更友好。取舍的标准是「上手快 + 改得动」。

### UI 模板：复用了 Geeker-Admin 的什么

界面骨架直接来自开源项目 [Geeker-Admin](https://github.com/HalseySpicy/Geeker-Admin)
（MIT License, Copyright (c) 2022 Halsey）。复用而不是手搓，是因为它把「中后台长什么样」
这件事已经做完了，而且 MIT 协议允许自由使用与修改。

**直接复用（几乎原样搬过来）**

| 复用件 | 位置 | 说明 |
|---|---|---|
| 样式层 | `src/styles/{reset,common,element,element-dark}.scss` | 卡片 / 表格 / 弹窗 / 滚动条 / 间距工具类的微调 |
| 布局骨架 | `src/layouts/LayoutVertical/` + `src/layouts/components/` | 竖向布局：左侧图标菜单、顶栏工具组、多页签、内容区 |
| ProTable | `src/components/ProTable/` | 搜索表单 + 工具栏 + 表格 + 分页 的封装，7 个列表页共用 |
| SearchForm | `src/components/SearchForm/` | 搜索表单栅格布局 + 展开/收起 |
| 图标字体 | `src/assets/iconfont/` | 顶栏用的 iconfont |
| 配色算法 | `src/utils/color.ts` | 由主色自动推导 Element Plus 的 light-3~9 / dark-2 色阶 |

**按本项目改写的**

- 菜单与面包屑：Geeker 从后端菜单接口取数据，本项目**从路由表推导**（`src/stores/modules/auth.ts`），
  加一个页面只要改路由表，菜单和面包屑自动跟着变
- **菜单层级自动扁平化**：某个模块下只有 1 个页面时，不再套一层可展开的二级菜单，
  直接把这个页面提升成顶级菜单项（「统计分析 → 统计分析」变成一个「统计分析」）；
  有 2 个以上页面的模块（学生管理、班级管理）才保留二级菜单。面包屑也会同步跳过被提升的父级，
  不会出现两个同名节点
- 登录态：Geeker 接的是 token 认证，本项目后端没有鉴权接口，改为接原有的 `src/store/user.ts`
- 多页签：Geeker 的页签列表存在 store 里，本项目同样照搬，但刷新后不保留
- 去掉了 Geeker 里用不到的部分：多语言切换、暗黑模式抽屉、消息中心、主题换肤、代码编辑、富文本

**主色**：Geeker 默认是 `#009688`（Material Teal 500）。本项目后来整体换成了
「教务墨册」视觉——主色改为墨色 `#1E2C3A`（主按钮 / 结构 / 分页当前页），
朱砂 `#C0392B` 只留给激活态、预警与删除，靛 / 紫 / 赭 / 青 承担数据语义色。
改主色只需改 `src/config/index.ts` 的 `DEFAULT_PRIMARY`；
完整设计 token 在 `src/styles/theme.css`。

> 移植时做了两件额外的事：① Geeker 的 `tsconfig` 关掉了 `noImplicitAny`，
> 而本项目开着，所以移植过来的组件都补了显式类型标注；② Geeker 用了 `vue-i18n`，
> 本项目没装，所有 `$t("...")` 都换成了中文文案。

---

## 二、目录结构

```
frontend/
├── index.html                     入口，title = 学生管理系统，lang = zh-CN
├── vite.config.ts                 dev server + /api 反向代理 + @ 路径别名
├── tsconfig.app.json              TS 配置，含 paths 别名
├── .env.development               开发环境变量（/api 前缀 + 后端地址）
├── .env.production                生产环境变量（只写 /api 前缀，不暴露后端地址）
├── .nvmrc                         建议的 Node 版本（配合 nvm use）
├── scripts/
│   ├── start-all.ps1              ★ 一键启动前后端（会检查环境、装依赖、等后端就绪）
│   ├── capture-screenshots.mjs     用系统 Edge 无头模式自动重拍 docs/screenshots/（1920x1080）
│   ├── verify-api.mjs             API 层端到端验证（78 项断言）
│   ├── check-api-paths.mjs        ★ 拿后端 openapi.json 逐条比对前端写的每个接口路径（查断链）
│   ├── gen-api-meta.mjs           ★ 从 openapi.json 重新生成 types/api-meta.ts（接口速查表）
│   ├── reset-demo-data.sql        ★ 演示数据复位：清掉后端并发调试写进正式库的测试数据
│   └── test-422.mjs               422 错误中文化验证（打真实后端）
├── docs/                          （空目录占位：截图不入库，需本地自行生成）
└── src/
    ├── main.ts                    应用入口：Element Plus / Pinia / Router / 全局样式
    ├── App.vue                    根组件，只放一个 <router-view>
    ├── api/                       ★ 接口层（每个后端模块一个文件）
    │   ├── http.ts                核心适配层：响应归一化 + 错误中文化
    │   ├── student.ts  score.ts  employment.ts  class.ts  teacher.ts  stat.ts
    ├── types/
    │   ├── common.ts              ApiResult / ApiErrorBody / ValidationErrorItem
    │   ├── models.ts              Student / Score / Employment / ClassInfo ... 类型
    │   └── api-meta.ts            后端 8 个模块 / 50 个接口的速查表（由 scripts/gen-api-meta.mjs 自动生成）
    ├── utils/
    │   ├── format.ts              金额、日期、百分比格式化
    │   ├── mappers.ts             ★ 中文字段 -> 英文字段的纯映射函数
    │   ├── color.ts               主色 -> Element Plus 色阶推导
    │   ├── icons.ts               路由 meta.icon（字符串）-> 图标组件
    │   ├── logger.ts              ★ 前端可观测日志：环形缓冲 + console/HTTP 采集
    │   ├── proTable.ts            ProTable 单元格工具（枚举格式化 / 列属性过滤）
    │   └── table.ts               ProTable 配套：uuid / prop 取值 / 分页形状转换
    ├── components/                ★ 移植自 Geeker-Admin 的通用组件
    │   ├── ProTable/              搜索 + 工具栏 + 表格 + 分页 的封装
    │   ├── SearchForm/            搜索表单（栅格 + 展开收起）
    │   ├── LogPanel/              ★ 运行日志抽屉（级别过滤 / 搜索 / 复制）
    │   └── Grid/                  响应式栅格容器
    ├── hooks/
    │   ├── useTable.ts             表格数据/分页/查询状态机
    │   └── useSelection.ts         表格多选状态
    ├── stores/modules/            ★ 布局相关状态
    │   ├── auth.ts                菜单树 + 面包屑（由路由表推导）
    │   ├── global.ts              侧栏折叠 / 面包屑 / 页签开关
    │   ├── tabs.ts                 多页签列表
    │   └── keepAlive.ts            页面缓存名单
    ├── store/user.ts              Pinia 登录态（localStorage: stu_ms_user）
    ├── router/index.ts            9 组路由（含独立大屏 /screen）+ 登录守卫
    ├── layouts/
    │   ├── BasicLayout.vue        布局入口（渲染竖向布局）
    │   ├── LayoutVertical/        ★ 竖向布局：logo + 图标菜单 + 顶栏 + 页签
    │   └── components/             ★ Header / Menu / Tabs / Main / Footer
    ├── styles/
    │   ├── index.scss              样式入口（Geeker 的 reset/common/element/dark）
    │   ├── theme.css               本项目的设计 token 与补充样式
    │   └── {reset,common,element,element-dark}.scss   Geeker 原件
    ├── assets/iconfont/            iconfont 字体
    └── views/
        ├── login/LoginView.vue
        ├── dashboard/DashboardView.vue
        ├── student/{StudentListView,AgentListView}.vue
        ├── score/ScoreListView.vue
        ├── employment/EmploymentListView.vue
        ├── class/{ClassListView,ClassTeacherListView}.vue
        ├── teacher/TeacherListView.vue
        ├── stat/StatAnalysisView.vue
        ├── screen/ScreenView.vue      ★ 数据大屏（独立路由，不套布局）
        └── error/NotFoundView.vue
```

---

## 三、跑起来

### 方式 A：一键启动（推荐，也是交接时最省事的）

```powershell
cd frontend
.\scripts\start-all.ps1
```

脚本会依次做这些事，任何一步不满足都会**明确告诉你缺什么**：

1. 检查 Node 版本（低于 `^20.19.0 || >=22.12.0` 直接报错退出）
2. 检查 `node_modules`，没有就自动 `npm install`
3. 检查 Python 虚拟环境 `.venv` 和数据库配置 `.env`
4. 后台拉起 FastAPI，等它**真正能响应且能查到数据库**才继续
5. 前台拉起 Vite（`localhost:5173`），`Ctrl+C` 时把后端一起停掉

如果后端已经手动跑着，加 `-SkipBackend` 只起前端：

```powershell
.\scripts\start-all.ps1 -SkipBackend
```

### 方式 B：分两个终端手动启动

**终端 1 —— 后端**

```powershell
cd <项目根目录>    # 换成你自己机器上的路径，例如 D:\work\student_ms
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8003
```

**终端 2 —— 前端**

```powershell
cd <项目根目录>\frontend
npm install     # 首次
npm run dev     # -> http://localhost:5173
```

> **PATH 提示**：Node.js 装在 `C:\Program Files\nodejs`，
> 新开的 PowerShell 里如果提示找不到 npm，先执行
> `$env:PATH = "C:\Program Files\nodejs;$env:PATH"`。
> （`start-all.ps1` 会自己处理这个，不用手动设。）

### 登录

演示模式，**任意账号密码都能进**（预填 `admin` / `123456`）。

---

## 三·补、把这个工程交给别人（全新环境从零跑起来）

给同事 / 换台机器时，**给对方整个项目根目录**（不是只给 `frontend/`），
因为前端依赖后端接口、后端依赖数据库。

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Node.js | **20.19+ 或 22.12+** | Vite 8 的硬性要求，版本低了会报一堆看不懂的错。`package.json` 的 `engines` 字段已声明，也有 `.nvmrc` |
| Python | 3.10+ | 跑 FastAPI 后端 |
| MySQL | 5.7+ / 8.x | 后端数据源 |

### 四步走

```powershell
# 第 1 步：建库 + 灌 1018 条测试数据（项目根目录执行）
#         不用连我的数据库，这一步会自己建一个 student_ms_demo 库
python sql/run_sql.py

# 第 2 步：装后端依赖
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 第 3 步：填数据库配置（项目根目录的 .env）
#         DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
#         注意 .env 已被 .gitignore 忽略，不会跟着 git 走，
#         对方需要自己建一份（可以让对方照抄你机器上的，或改库名/账号）

# 第 4 步：装前端依赖 + 启动
cd frontend
npm install
.\scripts\start-all.ps1
```

打开 http://localhost:5173 就能用了。

### 交接时要注意的几件事

1. **`.env` 里有数据库密码。** 它在 `.gitignore` 里，**走 git 传递不会带出去**；
   但**直接拷贝文件夹会带出去**。给不完全信任的人时，记得手动删掉 `.env`，
   让对方自己填。

2. **`node_modules/` 和 `dist/` 不用给。** 两者加起来几百 MB，
   对方 `npm install` 和 `npm run build` 重新生成即可。
   走 git 的话 `.gitignore` 已经排除了；拷贝文件夹的话记得手动删。

3. **`sql/` 目录要一起给。** 这是接手的人能独立跑起来的关键 ——
   有了它就不需要你的 MySQL 实例，也不需要连你的数据库。

4. **数据库名不一致要改两处**：`.env` 里的 `DB_NAME`，
   以及 `sql/run_sql.py` 里建库用的库名（默认 `student_ms_demo`）。

5. **后端接口有变动时**，前端这边按这个顺序动：

   ```powershell
   # ① 先体检：后端契约里还有没有前端在调的路径（抓断链）
   node scripts/check-api-paths.mjs

   # ② 再同步类型与中文字段映射
   #    src/types/models.ts  +  src/utils/mappers.ts

   # ③ 刷新接口速查表（api-meta.ts 现在是自动生成的，别手改）
   node scripts/gen-api-meta.mjs

   # ④ 最后跑全量验证
   npm run verify
   ```

   `check-api-paths.mjs` 会把 `src/api/*.ts` 里每个 `get/post/put/del(...)`
   的路径跟 `openapi.json` 逐条对一遍，输出断链清单。
   **后端改路由以后先跑它**，比逐个模块试错可靠得多。

### 交给对方之后，可以让他跑这两条命令验收

```powershell
cd frontend
npm run build      # 类型检查 + 生产构建，必须零错误
npm run verify     # 接口层端到端验证，78 项必须全过
```

---

## 四、两个关键设计

### 设计 1：响应适配层（`src/api/http.ts`）

后端 6 个模块有 7 种不同的返回格式，这是历史遗留：

| 模块 | 实际形状 |
|---|---|
| 学生 / 就业（列表） | `{code, message, total, Data}` |
| 学生（单条） | `{code, message, Data}` |
| 删除类操作 | `{code, message}` |
| 成绩 | `{msg, detail}` |
| 就业分页 | `{total, page, size, total_pages, items}` |
| 未就业学员 | `{total, result}` |
| 班级 / 老师 / 统计 | 裸数组 |

如果业务代码直接处理这 7 种形状，每个页面都要写一堆 if-else，后端改一次格式前端全得改。

所以在 **Axios 响应拦截器** 里统一拆包，业务层永远只看到一种形状：

```ts
{ code: number, message: string, data: T, total: number }
```

**后端要改返回格式？只需要改 `http.ts` 这一个文件。**

同一层还顺手做了两件事：

1. **422 校验错误中文化** —— Pydantic 原本返回的是
   `{"detail":[{"loc":["body","stu_age"],"msg":"Input should be greater than 18"}]}`，
   经过 `translatePydanticMsg()` + `formatValidationErrors()` 之后变成
   `年龄：必须大于 18；手机号：格式不正确；学历：不能为空`。
2. **错误统一弹提示** —— 页面里不用每处都写 `try/catch + ElMessage`。
   需要自己处理的请求可以加 `{ silent: true }` 静默。

### 设计 2：中文字段在 API 层转英文（`src/utils/mappers.ts`）

后端有 **2 个模块的响应字段名是中文的**（请求体反而是英文的）：

| 模块 | 后端中文 key | 前端统一用 |
|---|---|---|
| 成绩 | `学生编号` / `考试序次` / `学生姓名` / `班级名称` / `分数` | `stu_id` / `test_id` / `stu_name` / `class_name` / `score` |
| 班级 | `班级id` / `班级名字` / `开课时间` / `班主任id` / `授课老师` | `class_id` / `class_name` / `start_date` / `class_teacher_id` / `teacher_id` |
| 班主任 | `班主任id` / `班主任名字` / `班主任性别` | `class_teacher_id` / `class_teacher_name` / `class_teacher_sex` |

来源在后端源码里，是老代码留下的约定：
`API/score_api.py` 的 `_score_to_dict()`、`API/class_api.py` 的各个返回字典。

**如果不在这一层转换，界面就会出「表格有行数但整列空白」的怪现象** ——
这正是开发过程中真实踩到并修掉的 bug。

转换函数放在 `src/utils/mappers.ts`，因为它是**纯函数**（不依赖 Vue / axios / 路由），
所以验证脚本可以直接 `import` 进来做断言，验证的就是浏览器里真正跑的那段代码。

---

## 五、验证方式

### 类型检查 + 生产构建

```powershell
npm run build
```

`vue-tsc -b` 先跑，类型有任何问题都会直接挡住构建。当前：**零错误**。

### API 层端到端验证

```powershell
npm run verify
# 等价于 node scripts/verify-api.mjs
```

打的是**完整链路**：脚本 → Vite 代理 → FastAPI 后端 → MySQL。
共 **78 项断言**，覆盖全部 8 个模块的只读接口，以及写接口的
「创建 → 查询 → 修改 → 删除」完整生命周期，另含错误路径、旧路径 404 回归与代理链路断言。

**当前实测 77 通过 / 1 失败**（库清干净后跑）。失败的 1 项指向**同一个后端 bug**
（`GET /score/get_del` → 500），前端这边接口调用、字段映射、错误提示都已就绪，
**后端修好后不需要改前端一行代码**。根因、改法和已验证的修复方案见下面「已知后端阻塞」。

> 断言数会随「库里有没有软删成绩」浮动 1 条：
> 运行前库里有软删成绩 → **76 通过 / 2 失败**，多出来那条也是同一个 bug 的另一个入口
> （详见「已知后端阻塞」里对这个 bug 触发条件的说明）。
>
> 上一轮（2026-11-02）这里是「69 通过 / 3 失败」，
> 后端随后把 `put_score` 和 `del_score` 两处修好了，失败面从 3 处收窄到 1 处。

其中包含对上述两个关键设计的断言：

- 成绩接口的中文 key 确实被转换成了 `stu_id` / `test_id` / `score`，且不残留中文 key
- 班级 / 班主任接口的中文 key 确实被转换，且班主任的**性别字段没有丢失**
  （丢失会导致「修改班主任」把女班主任的性别改成男）
- 班级接口必须返回 `class_teacher_name` / `teacher_name` / `teacher_id`
  （后端把「授课老师」字段名换成了「授课老师id / 授课老师姓名」，
  这条断言就是防止字段漂移再次悄悄溜过、导致整列显示 `-`）

### 已知后端阻塞（成绩模块 1 处）

后端成绩模块还剩 **1 处**缺陷。根因是：
**DAO 层把「查询结果行（Row）」和「ORM 实体对象」搞混了**，
于是 API 层的字段转换取不到它要的列。

| # | 接口 | 现象 | 根因 |
|---|---|---|---|
| 1 | `GET /score/get_del` | 库里**有**软删成绩时 → HTTP **500**；一条都没有时 → HTTP **404** | `Dao/score_Dao.py:135` `get_del_score()` 返回 **Score ORM 对象**（`scores` 表没有 `stu_name` 列），而 `API/score_api.py:30` 的 `_score_to_dict()` 读 `row.stu_name` → `AttributeError: 'Score' object has no attribute 'stu_name'` |

> **这个 bug 的触发条件很刁钻**：空列表时 `_score_to_dict()` 一次都不会被调用，
> 所以接口返回 404 看着还挺正常；**只要库里存在任意一条被软删的成绩，就必炸 500**。
> 也就是说 —— 这个接口越是「有数据可查」，越是打不开。

> 前端这边不会崩：`fetchDeletedScores()` 对 404 和异常都兜成了空数组，
> 「已删除成绩」页面会安静地显示空列表，不会白屏、不会弹错。
> **但这恰恰是最容易把后端 bug 藏起来的地方** —— 没有报错，只有"查不到数据"。

> `del_score` / `put_score` 这两处后端已经在 2026-11-02 修好了：
> 两者现在都查 **ORM 实体**（`db.query(Score)`）而不是查询结果行，
> 「找不到」分支也统一返回 `{message, status_code}`。
> 所以现在只剩 `get_del_score` 这一处形状不一致。

**最小改法**（只动后端，前端零改动）——下面这份补丁**已在真实库上验证通过**：

```python
# Dao/score_Dao.py —— 只改这一个函数即可
def get_del_score(db: Session):
    # 和 get_stu_id_score / get_test_id_score 保持同一种行形状（带上 stu_name），
    # 否则 API 层 _score_to_dict() 取不到「学生姓名」会 500。
    # 用 outerjoin：学生也被软删了，成绩记录仍要看得见（审计用）。
    return (
        db.query(Score.stu_id, Score.test_id, Student_info.stu_name, Score.score)
        .outerjoin(Student_info, Score.stu_id == Student_info.stu_id)
        .filter(Score.is_del == 1)
        .order_by(Score.stu_id)
        .all()
    )
```

改完这 1 处，`npm run verify` 应当 **78 项全过**，前端不需要任何改动。

> 顺带一提：验证脚本会在成绩软删后**明确打印清理 SQL**
> （`DELETE FROM scores WHERE stu_id=... AND test_id=99;`）——
> 因为成绩的「删除」是软删（`is_del=1`），后端没有物理删除接口，
> 这行测试数据一定会留在库里。脚本把话说清楚，免得测试数据悄悄堆进正式数据。

### 422 中文化验证

```powershell
node scripts/test-422.mjs
```

用真实后端发一个非法请求，检查前端最终展示的文案。

### 演示数据复位（并发调试时必用）

**场景**：后端那边有人在同一个库上调接口，会往正式数据里写测试行。
这些行的命名特征很明显（`Z######`、`ZZTEST######`、`回归班2759`、`重复班2801`、
`状态码老师2801`、`测试班5040改`、`探针班2834`、`待删5251`…），
但它们**会原样出现在前端列表页上**，看着就像「前端数据出错了」。

跑这个脚本就能把库推回种子基线：

```powershell
# 在项目根目录执行；-p 会提示你输入密码，密码见根目录 .env 的 DB_PASSWORD
mysql -u root -p --default-character-set=utf8mb4 -D student_ms_demo `
  --execute="source frontend/scripts/reset-demo-data.sql"
```

脚本只按**命名特征**删，不碰种子行；先删子表再删父表，不破坏外键；
最后打印各表行数做自检，期望值是：

| 表 | 行数 |
|---|---|
| `student_info` | 200 |
| `scores` | 600 |
| `employment` | 134 |
| `clazz` | 36 |
| `class_teacher` | 12 |
| `teacher` | 24 |
| `agent` | 12 |

> ⚠️ 这个脚本救不了「**改值**型」的污染。
> 比如有人把学生 1 的院校改成 `'string'`（行还在，只是内容被覆盖了），
> 那得对着 `sql/02_seed_demo_data.sql` 手工比对还原。
> 判断方法：某个字段的值是 `string`、或者日期变成了当天，基本都是这类。

---

## 六、几个实现上的选择

### 学生管理为什么是「一次拉全量 + 前端分页」

后端 `/student/select_stu_skip` 的 `total` 返回的是**本页条数**（`len(rows)`）而不是总条数，
而且它的 `skip`/`limit` 与 `el-pagination` 的 1-based 页码对不上。
当前只有 232 条学生，一次拉全量再在前端分页最省事，也最不容易出显示 bug。

就业模块则相反 —— 它有真正的服务端分页接口 `/employment/page`，所以走服务端分页。
因为是服务端分页，**排序也必须交给后端做**（`?sort=salary:desc,stu_id:asc`，
字段走后端白名单），只在前端排的话，排的只是当前这一页，翻页之后顺序就断了。

### 演示模式的边界（重要）

当前登录是**纯前端模拟**：`store/user.ts` 把用户信息写进 `localStorage`，
路由守卫只检查「localStorage 里有没有用户信息」。

这能挡住「没登录直接敲 URL」，**挡不住直接调后端接口**。
后端目前也没有任何鉴权，所以任何人都能直接访问 `/student/select_stu_skip`。

将来后端加上 token 认证时，**只需要改两个地方**：

1. `src/store/user.ts` 的 `login()` —— 换成调后端登录接口、存 token
2. `src/api/http.ts` 的请求拦截器 —— 加一行 `config.headers.Authorization = token`

业务代码一行都不用改。

### 生产环境部署

开发时用 Vite proxy，生产用 Nginx 反代，前端代码零改动：

```nginx
server {
    listen 80;
    root /var/www/stu-ms-frontend/dist;

    location / {
        try_files $uri $uri/ /index.html;   # SPA history 路由兜底
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8003/;  # 注意末尾的 /
        proxy_set_header Host $host;
    }
}
```

`dist/` 目录由 `npm run build` 生成，直接丢到 Nginx 静态目录即可。

### 数据大屏：`/screen` 独立路由

后台看板（`/dashboard`）是「管理视角」，大屏是「展示视角」，两者诉求不同：
大屏要 1920×1080 铺满、要全屏、要一眼看到全局指标，但侧边栏和顶栏对它毫无意义。
所以大屏**不套 Layout**，是一条独立路由（`meta.hidden: true`，不出现在菜单里）。

| 项 | 做法 |
|---|---|
| 入口 | 统计分析页右上角「进入数据大屏」按钮 → `router.push('/screen')`；大屏右上角「返回后台」回来 |
| 适配 | 画布固定 1920×1080，外层用 `transform: scale()` 等比缩放到窗口，任何分辨率都不错位 |
| 全屏 | 右上角「全屏显示」按钮，走 `screenfull`，切换时重算缩放比例 |
| 数据 | 全部走 `src/api/**`，不直接调后端；后端接口形状变了只改 api 层，这个页面不用动 |
| 兜底 | 加载中 / 加载失败各有一层半透明遮罩，不会白屏 |

**上屏的内容**（对着 7 个模块的接口挑的，都是能自动算出来的指标）：

- 左列：在读学员总数 + 已就业/待就业拆分、性别构成环形图、待就业学员实时名录（无缝滚动）
- 中列：班级/老师/班主任/顾问/两科不及格/全优学员 六格 KPI、班级在读人数 TOP 10 发光排行、
  整体就业率仪表盘、平均薪资、平均就业周期、就业薪资 TOP 5
- 右列：学历构成、薪资区间分布、各场考试平均分趋势、学员年龄段分布

> 没做中国地图：`stu_from` 字段是「浙江 / 杭州 / 青岛 / 武汉」这种省、市混写的，
> 粒度不一致，映射到地图上会误导人。改成班级人数排行更实在。

**一个容易看岔的口径**：大屏 KPI 的「班级总数」取自 `/class/all_class`（**全部在册班级**，72 个，
含暂时没学员的空班）；而「班级在读人数 TOP 10」和浅色看板的「班级数量」取自
`/stat/class/statistics`（**只有 59 个班有学员**，也是「班级均人数 232÷59」的分母）。
两个数都对，只是口径不同 —— 大屏 KPI 上已加了悬浮提示说明，KPI 悬浮即可看到。

**配色跟着主题走**：`styles/theme.css` 里每个颜色都有固定职责，大屏严格照搬：

| 颜色 | 主题里的职责 | 大屏里的用法 |
|---|---|---|
| 靛蓝 `#5b8ac4` | 通用数据 | 面板、排行条、柱状图、折线图（主色） |
| 赭黄 `#d4a04a` | 就业 / 薪资 | 薪资区间、薪资榜、就业率仪表、排行榜前三名 |
| 青绿 `#4fb99a` | 达标 / 全优 | 已就业人数、全优学员 |
| 朱砂 `#e0574a` | 激活态 / 预警 / 删除 | 只用在「两科不及格」和屏幕自身的印章装饰（标题） |

色板在 `ScreenView.vue` 顶部定义成常量，再通过 `:style` 注入成 CSS 变量，
JS（ECharts）和 CSS（样式表）共用同一份真值，以后换配色只改那一处。

### 后端 2026-11-02 的三处接口变更（前端已同步）

后端改过一次接口契约，前端跟着改了，业务层无感知：

| 变更 | 之前 | 现在 |
|---|---|---|
| 顾问模块独立成路由 | `/student/agent`、`/student/add_agent`… | `/agent/agent`、`/agent/add_agent`… |
| id 改成 query 参数 | `stu_id` / `agent_id` 放 body | 放 query：`PUT /agent/update_agent?agent_id=`、`PUT /student/update_stu_class?stu_id=` |
| 「查全部学生」接口 | `GET /student/select_all` | `GET /student/select_stu_skip?skip=0&limit=5000`（`total` 是本页条数，总数自己数 `data.length`） |

外加一处返回形状：`GET /employment/unemployed` 返回 `{total, result}` 而不是常见的
`{code, message, total, Data}`，`http.ts` 的 `normalize()` 里补了这一种形态，
业务层拿到的仍然是 `{code, message, data, total}`。

表单校验也跟后端 Pydantic 约束对齐了（长度上限、正则、> 18 之类），
避免用户填完点提交才吃一个 422。

### 后端 2026-11-03 的三处接口变更（前端已同步）

后端又动了一次契约，前端跟着同步。**这次变动比上次隐蔽**：
上一次是「路径改了」，这一次是「路径没改、返回字段名改了」，
不体检根本看不出来（页面不报错，就是整列显示 `-`）。

| 变更 | 之前 | 现在 |
|---|---|---|
| 班主任独立成路由 | `/class/all_class_teacher`、`/class/get_class_teacher/{id}`… | `/class_teacher/all_class_teacher`、`/class_teacher/get_class_teacher/{id}`…（旧路径已整段注释掉，实测 404） |
| 班级返回字段名漂移 | `授课老师`（单字段，装 id） | `授课老师id` + `授课老师姓名` + `班主任id` + `班主任姓名`（DAO 层 JOIN 出了姓名） |
| 新增「班级学员」接口 | — | `GET /class/get_class/{stu_class_id}/students` → 返回该班学生数组，**英文 key**（`stu_id/stu_name/stu_age/stu_sex/…`，`agent_name` 可为 null） |

前端对应改了三处：

1. `src/api/class.ts` —— 5 处班主任路径全部迁到 `/class_teacher/*`，
   并新增 `fetchClassStudents(stu_class_id)` 封装新接口（英文 key 直接透传，不做中文映射）。
2. `src/utils/mappers.ts` —— `RawClass` 补 `班主任姓名/授课老师id/授课老师姓名`
   （保留旧的 `授课老师` 做兼容），`toClassInfo` 的 `teacher_id` 改成
   `raw.授课老师id ?? raw.授课老师 ?? null`。
3. `src/views/class/ClassListView.vue` —— 班级列表新增「学员」按钮 + 右侧抽屉，
   展示该班学生的学号/姓名/性别/年龄/电话/顾问/生源地/院校/专业/学历。
   班主任和授课老师两列**优先用后端直接返回的姓名**，本地反查老师表只作兜底 ——
   后端已经 JOIN 出姓名了，再绕一圈查老师表既多一次请求，
   又会在老师表变动时整列塌成 `-`。

同时补了两个防回归的机制：

- `scripts/check-api-paths.mjs` —— 把 `src/api/*.ts` 里每个接口路径
  跟 `openapi.json` 逐条对一遍，专门抓「后端改了路由、前端还写着旧路径」这种断链。
  这轮 5 处断链就是它一次性找出来的。
- `scripts/gen-api-meta.mjs` —— `api-meta.ts`（接口速查表）改成**从 `openapi.json` 自动生成**。
  之前它是手写的，里面还留着一堆早已下线的路径（`/student/select_all`、`/student/agent`…），
  这种「清单」手写维护必然随契约漂移而失效。

> 旧路径 `/class/all_class_teacher` 等 5 条已被加进 `verify-api.mjs` 的
> 「旧路径应返回 404」回归列表，防止以后误用。

### 2026-11-03 追加：两个列表页加查询 + 成绩加姓名列

这一轮**后端一行没动**，全在前端完成。

| 页面 | 改动 | 说明 |
|---|---|---|
| 学生成绩 | 加「学生姓名」列 | 后端 `/score/*` 本来就返回 `学生姓名`（JOIN 学生表带的），只是前端一直没映射、也没展示 |
| 班级列表 | 加关键词查询 | 匹配：班级名称 / 班级 ID / 开课时间 / 班主任姓名 / 授课老师姓名 |
| 班主任列表 | 加关键词查询 | 匹配：姓名 / 编号 / 性别 |

**成绩的姓名是怎么接上的**

后端 `API/score_api.py` 的 `_score_to_dict()` 返回的是中文 key：

```json
{"学生编号": 1, "考试序次": 1, "学生姓名": "李家怡", "分数": 92.0}
```

`学生姓名` 之前一直在响应里躺着没人用 —— 前端 `toScore()` 只映射了三个字段，
学生成绩页就只剩光秃秃的学号。现在补上：

```ts
// src/utils/mappers.ts
export interface RawScore {
  学生编号?: number
  考试序次?: number
  学生姓名?: string | null   // ← 新增
  分数?: number
}

export function toScore(raw: RawScore): Score {
  return {
    stu_id: Number(raw.学生编号 ?? 0),
    stu_name: String(raw.学生姓名 ?? ''),   // ← 新增
    test_id: Number(raw.考试序次 ?? 0),
    score: Number(raw.分数 ?? 0),
  }
}
```

**查询是前端过滤，不是后端查询**

班级 36 条、班主任 12 条，一次拉全量再在前端过滤最省事，
也不会多打后端。筛选逻辑写在页面里的 `filtered` computed 上：

```ts
// src/views/class/ClassListView.vue
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return classes.value
  return classes.value.filter(
    (c) =>
      c.class_name.toLowerCase().includes(kw) ||
      String(c.class_id).includes(kw) ||
      c.start_date.includes(kw) ||
      resolveClassTeacherName(c).toLowerCase().includes(kw) ||
      resolveTeacherName(c).toLowerCase().includes(kw),
  )
})
```

> 班主任 / 授课老师姓名参与匹配时，走的是 `resolveClassTeacherName()` /
> `resolveTeacherName()` —— 跟表格里显示的是**同一套取值逻辑**
> （后端直接给的姓名优先，本地反查表兜底），
> 不会出现「搜得到但表格里显示 `-`」这种自相矛盾的情况。

**副标题会跟着筛选结果变**：有筛选词时显示「共 4 个班级（全部 36 个）」，
一眼知道筛掉了多少。

**防回归**：`verify-api.mjs` 里加了两条断言 ——
① `toScore()` 必须把 `学生姓名` 映射成 `stu_name` 且不能为空；
② 查整场考试的成绩时也得带姓名（学生成绩页按场次查时显示这一列）。
少一条就会红。

---

### 2026-11-06 追加：学生成绩页加「班级」列（后端只加 JOIN）

学生成绩页原来只有「学号 / 学生姓名 / 考试次序 / 分数」，
一眼看不出这场考试里到底都有哪些班的人 —— 想按班看，只能另开班级列表去对。
现在表格里直接多一列「班级」，**后端只加了 JOIN，没有改表结构、没有大改**。

**表链路**：成绩表里只有 `stu_id`，班级挂在 `student_info.stu_class_id` 上，
班级名在 `clazz.class_name`，所以要 JOIN 两次：

```
scores  --(stu_id)-->  student_info  --(stu_class_id)-->  clazz
```

**为什么用 `outerjoin`（LEFT JOIN）而不是 `join`**：
成绩是硬数据，不能因为某个学生没分班（`stu_class_id` 为 NULL）、
或者班级被软删了，就让**这一整行成绩查不出来**。
用左连接时这类行的 `class_name` 是 `None`，接口层转成空串，页面显示「-」。
（这跟就业模块的口径不一样：那边用内连接 + `Class.is_del == 0`。）

**改动清单**：

| 文件 | 改了什么 |
|---|---|
| `Dao/score_Dao.py` | 新增 `_SCORE_COLUMNS` + `_score_query()` 两个小helper，5 个查询函数统一走它；**DAO 结构与表结构都没动** |
| `API/score_api.py` | `_score_to_dict()` 增加 `班级名称`（沿用成绩模块既有的中文 key 约定，不扩散到界面层） |
| `src/utils/mappers.ts` | `RawScore` 增加 `班级名称`，`toScore()` 映射成 `class_name` |
| `src/types/models.ts` | `Score` 接口增加 `class_name: string` |
| `src/views/score/ScoreListView.vue` | 新增「班级」列（`minWidth: 124`，可排序，落在「学生姓名」后面） |

**防回归**：`tests/test_api.py` 新增 `test_score_list_includes_class_name` ——
校验 4 个成绩接口的每一行都含 `班级名称` 且类型为字符串、已分班的学生班级名非空；
`verify-api.mjs` 里「查学生成绩」「查场次成绩」两条断言也加了 `class_name` 校验。

> **窄视口下表格不铺满，是 Element Plus 的原生行为，不是 bug**：
> 成绩表 7 列的 `minWidth` 合计 775px（序号 55 + 学号 96 + 姓名 120 + 班级 124 +
> 考试次序 106 + 分数 104 + 操作 170），
> 视口窄于这个值时 EP 会给表格加 `el-table--scrollable-x`，走横向滚动，
> 不再把剩余空间摊给弹性列。1920 宽下表格正常铺满整宽。

---

## 七、界面预览

界面为「教务墨册」风格：墨色书脊 + 朱砂印，楷体标题、Consolas 数字，
表格只留横向细线，主色用墨而非红。

> **本仓库不收录界面截图。** 截图是本地开发过程中的临时产物，
> 且会渲染出演示数据的真实姓名与手机号；公开仓库里不适合放。
> 需要看效果请自行启动后查看，或用
> `node scripts/capture-screenshots.mjs` 现场重拍到本地 `docs/screenshots/`
> （需前后端都已启动，也可带参数只拍某几页：`node scripts/capture-screenshots.mjs 顾问`）。
> 截图时会自动隐藏右下角的小管家悬浮球 —— 它浮在右下角，会盖住分页器和最后两行。

各页面看点（页面名 → 值得注意的设计）：

| 页面 | 看点 |
|---|---|
| 登录页 | 左墨右纸分栏：朱砂「管」字方印 + 竖排楷体书名，右侧表单标注「演示模式」边界 |
| 学生管理 | ProTable：搜索栏与表格合并成同一个册页面板、等宽数字、靛蓝/淡紫性别标签；**表头自带排序箭头，默认按学号→年龄→入学时间排好** |
| 顾问管理 | ProTable + 性别标签；默认按年龄→编号排序；**窄册页版式**（列少，整张册页收窄居中） |
| 学生成绩 | ProTable + 分数色阶标签（青=达标 / 赭=中等 / 朱砂=不及格）；**新增「学生姓名」列**；**新增「班级」列**（后端 JOIN 班级表带出，可排序） |
| 就业信息 | 服务端分页 + 赭色薪资高亮；**默认按薪资降序（服务端排序，翻页依然有序）** |
| 班级列表 | 班级 / 班主任 / 授课老师关联展示；行内「学员」按钮开右侧抽屉看该班名单；**顶部新增关键词查询** |
| 班主任 | 班级管理下的第二个页面（保留二级菜单）；**顶部新增关键词查询**；窄册页版式 |
| 授课老师 | 任教班级多标签展示 |
| 统计分析 | 八格册页副表 + 四个分区（总览/成绩/就业/班级）+「进入数据大屏」入口 |
| 数据大屏 | 同一套墨册色板的暗色驾驶舱：墨底 + 朱砂预警 + 靛/赭/青数据色；**新增就业去向热力中国地图** |
| 运行日志 | 顶栏日志抽屉：级别过滤 / 关键字搜索 / 复制，最新的在最上面 |
| 404 页 | 兜底路由，等宽大号 404 + 楷体标题 |
| 退出登录 | 二次确认弹窗 |

**表格列宽口径**：Element Plus 把「没写 `width` 的列」当弹性列，剩余空间**全分给它** ——
弹性列只剩一列时，那一列会被撑到整屏宽，表格中间出现一个巨大的空洞。
所以本项目的规矩是：序号列和操作列用 `width` 固定，其余内容列一律用 `minWidth`，
空间按 `minWidth` 比例摊开；可排序列的 `minWidth` 不低于 76（表头文字 + 排序箭头约 50px，
再窄表头会被省略号截成「年..」）。列少的页面（顾问管理 / 班主任）再给 ProTable 加 `narrow`，
整张册页收窄居中，像案头上摆的一本窄册。

**侧边栏层级**：模块下只有一个功能时不再套一层可展开的二级菜单。
比如「统计分析」原本是「统计分析 → 统计分析」，现在直接是一个顶级菜单项；
「学生成绩 / 就业信息 / 授课老师」同理。只有真正有多个页面的模块
（学生管理 → 学生管理/顾问管理、班级管理 → 班级列表/班主任）才保留二级菜单。

> **本轮菜单改名**：学生列表 → **学生管理**、成绩列表 → **学生成绩**、
> 老师列表 → **授课老师**；原来的「数据看板」已并入「统计分析」，
> 侧边栏不再单独出现「数据看板」，`/dashboard` 会重定向到 `/stat/analysis`。

---

## 七·补、运行日志面板（前端可观测性）

顶栏有一个 **`Tickets` 图标**（一叠单据，和「逐条记录」的意思对得上），
点开是右侧抽屉「运行日志」。不用开 F12，也不用 SSH 上服务器，
就能看到刚才这一分钟系统里发生了什么。

### 收什么、不收什么

| 来源 | 采到的内容 | 采集点 |
|---|---|---|
| 接口 | 方法、URL、状态码、耗时、后端返回的一句业务文案 | `src/api/http.ts` 的两个拦截器 |
| 控制台 | `console.log / info / warn / error / debug` | `src/utils/logger.ts` 的 `installConsoleLogger()` |
| 运行时 | 未捕获异常（`window.onerror`）、未处理的 Promise 拒绝 | 同上 |

**刻意不收请求体**：登录接口的 body 里带密码，落进日志就是明文泄露。
只记 method + URL + 状态码 + 业务 code/message；参数也只记「有几个」不记「是什么」。

### 边界说明（重要）

这个面板收的是**前端能看见的日志**，不是后端 stdout 的运行日志。
后端 `uvicorn` 的访问日志、SQL 打印、异常堆栈都在服务器那一侧，
在「后端代码一行不改」的前提下拿不到。
**要连后端运行日志一起看**，需要后端加一个只读接口（例如 `GET /log` 读日志文件尾部），
前端再轮询它 —— 这一步需要放宽「不改后端」的约束。

### 实现要点

| 文件 | 作用 |
|---|---|
| `src/utils/logger.ts` | 环形缓冲（最多 500 条，最新在最上）、console 拦截、异常监听 |
| `src/components/LogPanel/index.vue` | 抽屉式面板：级别过滤、关键字搜索、复制、清空 |
| `src/layouts/components/Header/components/LogButton.vue` | 顶栏图标 + 错误数朱砂角标 |
| `src/main.ts` | `installConsoleLogger()`（在业务代码跑起来之前装好，最早的报错才抓得到） |
| `src/api/http.ts` | 请求 / 响应 / 失败三处打点，带耗时 |

级别配色沿用全局「一色一义」：朱砂=错误、赭=警告、青=请求、靛=信息、灰=调试。

---

## 八、常见问题

**Q：`npm` 提示不是内部或外部命令？**
A：Node 装在 `C:\Program Files\nodejs`，新 shell 里先
`$env:PATH = "C:\Program Files\nodejs;$env:PATH"`。

**Q：页面报「请先登录」然后跳回登录页？**
A：localStorage 里的登录态丢了。正常点「登录」按钮即可重新进入。

**Q：接口全部 404 / 502？**
A：先确认后端在跑（`http://127.0.0.1:8003/student/select_stu_skip?skip=0&limit=1` 能返回 JSON），
再确认 `.env.development` 里的 `VITE_API_BASE=/api` 没被改掉。

**Q：改完代码页面没变化？**
A：Vite 热更新偶尔会漏。停掉 dev server 重启一次即可。

**Q：表格有行数但列全是空的？**
A：多半是后端改了字段名。先看浏览器 Network 里该接口的真实响应，
再对照 `src/types/models.ts` 和 `src/utils/mappers.ts` 调整映射。
