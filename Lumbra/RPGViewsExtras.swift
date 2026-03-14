import SwiftUI

// MARK: - Day/Night Indicator

struct DayNightIndicator: View {
  let isNight: Bool
  let cyclePosition: Int
  let cycleLength: Int
  let nightStart: Int

  private var fraction: Double {
    guard cycleLength > 0 else { return 0 }
    let raw: Double
    if isNight {
      let nightLength = cycleLength - nightStart
      guard nightLength > 0 else { return 0 }
      raw = Double(cyclePosition - nightStart) / Double(nightLength)
    } else {
      guard nightStart > 0 else { return 0 }
      raw = Double(cyclePosition) / Double(nightStart)
    }
    return Swift.max(0, Swift.min(1, raw))
  }

  var body: some View {
    HStack(spacing: 4) {
      Image(systemName: isNight ? "moon.fill" : "sun.max.fill")
        .font(Theme.fontTiny)
        .foregroundColor(isNight ? .indigo : .yellow)
      GeometryReader { geo in
        ZStack(alignment: .leading) {
          RoundedRectangle(cornerRadius: 2)
            .fill(Color.white.opacity(0.1))
          RoundedRectangle(cornerRadius: 2)
            .fill(isNight ? Color.indigo.opacity(0.7) : Color.yellow.opacity(0.7))
            .frame(width: geo.size.width * fraction)
            .animation(.easeInOut(duration: 0.4), value: cyclePosition)
        }
      }
      .frame(height: 4)
      Text(isNight ? "Night" : "Day")
        .font(Theme.fontTiny)
        .foregroundColor(isNight ? .indigo : .yellow)
    }
  }
}

// MARK: - Base Card

struct BaseCardView: View {
  let base: BaseState

  var body: some View {
    VStack(alignment: .leading, spacing: 6) {
      HStack {
        Image(systemName: "house.fill")
          .font(Theme.fontSmall)
          .foregroundColor(.brown)
        Text(base.name)
          .font(Theme.fontSmall.bold())
          .foregroundColor(.brown)
        Spacer()
        Text("Tier \(base.tier)")
          .font(Theme.fontTiny)
          .foregroundColor(Theme.mutedText)
      }

      if let desc = base.description, !desc.isEmpty {
        Text(desc)
          .font(Theme.fontTiny)
          .foregroundColor(Theme.mutedText)
          .lineLimit(2)
      }

      if let slots = base.storageSlots, slots > 0 {
        HStack(spacing: 4) {
          Image(systemName: "archivebox")
            .font(Theme.fontTiny)
            .foregroundColor(Theme.mutedText)
          Text("Storage: \(base.storage.count)/\(slots)")
            .font(Theme.fontTiny)
            .foregroundColor(Theme.bodyText)
        }
      }
    }
    .padding(Theme.cardPadding)
    .background(
      RoundedRectangle(cornerRadius: Theme.cardRadius)
        .fill(Color.brown.opacity(0.08))
        .overlay(
          RoundedRectangle(cornerRadius: Theme.cardRadius)
            .strokeBorder(Color.brown.opacity(0.25), lineWidth: 1)
        )
    )
  }
}

// MARK: - Storage Section

struct StorageSection: View {
  let items: [InventoryItem]
  let maxSlots: Int
  @State private var isExpanded = false

  var body: some View {
    DisclosureGroup(isExpanded: $isExpanded) {
      if items.isEmpty {
        Text("Empty")
          .font(Theme.fontSmall)
          .foregroundColor(Theme.mutedText)
      } else {
        ScrollView {
          VStack(alignment: .leading, spacing: 4) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
              ItemRowView(item: item)
            }
          }
        }
        .frame(maxHeight: 120)
      }
    } label: {
      HStack(spacing: 4) {
        Image(systemName: "archivebox")
          .font(Theme.fontSmall)
          .foregroundColor(.brown)
        Text("Storage (\(items.count)/\(maxSlots))")
          .font(Theme.fontSmall.bold())
          .foregroundColor(.brown)
      }
    }
    .tint(Theme.bodyText)
  }
}

