# Take-U-Trip 🧳

> 一个多智能体协作的智能旅游规划 Agent：用自然语言说清目的地、天数、预算和出发地，自动调用真实工具查询天气、景点、交通、酒店、餐饮，并产出一份带坐标、带预算核算、可在地图上导航的完整行程。

## ✨ 特性

- **多智能体编排（LangGraph）**：`Intake（意图识别）→ Planner（规划）→ Budgeter（确定性预算核算）→ Reviewer（独立审查打回）→ Finalize（定稿）`，局部修改走独立的 Modify 子图。
- **工具调用真实可用**：
  - 天气：和风天气（QWeather）未来 3 天预报
  - 景点/餐饮/酒店：高德 POI 检索，自动带经纬度
  - 大交通：12306 真实余票查询（多端点轮换 + 重试，抗反爬抖动）
  - 市内路线：高德驾车路径规划（带地理编码缓存，避免重复请求）
- **MCP 接入 Planner**：天气与景点通过 Model Context Protocol 独立子进程提供，Planner 通过 `bind_tools` 真实调用。
- **确定性兜底**：
  - Budgeter 不相信模型自己填的数字，用代码重算每天/分类费用；
  - `dedup_activities` 在结构化产出后确定性去除重复景点；
  - 时间感知模块统一注入"今天/明天/未来日期"，避免模型用过时示例日期。
- **前端**：React + Vite + Tailwind，聊天（SSE 流式）、行程清单、愿望清单、地图导航四页；地图用高德 JS API。

## 🧱 技术栈

| 层 | 技术 |
|---|---|
| LLM | DeepSeek（OpenAI 兼容接口） |
| 编排 | LangGraph + LangChain |
| 后端 | FastAPI + Uvicorn + SSE（sse-starlette） |
| 数据库 | SQLite + SQLAlchemy（业务库 + LangGraph checkpoint） |
| MCP | FastMCP（stdio） |
| 前端 | React 18 + Vite + TypeScript + Tailwind |
| 外部数据 | 高德 Web 服务、和风天气、12306（非官方逆向，免费免登录） |

## 🚀 快速开始

### 前置要求

- Python ≥ 3.11
- Node.js ≥ 18
- 各服务的 API Key（见下方环境变量）

### 1. 后端

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -e .
cp .env.example .env   # 然后填入真实 Key
uvicorn app.main:app --reload
```

后端启动在 <http://127.0.0.1:8000>，健康检查：`GET /health`。

> ⚠️ MCP 工具在后端启动时作为独立子进程拉起。修改 `mcp_server/` 或 adapter 代码后，需要**整体重启后端**，`--reload` 不会重启 MCP 子进程。

### 2. 前端

```bash
cd frontend
npm install
cp .env.example .env.local   # 填入高德 Web 端 Key
npm run dev
```

前端开发服务器默认在 <http://localhost:5173>。

## 🔑 环境变量

后端 `backend/.env`（参考 `.env.example`）：

| 变量 | 说明 |
|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL_NAME` | DeepSeek 接口，默认 `deepseek-chat` |
| `AMAP_API_KEY` | 高德 Web 服务 Key（POI/地理编码/路径规划） |
| `QWEATHER_API_KEY` / `QWEATHER_API_HOST` | 和风天气 Key 及专属 Host |
| `ADAPTER_MODE` | `mock`（假数据）或 `real`（真实 API） |
| `DB_URL` | 数据库连接，默认 SQLite |

前端 `frontend/.env.local`（参考 `.env.example`）：

| 变量 | 说明 |
|---|---|
| `VITE_AMAP_KEY` | 高德 **Web 端(JS API)** Key |
| `VITE_AMAP_SECURITY_CODE` | 高德 Web 端安全密钥（jscode） |

> 这些 Key 都**不要提交到 git**。`.env`、`.env.local`、`*.db`、`.venv`、`node_modules` 已在 `.gitignore` 中排除。

## 📁 目录结构

```
Take-U-Trip/
├── backend/
│   ├── app/
│   │   ├── adapters/        # 数据访问三层：base 抽象 → mock 假数据 → real 真实 API
│   │   │   └── real/        #   高德 POI、12306、和风天气、路线
│   │   ├── api/             # FastAPI 路由（SSE 聊天、行程、愿望清单）
│   │   ├── core/            # 多智能体图：multi_nodes / multi_graph / now(时间)
│   │   ├── memory/          # SQLite 记忆、用户画像、工具缓存
│   │   ├── models/          # Itinerary / Review / Intention 等 Pydantic 模型
│   │   └── tools/           # 对外工具封装
│   └── mcp_server/          # FastMCP 天气 / 景点服务
├── frontend/
│   └── src/
│       ├── pages/           # Chat / Itinerary / Wishlist / Map 四页
│       ├── stores/          # Zustand 状态
│       └── lib/             # 地图加载、地理编码、工具函数
└── docs/
```

## ⚠️ 已知数据边界（诚实说明）

为避免给使用者造成误解，这里明确标注哪些数据是**估算/占位**而非真实证据：

- 高德免费 POI 接口**不返回门票、开放时间、房价、人均消费**，这些字段当前为兜底占位值，行程里会以 warnings 形式提示"以实际为准"。
- 12306 余票接口**不返回票价**；机票暂无免费数据源。
- 和风天气免费档仅提供**未来 3 天**预报。
- 12306 为非官方逆向接口，仅用于学习演示，不保证长期稳定。


## 📄 License

[MIT](./LICENSE)
