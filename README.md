# Telegram AI Companion Bot

A Telegram chatbot that combines conversational AI with real-time AI image generation for immersive roleplay experiences.

---

## Overview

This bot creates an interactive companion experience where users can:
- Chat with an AI-powered character that maintains personality and context
- Receive dynamically generated images that visualize the conversation scenes
- Customize the character's appearance, location, and mood through interactive menus

The system uses **Grok/OpenRouter** for intelligent conversation and **Replicate** for high-quality anime-style image generation.

---

## Features

| Feature | Description |
|---------|-------------|
| **Conversational AI** | Powered by Grok (xAI) or OpenRouter with LangChain integration |
| **Dynamic Image Generation** | Creates scene visualizations using Replicate (Nova Anime ILXL) |
| **Context Awareness** | Tracks user state (clothing, location, mood) across the conversation |
| **Interactive Menus** | Telegram inline keyboards for character customization |
| **Tool Calling** | LLM can dynamically update mood, location, and clothing |
| **Prompt Enhancement** | Raw prompts are narratively refined before image generation |
| **Observability** | Full LangSmith tracking: agents, tools, metadata, and performance metrics |

---

## Architecture

The project follows a **Layered Architecture** pattern for clean separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                 │
│                    (Bootstrap & Config)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      src/config.py                              │
│              (Environment & Validation)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   src/handlers.py       │     │   src/menus.py          │
│   (Telegram Adapter)    │     │   (UI Components)       │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   src/orchestrator.py                           │
│                   (Business Logic Layer)                        │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Orchestrator │──│ContextMgr │──│ Coordinador │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   src/agent.py          │     │   src/image_gen.py      │
│   (LLM Integration)     │     │   (Replicate API)       │
│                         │     │                         │
│   • LangChain           │     │   • Image Generation    │
│   • Tool Calling        │     │   • Prompt Processing   │
│   • Prompt Redaction    │     │   • Style Optimization  │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              ▼                               ▼
        ┌───────────┐                 ┌───────────┐
        │  Grok /   │                 │ Replicate │
        │ OpenRouter│                 │    API    │
        └───────────┘                 └───────────┘
```

### Layer Responsibilities

| Layer | File | Responsibility |
|-------|------|----------------|
| **Config** | `config.py` | Load and validate environment variables |
| **Presentation** | `handlers.py`, `menus.py` | Handle Telegram updates, format responses |
| **Service** | `orchestrator.py` | Business logic, orchestration (platform-agnostic) |
| **Infrastructure** | `agent.py`, `image_gen.py` | External API integrations |
| **Domain** | `context.py` | Data models and state management |

---

## Message Flow

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌───────────┐
│ Telegram │────▶│ BotHandler   │────▶│ Orchestrator │────▶│   Agent   │
│   User   │     │ (handlers.py)│     │(orchestrator.py)│   │(agent.py) │
└──────────┘     └──────────────┘     └─────────────┘     └───────────┘
                                              │                  │
                                              │                  ▼
                                              │           ┌───────────┐
                                              │           │  Grok LLM │
                                              │           └───────────┘
                                              │                  │
                                              │    ┌─────────────┘
                                              │    │ (response + IMAGE_PROMPT)
                                              ▼    ▼
                                       ┌─────────────┐
                                       │ ImageGen    │
                                       │(image_gen.py)│
                                       └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  Replicate  │
                                       │     API     │
                                       └─────────────┘
                                              │
                                              ▼
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│ Telegram │◀────│ BotHandler   │◀────│ ChatResponse│
│   User   │     │              │     │ (text+image)│
└──────────┘     └──────────────┘     └─────────────┘
```

---

## Project Structure

```
telegramchat/
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not in git)
├── .env.example            # Template for .env
│
├── src/
│   ├── __init__.py
│   ├── config.py           # Configuration loader
│   ├── orchestrator.py     # Business logic (ChatOrchestrator)
│   ├── handlers.py         # Telegram event handlers
│   ├── menus.py            # Interactive menu components
│   ├── agent.py            # LLM integration (LangChain)
│   ├── image_gen.py        # Image generation (Replicate)
│   └── context.py          # User state management
│
├── tests/
│   ├── test_image_gen.py   # Image generation tests
│   └── test_prompt_image.py# Manual prompt testing
│
├── assets/
│   └── *.jpg               # Reference images
│
└── .cursor/
    └── rules/              # Cursor IDE rules
        ├── testing.mdc
        └── python_standards.mdc
```

---

## Requirements

