# Python 实现小说转剧本后端（YAML 驱动版）

> **项目定位**：面向小说作者的 AI 辅助剧本创作工具。作者上传 3 章以上的小说文本，系统通过多 AI 智能体协作，自动生成**结构化 YAML 剧本**，让作者快速获得可编辑、可进一步打磨的剧本初稿。
>
> **核心差异化**：输出采用 **YAML 格式而非纯文本**，每个场景、镜头、对白、音效都是结构化数据，作者可直接在编辑器中修改 YAML，前端可据此渲染可视化剧本。

---

## 技术栈

| 组件 | 选择 | 原因 |
|---|---|---|
| Web 框架 | **FastAPI** | 原生 async、Pydantic 校验、SSE 支持好 |
| ORM | **SQLAlchemy 2.0** + Alembic | 异步支持成熟 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 轻量开发、生产可扩展 |
| AI SDK | **openai Python SDK** (`AsyncOpenAI`) | 官方 SDK，异步原生支持 |
| 结构化输出 | **instructor** | 强制 AI 输出符合 YAML Schema 的结构化数据 |
| SSE | **sse-starlette** | FastAPI 原生 SSE 支持 |
| 认证 | **python-jose** (JWT) | 成熟稳定的 JWT 方案 |
| 加密 | **cryptography** (AES-256-GCM) | 业界标准的对称加密 |
| ID 混淆 | **hashids** | 短 ID 混淆，防枚举 |
| **YAML** | **pyyaml** | YAML 序列化/反序列化 |

---

## 项目目录结构

```
novel2script-api/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置管理（pydantic-settings）
│   ├── database.py                # SQLAlchemy 异步引擎 & Session
│   ├── dependencies.py            # 依赖注入（get_db, get_current_user）
│   │
│   ├── models/                    # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── novel_project.py
│   │   ├── novel_chapter.py
│   │   ├── novel_storyline.py
│   │   ├── novel_episode.py       # script_content 改为 YAML 格式存储
│   │   ├── novel_asset.py
│   │   ├── novel_chat_history.py
│   │   ├── user_model.py
│   │   └── user_model_scene.py
│   │
│   ├── schemas/                   # Pydantic 请求/响应模型
│   │   ├── __init__.py
│   │   ├── novel_project.py
│   │   ├── novel_agent.py
│   │   ├── novel_script.py
│   │   ├── model_config.py
│   │   └── common.py
│   │
│   ├── api/                       # FastAPI 路由
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── novel_project.py
│   │   ├── novel_agent.py         # 多智能体对话 SSE
│   │   ├── novel_script.py        # 剧本生成 SSE（返回 YAML）
│   │   ├── novel_asset.py
│   │   └── model_config.py
│   │
│   ├── services/                  # 业务逻辑
│   │   ├── __init__.py
│   │   ├── novel_project.py
│   │   ├── novel_agent.py         # 多智能体编排（核心~1200行）
│   │   ├── novel_script.py        # 剧本生成（YAML 格式）
│   │   ├── model_config.py
│   │   └── content_guard.py       # 安全过滤
│   │
│   ├── agents/                    # AI 智能体
│   │   ├── __init__.py
│   │   ├── base.py                # Agent 基类
│   │   ├── story_analyst.py       # AI1 故事师
│   │   ├── planner.py             # 规划师
│   │   ├── outline_writer.py      # AI2 大纲师
│   │   └── director.py            # 导演（审核）
│   │
│   ├── core/                      # 核心工具
│   │   ├── __init__.py
│   │   ├── ai_client.py           # OpenAI SDK 封装（3种模式）
│   │   ├── sse.py                 # SSE 流式工具
│   │   ├── encryption.py          # AES-256-GCM 加密/解密
│   │   ├── hash_id.py             # HashID 编码/解码
│   │   └── yaml_schema.py         # YAML Schema Pydantic 模型 + 序列化
│   │
│   └── prompts/                   # 提示词文件
│       ├── episode_script_yaml.txt  # YAML 格式剧本生成提示词
│       ├── episode_script.txt       # 纯文本格式剧本提示词（可选）
│       ├── 主AGENT/
│       │   └── 大纲故事线Agent.txt
│       └── 子Agent/
│           ├── 大纲故事线Agent-故事师.txt
│           ├── 大纲故事线Agent-大纲师.txt
│           ├── 大纲故事线Agent-规划师.txt
│           └── 大纲故事线Agent-导演.txt
│
├── docs/                          # 文档
│   └── script_yaml_schema.md      # YAML Schema 定义与设计说明
│
├── alembic/
│   └── versions/
├── alembic.ini
├── requirements.txt
├── .env.example
└── README.md
```

---

## 执行阶段

### 第一阶段：项目骨架与基础设施

