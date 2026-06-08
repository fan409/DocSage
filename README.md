# DocSage - 开源项目文档问答助手

基于 RAG（检索增强生成）的开源项目技术文档智能问答系统。支持对 Spring Framework、MyBatis、LangChain 等开源项目的官方文档进行语义检索和智能问答。

技术栈：FastAPI + LangChain + LangGraph + Milvus + Vue 3

## 本地部署

### 1) 环境准备
- Python `3.12+`
- 包管理建议：`uv`（也支持 `pip`）
- Docker / Docker Compose（用于启动 Milvus 依赖）

### 2) 使用 pyproject 安装依赖
在项目根目录执行：

```bash
# 方式 A：推荐（uv）
uv sync

# 运行服务
uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# 方式 B：pip
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# 运行服务
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

### 3) 创建 `.env` 文件
在项目根目录新建 `.env`，可直接使用下面模板：

```env
# ===== Model =====
ARK_API_KEY=your_ark_api_key
MODEL=your_model_name
BASE_URL=https://your-llm-endpoint/v1

# ===== 本地稠密向量（langchain_huggingface，默认 BAAI/bge-m3）=====
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
DENSE_EMBEDDING_DIM=1024

# ===== Rerank (可选，不配则自动降级) =====
RERANK_MODEL=your_rerank_model
RERANK_BINDING_HOST=https://your-rerank-host
RERANK_API_KEY=your_rerank_api_key

# ===== Milvus =====
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_COLLECTION=embeddings_collection

# ===== Database / Cache =====
DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/langchain_app
REDIS_URL=redis://127.0.0.1:6379/0

# ===== Auth =====
JWT_SECRET_KEY=replace-with-strong-random-secret
ADMIN_INVITE_CODE=docsage-admin-2026
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
PASSWORD_PBKDF2_ROUNDS=310000

# ===== BM25 稀疏统计持久化（默认 data/bm25_state.json，可改路径）=====
# BM25_STATE_PATH=/path/to/bm25_state.json

# ===== Auto-merging =====
# AUTO_MERGE_ENABLED=true
# AUTO_MERGE_THRESHOLD=2
# LEAF_RETRIEVE_LEVEL=3
```

### 4) Docker 部署（数据库 + 缓存 + 向量库）
当前仓库的 `docker-compose.yml` 同时承载业务依赖与 Milvus 依赖：
- 业务依赖：`postgres`、`redis`
- 向量依赖：`etcd`、`minio`、`standalone`、`attu`

```bash
# 启动所有依赖
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志（可选）
docker compose logs -f standalone
```

端口说明：
- PostgreSQL：`5432`
- Redis：`6379`
- Milvus：`19530`
- MinIO API：`9000` / Console：`9001`
- Attu：`8080`

### 5) 爬取官方文档

```bash
# 爬取所有源（每源默认 100 页）
python backend/doc_crawler.py --source all

# 单独爬取
python backend/doc_crawler.py --source spring --max-pages 50
python backend/doc_crawler.py --source mybatis --max-pages 30
python backend/doc_crawler.py --source langchain --max-pages 80
```

文档保存到 `data/docs/{source}/` 目录，每个页面一个 `.txt` 文件，包含 `title`、`url`、`content` 元信息。

### 6) 启动应用并访问
在 Milvus 启动后，运行后端应用：

```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

浏览器访问：
- 前端页面：`http://127.0.0.1:8000/`
- API 文档：`http://127.0.0.1:8000/docs`

### 7) 上传文档到知识库
以管理员身份登录后，在"设置"页面上传爬取的 `.txt` 文档文件。系统会执行三级分块、向量化并写入 Milvus。

## 项目概览

- **核心能力**：
  - LangChain Agent + 自定义工具，根据问题类型路由到不同处理路径。
  - 文档上传后执行三级滑动窗口分块（L1/L2/L3），叶子分块向量化写入 Milvus，父级分块写入 PostgreSQL。
  - 用户注册/登录、JWT 鉴权、基于角色的 RBAC 权限控制（admin/user）。
  - 会话记忆与摘要，聊天历史落地 PostgreSQL，并引入 Redis 缓存热点会话与父文档。
