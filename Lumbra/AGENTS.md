<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-13 | Updated: 2026-03-13 -->

# Lumbra

## Purpose
Native macOS SwiftUI application that visualizes the RPG game state. Listens on `localhost:8234` for JSON updates from the Python agent and renders character stats, combat, quests, NPCs, expeditions, equipment, inventory, base, and an event log in a dark-themed two-column layout with a menu bar extra showing HP.

## Key Files

| File | Description |
|------|-------------|
| `LumbraApp.swift` | App entry point (`@main`); configures main window, menu bar extra with HP display, and `AppDelegate` for lifecycle |
| `LumbraViewModel.swift` | `ObservableObject` view model; owns `LocalServer`, decodes JSON into `GameStateResponse`, tracks connection status with 90s timeout |
| `MainWindowView.swift` | Root view; header bar, two-column layout (sidebar: character/equipment/inventory/base; content: quest/combat/NPC/expeditions), draggable divider, event log footer |
| `GameModels.swift` | All `Codable` structs mirroring the Python agent's JSON: `GameStateResponse`, `CharacterState`, `CombatState`, `QuestState`, `NPCEncounterState`, `ExpeditionState`, `BaseState`, `InventoryItem`, `ActiveBuffState` |
| `LocalServer.swift` | Raw TCP server using `NWListener` on port 8234; parses HTTP POST requests, extracts JSON body, sends 200/400 responses |
| `RPGViews.swift` | Primary UI components: `CharacterCardView`, `HPBarView`, `StatRowView`, `QuestCardView`, `CombatCardView`, `EventLogView`, `NPCCardView`, `ExpeditionPanelView`, `EquipmentSection`, `ItemRowView` |
| `RPGViewsExtras.swift` | Additional UI components: `DayNightIndicator`, `BaseCardView`, `StorageSection`, `InventorySection` |
| `Theme.swift` | Design tokens: colors (dark theme), font scale, spacing constants |
| `Info.plist` | Sets `LSUIElement=true` (app runs as agent/menu bar app, no dock icon) |

## For AI Agents

### Working In This Directory
- This is a read-only UI — all game logic lives in `agent/`
- `GameModels.swift` must stay in sync with the JSON schema produced by `agent/game_state.py:GameState.to_dict()`
- Uses `snake_case` to `camelCase` mapping via `CodingKeys` enums (not `keyDecodingStrategy`)
- The app is a menu bar app (`LSUIElement=true`) with a window that can be shown/hidden
- No external Swift packages — uses only Apple frameworks (SwiftUI, Combine, Network)

### Testing Requirements
```bash
xcodebuild build -project Lumbra.xcodeproj -scheme Lumbra
swiftlint lint --strict
```

### Common Patterns
- Dark theme with card-based layout; all colors/fonts via `Theme` enum
- HP bars with color thresholds: green (>50%), orange (>25%), red
- `DisclosureGroup` for collapsible sections (equipment, inventory, storage, expeditions)
- Rarity color coding: common (gray), uncommon (green), rare (blue), legendary (purple)
- All views are stateless (`let` props) except for `@State` UI toggles (expand/collapse)
- Animated progress bars using `.animation(.easeInOut)` on value changes

## Dependencies

### Internal
- `agent/game_state.py` — JSON schema that `GameModels.swift` must mirror
- `agent/game_config.json` — defines content that determines what the UI will display

### External
- SwiftUI — declarative UI framework
- Combine — `AnyCancellable` for disconnect timer
- Network (`NWListener`, `NWConnection`) — raw TCP server

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
