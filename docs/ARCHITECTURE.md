# GTR Dashboard 架构设计

## 1. 项目概述

GTR Dashboard（GitHub Trending Reporter）是一个多 Agent 自动化选题流水线系统。核心目标是从 GitHub Trending 及外部数据源采集开源项目，通过 LLM 逐层分析生成内容选题建议，辅助社交媒体内容创作。

**核心流程**：采集 → 分析 → 策略 → 筛选 → 报告

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          React Dashboard                            │
│  Dashboard │ Topics │ Pipeline │ History │ Settings                 │
│       (Vite + Tailwind + Zustand + React Query 风格的 hooks)        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ HTTP /api/v1
┌─────────────────────────────────────────────────────────────────────┐
│                         FastAPI REST API                            │
│  /projects │ /topics │ /pipeline │ /preferences │ /weights          │
│  /reports  │ /history                                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │         SQLite (SQLModel)      │
                    │  raw_projects ──► project_     │
                    │  profiles ──► topic_suggestions │
                    │  user_actions │ pipeline_runs   │
                    └────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │      Pipeline Orchestrator     │
                    │   collect → profile → strategize│
                    │   → curate → report            │
                    └────────────────────────────────┘
                                    │
        ┌───────────┬───────────────┼───────────────┬───────────┐
        ▼           ▼               ▼               ▼           ▼
   ┌─────────┐ ┌─────────┐  ┌─────────────┐  ┌─────────┐ ┌──────────┐
   │ Legacy  │ │ Tavily  │  │    Exa      │  │  LLM    │ │ Markdown │
   │Collect  │ │Collect  │  │  Collect    │  │ Profile │ │  Report  │
   │(BS4)    │ │(Search) │  │(Semantic)   │  │Strategist│ │  Writer  │
   └─────────┘ └─────────┘  └─────────────┘  └─────────┘ └──────────┘
```

---

## 3. 数据流（Pipeline 五阶段）

### Stage 1: Collect — 多源采集

支持 4 种数据源模式，通过 `source` 参数切换：

| 模式 | 实现 | 说明 |
|---|---|---|
| `legacy` | `TrendingCollectorAgent` | BeautifulSoup 爬取 GitHub Trending 页面，支持按语言过滤 |
| `tavily` | `SearchCollectorAgent` | Tavily AI 搜索 API，深度搜索模式 |
| `exa` | `ExaCollectorAgent` | Exa 语义搜索 API，支持自然语言查询 |
| `both` | Tavily + Exa | 双源并行采集，自动去重 |

采集结果统一为 `RawProject`，包含：owner、name、language、stars、description。

**容错**：任一采集器失败不会阻断流水线，继续用已采集数据。

### Stage 2: Profile — 项目画像

`ProjectProfilerAgent` 为每个项目生成 LLM 分析结果：

- `novelty_score` (1-10): 技术新颖度
- `utility_score` (1-10): 实用价值
- `doc_quality_score` (1-10): 文档质量
- `local_ai_relevance` (1-10): 本地 AI 部署契合度
- `tags`: 技术标签 JSON 数组
- `summary`: 项目摘要

**性能优化**：
- 并发控制：Semaphore 限制 max 3 个并行 LLM 调用
- 日级缓存：同一项目当天不再重复分析
- README 获取：优先 fetch 仓库 README 作为分析上下文（20K token 截断）

**降级策略**：分析失败时标记 `analysis_status=degraded`，流水线继续。

### Stage 3: Strategize — 策略生成

`ContentStrategistAgent` 批量生成内容策略：

- 每批 10 个项目，减少 LLM 调用次数
- 输出：`why_post`（选题理由）、`differentiation_angle`（差异化角度）、`target_audience`（目标受众）、`engagement_estimate`（互动预估 high/medium/low）
- 内容草稿：`draft_tweet`、`draft_script`、`draft_outline`

**降级策略**：整批失败时，为每个项目生成降级 topic（仅含基础推文草稿）。

### Stage 4: Curate — 加权筛选

`CuratorAgent` 纯计算，无 LLM 调用：

```
final_score = novelty × 0.15
            + utility × 0.20
            + local_ai × user_weight(默认0.30)
            + doc_quality × 0.10
            + engagement_boost × 0.25

engagement_boost = { high: 10, medium: 6, low: 3 }
```

按分数降序排列，取 Top N（默认 10）。`ScoringWeight` 表支持动态调整权重。

### Stage 5: Report — 报告输出

生成 Markdown 日报保存至 `reports/daily_report_YYYY-MM-DD.md`，同时返回 `DailyReport` 对象供 API/CLI 消费。

---

## 4. 数据模型

### 核心关系链

```
RawProject (1) ──► ProjectProfile (1) ──► TopicSuggestion (1) ──► UserAction (N)
      │                                              ▲
      └──────────────────────────────────────────────┘
              (PipelineRun 追踪整个执行过程)
