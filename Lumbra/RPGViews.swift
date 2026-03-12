import SwiftUI

struct HPBarView: View {
    let current: Int
    let max: Int
    var barColor: Color = .red
    var height: CGFloat = 8

    private var fraction: Double {
        guard max > 0 else { return 0 }
        return Double(current) / Double(max)
    }

    private var displayColor: Color {
        if fraction > 0.5 { return .green }
        if fraction > 0.25 { return .orange }
        return .red
    }

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: height / 2)
                    .fill(Color.primary.opacity(0.1))

                RoundedRectangle(cornerRadius: height / 2)
                    .fill(displayColor)
                    .frame(width: geo.size.width * Swift.max(0, Swift.min(1, fraction)))
                    .animation(.easeInOut(duration: 0.4), value: current)
            }
        }
        .frame(height: height)
    }
}

struct StatRowView: View {
    let icon: String
    let label: String
    let value: String

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2)
                .foregroundColor(.secondary)
                .frame(width: 14)
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.caption.monospacedDigit())
                .bold()
        }
    }
}

struct QuestCardView: View {
    let quest: QuestState

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "scroll")
                    .font(.caption)
                    .foregroundColor(.yellow)
                Text("Quest")
                    .font(.caption.bold())
                    .foregroundColor(.yellow)
                Spacer()
                Text("\(quest.progress)/\(quest.goal)")
                    .font(.caption.monospacedDigit().bold())
            }

            Text(quest.description)
                .font(.caption)
                .lineLimit(2)

            // Progress bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.primary.opacity(0.1))
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.yellow.opacity(0.8))
                        .frame(width: geo.size.width * Double(quest.progress) / Double(max(1, quest.goal)))
                        .animation(.easeInOut(duration: 0.4), value: quest.progress)
                }
            }
            .frame(height: 6)

            if let reward = quest.reward_item {
                HStack(spacing: 4) {
                    Text("Reward:")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(quest.reward_xp) XP")
                        .font(.caption2.bold())
                    Text("+ \(reward)")
                        .font(.caption2)
                        .foregroundColor(.orange)
                }
            } else {
                Text("Reward: \(quest.reward_xp) XP")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.yellow.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color.yellow.opacity(0.2), lineWidth: 1)
                )
        )
    }
}

struct CombatCardView: View {
    let combat: CombatState

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "flame")
                    .font(.caption)
                    .foregroundColor(.red)
                Text("Combat — Turn \(combat.turn)")
                    .font(.caption.bold())
                    .foregroundColor(.red)
                Spacer()
                Text(combat.ai_strategy.uppercased())
                    .font(.caption2.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(strategyColor.opacity(0.2))
                    .cornerRadius(4)
            }

            HStack {
                Text(combat.enemy_name)
                    .font(.caption.bold())
                Spacer()
                Text("\(combat.enemy_hp)/\(combat.enemy_max_hp) HP")
                    .font(.caption.monospacedDigit())
            }

            HPBarView(current: combat.enemy_hp, max: combat.enemy_max_hp, barColor: .red, height: 6)

            HStack(spacing: 12) {
                StatRowView(icon: "bolt.fill", label: "ATK", value: "\(combat.enemy_attack)")
                StatRowView(icon: "shield.fill", label: "DEF", value: "\(combat.enemy_defense)")
            }
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.red.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color.red.opacity(0.2), lineWidth: 1)
                )
        )
    }

    private var strategyColor: Color {
        switch combat.ai_strategy {
        case "attack": return .red
        case "defend": return .blue
        case "flee": return .yellow
        default: return .gray
        }
    }
}

struct EventLogView: View {
    let entries: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            ForEach(Array(entries.suffix(6).enumerated()), id: \.offset) { _, entry in
                Text(entry)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct InventorySection: View {
    let items: [InventoryItem]
    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            if items.isEmpty {
                Text("Empty")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(items) { item in
                        HStack {
                            Text(item.name)
                                .font(.caption)
                            Spacer()
                            Text(item.rarity)
                                .font(.caption2)
                                .foregroundColor(rarityColor(item.rarity))
                        }
                    }
                }
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "bag")
                    .font(.caption)
                Text("Inventory (\(items.count))")
                    .font(.caption.bold())
            }
        }
    }

    private func rarityColor(_ rarity: String) -> Color {
        switch rarity {
        case "uncommon": return .green
        case "rare": return .blue
        case "legendary": return .purple
        default: return .secondary
        }
    }
}
