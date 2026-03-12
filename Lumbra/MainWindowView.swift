import SwiftUI

struct MainWindowView: View {
    @ObservedObject var viewModel: LumbraViewModel
    @State private var sidebarWidth: CGFloat = 260
    @State private var dragStartWidth: CGFloat = 260

    var body: some View {
        VStack(spacing: 0) {
            // Header bar
            HStack {
                Image(systemName: "brain.head.profile")
                    .font(Theme.fontBody)
                    .foregroundColor(Theme.accent)
                Text("Lumbra")
                    .font(Theme.fontTitle.bold())
                    .foregroundColor(Theme.headerText)
                Spacer()
                Circle()
                    .fill(viewModel.isAgentConnected ? Color.green : Color.gray)
                    .frame(width: 8, height: 8)
                Text(viewModel.isAgentConnected ? "Connected" : "Waiting")
                    .font(Theme.fontSmall)
                    .foregroundColor(Theme.mutedText)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(Theme.cardBackground)

            if let gs = viewModel.gameState {
                // Two-column layout
                HStack(alignment: .top, spacing: 0) {
                    // Left sidebar
                    ScrollView {
                        VStack(spacing: 12) {
                            CharacterCardView(character: gs.character, zone: gs.zone)
                            InventorySection(items: gs.character.inventory, weapon: gs.character.weapon, armor: gs.character.armor)
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
                        .padding(12)
                    }
                    .frame(width: sidebarWidth)

                    // Draggable divider
                    Rectangle()
                        .fill(Theme.cardBorder)
                        .frame(width: 4)
                        .padding(.horizontal, 4)
                        .contentShape(Rectangle())
                        .onHover { hovering in
                            if hovering {
                                NSCursor.resizeLeftRight.push()
                            } else {
                                NSCursor.pop()
                            }
                        }
                        .gesture(
                            DragGesture(minimumDistance: 1)
                                .onChanged { value in
                                    let newWidth = dragStartWidth + value.translation.width
                                    sidebarWidth = min(max(newWidth, 180), 400)
                                }
                                .onEnded { _ in
                                    dragStartWidth = sidebarWidth
                                }
                        )

                    // Right content
                    ScrollView {
                        VStack(spacing: 12) {
                            if let quest = gs.quest {
                                QuestCardView(quest: quest)
                            }
                            if let combat = gs.combat {
                                CombatCardView(combat: combat)
                            }
                            if let npc = gs.npc_encounter {
                                NPCCardView(encounter: npc)
                            }
                            if let expeditions = gs.expeditions, !expeditions.isEmpty {
                                ExpeditionPanelView(expeditions: expeditions)
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
                        .padding(12)
                    }
                }

                Divider()
                    .background(Theme.cardBorder)

                // Bottom: Event log + Quit
                HStack(alignment: .bottom) {
                    if !gs.log.isEmpty {
                        EventLogView(entries: gs.log)
                    } else {
                        Spacer()
                    }
                    Spacer()
                    Button("Quit") {
                        NSApplication.shared.terminate(nil)
                    }
                    .buttonStyle(.borderless)
                    .foregroundColor(Theme.mutedText)
                    .font(Theme.fontSmall)
                }
                .padding(14)
                .background(Theme.cardBackground.opacity(0.5))
            } else {
                Spacer()
                VStack(spacing: 12) {
                    Image(systemName: "gamecontroller")
                        .font(.system(size: 40))
                        .foregroundColor(Theme.mutedText)
                    Text("Waiting for game engine...")
                        .font(Theme.fontBody)
                        .foregroundColor(Theme.mutedText)
                }
                Spacer()

                HStack {
                    Spacer()
                    Button("Quit") {
                        NSApplication.shared.terminate(nil)
                    }
                    .buttonStyle(.borderless)
                    .foregroundColor(Theme.mutedText)
                    .font(Theme.fontSmall)
                }
                .padding(14)
            }
        }
        .background(Theme.windowBackground)
        .frame(minWidth: 520, minHeight: 420)
    }
}
