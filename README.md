# AI Voice Scheduler — 智能语音日程管家
链接： https://b23.tv/FBB5HFN
一个以语音交互为核心、具备主动智能的日程管理工具。支持自然语言对话操作日程、多轮上下文记忆、冲突检测与智能排程，以及 TTS 语音播报。

## 功能特性

### 自然语言交互
- **语音 + 文字双输入**：支持 Web Speech API 实时语音转文字，也支持键盘输入
- **多轮对话上下文记忆**：服务重启后可恢复进行中的对话状态
- **自我修正识别**：检测"不对，改成..."等转折词，自动修正意图
- **缺失信息主动追问**：时间/标题不明确时，AI 主动提问补全

### 日程管理
- **创建 / 查询 / 修改 / 删除日程**：全程通过对话或表单完成
- **冲突检测**：新增日程时自动检查时间冲突，并给出替代时段建议
- **可拖拽时间轴视图**：直观展示当日日程分布，支持拖拽调整时间

### 智能排程
- **自动排程**：输入"这周健身两次 + 写周报"，系统自动扫描空闲时间并填入
- **忙碌指数仪表盘**：量化每日时间占用，按轻松/适中/忙碌/超负荷分级
- **每日早报**：汇总当日日程、空闲时段，支持一键 TTS 语音播报

### 提醒与通勤
- **提前提醒**：默认创建 15 分钟前置提醒
- **通勤时间计算**：接入高德地图 API，计算从家到目的地的时间
- **出发提醒**：结合通勤时间，提前通知用户出发

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite |
| 后端 | Python FastAPI + SQLAlchemy + SQLite |
| NLU | OpenAI GPT-4o（可替换为任意 OpenAI 兼容模型） |
| 语音 | Web Speech API（ASR + TTS） |
| 地图 | 高德地图 API（通勤计算） |

## 项目结构

```
calender/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── requirements.txt        # Python 依赖
│   ├── run.bat                 # Windows 一键启动
│   └── app/
│       ├── config.py           # 配置管理（环境变量）
│       ├── database.py         # 数据库连接与会话
│       ├── models/             # ORM 模型
│       │   ├── event.py        # 日程 + 待办事项
│       │   ├── dialogue.py     # 对话会话 + 消息
│       │   └── reminder.py     # 提醒
│       ├── schemas/            # Pydantic 请求/响应模型
│       ├── routes/             # API 路由
│       │   ├── dialogue.py     # 对话处理（核心）
│       │   ├── events.py       # 日程 CRUD
│       │   ├── schedule.py     # 自动排程 + 早报
│       │   ├── tasks.py        # 待办事项管理
│       │   └── reminders.py    # 提醒 + 通勤
│       └── services/           # 业务逻辑层
│           ├── dialogue_manager.py  # 对话状态机
│           ├── nlu_service.py       # NLU 意图解析（LLM + 本地回退）
│           ├── scheduler.py         # 冲突检测 + 自动排程
│           ├── reminder_service.py  # 提醒生命周期
│           └── map_service.py       # 通勤时间计算
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # 主应用（路由 + 状态）
│   │   ├── api.js              # API 客户端封装
│   │   ├── components/
│   │   │   ├── Timeline.jsx    # 可拖拽时间轴
│   │   │   ├── VoiceInput.jsx  # 语音/文字输入
│   │   │   ├── DialoguePanel.jsx # 对话消息列表
│   │   │   ├── Dashboard.jsx   # 忙碌指数仪表盘
│   │   │   ├── EventForm.jsx   # 日程表单弹窗
│   │   │   └── ReminderPanel.jsx # 即将提醒侧栏
│   │   ├── hooks/
│   │   │   ├── useVoiceInput.js # Web Speech 识别 Hook
│   │   │   └── useTTS.js        # TTS 语音播报 Hook
│   │   └── styles/
│   │       └── global.css      # 全局样式
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── doc_content.txt             # 原始设计文档
├── .env.example                # 环境变量模板
└── .gitignore
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yianan521/calender.git
cd calender
```

