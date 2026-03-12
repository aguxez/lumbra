import SwiftUI

// MARK: - Character Card (extracted from LumbraPanel)

struct CharacterCardView: View {
    let character: CharacterState
    let zone: String

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text(character.name)
                    .font(Theme.fontBody.bold())
                    .foregroundColor(Theme.headerText)
                Spacer()
                Text(zone)
                    .font(Theme.fontSmall)
                    .foregroundColor(Theme.mutedText)
            }

            HStack(spacing: 8) {
                HPBarView(current: character.hp, max: character.max_hp, height: Theme.hpBarHeight)
                Text("\(character.hp)/\(character.max_hp)")
                    .font(Theme.fontSmall.monospacedDigit())
                    .foregroundColor(Theme.bodyText)
                    .frame(width: 55, alignment: .trailing)
            }

            HStack(spacing: 16) {
                if let effAtk = character.effective_attack, effAtk != character.attack {
                    StatRowView(icon: "bolt.fill", label: "ATK", value: "\(effAtk) (\(character.attack))")
                } else {
                    StatRowView(icon: "bolt.fill", label: "ATK", value: "\(character.attack)")
                }
                if let effDef = character.effective_defense, effDef != character.defense {
                    StatRowView(icon: "shield.fill", label: "DEF", value: "\(effDef) (\(character.defense))")
                } else {
                    StatRowView(icon: "shield.fill", label: "DEF", value: "\(character.defense)")
                }
                StatRowView(icon: "star.fill", label: "XP", value: "\(character.xp)")
            }
        }
        .padding(Theme.cardPadding)
        .background(
            RoundedRectangle(cornerRadius: Theme.cardRadius)
                .fill(Theme.cardBackground)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.cardRadius)
                        .strokeBorder(Theme.cardBorder, lineWidth: 1)
                )
        )
    }
}

// MARK: - HP Bar

struct HPBarView: View {
    let current: Int
    let max: Int
    var barColor: Color = .red
    var height: CGFloat = Theme.hpBarHeight

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
                    .fill(Color.white.opacity(0.1))

                RoundedRectangle(cornerRadius: height / 2)
                    .fill(displayColor)
                    .frame(width: geo.size.width * Swift.max(0, Swift.min(1, fraction)))
                    .animation(.easeInOut(duration: 0.4), value: current)
            }
        }
        .frame(height: height)
    }
}

// MARK: - Stat Row

struct StatRowView: View {
    let icon: String
    let label: String
    let value: String

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(Theme.fontTiny)
                .foregroundColor(Theme.mutedText)
                .frame(width: 14)
            Text(label)
                .font(Theme.fontSmall)
                .foregroundColor(Theme.mutedText)
            Spacer()
            Text(value)
                .font(Theme.fontSmall.monospacedDigit())
                .bold()
                .foregroundColor(Theme.bodyText)
        }
    }
}

// MARK: - Quest Card

struct QuestCardView: View {
    let quest: QuestState

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "scroll")
                    .font(Theme.fontSmall)
                    .foregroundColor(.yellow)
                Text("Quest")
                    .font(Theme.fontSmall.bold())
                    .foregroundColor(.yellow)
                Spacer()
                Text("\(quest.progress)/\(quest.goal)")
                    .font(Theme.fontSmall.monospacedDigit().bold())
                    .foregroundColor(Theme.bodyText)
            }

            Text(quest.description)
                .font(Theme.fontSmall)
                .foregroundColor(Theme.bodyText)
                .lineLimit(2)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.white.opacity(0.1))
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
                        .font(Theme.fontTiny)
                        .foregroundColor(Theme.mutedText)
                    Text("\(quest.reward_xp) XP")
                        .font(Theme.fontTiny.bold())
                        .foregroundColor(Theme.bodyText)
                    Text("+ \(reward)")
                        .font(Theme.fontTiny)
                        .foregroundColor(.orange)
                }
            } else {
                Text("Reward: \(quest.reward_xp) XP")
                    .font(Theme.fontTiny)
                    .foregroundColor(Theme.mutedText)
            }
        }
        .padding(Theme.cardPadding)
        .background(
            RoundedRectangle(cornerRadius: Theme.cardRadius)
                .fill(Color.yellow.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.cardRadius)
                        .strokeBorder(Color.yellow.opacity(0.25), lineWidth: 1)
                )
        )
    }
}

