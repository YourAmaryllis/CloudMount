import Foundation

/// Finds the CloudMount python source tree and spawns `cloudmount serve`
/// if nothing is already listening on the target port. Mirrors the
/// resolution order used by bin/cloudmount-launch and gui/tray.py.
enum ServerLauncher {
    static func findRoot() -> URL? {
        if let env = ProcessInfo.processInfo.environment["CLOUDMOUNT_ROOT"] {
            let url = URL(fileURLWithPath: env)
            if FileManager.default.fileExists(atPath: url.appendingPathComponent("bin/cloudmount").path) {
                return url
            }
        }
        // Resolve relative to THIS app's own bundle first — correct no
        // matter where the .app actually lives (/Applications, dist/ before
        // install, a second copy, etc). A hardcoded /Applications path here
        // would silently pick up a stale sibling install instead of the
        // Python core this exact binary was built and signed together with.
        if let resources = Bundle.main.resourceURL {
            let bundled = resources.appendingPathComponent("wasabi")
            if FileManager.default.fileExists(atPath: bundled.appendingPathComponent("bin/cloudmount").path) {
                return bundled
            }
        }
        let devFallback = NSHomeDirectory() + "/YourAmaryllis/CloudMount"
        if FileManager.default.fileExists(atPath: devFallback + "/bin/cloudmount") {
            return URL(fileURLWithPath: devFallback)
        }
        return nil
    }

    static func findPython3() -> String? {
        let candidates = [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
        ]
        for c in candidates where FileManager.default.isExecutableFile(atPath: c) {
            return c
        }
        // Fall back to the user's actual login shell resolution — covers
        // pyenv/asdf/conda installs the hardcoded paths above miss. A
        // GUI-launched app doesn't inherit the shell's PATH, so ask the
        // shell directly instead of trusting our own environment.
        let shells = [("/bin/zsh", "-lc"), ("/bin/bash", "-lc")]
        for (shell, flag) in shells where FileManager.default.isExecutableFile(atPath: shell) {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: shell)
            p.arguments = [flag, "command -v python3"]
            let pipe = Pipe()
            p.standardOutput = pipe
            p.standardError = FileHandle.nullDevice
            do {
                try p.run()
                p.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                if let path = String(data: data, encoding: .utf8)?
                    .trimmingCharacters(in: .whitespacesAndNewlines), !path.isEmpty,
                    FileManager.default.isExecutableFile(atPath: path) {
                    return path
                }
            } catch {
                continue
            }
        }
        return nil
    }

    /// Spawns `python3 bin/cloudmount serve --port <port> --no-open`.
    /// Process-spawned children are independent OS processes that Foundation
    /// never signals on our own exit, so this outlives the menu-bar app —
    /// same lifecycle the rest of CloudMount already relies on.
    static func startServerIfNeeded(port: Int, log: @escaping (String) -> Void) {
        guard let root = findRoot() else {
            log("cloudmount root not found (set CLOUDMOUNT_ROOT for dev)")
            return
        }
        guard let python3 = findPython3() else {
            log("python3 not found")
            return
        }
        let cmd = root.appendingPathComponent("bin/cloudmount").path

        let process = Process()
        process.executableURL = URL(fileURLWithPath: python3)
        process.arguments = [cmd, "serve", "--port", String(port), "--no-open"]
        process.currentDirectoryURL = root
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = root.path + (env["PYTHONPATH"].map { ":" + $0 } ?? "")
        process.environment = env
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice

        // New session so the server isn't tied to this app's process group.
        do {
            try process.run()
            log("started cloudmount serve pid=\(process.processIdentifier)")
        } catch {
            log("failed to start server: \(error)")
        }
    }
}