// MARK: - Market Pulse (Sidebar)

struct MarketPulseView: View {
  let economy: EconomyData

  private var totalGold: Int {
    economy.merchantStates.values.reduce(0) { $0 + $1.gold }
  }

  var body: some View {
    HStack(spacing: 6) {
      Image(systemName: "chart.line.uptrend.xyaxis")
        .font(Theme.fontTiny)
        .foregroundColor(.yellow)
      Text("\(totalGold)g total")
        .font(Theme.fontTiny.monospacedDigit())
        .foregroundColor(Theme.bodyText)
      Text("|")
        .font(Theme.fontTiny)
        .foregroundColor(Theme.mutedText)
      Text("\(economy.priceAdjustments.count) adj")
        .font(Theme.fontTiny.monospacedDigit())
        .foregroundColor(Theme.bodyText)
      Text("|")
        .font(Theme.fontTiny)
        .foregroundColor(Theme.mutedText)
      Text("\(economy.tradeHistory.count) trades")
        .font(Theme.fontTiny.monospacedDigit())
        .foregroundColor(Theme.bodyText)
      Spacer()
    }
    .padding(.horizontal, 4)
  }
}

// MARK: - Economy Card

struct EconomyCardView: View {
  let economy: EconomyData
  @State private var rosterExpanded = false
  @State private var adjustmentsExpanded = false
  @State private var tradesExpanded = false

  private func adjustmentStyle(_ mult: Double) -> (color: Color, icon: String) {
    if mult < 1.0 { return (.green, "arrow.down") }
    if mult > 1.0 { return (.red, "arrow.up") }
    return (Theme.mutedText, "minus")
  }

  private var sortedMerchants: [(String, MerchantStateData)] {
    economy.merchantStates.sorted { $0.value.gold > $1.value.gold }
  }