- Python 3.12+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Grok API Key (from [x.ai](https://x.ai)) **or** OpenRouter API Key
- Replicate API Token (from [replicate.com](https://replicate.com))

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/telegramchat.git
cd telegramchat
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

Create a `.env` file in the project root:

```env
# === Telegram ===
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# === LLM (Choose one) ===
# Option A: Grok (xAI)
GROK_API_KEY=your_xai_api_key
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL_NAME=grok-4-1-fast-non-reasoning

# Option B: OpenRouter
# OPENROUTER_API_KEY=your_openrouter_key
# LLM_BASE_URL=https://openrouter.ai/api/v1
# LLM_MODEL_NAME=openai/gpt-4

# === Image Generation (Replicate) ===
REPLICATE_API_TOKEN=your_replicate_token
REPLICATE_MODEL_ID=aisha-ai-official/nova-anime-ilxl-v5.5:ac582da6619c6deb7ff561eefb5824324c9ff0f485ccb7867964bce7040b0568
```

---

## Usage

### Start the bot (Telegram mode)

```bash
python main.py
```

### Start the bot (Terminal Chat mode)

```bash
python main.py --chat-terminal
```

### In Telegram

1. Find your bot and send `/start`
2. Select initial clothing from the menu
3. Select location from the menu
4. Start chatting - the bot will respond with text and periodically generate images

### Image Generation Logic

Images are generated when:
- First message after setup (establishing the scene)
- Every 3rd message thereafter

The image generation logic is handled by the orchestrator layer with a per-user counter to ensure consistent timing across different platforms (Telegram, terminal chat, etc.).

---

## Development

### Running Tests

```bash
# Interactive image generation test
python -m tests.test_image_gen

# Manual prompt test
python -m tests.test_prompt_image
```

### Code Standards

See `.cursor/rules/` for project conventions:
- All test files must use `test_` prefix
- Type hints required on all functions
- Async/await for I/O operations

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | [python-telegram-bot](https://python-telegram-bot.org/) v21+ |
| LLM Integration | [LangChain](https://python.langchain.com/) |
| LLM Provider | [Grok (xAI)](https://x.ai) / [OpenRouter](https://openrouter.ai) |
| Image Generation | [Replicate](https://replicate.com) |
| Image Model | Nova Anime ILXL v5.5 |
| Observability | [LangSmith](https://smith.langchain.com/) (Optional) |
| Config Management | python-dotenv |

---

## LangSmith Integration (Optional)

[LangSmith](https://smith.langchain.com/) provides observability for your LLM calls - tracing, debugging, and monitoring.

### Setup

1. Create an account at [smith.langchain.com](https://smith.langchain.com/)
2. Get your API key from the settings page
3. Add these variables to your `.env`:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=telegram-ai-bot
```

### What You Get

When enabled, LangSmith will trace **todo el flujo completo** con tracking individual de:

```
┌─────────────────────────────────────────────────────────────┐
│                    LangSmith Dashboard                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📊 Traces Completos                                        │
│  ├── Orchestrator_ProcessMessage                           │
│  │   ├── Metadata: user_id, msg_count, mood, energy        │
│  │   ├── ConversationAgent (roleplay)                      │
│  │   │   ├── System Prompt + Context                       │
│  │   │   ├── User Message (+ imagen si la hay)             │
│  │   │   ├── ExecuteTool: update_mood ✅                   │
│  │   │   ├── ExecuteTool: update_clothes ✅                │
│  │   │   └── LLM Response + Tokens + Latency               │
│  │   │                                                      │
│  │   └── Orchestrator_GenerateImage                        │
│  │       └── ImagePromptAgent_Generate                     │
│  │           ├── Context: character, location, clothes     │
│  │           ├── Conversation History (últimos 4 msgs)     │
│  │           ├── Last Prompt (si existe)                   │
│  │           └── Generated ILXL Tags                        │
│  │                                                          │
│  📈 Métricas Detalladas                                     │
│  ├── Token usage por agente y operación                    │
│  ├── Latencia (p50, p95, p99) por componente               │
│  ├── Tool success/error rates                              │
│  └── Image generation frequency                            │
│                                                             │
│  🔍 Búsqueda Avanzada                                       │
│  ├── Por tags: conversation, roleplay, image, tool         │
│  ├── Por metadata: user_id, mood, msg_count                │
│  └── Por operación: generate, redact, execute              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Ver más detalles**: Consulta [LANGSMITH_TRACKING.md](./LANGSMITH_TRACKING.md) para documentación completa.

### When to Use It

- **Development**: Debug prompts, see exactly what's sent to the LLM
- **Production**: Monitor performance, catch errors, analyze usage patterns
- **Optimization**: Identify slow calls, reduce token usage

---

## Key Design Decisions

### 1. Platform-Agnostic Service Layer
The `ChatOrchestrator` knows nothing about Telegram. This makes it easy to:
- Write unit tests without mocking Telegram objects
- Port to other platforms (Discord, WhatsApp, Web)

### 2. Configuration as Code
All sensitive data comes from `.env`, validated at startup. No hardcoded API keys or model IDs.

### 3. Prompt Enhancement Pipeline
Raw LLM prompts are passed through a "redaction" step that converts keywords into natural narrative sentences before sending to the image model.

### 4. Graceful Degradation
If image generation fails, the bot still sends the text response. The user experience is never completely blocked.

---

## License

MIT License - See LICENSE file for details.
