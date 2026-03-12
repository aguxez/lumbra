import SwiftUI

@main
struct LumbraApp: App {
    @StateObject private var viewModel = LumbraViewModel()

    var body: some Scene {
        MenuBarExtra {
            LumbraPanel(viewModel: viewModel)
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "brain.head.profile")
                Text(viewModel.hpDisplay)
                    .monospacedDigit()
            }
        }
        .menuBarExtraStyle(.window)
    }
}