- **运行形态**：FastAPI 后端 + 纯前端（Vue 3 CDN 单页）+ Milvus 向量库。

## 关键创新点

- **混合检索落地**：稠密向量 + BM25 稀疏向量，Milvus Hybrid Search + RRF 排序，兼顾语义与词匹配。
- **Jina Rerank 接入**：Hybrid/Dense 召回后进行 API 级精排，支持返回 `rerank_score` 并在前端可视化。
- **双向降级**：稀疏生成或 Hybrid 调用失败时自动降级为纯稠密检索，提升稳定性。
- **流式输出（Streaming）**：后端基于 `agent.astream(stream_mode="messages")` 逐 token 推送，前端 SSE + ReadableStream 实现打字机效果。
- **实时 RAG 过程可视化**：检索过程在模型"思考中"阶段就开始展示，通过 `asyncio.Queue` + 后台任务架构实现工具执行期间的实时推送。
- **回答终止功能**：前端 `AbortController` + 后端 `StreamingResponse` 支持用户随时中断正在生成的回答。
- **会话摘要记忆**：自动摘要旧消息并注入系统提示，维持上下文且控制 token。
- **文档处理链路**：上传 → 切分 → 稠密/稀疏向量同步生成 → Milvus 入库，支持重复上传自动清理旧 chunk。
- **BM25 统计持久化**：`词表 + 文档频次 df + 文档数 N` 落盘到 `data/bm25_state.json`，入库时增量增加、删除/覆盖上传前按文件名从 Milvus 拉取 chunk 文本后增量扣减，与向量库同步；`embedding_service` 在 API 与检索模块间单例共享。
- **三级分块 + Auto-merging**：L1/L2/L3 三层滑窗切分；检索时优先召回 L3，满足阈值后自动合并到父块（L3->L2->L1）。
- **Leaf-only 向量化存储**：仅叶子分块写入 Milvus，父块写入 DocStore，减少向量冗余并保留上下文聚合能力。
- **工具可扩展**：知识库检索工具可按需增添第三方 API 或企业数据源。
- **RAG 过程可观测**：记录检索、评分、重写与来源信息，前端可展开查看每一步细节。
- **查询重写体系**：Step-Back 与 HyDE 两种扩展方式 + 路由选择，必要时触发重写检索。
- **相关性评分门控**：基于结构化输出的 `grade_documents` 判断是否需要重写检索。
- **实时思考链路展示**：通过 `asyncio` 事件循环穿透技术，实现 Agent 在执行 RAG、评分、重写等同步工具时，实时向前端推送思考步骤（Searching -> Grading -> Rewriting），彻底解决"静默思考"问题。
- **RAG 检索评估体系**：内置 18 个问答对测试集，支持 Dense-only / Hybrid / Hybrid+Rerank 三种模式对比，输出 Hit Rate、Keyword Recall、MRR 指标。

## 目录与架构

```
├── backend/
│   ├── app.py                  # FastAPI 入口、CORS、静态资源挂载
│   ├── api.py                  # 聊天、会话管理、文档管理接口
│   ├── auth.py                 # 注册登录、JWT 鉴权、权限检查、密码哈希
│   ├── database.py             # 数据库引擎与会话工厂、建表入口
│   ├── models.py               # ORM 模型（User、ChatSession、ChatMessage、ParentChunk）
│   ├── cache.py                # Redis JSON 缓存封装
│   ├── agent.py                # LangChain Agent、会话存储、摘要逻辑
│   ├── tools.py                # 天气查询、知识库检索工具
│   ├── rag_pipeline.py         # LangGraph RAG 状态机（retrieve -> grade -> rewrite）
│   ├── rag_utils.py            # 检索逻辑：hybrid search、auto-merge、rerank、step-back、HyDE
│   ├── embedding.py            # 本地 HuggingFace 稠密向量 + BM25 稀疏向量
│   ├── document_loader.py      # PDF/Word/Excel 加载与三级滑窗分块
│   ├── parent_chunk_store.py   # 父级分块仓储（PostgreSQL + Redis，Auto-merging 回取）
│   ├── milvus_writer.py        # 向量写入（稠密+稀疏）
│   ├── milvus_client.py        # Milvus 集合定义、混合检索、dense 检索
│   ├── schemas.py              # Pydantic 请求/响应模型
│   ├── upload_jobs.py          # 上传任务进度管理
│   ├── doc_crawler.py          # 开源项目官方文档爬虫（Spring/MyBatis/LangChain）
│   ├── eval_rag.py             # RAG 检索评估脚本（Dense vs Hybrid vs Rerank）
│   └── test_cases.py           # 评估测试集（18 个问答对）
│
├── frontend/
│   ├── index.html              # Vue 3 SPA 单页
│   ├── script.js               # 前端逻辑：认证、SSE 流式、文档管理
│   └── style.css               # 样式（蓝灰色专业主题）
│
├── data/
│   ├── bm25_state.json         # BM25 词表与统计（稀疏检索 IDF）
│   ├── documents/              # 上传文档原文件
│   └── docs/                   # 爬取的官方文档（按 source 分目录）
│
├── docker-compose.yml          # PostgreSQL + Redis + Milvus + Attu
├── pyproject.toml              # Python 依赖
└── .env.example                # 环境变量模板
```

