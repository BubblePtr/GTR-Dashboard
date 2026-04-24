# TODOS

## M1: Agent Pipeline + SQLite + CLI Markdown

### Done

- [x] 搭建项目结构（pyproject.toml, 目录结构）
- [x] SQLModel 数据模型定义（raw_projects, project_profiles, topic_suggestions, user_actions, pipeline_runs, pipeline_run_stages, user_preferences, scoring_weights）
- [x] Prompt 加载器（从 prompts/*.md 加载）
- [x] TrendingCollectorAgent（BeautifulSoup 爬取 GitHub Trending）
- [x] SearchCollectorAgent（Tavily AI 搜索）
- [x] ExaCollectorAgent（Exa 语义搜索）
- [x] ProjectProfilerAgent（并行分析，max 3 并发，缓存策略，降级策略）
- [x] ContentStrategistAgent（批量处理，10 项目/批，降级策略）
- [x] CuratorAgent（加权排序，显式状态标签）
- [x] Pipeline orchestrator（统一调度 + 批量写入 SQLite + stage 进度追踪）
- [x] CLI Markdown 报告生成器
- [x] 单元测试（pytest，7 个测试模块）
- [x] Eval 测试（pipeline 端到端验证）
- [x] 设计文档审批（/office-hours）
- [x] 工程审查（/plan-eng-review）

---

## M2: FastAPI + React Dashboard

### Done

- [x] FastAPI REST API（projects / topics / pipeline / preferences / weights / reports / history）
- [x] React Dashboard（Vite + Tailwind，5 页面）
- [x] 状态管理（待审核 / 已采纳 / 已发布 / 跳过）
- [x] 实时权重调整 UI（SettingsPage + `/api/v1/weights`）
- [x] 历史对比功能（HistoryPage + `/api/v1/history`）
- [x] APScheduler 定时任务（`run_scheduled_pipeline`）

---

## M3: Content Export + Platform Integration（Next）

### In Progress

- [ ] **推文生成质量优化** — draft_tweet 目前由 strategist 一次性生成，需要迭代优化格式、 hashtags、线程拆分
- [ ] **报告汇总增强** — 从纯 Markdown 扩展到支持多格式导出（如 JSON / 结构化摘要）

### Todo

- [ ] **Twitter API 自动发布** — 对接 X API，支持一键发布 approved 状态的推文草稿
- [ ] **HackerNews 数据源** — 增加 HN 作为补充采集源
- [ ] **加权公式校准策略** — 当前权重是启发式设定（novelty×0.15 + utility×0.20 + local_ai_relevance×user_weight + doc×0.10 + engagement×0.25）。需要建立校准机制：手动 A/B 测试、收集 approve/skip 反馈作为标签、或定期 review
- [ ] **反推荐引擎** — 追踪 star 增速，预测即将火的项目
- [ ] **Docker 镜像 / CI/CD** — 容器化部署与 GitHub Actions

---

## Deferred（No Timeline）

- [ ] 多语言趋势扩展（ beyond GitHub Trending ）
- [ ] 用户行为分析看板（approve/skip 率趋势图）
