import Foundation
import Network

final class LocalServer {
  var onDataReceived: ((Data) -> Void)?

  private var listener: NWListener?
  private let queue = DispatchQueue(label: "com.lumbra.localserver")

  func start() {
    do {
      let params = NWParameters.tcp
      params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: 8234)
      listener = try NWListener(using: params)
    } catch {
      print("[LocalServer] Failed to create listener: \(error)")
      return
    }

    listener?.newConnectionHandler = { [weak self] connection in
      self?.handleConnection(connection)
    }

    listener?.stateUpdateHandler = { state in
      switch state {
      case .ready:
        print("[LocalServer] Listening on 127.0.0.1:8234")
      case .failed(let error):
        print("[LocalServer] Listener failed: \(error)")
      default:
        break
      }
    }

    listener?.start(queue: queue)
  }

  func stop() {
    listener?.cancel()
    listener = nil
  }

  private func handleConnection(_ connection: NWConnection) {
    connection.start(queue: queue)
    receiveData(on: connection, accumulated: Data())
  }

  private func receiveData(on connection: NWConnection, accumulated: Data) {
    connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) {
      [weak self] content, _, isComplete, error in
      guard let self else { return }

      var data = accumulated
      if let content { data.append(content) }

      // Check if we have the full HTTP request by parsing Content-Length
      if self.hasCompleteRequest(data) || isComplete || error != nil {
        self.processRequest(data: data, connection: connection)
      } else {
        self.receiveData(on: connection, accumulated: data)
      }
    }
  }

  private func hasCompleteRequest(_ data: Data) -> Bool {
    guard let raw = String(data: data, encoding: .utf8),
      let headerEnd = raw.range(of: "\r\n\r\n")
    else {
      return false
    }
    let headers = raw[raw.startIndex..<headerEnd.lowerBound].lowercased()
    let body = raw[headerEnd.upperBound...]

    // If there's a Content-Length header, check we have enough bytes
    if let clRange = headers.range(of: "content-length:") {
      let rest = headers[clRange.upperBound...].trimmingCharacters(in: .whitespaces)
      let lengthStr = rest.prefix(while: { $0.isNumber })
      if let expected = Int(lengthStr) {
        return body.utf8.count >= expected
      }
    }
    // No Content-Length — headers alone are enough (e.g. GET)
    return true
  }

  private func processRequest(data: Data, connection: NWConnection) {
    // Find JSON body after the HTTP headers (double CRLF)
    guard let raw = String(data: data, encoding: .utf8),
      let bodyRange = raw.range(of: "\r\n\r\n")
    else {
      sendResponse(
        connection: connection, status: "400 Bad Request", body: #"{"error":"invalid request"}"#)
      return
    }

    let bodyString = String(raw[bodyRange.upperBound...])
    guard let bodyData = bodyString.data(using: .utf8), !bodyString.isEmpty else {
      sendResponse(
        connection: connection, status: "400 Bad Request", body: #"{"error":"empty body"}"#)
      return
    }

    DispatchQueue.main.async {
      self.onDataReceived?(bodyData)
    }

    sendResponse(connection: connection, status: "200 OK", body: #"{"status":"ok"}"#)
  }

  private func sendResponse(connection: NWConnection, status: String, body: String) {
    let response =
      "HTTP/1.1 \(status)\r\nContent-Type: application/json\r\nContent-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n\(body)"
    let data = Data(response.utf8)
    connection.send(
      content: data,
      completion: .contentProcessed { _ in
        connection.cancel()
      })
  }
}