## 核心流程

### 1) 项目全链路（端到端）
1. 用户在前端输入问题，调用 `POST /chat/stream`（流式）。
2. FastAPI `api.py` 返回 `StreamingResponse(media_type="text/event-stream")`。
3. LangChain Agent 根据问题类型决定是否调用工具（天气查询 / 知识库检索）。
4. 若命中知识库工具，进入 `rag_pipeline.py` 执行检索工作流，各阶段通过 `emit_rag_step()` 实时推送到前端。
5. 检索结果与 RAG Trace 一起返回，Agent 流式生成最终回答（逐 token 推送）。
6. 前端 ReadableStream 逐块解析 SSE，打字机效果实时渲染。
7. 同时消息持久化到 PostgreSQL，并通过 Redis 缓存加速历史会话回放。

### 2) RAG 全链路（重点）
1. **初次召回**：`retrieve_initial`
   - 调用 `retrieve_documents`。
   - 先按 `chunk_level == 3` 执行 Milvus Hybrid 检索（Dense + Sparse + RRF）。
   - 取更大候选集后走 Jina Rerank 精排。
   - 对召回叶子块执行 Auto-merging（L3->L2->L1），父块从 DocStore 读取。
2. **相关性打分门控**：`grade_documents`
   - 使用结构化输出打分 `yes/no`。
   - `yes` 直接进入生成回答；`no` 进入重写阶段。
3. **查询重写路由**：`rewrite_question`
   - 在 `step_back / hyde / complex` 中选择策略。
   - 生成 `rewrite_query`、`step_back_question`、`hypothetical_doc` 等中间结果。
4. **二次召回**：`retrieve_expanded`
   - 对重写后的查询（或 HyDE 文档）再次检索。
   - 同样执行 L3 召回 + Auto-merging，结果去重后返回上下文。
5. **答案生成**：Agent 结合上下文生成最终回答。
6. **可观测追踪**：返回 `rag_trace`，包括评分结果、重写策略、检索分数、合并信息等。

### 3) 文档入库链路
1. 前端上传文档到 `POST /documents/upload/async`。
2. 若同名文件已存在：先从 Milvus 分页查询该文件全部叶子 chunk 的 `text`，对 BM25 统计执行 `increment_remove`，再删除旧向量与父块缓存。
3. `document_loader.py` 执行三级滑动窗口分块并写入层级元数据（`chunk_id` / `parent_chunk_id` / `root_chunk_id` / `chunk_level`）。
4. L1/L2 父级分块写入 `parent_chunk_store.py`（PostgreSQL + Redis）。
5. L3 叶子分块在 `milvus_writer` 中先对本轮 chunk 文本执行 BM25 `increment_add`，再经 `embedding.py` 生成 Dense 与 Sparse 向量并写入 Milvus。
6. 后续检索可直接利用新文档参与召回。

### 4) BM25 状态文件（`data/bm25_state.json`）
- **内容**：`version`、全局 `total_docs`（chunk 篇数）、`sum_token_len`、`vocab`（词 → 稀疏维度下标）、`doc_freq`（词 → 文档频次，用于 IDF）。
- **增量**：每入库一批叶子 chunk 增加统计；删除文档或覆盖上传前按文件名扣减。词表下标不回收，避免与历史稀疏向量维度冲突。