  var body: some View {
    VStack(alignment: .leading, spacing: 8) {
      HStack {
        Image(systemName: "dollarsign.circle.fill")
          .font(Theme.fontSmall)
          .foregroundColor(.yellow)
        Text("Economy")
          .font(Theme.fontSmall.bold())
          .foregroundColor(.yellow)
        Spacer()
        if !economy.marketNews.isEmpty {
          Text(economy.marketNews)
            .font(Theme.fontTiny)
            .foregroundColor(Theme.mutedText)
            .lineLimit(1)
        }
      }

      // Merchant Roster
      DisclosureGroup(isExpanded: $rosterExpanded) {
        VStack(spacing: 6) {
          ForEach(sortedMerchants, id: \.0) { _, merchant in
            MerchantRowView(merchant: merchant)
          }
        }
      } label: {
        Text("Merchants (\(economy.merchantStates.count))")
          .font(Theme.fontSmall.bold())
          .foregroundColor(.yellow)
      }
      .tint(Theme.bodyText)

      // Price Adjustments
      DisclosureGroup(isExpanded: $adjustmentsExpanded) {
        if economy.priceAdjustments.isEmpty {
          Text("No active adjustments")
            .font(Theme.fontSmall)
            .foregroundColor(Theme.mutedText)
        } else {
          VStack(alignment: .leading, spacing: 4) {
            ForEach(
              economy.priceAdjustments.sorted(by: { $0.key < $1.key }), id: \.key
            ) { item, mult in
              let style = adjustmentStyle(mult)
              HStack {
                Text(item)
                  .font(Theme.fontSmall)
                  .foregroundColor(Theme.bodyText)
                Spacer()
                Text(String(format: "x%.1f", mult))
                  .font(Theme.fontSmall.monospacedDigit().bold())
                  .foregroundColor(style.color)
                Image(systemName: style.icon)
                  .font(Theme.fontTiny)
                  .foregroundColor(style.color)
              }
            }
          }
        }
      } label: {
        Text("Price Adjustments (\(economy.priceAdjustments.count))")
          .font(Theme.fontSmall.bold())
          .foregroundColor(.yellow)
      }
      .tint(Theme.bodyText)

      // Recent Trades
      DisclosureGroup(isExpanded: $tradesExpanded) {
        if economy.tradeHistory.isEmpty {
          Text("No trades yet")
            .font(Theme.fontSmall)
            .foregroundColor(Theme.mutedText)
        } else {
          VStack(alignment: .leading, spacing: 4) {
            ForEach(economy.tradeHistory.suffix(10).reversed()) { trade in
              let isBuy = trade.action == "buy"
              HStack(spacing: 6) {
                Text("T\(trade.tick)")
                  .font(Theme.fontTiny.monospacedDigit())
                  .foregroundColor(Theme.mutedText)
                  .frame(width: 36, alignment: .leading)
                Text(trade.action.uppercased())
                  .font(Theme.fontTiny.bold())
                  .foregroundColor(isBuy ? .green : .orange)
                  .padding(.horizontal, 4)
                  .padding(.vertical, 1)
                  .background(
                    (isBuy ? Color.green : Color.orange).opacity(0.15)
                  )
                  .cornerRadius(3)
                Text(trade.itemName)
                  .font(Theme.fontSmall)
                  .foregroundColor(Theme.bodyText)
                  .lineLimit(1)
                Spacer()
                if trade.price > 0 {
                  Text(isBuy ? "-\(trade.price)g" : "+\(trade.price)g")
                    .font(Theme.fontSmall.monospacedDigit())
                    .foregroundColor(isBuy ? .red : .green)
                }
              }
            }
          }
        }
      } label: {
        Text("Recent Trades (\(economy.tradeHistory.count))")
          .font(Theme.fontSmall.bold())
          .foregroundColor(.yellow)
      }
      .tint(Theme.bodyText)
    }
    .padding(Theme.cardPadding)
    .background(
      RoundedRectangle(cornerRadius: Theme.cardRadius)
        .fill(Color.yellow.opacity(0.06))
        .overlay(
          RoundedRectangle(cornerRadius: Theme.cardRadius)
            .strokeBorder(Color.yellow.opacity(0.25), lineWidth: 1)
        )
    )
  }
}

// MARK: - Merchant Row

struct MerchantRowView: View {
  let merchant: MerchantStateData

  var body: some View {
    VStack(alignment: .leading, spacing: 3) {
      HStack {
        Text(merchant.npcName)
          .font(Theme.fontSmall.bold())
          .foregroundColor(Theme.headerText)
        Spacer()
        Text("\(merchant.gold)/\(merchant.goldCap)g")
          .font(Theme.fontTiny.monospacedDigit())
          .foregroundColor(Theme.bodyText)
        Text("\(merchant.inventory.count) items")
          .font(Theme.fontTiny)
          .foregroundColor(Theme.mutedText)
      }
      HPBarView(current: merchant.gold, max: merchant.goldCap, height: 4)
    }
    .padding(6)
    .background(
      RoundedRectangle(cornerRadius: 6)
        .fill(Color.yellow.opacity(0.04))
    )
  }
}

// MARK: - Event Log

struct EventLogView: View {
  let entries: [String]

  // Log prefix contract: prefixes like [TRADE], [COMBAT], etc. are defined in agent/main.py
  private func entryColor(_ entry: String) -> Color {
    if entry.hasPrefix("[TRADE]") { return .yellow }
    if entry.hasPrefix("[MARKET]") { return .green }
    if entry.hasPrefix("[RESTOCK]") { return .orange }
    return Theme.mutedText
  }

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
              .foregroundColor(entryColor(entry))
              .lineLimit(2)
          }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
      }
      .frame(maxHeight: 120)
    }
  }
}

// MARK: - Inventory Section

struct InventorySection: View {
  let items: [InventoryItem]
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
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
              ItemRowView(item: item)
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
}