### 2. 后端配置

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量模板并编辑
cp ../.env.example ../.env
```

编辑 `.env` 文件，填入你的 API Key：

```env
LLM_API_KEY=sk-your-openai-key-here    # 必需，NLU 智能解析
MAP_API_KEY=your-amap-key-here         # 可选，通勤时间计算
MAP_CITY=北京                          # 默认城市
```

> 不填 `LLM_API_KEY` 时，系统会使用内置的本地规则解析器，仍可处理大部分中文日程指令。

### 3. 启动后端

```bash
# Windows 用户可直接双击 run.bat
uvicorn main:app --reload --port 8000
```

后端运行在 [http://localhost:8000](http://localhost:8000)，可访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger API 文档。

### 4. 前端配置

```bash
cd ../frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在 [http://localhost:3000](http://localhost:3000)。

> 开发模式下，Vite 自动将 `/api` 请求代理到 `localhost:8000`，无需额外配置。

## API 概览

### 对话（核心）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/dialogue/` | 发送文本消息，返回 AI 回复 + 执行动作 |
| GET | `/dialogue/sessions` | 列出所有对话会话 |
| GET | `/dialogue/sessions/{id}/messages` | 获取会话消息历史 |

### 日程

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/events/` | 按时间范围查询日程 |
| POST | `/events/` | 创建日程（含冲突检测） |
| PUT | `/events/{id}` | 更新日程 |
| DELETE | `/events/{id}` | 删除日程 |
| GET | `/events/check-conflict/{id}` | 检查单个日程冲突 |

### 智能排程

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/schedule/auto` | 自动排程待办事项 |
| GET | `/schedule/conflicts` | 按时间段检查冲突 |
| GET | `/schedule/free-slots` | 获取空闲时段 |
| GET | `/schedule/daily-brief` | 生成每日早报 |

### 提醒 & 通勤

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/reminders/` | 列出提醒 |
| POST | `/reminders/` | 创建提醒 |
| POST | `/reminders/commute` | 计算通勤时间 |
| POST | `/reminders/commute/create` | 创建出发提醒 |
| GET | `/reminders/events/5hours` | 获取 5 小时内即将开始的日程和提醒 |
| POST | `/reminders/{id}/trigger` | 触发提醒 |
| POST | `/reminders/{id}/dismiss` | 忽略提醒 |

## 使用示例

### 基本对话

```
用户：帮我预约明天下午三点的牙医，地点在协和医院
助手：已为您创建日程「牙医」，时间：05月31日 15:00，已设置提前15分钟提醒。
      地点在协和医院，需要帮您计算通勤时间并设置出发提醒吗？

用户：好的
助手：前往「牙医」预计需要25分钟（约8.5公里），建议在14:25前出发。
      已为您设置出发提醒，将在14:25通知您。
```

### 自我修正

```
用户：帮我约这周五上午开会……不对，改成周四下午
助手：已为您创建日程「开会」，时间：06月04日 15:00。
```

### 查询日程

```
用户：明天有什么安排？
助手：您的日程如下：
      • 09:00 项目周会
      • 15:00 牙医
```

### 自动排程

```
用户：这周帮我安排健身三次，再写一个项目周报
助手：已为您自动安排4个事项。
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_URL` | `https://api.openai.com/v1/chat/completions` | LLM API 地址 |
| `LLM_API_KEY` | （空） | API Key，为空时使用本地解析器 |
| `LLM_MODEL` | `gpt-4o` | 模型名称 |
| `MAP_API_KEY` | （空） | 高德地图 API Key |
| `MAP_CITY` | `北京` | 默认城市 |
| `DATABASE_URL` | `sqlite:///./scheduler.db` | 数据库连接 |
| `WORKING_HOUR_START` | `8` | 工作时间起始（早报/排程用） |
| `WORKING_HOUR_END` | `22` | 工作时间结束 |
| `DEBUG` | `true` | 调试模式，打印 SQL |

## 演示剧本

评审或面试建议按以下顺序演示：

1. **自然对话**：语音输入"帮我约个牙医，周五下午……不对，改成周四上午吧"
2. **冲突检测**：接着说"周四上午十点我要开个短会"，观察冲突提示
3. **自动排程**："这周我还要健身两次、写项目周报，帮我自动安排"
4. **仪表盘**：切换到仪表盘查看忙碌指数，点击"播报早报"
5. **拖拽调整**：在时间轴上拖拽日程调整时间