### 5) 会话记忆链路
1. 每轮问答按当前登录用户 + `session_id` 写入 PostgreSQL。
2. 当消息过长时触发摘要压缩，保留长期上下文。
3. Redis 缓存会话列表与会话消息，减少高频读取数据库压力。
4. 前端可通过会话接口读取、删除当前用户自己的历史对话。

## 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| 后端框架 | FastAPI + Uvicorn | 异步 Web 服务，SSE 流式输出 |
| AI/Agent | LangChain + LangGraph | Agent 编排、工具调用、RAG 状态机 |
| LLM | OpenAI 兼容 API | 字节跳动豆包模型（doubao-seed-2-0-pro 等） |
| 稠密嵌入 | BAAI/bge-m3 (HuggingFace) | 本地部署，1024 维，L2 归一化 |
| 稀疏检索 | BM25（手写实现） | 中英混合分词，统计持久化到 JSON |
| 向量数据库 | Milvus 2.5 | HNSW 稠密索引 + SPARSE_INVERTED_INDEX 稀疏索引 |
| 融合排序 | RRF (k=60) | Reciprocal Rank Fusion，无参数化融合 |
| 精排 | Jina Reranker v3 | 可选，API 调用，支持降级 |
| 关系数据库 | PostgreSQL 15 | 用户、会话、消息、父级分块存储 |
| 缓存 | Redis 7 | 会话缓存、父文档缓存，TTL 过期 |
| 认证 | JWT + PBKDF2-SHA256 | python-jose 签发，角色隔离（admin/user） |
| 前端 | Vue 3 (CDN) | marked.js + highlight.js，纯静态部署 |
| 包管理 | uv / pip | Python 3.12+ |

## 环境变量

需在仓库根目录或运行环境配置：
- 模型相关：`ARK_API_KEY`、`MODEL`、`BASE_URL`
- 稠密向量：`EMBEDDING_MODEL`、`EMBEDDING_DEVICE`、`DENSE_EMBEDDING_DIM`
- BM25 持久化：`BM25_STATE_PATH`（可选，默认 `data/bm25_state.json`）
- Rerank 相关：`RERANK_MODEL`、`RERANK_BINDING_HOST`、`RERANK_API_KEY`
- Milvus：`MILVUS_HOST`、`MILVUS_PORT`、`MILVUS_COLLECTION`
- 数据库缓存：`DATABASE_URL`、`REDIS_URL`
- 鉴权相关：`JWT_SECRET_KEY`、`ADMIN_INVITE_CODE`、`JWT_ALGORITHM`、`JWT_EXPIRE_MINUTES`
- 密码参数：`PASSWORD_PBKDF2_ROUNDS`
- Auto-merging：`AUTO_MERGE_ENABLED`、`AUTO_MERGE_THRESHOLD`、`LEAF_RETRIEVE_LEVEL`

## API 速览

- 鉴权
  - `POST /auth/register`：注册（支持普通用户/管理员邀请码模式）
  - `POST /auth/login`：登录，返回 Bearer Token
  - `GET /auth/me`：获取当前登录用户信息
- 聊天
  - `POST /chat/stream`：聊天（流式 SSE），入参 `message`、`session_id`，返回 `text/event-stream`
- 会话（用户隔离）
  - `GET /sessions`：列出当前用户会话
  - `GET /sessions/{session_id}`：拉取当前用户某会话消息
  - `DELETE /sessions/{session_id}`：删除当前用户会话
- 文档（管理员权限）
  - `GET /documents`：列出已入库文档及 chunk 数
  - `POST /documents/upload/async`：上传并向量化文档
  - `DELETE /documents/delete/async/{filename}`：删除指定文档向量数据
- 评估
  - `python backend/eval_rag.py`：运行 Dense-only / Hybrid / Hybrid+Rerank 对比评估

## 流式输出与实时检索过程 — 技术细节

### 1. 跨线程事件调度（Cross-Thread Event Scheduling）

