import SwiftUI

enum Theme {
  // Backgrounds
  static let windowBackground = Color(red: 0.10, green: 0.10, blue: 0.13)
  static let cardBackground = Color(red: 0.14, green: 0.14, blue: 0.18)
  static let cardBorder = Color.white.opacity(0.08)

  // Accents
  static let accent = Color(red: 0.55, green: 0.45, blue: 0.85)  // muted purple
  static let headerText = Color.white.opacity(0.9)
  static let bodyText = Color.white.opacity(0.7)
  static let mutedText = Color.white.opacity(0.45)

  // Font scale (replaces scattered .caption/.caption2)
  static let fontTiny: Font = .caption2
  static let fontSmall: Font = .caption
  static let fontBody: Font = .subheadline
  static let fontHeading: Font = .headline
  static let fontTitle: Font = .title3

  // Spacing
  static let cardPadding: CGFloat = 14
  static let cardRadius: CGFloat = 10
  static let hpBarHeight: CGFloat = 12
}