1. 创建上述目录结构
2. 配置 `requirements.txt`（引入 `pyyaml`）
3. 实现 `app/config.py`（pydantic-settings）
4. 实现 `app/database.py`（异步引擎 + session）
5. 实现 `app/dependencies.py`（JWT 认证注入）
6. 实现 `app/main.py`（FastAPI 应用入口，注册路由）
7. 配置 `alembic` 迁移环境

### 第二阶段：数据模型（9 个核心模型）

| 模型 | 用途说明 | 关键字段 |
|---|---|---|
| `User` | 用户账号 | id, phone, nickname, password, vip_tier_id |
| `NovelProject` | 小说项目 | id, title, total_episodes, duration, gender, genres(JSON), episode_plan(JSON), characters(LongText) |
| `NovelChapter` | 小说章节 | id, project_id, chapter_index, title, content(LongText), word_count |
| `NovelStoryline` | 故事线分析结果 | id, project_id, content(LongText), is_locked |
| `NovelEpisode` | 分集（含 YAML 剧本） | id, project_id, episode_number, title, chapter_range(JSON), outline(LongText), outline_detail(JSON), data(JSON), **script_content** → (YAML 文本), script_status |
| `NovelAsset` | 项目素材（角色等） | id, project_id, type, name, intro, prompt(JSON), source |
| `NovelChatHistory` | 多智能体对话历史 | id, project_id, role, agent_type, content(LongText), tool_calls(JSON) |
| `UserModel` | 用户自定义 AI 模型 | id, user_id, provider, api_key(加密), base_url, model_id, max_tokens, temperature |
| `UserModelScene` | 模型-场景绑定 | id, user_id, scene_code, model_id |

> **关键变更**：`NovelEpisode.script_content` 字段存储的是 **YAML 格式文本**，而非纯文本剧本。

### 第三阶段：AI 客户端封装

`app/core/ai_client.py` — 统一 OpenAI SDK 调用封装，提供 3 种模式：

- **`AIClient.chat()`** → `generateText()` 非流式对话
- **`AIClient.chat_stream()`** → 文本流式生成（`stream=True`, yield chunks）
- **`AIClient.agent_stream()`** → 工具调用流式生成（处理 `delta.tool_calls`）

**核心设计**：剧本生成采用 **instructor 模式**，让 AI 直接输出符合 YAML Schema 的结构化 JSON，再序列化为 YAML：

```python
from instructor import from_openai
from app.core.yaml_schema import EpisodeScript

client = from_openai(openai.AsyncOpenAI(...))

script = await client.chat.completions.create(
    response_model=EpisodeScript,  # Pydantic model 定义 YAML Schema
    messages=[system_msg, user_msg]
)
yaml_output = script.to_yaml()  # 序列化为 YAML 文本
```

### 第四阶段：YAML Schema 定义 (`app/core/yaml_schema.py`)

定义完整的 Pydantic 模型层次结构，对应 YAML Schema 文档中的每一层：

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Shot(BaseModel):
    """镜头"""
    shot_size: str = Field(..., description="景别", pattern=r"^(大远景|远景|全景|中景|近景|特写|大特写)$")
    camera_angle: str = Field(..., description="机位", pattern=r"^(平拍|俯拍|仰拍|侧拍)$")
    frame_position: str = Field(..., pattern=r"^(画中|画左|画右)$")
    description: str = Field(..., min_length=5)

class Dialogue(BaseModel):
    """对白"""
    character: str
    emotion: Optional[str] = None
    line: str

class Scene(BaseModel):
    """场景"""
    id: str
    time: str
    location_type: str  # 内/外
    location: str
    ambience: str
    bgm: str
    characters: List[str]
    shots: List[Shot]
    sound_effects: List[str] = []
    dialogues: List[Dialogue] = []
    ...

class EpisodeScript(BaseModel):
    """全集剧本"""
    episode_number: int
    title: str
    phase: str
    emotional_curve: str
    scenes: List[Scene]
    episode_ending: str
    next_episode_hook: str

    def to_yaml(self) -> str:
        import yaml
        return yaml.dump(self.model_dump(), allow_unicode=True, sort_keys=False)
```

### 第五阶段：核心业务逻辑（4 个模块并行）

**5.1 小说项目管理** — CRUD + 章节管理 + 资产同步

**5.2 "3 章以上 → YAML" 核心管线**：

```
用户上传 ≥3 章小说文本
    ↓
故事师 (AI1) 分析所有章节 → 生成故事线
    ↓
规划师 制定分集规划（多少集、每集覆盖哪些章节）
    ↓
大纲师 (AI2) 按集生成结构化大纲
    ↓
导演 审核质量（不符合则退回修改）
    ↓
instructor 驱动 AI 输出 EpisodeScript（Pydantic model）
    ↓