这是一个解决"同步工具阻塞异步事件循环"问题的关键架构设计。

**痛点**：FastAPI 运行在单线程的 asyncio Event Loop 上。LangChain 将同步工具（如 `search_knowledge_base`）放到 `ThreadPoolExecutor` 中运行，但在子线程中无法直接访问主线程的 `asyncio.Queue`。

**解决方案 — "Global Loop Capture + Threadsafe Callback" 模式**：

1. **Loop 捕获（Main Thread）**：Agent 开始生成前，主线程调用 `set_rag_step_queue()`，捕获当前运行循环 `_RAG_STEP_LOOP = asyncio.get_running_loop()` 并保存为全局变量。
2. **跨线程发射（Worker Thread）**：RAG 工具在子线程运行时调用 `emit_rag_step()`，内部使用 `_RAG_STEP_LOOP.call_soon_threadsafe(queue.put_nowait, step_data)`。
3. **原理**：`call_soon_threadsafe` 是 asyncio 唯一允许从其他线程向 Loop 注入回调的方法，主 Loop 在下一次 tick 立即执行，实现数据平滑流转。

```python
# 核心代码摘要 (tools.py)
def set_rag_step_queue(queue):
    global _RAG_STEP_QUEUE, _RAG_STEP_LOOP
    _RAG_STEP_QUEUE = queue
    _RAG_STEP_LOOP = asyncio.get_running_loop()  # 关键：在主线程捕获 Loop

def emit_rag_step(icon, label):
    if _RAG_STEP_LOOP and not _RAG_STEP_LOOP.is_closed():
        _RAG_STEP_LOOP.call_soon_threadsafe(
            _RAG_STEP_QUEUE.put_nowait,
            {"icon": icon, "label": label}
        )
```

### 2. 混合检索（Hybrid Search）深度实现

项目手动构建了稀疏-稠密双塔检索：

- **Dense Pathway**：使用 `langchain_huggingface.HuggingFaceEmbeddings`（默认 `BAAI/bge-m3`）生成稠密向量，维度 1024，L2 归一化后与 Milvus `IP` 度量配合。
- **Sparse Pathway**：在 `embedding.py` 中基于中英混合规则分词（单字中文 + 英文单词）实现 BM25，生成 `{稀疏维度下标: BM25 分数}`，写入 Milvus `SPARSE_FLOAT_VECTOR`。全局 `N` / `doc_freq` / 平均文档长等统计持久化在 `bm25_state.json`，入库与删除走增量更新。
- **Milvus 融合**：使用 `AnnSearchRequest` 同时发起两个请求，`RRFRanker(k=60)` 倒数排名融合，避免加权求和中调节 `alpha` 参数的困难。

### 3. 前端 "Thinking State Machine"

前端 `script.js` 维护了一个微型状态机来处理 SSE 混合流：

1. **Idle**：等待用户输入。
2. **Thinking (Initial)**：创建消息气泡，`isThinking=true`，显示跳动圆点。
3. **Thinking (Active RAG)**：收到 `type: rag_step` 事件，动态更新 Header 文字（如"正在重写查询..."），向 `ragSteps` 数组追加步骤。
4. **Streaming**：收到第一个 `type: content` 事件，立即设置 `isThinking=false`，在同一气泡内开始追加 Markdown 文本，实现从"思考"到"回答"的无缝视觉过渡。

## 整体架构

```
用户发送消息
    │
    ▼
POST /chat/stream → StreamingResponse(text/event-stream)
    │
    ▼
chat_with_agent_stream()
    │
    ├── 创建统一输出队列 (asyncio.Queue)
    ├── 设置 _RagStepProxy → emit_rag_step() 的输出直接入队
    ├── 启动 _agent_worker 后台任务 (asyncio.create_task)
    │     └── agent.astream(stream_mode="messages") 逐 token 产出
    │           ├── AIMessageChunk (文本) → {"type": "content"} 入队
    │           └── tool_call_chunks (工具调用) → 跳过
    │
    └── 主循环：await output_queue.get() → yield SSE
          ▲
          │ (并发) RAG 工具在线程池中执行
          │ emit_rag_step() → loop.call_soon_threadsafe → 入队
          │ {"type": "rag_step"} 立即从队列取出并推送到前端
```

