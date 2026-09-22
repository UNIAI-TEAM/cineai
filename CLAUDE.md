# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

PRINTFILM（仓库目录 `ai_movie`）：模板驱动的 AI 短视频（科普 kepu）与漫剧创作平台。两条产品线共用同一套 AI 能力：

- **科普短视频**：主题/口播 → 模板拆镜 → 分镜图 →（可选）视频 → 旁白 → FFmpeg 合成；状态机 `SCRIPTING → IMAGING → VIDEOING/AUDIOING → COMPOSING → DONE`
- **漫剧 drama**：项目 → 剧本摘要/分集 → 资产库（角色/场景/道具/音色）→ 分集分镜 → React Flow 画布
- 另有工具中心（t2i/i2p/t2v 等）、开放 API（`/api/v1`）、管理后台、可选钱包计费（银行转账 + 管理员确认到账）

三条独立进程 + 两个容器中间件：FastAPI(:8000)、用户端 Vite(:5173)、管理端 Vite(:5174)、Postgres(:15432)、Redis(:16379)。技术栈：Python 3.12 / FastAPI / SQLAlchemy(asyncpg) / React 19 / TS / Vite 8。需要本机安装 FFmpeg。

## 常用命令

```bash
# 中间件（先 cp deploy/.env.prod.example deploy/.env.prod 并改密码）
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.prod up -d

# 后端（在 backend/ 下；先 cp .env.example .env）
uvicorn app.main:app --reload --port 8000

# 用户端 / 管理端（各自目录）
npm install && npm run dev      # 5173 / 5174
npm run lint                    # oxlint（无后端 linter/formatter 配置）
npm run build                   # tsc -b && vite build
```

测试（在 `backend/` 下，需 `pip install -r requirements-dev.txt`，`pytest.ini` 已设 `asyncio_mode=auto`、`pythonpath=.`）：

```bash
pytest                                  # 全量
pytest tests/test_kepu_continuity.py    # 单文件
pytest tests/test_x.py::test_name       # 单测
```

注意：使用 `db_session` fixture 的是集成测试，**需要 PostgreSQL 在运行**（事务回滚隔离，不写库）；其余为纯单测可直接跑。conftest 已自动 stub TokenFree 价目网络请求。

健康检查 `/api/health`（含 task_runtime / db_pool / models），Swagger `/docs`。

## 架构要点（需要读多个文件才能拼出的全局）

### 统一任务平台（核心，易误判）

代码里没有独立 worker 进程：Celery 仅是遗留依赖（`USE_CELERY` 代码已不读取，`workers/` 目录不存在）。实际运行时是 **随 FastAPI 启动的进程内三件套**（`app/services/tasks/`）：

- `scheduler.py`：定时租约到期任务（pending→leased→running），受全站槽位 `TASK_RUNTIME_MAX_CONCURRENCY` 与单用户槽位 `TASK_USER_MAX_CONCURRENCY` 限制；含孤儿任务回收
- `executor.py`：执行 handler
- `poller.py`：NIO 式 Selector，集中非阻塞轮询所有 `awaiting_poll` 的上游任务（信号量 `TASK_POLL_MAX_CONCURRENCY`），完成后触发计费结算
- `runtime.py` + watchdog：心跳过期自动软重启调度/轮询循环

`TaskRun` 状态与 steps/events/targets 见 `models_tasks.py`；**新任务类型必须在 `tasks/handlers.py` 的 `HANDLERS` 注册表登记 `(domain, task_type)`**（kepu/drama/api/studio/tools 五个 domain）。部分类型注册为 `_noop_ephemeral`——这些在创建请求内联执行，TaskRun 仅用于计费/留痕。管理端任务中心 `/queues` 直接读这些表。

### 科普流水线与分阶段计费共用同一就绪判定

