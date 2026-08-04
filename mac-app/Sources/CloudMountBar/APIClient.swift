import Foundation

struct StatusResponse: Decodable {
    struct Summary: Decodable {
        let mountsTotal: Int
        let mountsUp: Int

        enum CodingKeys: String, CodingKey {
            case mountsTotal = "mounts_total"
            case mountsUp = "mounts_up"
        }
    }

    struct MountItem: Decodable, Identifiable {
        let id: String
        let label: String?
        let mountKind: String?
        let path: String?
        let mounted: Bool?

        enum CodingKeys: String, CodingKey {
            case id, label, path, mounted
            case mountKind = "mount_kind"
        }
    }

    let summary: Summary
    let mounts: [MountItem]
}

enum APIError: Error {
    case badResponse
}

/// Thin client for the CloudMount server's local HTTP API
/// (gui/server.py). Never talks to Keychain/rclone directly — that stays
/// in the Python core so there is exactly one source of truth.
struct APIClient {
    let port: Int

    private var base: String { "http://127.0.0.1:\(port)" }

    func fetchStatus(light: Bool = true) async throws -> StatusResponse {
        let url = URL(string: "\(base)/api/status?light=\(light ? 1 : 0)")!
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.badResponse
        }
        return try JSONDecoder().decode(StatusResponse.self, from: data)
    }

    @discardableResult
    private func post(_ path: String, body: [String: Any] = [:]) async throws -> Data {
        var req = URLRequest(url: URL(string: "\(base)\(path)")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.badResponse
        }
        return data
    }

    func mountUp(id: String) async throws { try await post("/api/mount/up", body: ["id": id]) }
    func mountDown(id: String) async throws { try await post("/api/mount/down", body: ["id": id]) }
    func mountAllUp() async throws { try await post("/api/mount/all-up") }
    func mountAllDown() async throws { try await post("/api/mount/all-down") }

    func runSetup() async throws {
        let url = URL(string: "\(base)/api/setup")!
        _ = try await URLSession.shared.data(from: url)
    }

    func quit() async throws { try await post("/api/quit") }

    /// True once the server answers — used to decide whether to spawn it.
    func isReachable() async -> Bool {
        (try? await fetchStatus(light: true)) != nil
    }
}
