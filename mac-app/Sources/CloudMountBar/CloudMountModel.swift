import Foundation
import AppKit
import SwiftUI

@MainActor
final class CloudMountModel: ObservableObject {
    @Published var labelText: String = ""
    @Published var mounts: [StatusResponse.MountItem] = []
    @Published var busy: Set<String> = []
    @Published var lastError: String?

    let port = 8765
    private let client: APIClient
    private var timer: Timer?
    private var lastSpawnAttempt: Date = .distantPast

    init() {
        client = APIClient(port: port)
    }

    /// Shared with both the menu-bar icon and the dropdown header, so the
    /// two are always in sync: green = fully mounted, orange = partial,
    /// gray = nothing mounted or not configured yet.
    var statusColor: Color {
        let total = mounts.count
        let up = mounts.filter { $0.mounted == true }.count
        if total == 0 { return .gray }
        if up == total { return .green }
        if up == 0 { return .gray }
        return .orange
    }

    func start() {
        log("starting")
        Task {
            if await !client.isReachable() {
                ServerLauncher.startServerIfNeeded(port: port, log: log)
            }
            await refresh()
        }
        let t = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in await self.refresh() }
        }
        // Let the OS coalesce this wake with other system timers instead of
        // forcing a precise 5s schedule — a bare Timer with zero tolerance
        // is exactly what tanks "Energy Impact" in Activity Monitor/Juicy,
        // even though the work per tick is trivial and CPU% stays near 0.
        t.tolerance = 1.5
        timer = t
    }

    func refresh() async {
        do {
            let status = try await client.fetchStatus(light: true)
            mounts = status.mounts
            let up = status.summary.mountsUp
            let total = status.summary.mountsTotal
            labelText = total == 0 ? "+" : (up == total ? "\(up)" : "\(up)/\(total)")
            lastError = nil
            log("refresh ok: \(mounts.count) mounts, \(up)/\(total) up")
        } catch {
            // Server may still be starting, or died and needs a respawn —
            // either way, don't just sit on "unreachable" forever.
            lastError = "CloudMount server unreachable"
            log("refresh failed: \(error)")
            maybeRespawnServer()
        }
    }

    /// At most one spawn attempt per 10s, so a persistently-down server
    /// (e.g. python3/repo genuinely missing) doesn't get hammered with a
    /// Process.run() every single 5s poll.
    private func maybeRespawnServer() {
        let now = Date()
        guard now.timeIntervalSince(lastSpawnAttempt) > 10 else { return }
        lastSpawnAttempt = now
        ServerLauncher.startServerIfNeeded(port: port, log: log)
    }

    func toggle(_ mount: StatusResponse.MountItem) {
        let id = mount.id
        guard !busy.contains(id) else { return }
        busy.insert(id)
        Task {
            do {
                if mount.mounted == true {
                    try await client.mountDown(id: id)
                } else {
                    try await client.mountUp(id: id)
                }
            } catch {
                lastError = "\(mount.label ?? id): action failed"
            }
            busy.remove(id)
            await refresh()
        }
    }

    func mountAll() {
        Task {
            try? await client.mountAllUp()
            await refresh()
        }
    }

    func unmountAll() {
        Task {
            try? await client.mountAllDown()
            await refresh()
        }
    }

    func runSetup() {
        Task {
            try? await client.runSetup()
            await refresh()
        }
    }

    func openUI() {
        Task { _ = await client.isReachable() } // nudge server awake if asleep
        if let url = URL(string: "http://127.0.0.1:\(port)/") {
            NSWorkspace.shared.open(url)
        }
    }

    /// Stops the background server, then quits this menu-bar app itself —
    /// unlike the old SwiftBar plugin's "Quit CloudMount" (which only ever
    /// stopped the server since SwiftBar itself was a separate app to quit
    /// separately), there is no separate host here: this app IS the menu bar
    /// icon, so quitting it should be a full, clean stop. Mounts are
    /// unaffected either way — they run fully detached from the server.
    func quit() {
        Task {
            try? await client.quit()
            NSApplication.shared.terminate(nil)
        }
    }

    private func log(_ msg: String) {
        #if DEBUG
        FileHandle.standardError.write("[CloudMountBar] \(msg)\n".data(using: .utf8)!)
        #endif
    }
}