`services/pipeline.py`（约 2000 行，历史大文件，新增逻辑优先拆新文件）是科普编排主体。`pipeline_mode`：`full`（图+视频+合成）或 `image_text`（静图+旁白）。关键约定：**`services/kepu_stages.py` 的 `resolve_kepu_billing_phase()`（script|assets|videos|compose）是计费预扣与流水线恢复共用的唯一"下一阶段"真相源**，改就绪规则必须两边语义一致。连续性（首尾帧/参考图）在 `kepu_continuity.py`；FFmpeg 合成在 `ffmpeg_compose.py`（SIGTERM 中断有自动重试）。

### 漫剧模块独立成包

`api/drama/` + `services/drama/`（30+ 小文件，按 jobs/fragment/voice/asset 等拆分）+ `models_drama.py`（projects→scripts→episodes→fragments→asset_refs）。分镜视频是一镜一 TaskRun（`fragment_video`），有预算、最大尝试次数与排队上限（见 config 中 `DRAMA_*`）。产品规则见 `docs/EPISODE_RULES.md`、`docs/SHOT_SPLITTING.md`。

### 模型路由：Provider 适配层，直连 OpenAI + BytePlus ModelArk

已下线 TokenFree 网关：现在直接对接多个上游，`services/providers/`（`base.py` 定义 `ProviderAdapter` Protocol + 公共类型，`registry.get_adapter(protocol)` 按 `openai|ark|volc_tts` 返回单例，`openai_adapter.py`/`ark_adapter.py`/`volc_tts_adapter.py` 各实现一个协议，`presets.py` 是管理后台新增 provider 时的模板）。新增 provider：写一个新 adapter 文件实现该 Protocol，在 `registry.get_adapter` 里加一个分支，需要的话把预设加进 `presets.PROVIDER_PRESETS`；`function_router.py`/`media_gateway.py` 只认 `protocol` 字符串，不直接 import 具体 adapter 类。

按「功能」而不是按渠道分配模型：`services/functions.py` 是固定的功能目录（`kepu.script/kepu.image/kepu.video/kepu.tts/drama.*/tools.*` 等，domain × 能力），`function_bindings.py` 定义 `FunctionBindings{slots: 按能力(text/image/video/audio)的默认模型列表, overrides: 按 function_id 覆盖}`，`effective_bindings()` 优先取该功能的 override，没有则退到能力 slot；同一 slot 内多个 `{channel_id, model, weight}` 按 weight 加权随机排序，遇到上游临时错误（`adapter.is_transient_error`）就换下一个候选（failover）。`function_router.resolve_function_candidates(function_id, requested_model)` 是唯一的路由解析入口。管理后台经 `GET/PATCH /api/admin/settings/routing`（`model_settings.py` 生成/保存 `AdminRoutingSettingsOut`，存 `system_model_channels` / `app_settings` 表）配置 provider 与 function_bindings；`config.get_settings()`（lru_cache）仍以 DB overlay 优先叠加到 env 配置之上，`.env` 仅首次（DB 无任何 provider 时）用于 seed。无 Key 联调设 `ARK_MOCK=true`（或不配任何 provider key）走本地 mock 素材，`MediaGateway.mock` 会自动判定。

`media_gateway.py` 是唯一对外的生成入口（facade，不含 HTTP，只做路由解析 + 调 adapter + 落盘/OSS + failover + mock）；文本走 `llm_client.py`（同样经 `function_router` 解析到 OpenAI 兼容渠道）；配音豆包 openspeech（`VOLC_TTS_*`，与 OpenAI/Ark Key 不同）优先，`tts_service.py` 里 mock → slot 内模型级联 → 均失败才回退 edge-tts。视频只能走 `ark`（BytePlus ModelArk / Seedance）协议，OpenAI 适配器的 `create_video`/`fetch_video` 直接 raise 不支持。轮询正在进行的视频任务时，`TaskRun.provider_channel_id` 记录了创建任务时用的渠道，poller 按这个字段回访同一渠道（不会因为 weight 重新洗牌落到别的 provider 而查不到任务）。详见 `docs/PROVIDERS.md`（adapter 写法、BytePlus 静态模型表、function_bindings JSON 示例、curl 配置示例、已知限制）。

### 计费：每个 TaskRun 走「预扣 → 用量行 → 结算」