### 后端实现

#### 1) 流式生成 (`agent.py`)
- 使用 LangGraph `agent.astream(stream_mode="messages")` 获取逐 token 的 `AIMessageChunk`。
- 过滤 `tool_call_chunks`，只转发文本内容给前端。
- Agent 流式循环运行在 `asyncio.create_task` 后台任务中，主生成器只负责从统一 `output_queue` 取事件并 yield。RAG 步骤在工具执行期间仍可实时推送到前端。

#### 2) 实时 RAG 步骤推送 (`tools.py` + `rag_pipeline.py`)
- `emit_rag_step(icon, label, detail)` 通过 `call_soon_threadsafe` 从同步线程安全推送到异步队列。
- `_RagStepProxy` 代理对象将 step dict 包装为 `{"type": "rag_step", "step": {...}}` 后放入统一输出队列，无需额外 relay 任务。
- `rag_pipeline.py` 在每个关键节点发射步骤：
  - `retrieve_initial` → "正在检索知识库..."
  - `grade_documents` → "正在评估文档相关性..."
  - `rewrite_question` → "正在重写查询..."（含策略选择）
  - `retrieve_expanded` → "使用扩展查询重新检索..."

#### 3) SSE 协议格式
每个事件格式：`data: {JSON}\n\n`，类型字段：
- `content`：文本 token（打字机效果）
- `rag_step`：实时检索步骤（`{icon, label, detail}`）
- `trace`：完整 RAG 追踪信息（回答完成后发送）
- `error`：错误信息
- `[DONE]`：流结束标记

#### 4) 终止功能
- 前端 `AbortController` 触发后，FastAPI 的 `StreamingResponse` 检测到 socket 断开。
- 生成器收到 `GeneratorExit`，显式执行 `agent_task.cancel()`。
- `agent_task.cancel()` 立即注入 `CancelledError`，触发 `httpx` 关闭 TCP 连接，服务端停止推理，实现真正的 Token 节省。

### 前端实现

#### 1) ReadableStream 解析 (`script.js`)
- 使用 `response.body.getReader()` + `TextDecoder` 逐块读取。
- 手动按 `\n\n` 分割 SSE 事件，解析 `data: ` 前缀后的 JSON。
- `content` 事件追加到消息文本；`rag_step` 事件追加到检索步骤数组。

#### 2) 思考气泡二合一
- 发送消息后立即创建带 `isThinking: true` 的气泡，显示跳动圆点 + 动态文字。
- 收到 `rag_step` 时，`thinkingLabel` 更新为当前步骤。
- 收到第一个 `content` token 时，`isThinking = false`，同一气泡无缝切换为正常文本流。

#### 3) Vue 3 响应式注意事项
- 通过 `this.messages[botMsgIdx]` 索引访问确保拿到 Vue 的 reactive proxy。
- `ragSteps` 数组通过 `push()` 触发响应式更新。

## RAG 检索评估

### 运行评估

```bash
python backend/eval_rag.py
```

### 测试集

`backend/test_cases.py` 包含 18 个问答对，覆盖三个文档源：

| 类型 | 数量 | 示例 |
|------|------|------|
| 事实型 | 6 | "@Transactional 的 propagation 有哪些值？" |
| 概念型 | 6 | "一级缓存和二级缓存有什么区别？" |
| 用法型 | 4 | "LangChain 中如何自定义 Tool？" |
| 跨文档型 | 2 | "Spring 和 MyBatis 整合时如何配置数据源？" |

### 评估指标

- **Hit Rate@5**：top-5 结果中是否有包含预期关键词的 chunk
- **Keyword Recall@5**：预期关键词在 top-5 chunk 中被覆盖的比例
- **MRR**：第一个相关结果的排名倒数

### 输出样例

```
模式                   Hit Rate@5   Keyword Recall    Avg MRR
---------------------------------------------------------------
Dense-only                  0.75            0.62       0.58
Hybrid                      0.85            0.78       0.72
Hybrid+Rerank               0.90            0.85       0.81
```

同时生成 `eval_report.md`，包含完整对比表格和每个 case 的详细结果。

## License

MIT