// MARK: - Combat Card

struct CombatCardView: View {
    let combat: CombatState

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "flame")
                    .font(Theme.fontSmall)
                    .foregroundColor(.red)
                Text("Combat — Turn \(combat.turn)")
                    .font(Theme.fontSmall.bold())
                    .foregroundColor(.red)
                Spacer()
                Text(combat.ai_strategy.uppercased())
                    .font(Theme.fontTiny.bold())
                    .foregroundColor(Theme.bodyText)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(strategyColor.opacity(0.2))
                    .cornerRadius(4)
            }

            HStack {
                Text(combat.enemy_name)
                    .font(Theme.fontSmall.bold())
                    .foregroundColor(Theme.headerText)
                Spacer()
                Text("\(combat.enemy_hp)/\(combat.enemy_max_hp) HP")
                    .font(Theme.fontSmall.monospacedDigit())
                    .foregroundColor(Theme.bodyText)
            }

            HPBarView(current: combat.enemy_hp, max: combat.enemy_max_hp, barColor: .red, height: 6)

            HStack(spacing: 12) {
                StatRowView(icon: "bolt.fill", label: "ATK", value: "\(combat.enemy_attack)")
                StatRowView(icon: "shield.fill", label: "DEF", value: "\(combat.enemy_defense)")
            }
        }
        .padding(Theme.cardPadding)
        .background(
            RoundedRectangle(cornerRadius: Theme.cardRadius)
                .fill(Color.red.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.cardRadius)
                        .strokeBorder(Color.red.opacity(0.25), lineWidth: 1)
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

// MARK: - Event Log

struct EventLogView: View {
    let entries: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: "text.book.closed")
                    .font(Theme.fontSmall)
                    .foregroundColor(Theme.accent)
                Text("Event Log")
                    .font(Theme.fontSmall.bold())
                    .foregroundColor(Theme.accent)
                Spacer()
            }

            ScrollView {
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(Array(entries.suffix(10).enumerated()), id: \.offset) { _, entry in
                        Text(entry)
                            .font(Theme.fontSmall)
                            .foregroundColor(Theme.mutedText)
                            .lineLimit(2)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 120)
        }
    }
}

// MARK: - NPC Card

struct NPCCardView: View {
    let encounter: NPCEncounterState

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "person.wave.2")
                    .font(Theme.fontSmall)
                    .foregroundColor(.teal)
                Text(encounter.npc_name)
                    .font(Theme.fontSmall.bold())
                    .foregroundColor(.teal)
                Spacer()
                Text(encounter.npc_role.capitalized)
                    .font(Theme.fontTiny)
                    .foregroundColor(Theme.mutedText)
            }

            Text(encounter.dialogue)
                .font(Theme.fontSmall)
                .foregroundColor(Theme.bodyText)
                .italic()
                .lineLimit(3)

            if encounter.interaction_type == "trade" {
                HStack(spacing: 4) {
                    if let request = encounter.request_item {
                        Text("Trade: \(request)")
                            .font(Theme.fontTiny)
                            .foregroundColor(Theme.mutedText)
                        Image(systemName: "arrow.right")
                            .font(Theme.fontTiny)
                            .foregroundColor(Theme.mutedText)
                    } else {
                        Text("Gift:")
                            .font(Theme.fontTiny)
                            .foregroundColor(Theme.mutedText)
                    }
                    if let offer = encounter.offer_item {
                        Text(offer)
                            .font(Theme.fontTiny.bold())
                            .foregroundColor(.teal)
                    }
                }
            } else if encounter.interaction_type == "buff" {
                if let buffType = encounter.buff_type, let buffVal = encounter.buff_value, let ticks = encounter.buff_ticks {
                    Text("Buff: +\(buffVal) \(buffType) for \(ticks) ticks")
                        .font(Theme.fontTiny)
                        .foregroundColor(.cyan)
                }
            } else {
                Text("Shared ancient lore")
                    .font(Theme.fontTiny)
                    .foregroundColor(Theme.mutedText)
            }
        }
        .padding(Theme.cardPadding)
        .background(
            RoundedRectangle(cornerRadius: Theme.cardRadius)
                .fill(Color.teal.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.cardRadius)
                        .strokeBorder(Color.teal.opacity(0.25), lineWidth: 1)
                )
        )
    }
}