钱包单位为**分**（`users.balance_fen/frozen_fen`）。`services/billing/`：建任务时按估价 freeze → 执行中写 `usage_events` → poller 收尾 `settle_task` 扣实费退冻结。优先取上游真实 quota（New API: 500000 quota = 1 USD，`BILLING_USD_CNY`），取不到才用本地保守估价；官方价目由 `tokenfree_pricing.py` 拉取缓存。默认 `BILLING_ENABLED=false`。详见 `docs/BILLING.md`。**界面不展示人民币**：`services/billing/money.py` 按 `BILLING_DISPLAY_CURRENCY`（VND 默认 / USD）与汇率 `BILLING_CNY_VND`、`BILLING_USD_CNY` 折算展示，充值包以 VND 定义（`pricing.py`），充值走银行转账建单 + 管理端「订单」确认到账（`services/billing/topup.py`），无第三方支付网关。

### 数据层与"迁移"方式

- 异步引擎 asyncpg（`AsyncSessionLocal`，业务全异步）；同步引擎 psycopg2 仅少量场景
- ORM 按域拆文件：`models.py`（users/projects/shots/templates/计费/订单/tool_runs 等）、`models_drama.py`、`models_tasks.py`、`models_api.py`（API Key）、`models_agent.py`（导演 Skill）、`models_settings.py`
- **没有 Alemantic 类迁移工具**：启动时 `init_db()` 做 `create_all`，新增列必须手写进 `main.py` 的 `_apply_schema_patches()`（只允许 additive 的 PG DDL；conftest 里的测试 schema 也要同步）。线上建议 uvicorn 单 worker 以规避建表竞态
- 启动还会执行：模板 seed（只插缺失，不覆盖后台改动）、内置 Skill seed、`ADMIN_BOOTSTRAP_EMAILS` 提权（只提升已注册用户，不造号，需重启）

### 媒体与 OSS

所有成片/分镜**先落本地** `backend/static/generated/p{id}/`（FFmpeg 只读本地），返回 `/static/...`；开启 OSS 后经 `oss_queue.py` 异步入队上传并回填公网 URL（`storage.py` / `oss.py`）。删除项目需级联清理素材与 works 等从属数据。

### 前端两个应用的差异

- `frontend/`：**vite 未配 proxy**。API base 规则：未设 `VITE_API_BASE` → `当前主机:8000`（开发）；设为空字符串 → 同源（生产 nginx）。请求统一走 `src/api.ts` 与 `src/api/*`。样式体系是 `styles/printfilm.css` + `pf-*` 语义 class（**不要**在用户端引 Tailwind）。含中/英 i18n
- `admin/`：Tailwind v4 + Radix/shadcn 风格组件，`@` → `src`，vite 代理 `/api`、`/static` 到 :8000；用 `cn()`；列表必须服务端分页（`page/page_size/meta.total`，复用 `PaginationBar`）

两端公共逻辑放 `lib/`（用户端已有大量 `drama*` 纯函数 helper，新功能先搜再写），页面只做编排。

## 仓库约定（来自 docs/STANDARDS.md，摘要）

- **用户可见文案、提交信息、文档默认简体中文**；对外报错 `detail` 用中文短句，不回传堆栈
- 每个函数 / 组件 / Hook 顶部写功能注释（复杂的写参数/返回值），成组 state 用块注释
- 单文件尽量 ≤ 500 行；分层：`api/` 只做鉴权/校验/调 service，业务在 `services/`；前端页面不直接拼请求细节
- 列表筛选与分页一律服务端；加载/空态/错误三态齐全；危险操作需确认
- 禁止提交：`.env`（仅允许 `*.example`）、`deploy/scripts/deploy_kepu*.py`、`.tmp/`、生成媒体、`dist/`
- 改了计费/发布方式/占位入口要同步更新 `docs/` 对应文档；**每次线上发布后在 `docs/releases/` 追加一条**
- 提 PR 前对照 `docs/STANDARDS.md` 第 9 节自检清单；专项文档：`docs/DEPLOY.md`、`docs/BILLING.md`、`docs/SEEDANCE_2_5.md`