```

### 关键表说明

| 表名 | 职责 | 关键字段 |
|---|---|---|
| `raw_projects` | 采集原始数据 | github_url(唯一索引)、owner、name、language、stars |
| `project_profiles` | LLM 分析结果 | novelty_score、utility_score、local_ai_relevance、analysis_status |
| `topic_suggestions` | 内容策略输出 | draft_tweet、engagement_estimate、final_score、generation_status |
| `user_actions` | 用户反馈 | action(pending/approved/published/skipped)、notes |
| `pipeline_runs` | 执行记录 | status、projects_collected、topics_generated、triggered_by |
| `pipeline_run_stages` | 阶段进度 | stage_name、status、progress(0-100) |
| `user_preferences` | 用户偏好 | positioning、local_ai_weight、daily_run_time、auto_publish |
| `scoring_weights` | 评分权重 | novelty/utility/local_ai/doc_quality/engagement_weight |

---

## 5. API 设计

### Router 列表

| Router | 前缀 | 关键端点 |
|---|---|---|
| `projects` | `/api/v1/projects` | GET 列表 |
| `topics` | `/api/v1/topics` | GET 列表(支持 status 过滤)、PATCH `/{id}/action`、GET `/stats` |
| `pipeline` | `/api/v1/pipeline` | POST `run` 触发执行、GET `/{id}` 查询状态 |
| `preferences` | `/api/v1/preferences` | GET/PUT 用户偏好 |
| `weights` | `/api/v1/weights` | GET/PUT 评分权重 |
| `reports` | `/api/v1/reports` | GET 列表、GET `/{date}` 查看 |
| `history` | `/api/v1/history` | GET 历史趋势数据 |

### 核心交互

```
# 触发流水线
POST /api/v1/pipeline/run
→ { run_id: 42, status: "running" }

# 轮询状态
GET /api/v1/pipeline/42
→ { status, stages: [...], projects_collected, topics_generated }

# 审核选题
PATCH /api/v1/topics/123/action
→ { action: "approved" }

# 获取统计
GET /api/v1/topics/stats
→ { pending, approved, published, skipped, total }
```

---

## 6. 前端架构

### 技术栈

- **构建**：Vite
- **样式**：Tailwind CSS
- **状态**：Zustand（仅 UI 状态：sidebar、activePipelineRunId）
- **数据获取**：自定义 hooks（`useApi.ts`），基于 axios + 手动缓存
- **路由**：React Router（5 个页面）

### 页面职责

| 页面 | 职责 |
|---|---|
| Dashboard | 统计卡片、最新待审选题、最近 Pipeline 运行记录 |
| Topics | 选题管理（四态 Tab + 排序）、操作按钮（采纳/发布/跳过/重置） |
| Pipeline | 手动触发流水线、运行历史列表 |
| History | 历史数据对比、趋势分析 |
| Settings | 用户偏好配置、评分权重实时调整 |

---

## 7. 调度系统

APScheduler `AsyncIOScheduler` 提供定时任务：

- 默认每天 09:00 自动执行 Pipeline（`daily_pipeline` job）
- 支持通过 `/api/v1/preferences` 修改 `daily_run_time` 重新调度
- 触发方式标记为 `triggered_by=scheduled`，与手动/API 触发区分

---

## 8. CLI 工具

Typer 构建的三命令 CLI：

```bash
gtr run          # 执行完整流水线（支持 --source --model --limit 等参数）
gtr report       # 查看报告（默认最新，支持 --date）
gtr config       # 查看当前用户偏好
```

`.env` 自动加载：CLI 启动时从项目根目录 `.env` 读取环境变量。

---

## 9. Prompt 体系

所有 Agent System Prompt 存放在 `prompts/` 目录：

| 文件 | 使用者 |
|---|---|
| `collector_system.md` | SearchCollectorAgent |
| `profiler_system.md` | ProjectProfilerAgent |
| `strategist_system.md` | ContentStrategistAgent |
| `curator_system.md` | CuratorAgent（辅助说明） |

`prompts.py` 提供统一加载器，支持热重载。

---

## 10. 关键技术决策

### 为什么用 SQLModel 而不是纯 SQLAlchemy？

SQLModel 由 FastAPI 作者开发，天然兼容 Pydantic，API Schema 和 DB Model 可以共享定义，减少样板代码。

### 为什么权重公式是硬编码的？

当前为启发式设定（基于业务经验），M3 阶段将引入校准机制：收集用户的 approve/skip 行为作为标签，定期优化权重。参见 TODOS.md。

### 为什么 Collector 支持多数据源？

GitHub Trending 页面结构不稳定，BeautifulSoup 解析可能失效。Tavily/Exa 提供 API 级采集能力作为 fallback，且语义搜索能发现 Trending 未覆盖的优质项目。

### 为什么 Profile 并发限制为 3？

LLM API 调用是主要瓶颈。限制并发可避免触发 rate limit，同时保持合理吞吐。缓存机制进一步降低实际调用量。

### 为什么前端用自定义 hooks 而不是 TanStack Query？

项目规模较小，自定义 hooks（`useApi.ts`）足够覆盖 CRUD + mutation 场景，避免引入额外依赖。

---

## 11. 部署与运行

### 环境变量（`.env`）

```bash
# LLM API（默认 DashScope / 通义千问）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 数据源 API（可选）
TAVILY_API_KEY=tvly-xxx
EXA_API_KEY=exa-xxx
```

### 启动方式

```bash
# 后端 API
python -m gtrdashboard.api.main   # localhost:9000

# 前端开发
npm run dev                        # localhost:5173

# CLI 运行
python -m gtrdashboard.cli run
```

---

## 12. 扩展路线图

当前完成 M1 + M2，M3 规划：

1. **推文生成优化** — draft_tweet 格式迭代、hashtags、线程拆分
2. **Twitter API 发布** — 一键发布 approved 状态的推文草稿
3. **HackerNews 数据源** — 补充采集源
4. **权重校准** — 基于用户行为的自动化 A/B 测试
5. **反推荐引擎** — 追踪 star 增速，预测即将流行的项目
