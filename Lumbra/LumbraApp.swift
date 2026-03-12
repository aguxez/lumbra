import SwiftUI

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Bring app to front on launch so the window appears
        NSApplication.shared.activate(ignoringOtherApps: true)
    }
}

@main
struct LumbraApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var viewModel = LumbraViewModel()
    @Environment(\.openWindow) private var openWindow

    var body: some Scene {
        Window("Lumbra", id: "main") {
            MainWindowView(viewModel: viewModel)
        }
        .defaultSize(width: 620, height: 520)

        MenuBarExtra {
            Button("Show Lumbra") {
                openWindow(id: "main")
                NSApplication.shared.activate(ignoringOtherApps: true)
            }
            Divider()
            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "brain.head.profile")
                Text(viewModel.hpDisplay)
                    .monospacedDigit()
            }
        }
    }
}
