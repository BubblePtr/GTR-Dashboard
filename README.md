# GTR Dashboard

GitHub Trending 多 Agent 选题流水线。

自动采集 GitHub Trending 项目，通过多 Agent 分析生成内容选题建议，辅助社交媒体内容创作。

## 快速开始

```bash
# 1. 安装后端依赖
pip install -e ".[dev]"

# 2. 配置 API Key（复制 .env.example 为 .env，填入你的 Key）
cp .env.example .env

# 3. 安装前端依赖
cd frontend && npm install
```

### 启动开发环境

**一键启动前后端（推荐）：**
```bash
cd frontend
npm run dev:all
```

**分别启动：**
```bash
# 终端 1 — 后端 API
gtr-api
# 或：python -m gtrdashboard.api.main

# 终端 2 — 前端开发服务器
cd frontend
npm run dev
```

**运行流水线（CLI）：**
```bash
python -m gtrdashboard.cli run
# 或：gtr run

# 运行测试
pytest
```

## 模型配置

默认使用 **通义千问 qwen3.6-max-preview**（通过 DashScope 兼容 API）。

如需改用 OpenAI 或其他兼容 provider，修改 `.env`：

```bash
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1  # 或其他兼容 endpoint
```

运行时可覆盖模型：

```bash
gtr run --model gpt-4o-mini
```

## 项目结构

```
src/
  agents/         # Agent 实现
  models.py       # SQLModel 数据模型
  database.py     # 数据库操作
  prompts.py      # Prompt 加载器
  pipeline.py     # 流水线编排器
  cli.py          # CLI 入口
prompts/          # Agent prompt 模板
tests/            # 测试
```
