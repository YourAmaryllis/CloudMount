import SwiftUI

/// The tray click target: a rich, colorful "everything at a glance" view.
/// The web UI (opened via the footer button) is for configuration —
/// adding hosts, editing mount definitions — not for checking status.
struct MenuBarView: View {
    @ObservedObject var model: CloudMountModel

    private var upCount: Int { model.mounts.filter { $0.mounted == true }.count }
    private var total: Int { model.mounts.count }
    private var statusColor: Color { model.statusColor }

    private var statusText: String {
        if total == 0 { return "No mounts configured" }
        if upCount == total { return "All mounts active" }
        if upCount == 0 { return "Nothing mounted" }
        return "\(upCount) of \(total) mounted"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            Divider()
            if model.mounts.isEmpty {
                emptyState
            } else {
                // No ScrollView: it doesn't reliably force a
                // MenuBarExtra(.window) popover to resize to its content,
                // which was silently hiding this whole section. A plain
                // VStack lets the popover size itself to the real content.
                VStack(spacing: 6) {
                    ForEach(model.mounts) { m in
                        MountCard(mount: m, busy: model.busy.contains(m.id)) {
                            model.toggle(m)
                        }
                    }
                }
                .padding(.horizontal, 12)
                .padding(.top, 10)
                .padding(.bottom, 4)
            }
            Divider()
            footer
        }
        .frame(width: 300)
    }

    private var header: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(statusColor.gradient)
                    .frame(width: 44, height: 44)
                Image(systemName: "icloud.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(.white)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text("CloudMount")
                    .font(.system(size: 15, weight: .semibold))
                Text(statusText)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let err = model.lastError {
                    Text(err)
                        .font(.caption2)
                        .foregroundStyle(.red)
                }
            }
            Spacer()
            Button {
                Task { await model.refresh() }
            } label: {
                Image(systemName: "arrow.clockwise.circle.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding(14)
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "icloud.slash")
                .font(.system(size: 28))
                .foregroundStyle(.secondary)
            Text("No mounts configured yet")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(28)
    }

    private var footer: some View {
        VStack(spacing: 10) {
            HStack(spacing: 8) {
                Button("Mount All") { model.mountAll() }
                    .tint(.green)
                Button("Unmount All") { model.unmountAll() }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
            .padding(.horizontal, 14)
            .padding(.top, 10)

            VStack(spacing: 0) {
                Button {
                    model.openUI()
                } label: {
                    HStack {
                        Image(systemName: "slider.horizontal.3")
                        Text("Configure Hosts & Mounts…")
                        Spacer()
                        Image(systemName: "arrow.up.right").font(.caption)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)

                Button {
                    model.runSetup()
                } label: {
                    HStack {
                        Image(systemName: "wrench.and.screwdriver")
                        Text("Re-check setup (rclone, macFUSE)")
                        Spacer()
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 14)
                .padding(.vertical, 6)
            }

            Divider()

            Button {
                model.quit()
            } label: {
                HStack {
                    Text("Quit CloudMount")
                    Spacer()
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14)
            .padding(.bottom, 10)
        }
    }
}

private struct MountCard: View {
    let mount: StatusResponse.MountItem
    let busy: Bool
    let onToggle: () -> Void

    private var isMounted: Bool { mount.mounted == true }
    private var tint: Color { isMounted ? .green : .secondary }

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: isMounted ? "checkmark.circle.fill" : "circle.dashed")
                .font(.system(size: 18))
                .foregroundStyle(tint)
                .symbolRenderingMode(.hierarchical)

            VStack(alignment: .leading, spacing: 1) {
                Text(mount.label ?? mount.id)
                    .font(.system(size: 13, weight: .medium))
                if let path = mount.path, !path.isEmpty {
                    Text(path)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            }

            Spacer()

            if busy {
                ProgressView().controlSize(.small)
            } else {
                Button(isMounted ? "Unmount" : "Mount") { onToggle() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .tint(isMounted ? .red : .accentColor)
            }
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(tint.opacity(isMounted ? 0.14 : 0.07))
        )
    }
}