序列化为 YAML 文本 → 存入 database → 返回给前端
```

**5.3 剧本生成服务** — 使用 instructor `response_model=EpisodeScript` 让 AI 直接输出符合 Schema 的结构化数据

**5.4 内容安全守卫** — Prompt 指纹检测 + 品牌名替换 + 流式守卫

**5.5 模型配置管理** — AES-256-GCM 加密存储 API Key

**5.6 多智能体编排器** `NovelAgentOrchestrator`：

```
用户输入消息
    ↓
主 Agent（带 4 个工具：AI1/planner/AI2/director）
    ├── 调用 故事师 → 分析章节 → 生成故事线（支持续写）
    ├── 调用 规划师 → 制定分集规划表
    ├── 调用 大纲师 → 按规划生成每集大纲
    └── 调用 导演 → 审核质量，退回修改
    ↓
instructor 结构化输出 → YAML 序列化 → SSE 流式返回
```

关键机制：
- **续写循环**：长篇小说自动分 chunk 多次 AI 调用（默认最多 3 轮重试）
- **强制兜底**：主 Agent 未触发工具调用时自动识别意图并强制调度
- **审核循环**：子 Agent 输出 → 导演审核 → 用户确认 → 修改

### 第六阶段：API 路由与 SSE 流式

- 使用 `sse-starlette` 的 `EventSourceResponse`
- 剧本生成接口返回 YAML 文本块（流式拼接后在前端渲染）
- `GET /api/novel-episode/{id}/script/yaml` 获取完整 YAML
- `POST /api/novel-project/{id}/export-all` 导出全集 YAML

### 第七阶段：YAML Schema 文档 (`docs/script_yaml_schema.md`)

创建独立文档，包含：
- Schema 完整定义（每层字段、类型、枚举值）
- 完整示例 YAML 文件
- 各层设计原因说明
- 与纯文本剧本格式的对比分析

### 第八阶段：集成与测试

- pytest + httpx.AsyncClient 测试每个端点
- YAML 序列化/反序列化 round-trip 测试
- ollama 本地 LLM 模拟 AI 调用做集成测试
- SSE 事件流格式验证
- API Key 加密/解密安全测试

---

## API 端点清单

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/novel-project` | 创建小说项目 |
| GET | `/api/novel-project` | 项目列表 |
| GET | `/api/novel-project/{id}` | 项目详情 |
| PUT | `/api/novel-project/{id}` | 更新项目 |
| DELETE | `/api/novel-project/{id}` | 删除项目 |
| POST | `/api/novel-agent/chat` | 多智能体对话 SSE |
| POST | `/api/novel-agent/stop` | 停止智能体 |
| GET | `/api/novel-agent/history` | 对话历史 |
| POST | `/api/novel-episode/{id}/generate-script` | **剧本生成 SSE（返回 YAML 文本块）** |
| POST | `/api/novel-episode/{id}/stop-generate` | 停止生成 |
| PUT | `/api/novel-episode/{id}/script` | 保存/编辑剧本（接受 YAML） |
| **GET** | `/api/novel-episode/{id}/script/yaml` | **获取 YAML 剧本全文** |
| **POST** | `/api/novel-project/{id}/export-all` | **导出全集 YAML** |
| POST | `/api/novel-project/{id}/assets/sync-characters` | AI 同步角色 |
| CRUD | `/api/model-config/models` | 模型配置 |
| POST | `/api/model-config/scenes/bind` | 绑定场景 |

---

## 技术选型一览

| 方面 | 选择 | 理由 |
|---|---|---|
| 运行时 | Python 3.11+ | async/await 原生支持，生态成熟 |
| Web 框架 | FastAPI | 原生 async、Pydantic 校验、SSE 支持好 |
| AI SDK | OpenAI SDK (AsyncOpenAI) | 官方异步 SDK，支持流式 |
| 结构化输出 | instructor + Pydantic | 强制 AI 输出符合 Schema 的结构化数据 |
| **剧本格式** | **YAML 结构化数据** | 机器可读、编辑友好、前端可渲染 |
| 流式 | SSE via sse-starlette | FastAPI 原生 SSE 支持 |
| ORM | SQLAlchemy 2.0 async | 异步查询、类型安全 |

---

## 验证方案

1. **YAML round-trip 测试**：Pydantic model → YAML → 解析 → 与原始结构一致
2. **3 章+ 管线测试**：上传 3 章小说 → 验证输出完整 YAML 剧本
3. **单元测试**：每个 Service/Agent 方法独立测试
4. **API 测试**：`pytest` + `httpx.AsyncClient`
5. **集成测试**：ollama 本地 LLM 模拟
6. **SSE 测试**：验证 YAML 流式拼接正确
