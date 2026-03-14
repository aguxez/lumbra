# Lumbra

## Purpose
An AI-driven idle RPG that autonomously explores a fantasy world, fights monsters, completes quests, and levels up — all visualized through a native macOS app. The Python agent runs the game loop and sends state updates over HTTP to a SwiftUI frontend.

## Key Files

| File | Description |
|------|-------------|
| `README.md` | Project overview, setup instructions, and tech stack |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `agent/` | Python game engine: AI brain, combat, world simulation, config |
| `Lumbra/` | SwiftUI macOS app: views, models, networking, theming |
| `Lumbra.xcodeproj/` | Xcode project configuration and Swift Package Manager settings |

## Working In This Repo
- The agent and UI communicate via HTTP POST to `localhost:8234`
- The Python agent is the source of truth for game state; the Swift app is a read-only visualizer
- `game_config.json` in `agent/` defines all game content (items, mobs, zones, NPCs, expeditions, base tiers, day/night)
- Changes to the JSON schema in `game_config.json` must be reflected in both `agent/game_state.py` (Python dataclasses) and `Lumbra/GameModels.swift` (Swift Codable structs)

## Testing Requirements
- Python: `uv run ruff format --check .`, `uv run ruff check .`, `uv run basedpyright .` (from `agent/`)
- Swift: `swiftlint lint --strict`
- Build: `xcodebuild build -project Lumbra.xcodeproj -scheme Lumbra`

## Architecture
```
[Python Agent] --HTTP POST (JSON)--> [SwiftUI App]
    |                                      |
    main.py (game loop)             LocalServer.swift (TCP listener)
    game_state.py (state model)     GameModels.swift (Codable structs)
    game_config.json (content)      LumbraViewModel.swift (state binding)
    combat.py, world.py (systems)   RPGViews.swift + RPGViewsExtras.swift (UI)
    ai_brain.py (optional LLM)      Theme.swift (design tokens)
```

## Dependencies

### External
- Python 3.10+, PyTorch, Hugging Face Transformers (Qwen/Qwen3-0.6B)
- SwiftUI, Combine, Network framework (Apple)
- Ruff, basedpyright (Python linting); SwiftLint (Swift linting)
