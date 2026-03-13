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
