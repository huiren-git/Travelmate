# TravelMate

> 基于 FastAPI、React 与 LangGraph 多 Agent 的智能旅行规划和动态应急助手。

TravelMate 将自然语言旅行需求转成可执行的日程，并支持预算控制、偏好记忆、增量重规划、流式生成、行程中断恢复以及全链路 Trace。项目同时提供 Mock LLM 回归与真实模型基准设施，可量化验证 Agent 的质量、延迟、Token 和调用成本。

## 核心能力

- **智能行程生成**：根据目的地、日期、预算、同行人、节奏和兴趣生成每日行程。
- **多 Agent 编排**：由 LangGraph 协调需求理解、行程生成、成本补全、预算校验与重规划。
- **预算中断与恢复**：预算超支时展示决策；选择方案后从同一检查点恢复，避免重复执行。
- **状态驱动的重规划**：行程项按 `upcoming → ongoing → completed` 刷新状态；`ongoing` 和 `completed` 项不可修改。
- **用户偏好与隔离**：支持维护个人偏好并影响后续规划；前端可切换整数用户 ID 以验证用户隔离。
- **流式交互与停止生成**：通过 SSE 推送 Agent 过程与结果，可停止正在执行的生成任务。
- **可观测性与评测**：记录 Trace、Span、LLM Token、TTFT、端到端延迟和模型成本，并提供真实模型基准及匿名人工评分包。

## 架构概览

```text
React + TypeScript (Vite)
        │  HTTP / SSE
        ▼
FastAPI API
        │
        ▼
LangGraph 多 Agent 工作流
  Supervisor → Itinerary → Cost Enrich → Budget / Replan
        │
        ├── SQLite（会话、检查点、Trace）
        ├── ChromaDB（偏好与行为记忆）
        ├── Redis（外部数据缓存，可选）
        └── LLM / 高德地图 / 和风天气
```

## 技术栈

| 分层 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、Vite、Ant Design、Zustand |
| 后端 | Python 3.10+、FastAPI、Pydantic、Uvicorn |
| Agent | LangChain、LangGraph、DeepSeek / OpenAI / Qwen / Moonshot |
| 数据与缓存 | SQLite、ChromaDB、Redis（可选） |
| 测试与评测 | Pytest、Node Test、真实模型基准、Trace 与人工双评 |

## 目录结构

```text
.
├── backend/
│   ├── src/                 # FastAPI、Agent、工作流与数据服务
│   ├── tests/               # 后端单元与接口测试
│   └── benchmarks/          # 真实模型基准、参考数据、评分包脚本
├── frontend/
│   ├── src/                 # React 页面、组件、状态与 API 客户端
│   └── tests/               # 前端回归测试
├── UI设计/                  # 交互/视觉设计资料
└── api说明书/               # API 说明资料
```

## 快速开始

### 1. 前置要求

- Python 3.10 或更高版本
- Node.js 20 或更高版本
- npm 10 或兼容版本

Redis 为可选依赖：未配置 `REDIS_URL` 时，缓存功能会降级，不影响本地基础启动。

### 2. 配置后端环境

在 `backend` 目录创建 `.env`（不要提交到 Git）：

```dotenv
# 至少配置一个与 DEFAULT_LLM_MODEL 对应的模型密钥
DEEPSEEK_API_KEY=your_deepseek_key
DEFAULT_LLM_MODEL=deepseek:deepseek-chat

# 可选：真实地图和天气数据
AMAP_API_KEY=your_amap_key
QWEATHER_API_KEY=your_qweather_key
QWEATHER_API_HOST=your_qweather_host

# 可选：Redis 缓存
REDIS_URL=redis://localhost:6379/0
```

可替换为 `OPENAI_API_KEY`、`QWEN_API_KEY` 或 `MOONSHOT_API_KEY`，并同步调整 `DEFAULT_LLM_MODEL`。运行时数据库默认写入 `backend/data/`；如需隔离环境，可设置 `DATABASE_DIR`。

### 3. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

启动后可访问：

- API 文档：<http://localhost:8000/api/docs>
- 健康检查：<http://localhost:8000/api/v1/health>

### 4. 启动前端

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>。Vite 会将 `/api` 请求代理到 `http://localhost:8000`。

## 测试与质量基准

```powershell
# 后端核心接口回归
cd backend
python -m pytest -q tests/test_chat_api.py

# 前端关键交互回归
cd ..\frontend
node --test tests/chatStop.test.mjs tests/reference.test.mjs

# 前端生产构建
npm run build
```

完整用例设计、质量门槛和实测结果见 [docs/TravelMate-测试用例设计书.md](docs/TravelMate-测试用例设计书.md)。覆盖功能正确性、Agent 质量、性能成本和鲁棒性四个维度；真实模型基准脚本位于 `backend/benchmarks/`。
