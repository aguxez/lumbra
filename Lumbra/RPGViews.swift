import SwiftUI

// MARK: - Shared Helpers

private func rarityColor(_ rarity: String) -> Color {
  switch rarity {
  case "uncommon": return .green
  case "rare": return .blue
  case "legendary": return .purple
  default: return Theme.mutedText
  }
}

struct ItemRowView: View {
  let item: InventoryItem

  var body: some View {
    HStack(spacing: 4) {
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
      if item.effectType == "heal", let val = item.effectValue, val > 0 {
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

// MARK: - Character Card (extracted from LumbraPanel)

struct CharacterCardView: View {
  let character: CharacterState
  let zone: String
  var npcsInZone: [NPCPresence]?

  private func roleIcon(_ role: String) -> String {
    switch role {
    case "merchant": return "bag.fill"
    case "sage": return "star.fill"
    case "blacksmith": return "hammer.fill"
    case "wanderer": return "figure.walk"
    default: return "person.fill"
    }
  }

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

      if let npcs = npcsInZone, !npcs.isEmpty {
        HStack(spacing: 6) {
          ForEach(npcs, id: \.name) { npc in
            HStack(spacing: 2) {
              Image(systemName: roleIcon(npc.role))
                .font(Theme.fontTiny)
                .foregroundColor(.teal)
              Text(npc.name.components(separatedBy: " ").last ?? npc.name)
                .font(Theme.fontTiny)
                .foregroundColor(.teal)
            }
          }
          Spacer()
        }
      }

      HStack(spacing: 8) {
        HPBarView(
          current: character.hitPoints, max: character.maxHitPoints, height: Theme.hpBarHeight)
        Text("\(character.hitPoints)/\(character.maxHitPoints)")
          .font(Theme.fontSmall.monospacedDigit())
          .foregroundColor(Theme.bodyText)
          .frame(width: 55, alignment: .trailing)
      }

      HStack(spacing: 16) {
        if let effAtk = character.effectiveAttack, effAtk != character.attack {
          StatRowView(icon: "bolt.fill", label: "ATK", value: "\(effAtk) (\(character.attack))")
        } else {
          StatRowView(icon: "bolt.fill", label: "ATK", value: "\(character.attack)")
        }
        if let effDef = character.effectiveDefense, effDef != character.defense {
          StatRowView(icon: "shield.fill", label: "DEF", value: "\(effDef) (\(character.defense))")
        } else {
          StatRowView(icon: "shield.fill", label: "DEF", value: "\(character.defense)")
        }
        StatRowView(icon: "star.fill", label: "XP", value: "\(character.experience)")
        if let gold = character.gold {
          StatRowView(icon: "dollarsign.circle.fill", label: "Gold", value: "\(gold)")
        }
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

      if let reward = quest.rewardItem {
        HStack(spacing: 4) {
          Text("Reward:")
            .font(Theme.fontTiny)
            .foregroundColor(Theme.mutedText)
          Text("\(quest.rewardXp) XP")
            .font(Theme.fontTiny.bold())
            .foregroundColor(Theme.bodyText)
          Text("+ \(reward)")
            .font(Theme.fontTiny)
            .foregroundColor(.orange)
        }
      } else {
        Text("Reward: \(quest.rewardXp) XP")
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

  private var isBoss: Bool { combat.isBoss == true }

  private var cardFillColor: Color {
    isBoss ? Color.purple.opacity(0.10) : Color.red.opacity(0.08)
  }

  private var cardBorderColor: Color {
    isBoss ? Color.purple.opacity(0.4) : Color.red.opacity(0.25)
  }

  private var headerColor: Color {
    isBoss ? .purple : .red
  }

  var body: some View {
    VStack(alignment: .leading, spacing: 6) {
      HStack {
        Image(systemName: isBoss ? "crown.fill" : "flame")
          .font(Theme.fontSmall)
          .foregroundColor(headerColor)
        Text(isBoss ? "Boss Fight — Turn \(combat.turn)" : "Combat — Turn \(combat.turn)")
          .font(Theme.fontSmall.bold())
          .foregroundColor(headerColor)
        Spacer()
        Text(combat.aiStrategy.uppercased())
          .font(Theme.fontTiny.bold())
          .foregroundColor(Theme.bodyText)
          .padding(.horizontal, 6)
          .padding(.vertical, 2)
          .background(strategyColor.opacity(0.2))
          .cornerRadius(4)
      }

      HStack {
        if isBoss {
          Image(systemName: "crown.fill")
            .font(Theme.fontTiny)
            .foregroundColor(.yellow)
        }
        Text(isBoss ? "Boss: \(combat.enemyName)" : combat.enemyName)
          .font(Theme.fontSmall.bold())
          .foregroundColor(Theme.headerText)
        Spacer()
        Text("\(combat.enemyHp)/\(combat.enemyMaxHp) HP")
          .font(Theme.fontSmall.monospacedDigit())
          .foregroundColor(Theme.bodyText)
      }

      if isBoss, let phase = combat.bossPhase {
        Text("Phase \(phase + 1)/\(combat.bossPhaseCount ?? 3)")
          .font(Theme.fontTiny.bold())
          .foregroundColor(.purple)
      }

      HPBarView(current: combat.enemyHp, max: combat.enemyMaxHp, barColor: isBoss ? .purple : .red, height: 6)

      HStack(spacing: 12) {
        StatRowView(icon: "bolt.fill", label: "ATK", value: "\(combat.enemyAttack)")
        StatRowView(icon: "shield.fill", label: "DEF", value: "\(combat.enemyDefense)")
      }
    }
    .padding(Theme.cardPadding)
    .background(
      RoundedRectangle(cornerRadius: Theme.cardRadius)
        .fill(cardFillColor)
        .overlay(
          RoundedRectangle(cornerRadius: Theme.cardRadius)
            .strokeBorder(cardBorderColor, lineWidth: isBoss ? 2 : 1)
        )
    )
  }

  private var strategyColor: Color {
    switch combat.aiStrategy {
    case "attack": return .red
    case "defend": return .blue
    case "flee": return .yellow
    default: return .gray
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
        Text(encounter.npcName)
          .font(Theme.fontSmall.bold())
          .foregroundColor(.teal)
        Spacer()
        Text(encounter.npcRole.capitalized)
          .font(Theme.fontTiny)
          .foregroundColor(Theme.mutedText)
      }

      Text(encounter.dialogue)
        .font(Theme.fontSmall)
        .foregroundColor(Theme.bodyText)
        .italic()
        .lineLimit(3)

      if encounter.interactionType == "trade" {
        HStack(spacing: 4) {
          if let request = encounter.requestItem {
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
          if let offer = encounter.offerItem {
            Text(offer)
              .font(Theme.fontTiny.bold())
              .foregroundColor(.teal)
          }
        }
      } else if encounter.interactionType == "buff" {
        if let buffType = encounter.buffType, let buffVal = encounter.buffValue,
          let ticks = encounter.buffTicks
        {
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
              if let risk = exp.riskLevel {
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
                  .frame(
                    width: geo.size.width * Double(exp.progress) / Double(max(1, exp.duration))
                  )
                  .animation(.easeInOut(duration: 0.4), value: exp.progress)
              }
            }
            .frame(height: 5)

            HStack {
              Text("\(exp.progress)/\(exp.duration)")
                .font(Theme.fontTiny.monospacedDigit())
                .foregroundColor(Theme.mutedText)
              Spacer()
              if let reward = exp.rewardXp {
                Text("+\(reward) XP")
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

// MARK: - Equipment Section

struct EquipmentSection: View {
  let equipment: EquipmentState
  @State private var isExpanded = true

  var body: some View {
    DisclosureGroup(isExpanded: $isExpanded) {
      VStack(alignment: .leading, spacing: 6) {
        slotRow(icon: "bolt.fill", label: "Weapon", item: equipment.weapon, statKey: .attack)
        slotRow(icon: "shield.fill", label: "Armor", item: equipment.armor, statKey: .defense)
        slotRow(icon: "ring.circle", label: "Accessory", item: equipment.accessory, statKey: .defense)
      }
    } label: {
      HStack(spacing: 4) {
        Image(systemName: "figure.arms.open")
          .font(Theme.fontSmall)
          .foregroundColor(.cyan)
        Text("Equipment")
          .font(Theme.fontSmall.bold())
          .foregroundColor(.cyan)
      }
    }
    .tint(Theme.bodyText)
  }

  private enum StatKey { case attack, defense }

  private func slotRow(icon: String, label: String, item: InventoryItem?, statKey: StatKey) -> some View {
    HStack(spacing: 6) {
      Image(systemName: icon)
        .font(Theme.fontTiny)
        .foregroundColor(Theme.mutedText)
        .frame(width: 14)
      Text(label)
        .font(Theme.fontSmall)
        .foregroundColor(Theme.mutedText)
        .frame(width: 65, alignment: .leading)
      if let item = item {
        Text(item.name)
          .font(Theme.fontSmall)
          .foregroundColor(Theme.bodyText)
        Spacer()
        if statKey == .attack, let atk = item.attack, atk > 0 {
          Text("+\(atk) ATK")
            .font(Theme.fontTiny)
            .foregroundColor(.orange)
        }
        if statKey == .defense, let def = item.defense, def > 0 {
          Text("+\(def) DEF")
            .font(Theme.fontTiny)
            .foregroundColor(.blue)
        }
        Text(item.rarity)
          .font(Theme.fontTiny)
          .foregroundColor(rarityColor(item.rarity))
      } else {
        Text("Empty")
          .font(Theme.fontSmall)
          .foregroundColor(Theme.mutedText.opacity(0.5))
        Spacer()
      }
    }
  }
}
