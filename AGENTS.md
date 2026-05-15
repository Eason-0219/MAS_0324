# Repository Guidelines

## Project Structure & Module Organization

This repository implements MAS, a display-card assembly multi-agent system. `main.py` starts the CLI workflow. Backend modules are split by responsibility: `graph/` for LangGraph routing and nodes, `agents/` for domain agents, `tools/` for robot/SOP/safety/troubleshooting tools, `rag/` for retrieval, `memory/` for Neo4j-backed memory, `mcp_servers/` for time/weather/search, and `voice/` for STT/TTS. Configuration lives in `config/settings.py`; knowledge assets and FAISS state live under `data/`. The React UI is in `frontend/src/`; build output is `frontend/dist/`. Top-level smoke tests are `test_system.py` and `test_rag_system.py`.

## Build, Test, and Development Commands

Use Python 3.11; Python 3.13 has known dependency issues.

```bash
pip install -r requirements.txt      # install backend dependencies
docker-compose up -d                 # start Neo4j for memory features
python main.py                       # run the MAS CLI
python test_system.py                # run router, language, and workflow checks
python test_rag_system.py            # validate FAISS/RAG and checklist tools
```

For the frontend:

```bash
cd frontend
npm install
npm run dev                          # local Vite server
npm run build                        # production build
npm run preview                      # preview built assets
```

## Coding Style & Naming Conventions

Python code uses 4-space indentation, type hints where helpful, and snake_case for modules, functions, and variables. Keep agent/tool names aligned with route labels such as `robot`, `sop`, `safety`, `mcp`, `chat`, and `troubleshoot`. React components use PascalCase filenames in `frontend/src/components/`; hooks use `useXxx.js` naming under `frontend/src/hooks/`. Prefer small, responsibility-focused modules over broad utility files.

## Testing Guidelines

Add or update tests when changing routing, workflow nodes, RAG behavior, safety checklist logic, or external tool integrations. Place new integration checks beside the existing `test_*.py` scripts, or add focused tests near the affected package if a test framework is introduced. RAG tests may require `faiss-cpu`, Ollama, and the `bge-m3` embedding model.

## Commit & Pull Request Guidelines

This checkout does not expose readable Git history, so use clear imperative commit messages such as `Add RAG checklist validation` or `Fix wake listener reconnect`. Pull requests should include a short purpose statement, affected modules, setup or migration notes, test results, and screenshots or recordings for frontend changes. Never commit `.env`, generated caches, virtual environments, or local model files.

## Security & Configuration Tips

Keep API keys in `.env` only. Required and optional keys include OpenAI/OpenRouter, Tavily, OpenWeather, and ElevenLabs. Treat `data/faiss_index.pkl`, local voice/model assets, and Neo4j data as environment-specific artifacts unless intentionally updating project knowledge.
