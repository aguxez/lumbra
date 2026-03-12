import Combine
import SwiftUI

class LumbraViewModel: ObservableObject {
  @Published var gameState: GameStateResponse?
  @Published var isAgentConnected: Bool = false

  private var disconnectTimer: AnyCancellable?
  private let server = LocalServer()

  init() {
    server.onDataReceived = { [weak self] data in
      guard let self else { return }
      do {
        let state = try JSONDecoder().decode(GameStateResponse.self, from: data)
        self.gameState = state
        self.isAgentConnected = true
        self.resetDisconnectTimer()
      } catch {
        print("[ViewModel] JSON decode error: \(error)")
      }
    }

    server.start()
  }

  deinit {
    server.stop()
  }

  var hpDisplay: String {
    guard let state = gameState else { return "---" }
    return "\(state.character.hitPoints)/\(state.character.maxHitPoints)"
  }

  private func resetDisconnectTimer() {
    disconnectTimer?.cancel()
    disconnectTimer = Just(())
      .delay(for: .seconds(90), scheduler: DispatchQueue.main)
      .sink { [weak self] _ in
        self?.isAgentConnected = false
      }
  }
}