// MARK: - Expedition Panel

struct ExpeditionPanelView: View {
    let expeditions: [ExpeditionState]
    @State private var isExpanded = true

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            VStack(spacing: 8) {
                ForEach(expeditions) { exp in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(exp.destination)
                                .font(Theme.fontSmall.bold())
                                .foregroundColor(Theme.headerText)
                            Spacer()
                            if let risk = exp.risk_level {
                                Text("Risk \(risk)")
                                    .font(Theme.fontTiny)
                                    .foregroundColor(Self.riskColor(risk))
                            }
                        }

                        GeometryReader { geo in
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(Color.white.opacity(0.1))
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(Color.indigo.opacity(0.7))
                                    .frame(width: geo.size.width * Double(exp.progress) / Double(max(1, exp.duration)))
                                    .animation(.easeInOut(duration: 0.4), value: exp.progress)
                            }
                        }
                        .frame(height: 5)

                        HStack {
                            Text("\(exp.progress)/\(exp.duration)")
                                .font(Theme.fontTiny.monospacedDigit())
                                .foregroundColor(Theme.mutedText)
                            Spacer()
                            if let xp = exp.reward_xp {
                                Text("+\(xp) XP")
                                    .font(Theme.fontTiny)
                                    .foregroundColor(.indigo)
                            }
                        }

                        if let events = exp.events, let lastEvent = events.last {
                            Text(lastEvent)
                                .font(Theme.fontTiny)
                                .foregroundColor(Theme.mutedText)
                                .italic()
                                .lineLimit(2)
                        }
                    }
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Color.indigo.opacity(0.06))
                    )
                }
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "map")
                    .font(Theme.fontSmall)
                    .foregroundColor(.indigo)
                Text("Expeditions (\(expeditions.count))")
                    .font(Theme.fontSmall.bold())
                    .foregroundColor(.indigo)
            }
        }
        .tint(Theme.bodyText)
    }

    private static func riskColor(_ risk: Int) -> Color {
        switch risk {
        case 1: return .green
        case 2: return .yellow
        case 3: return .orange
        case 4...5: return .red
        default: return .secondary
        }
    }
}

// MARK: - Inventory Section

struct InventorySection: View {
    let items: [InventoryItem]
    var weapon: String? = nil
    var armor: String? = nil
    @State private var isExpanded = true

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            if items.isEmpty {
                Text("Empty")
                    .font(Theme.fontSmall)
                    .foregroundColor(Theme.mutedText)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(items) { item in
                            HStack(spacing: 4) {
                                if item.name == weapon || item.name == armor {
                                    Text("E")
                                        .font(.system(size: 9).bold())
                                        .foregroundColor(.white)
                                        .padding(.horizontal, 3)
                                        .padding(.vertical, 1)
                                        .background(Color.blue)
                                        .cornerRadius(3)
                                }
                                Text(item.name)
                                    .font(Theme.fontSmall)
                                    .foregroundColor(Theme.bodyText)
                                Spacer()
                                if let atk = item.attack, atk > 0 {
                                    Text("+\(atk) ATK")
                                        .font(Theme.fontTiny)
                                        .foregroundColor(.orange)
                                }
                                if let def = item.defense, def > 0 {
                                    Text("+\(def) DEF")
                                        .font(Theme.fontTiny)
                                        .foregroundColor(.blue)
                                }
                                if item.effect_type == "heal", let val = item.effect_value, val > 0 {
                                    Text("+\(val) HP")
                                        .font(Theme.fontTiny)
                                        .foregroundColor(.green)
                                }
                                Text(item.rarity)
                                    .font(Theme.fontTiny)
                                    .foregroundColor(rarityColor(item.rarity))
                            }
                        }
                    }
                }
                .frame(maxHeight: 150)
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "bag")
                    .font(Theme.fontSmall)
                    .foregroundColor(Theme.accent)
                Text("Inventory (\(items.count))")
                    .font(Theme.fontSmall.bold())
                    .foregroundColor(Theme.accent)
            }
        }
        .tint(Theme.bodyText)
    }

    private func rarityColor(_ rarity: String) -> Color {
        switch rarity {
        case "uncommon": return .green
        case "rare": return .blue
        case "legendary": return .purple
        default: return Theme.mutedText
        }
    }
}
