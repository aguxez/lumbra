# Lumbra

An AI-driven idle RPG that autonomously explores a fantasy world, fights monsters, completes quests, and levels up — all visualized through a native macOS app.

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- macOS with Xcode (for the UI app)

### Run the Agent

```bash
cd agent
uv run python main.py
```

The agent loads `game_config.json`, optionally downloads the LLM on first run, and begins the game loop. It sends state updates to `localhost:8234` via HTTP POST.

### Run the macOS App

Open `Lumbra.xcodeproj` in Xcode and run, or build from the command line:

```bash
xcodebuild build -project Lumbra.xcodeproj -scheme Lumbra
```

The app listens on `localhost:8234` and displays the game state as it arrives from the agent.

## Game Mechanics

- **Zones** with scaling difficulty for progressive exploration
- **Turn-based combat** with multiple strategies, critical hits, and auto-potion usage
- **Auto-generated quests** per zone with XP and item rewards
- **NPCs** with affinity systems, trades, buffs, and dialogue
- **Expeditions** with varying risk/reward
- **Items** across weapons, armor, shields, accessories, and consumables
- **Mobs** spanning multiple tiers and types

## Development

### Linting and Type Checking

```bash
cd agent
uv sync --group dev
uv run ruff format --check .
uv run ruff check .
uv run basedpyright .
```

```bash
swiftlint lint --strict
```

CI runs these checks automatically via GitHub Actions on every push.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Game engine | Python 3.10+, Hugging Face Transformers, PyTorch |
| UI | SwiftUI, Combine, Network framework |
| Communication | HTTP (localhost:8234) |
| AI | Qwen/Qwen3-0.6B (optional, local inference) |
| Linting | Ruff, basedpyright, SwiftLint |
