# agent

## Purpose
Python game engine that runs the autonomous RPG game loop. Handles tick-based simulation including combat, quests, NPC interactions, expeditions, day/night cycles, base management, and optional LLM-powered text generation. Sends game state to the macOS UI via HTTP POST on each tick.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | Entry point and game loop; tick dispatch, equipment logic, AI wrappers, HTTP state sender |
| `game_state.py` | All dataclasses (`GameState`, `Character`, `Enemy`, `Quest`, `Combat`, `Expedition`, `NPCEncounter`, `Base`, etc.); save/load from `savegame.json` |
| `combat.py` | Turn-based combat resolution: damage calculation, critical hits, flee, defend, auto-potion, stat growth |
| `world.py` | World systems: encounter rolls, quest generation, NPC interactions (trade/buff/lore), expedition creation and resolution, loot |
| `economy.py` | Economy system: merchant shops, pricing, trade options, buy/sell resolution, gold caps, trade history |
| `ai_brain.py` | Optional LLM integration (Qwen3-0.6B): combat strategy, quest generation, exploration text, NPC dialogue, expedition events |
| `config_loader.py` | Loads `game_config.json` at import time; provides lookup functions for zones, mobs, items, NPCs, expeditions, base tiers, day/night config |
| `game_config.json` | All game content data: 50+ items, 35+ mobs across 10 tiers, 15 zones, 10 NPCs, 5 expedition destinations, 4 base tiers, day/night settings |
| `pyproject.toml` | Project metadata, dependencies (transformers, torch, requests), dev tools (ruff, basedpyright) |
| `savegame.json` | Persistent game state (auto-generated at runtime) |
| `uv.lock` | Locked dependency versions |

## Working In This Directory
- Run with `uv run python main.py` from this directory
- The game loop in `main.py` ticks continuously with varying intervals (6-15s depending on activity)
- `game_config.json` is the single source of truth for all game content — modify it to add items, mobs, zones, NPCs, etc.
- All state is persisted to `savegame.json` via atomic write (tmp + rename)
- The AI brain (LLM) is optional — all functions have hardcoded fallbacks
- `config_loader.py` loads config at module import time; changes require restart
- `equip_or_stash` lives in `game_state.py` (no circular imports)

## Testing Requirements
```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright .
```

## Common Patterns
- Dataclasses with `to_dict()` methods for JSON serialization
- Functions return `list[str]` of log messages (appended to `state.log`)
- Combat uses dice rolls (1-6): roll 6 = critical (2x damage), roll 1 = miss
- Night multipliers applied to mob stats and loot chances
- NPC affinity gates interactions: lore (0+), buff (15+), trade (30+)
- Expeditions run in background with progress ticks, risk-based success chance

## Dependencies

### Internal
- `game_config.json` provides all content data to `config_loader.py`
- `config_loader.py` is imported by all other modules
- `game_state.py` defines shared dataclasses used everywhere
- `main.py` orchestrates all other modules

### External
- `transformers` + `torch` — Qwen3-0.6B local inference (optional)
- `requests` — HTTP POST to SwiftUI app
- `ruff` + `basedpyright` — dev linting/type-checking
