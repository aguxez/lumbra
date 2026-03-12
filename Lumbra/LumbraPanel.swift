import SwiftUI

struct LumbraPanel: View {
    @ObservedObject var viewModel: LumbraViewModel

    var body: some View {
        VStack(spacing: 12) {
            // Header
            HStack {
                Text("Lumbra")
                    .font(.headline)
                Spacer()
                Circle()
                    .fill(viewModel.isAgentConnected ? Color.green : Color.gray)
                    .frame(width: 8, height: 8)
                Text(viewModel.isAgentConnected ? "Connected" : "Waiting")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if let gs = viewModel.gameState {
                // Character bar
                VStack(spacing: 6) {
                    HStack {
                        Text(gs.character.name)
                            .font(.subheadline.bold())
                        Spacer()
                        Text(gs.zone)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    HStack(spacing: 8) {
                        HPBarView(current: gs.character.hp, max: gs.character.max_hp)
                        Text("\(gs.character.hp)/\(gs.character.max_hp)")
                            .font(.caption.monospacedDigit())
                            .frame(width: 50, alignment: .trailing)
                    }

                    HStack(spacing: 16) {
                        if let effAtk = gs.character.effective_attack, effAtk != gs.character.attack {
                            StatRowView(icon: "bolt.fill", label: "ATK", value: "\(effAtk) (\(gs.character.attack))")
                        } else {
                            StatRowView(icon: "bolt.fill", label: "ATK", value: "\(gs.character.attack)")
                        }
                        if let effDef = gs.character.effective_defense, effDef != gs.character.defense {
                            StatRowView(icon: "shield.fill", label: "DEF", value: "\(effDef) (\(gs.character.defense))")
                        } else {
                            StatRowView(icon: "shield.fill", label: "DEF", value: "\(gs.character.defense)")
                        }
                        StatRowView(icon: "star.fill", label: "XP", value: "\(gs.character.xp)")
                    }
                }
                .padding(10)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color.primary.opacity(0.03))
                )

                // Quest card
                if let quest = gs.quest {
                    QuestCardView(quest: quest)
                }

                // Combat card
                if let combat = gs.combat {
                    CombatCardView(combat: combat)
                }

                // Event log
                if !gs.log.isEmpty {
                    Divider()
                    EventLogView(entries: gs.log)
                }

                // Inventory
                InventorySection(items: gs.character.inventory, weapon: gs.character.weapon, armor: gs.character.armor)

            } else {
                VStack(spacing: 8) {
                    Image(systemName: "gamecontroller")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)
                    Text("Waiting for game engine...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
            }

            Divider()

            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .buttonStyle(.borderless)
            .foregroundColor(.secondary)
        }
        .padding(20)
        .frame(width: 340)
    }
}
