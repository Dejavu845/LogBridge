import SwiftUI

/// Shared chrome for a dark, preview-first window.
/// Colors only. No new user-facing sentences. Not a second process path.
enum LBChrome {
    static let canvas = Color(red: 0.06, green: 0.06, blue: 0.07)
    static let panel = Color(red: 0.11, green: 0.11, blue: 0.12)
    static let inset = Color(red: 0.15, green: 0.15, blue: 0.16)
    static let hairline = Color.white.opacity(0.07)
    static let pending = Color(red: 0.90, green: 0.70, blue: 0.32)
    static let locked = Color(red: 0.42, green: 0.70, blue: 0.76)
    static let written = Color(red: 0.40, green: 0.62, blue: 0.50)
    static let warn = Color(red: 0.93, green: 0.55, blue: 0.30)

    /// Control-layer fill. System material so Tahoe can map it to Liquid Glass.
    /// Do not call the macOS 26 glass-effect view APIs — older Xcode CI cannot type-check them.
    static let controlMaterial = Material.ultraThinMaterial

    /// Motion lock: any withAnimation must read accessibilityReduceMotion and snap when on.
    /// Preview canvas / image hosts never animate opacity. No spring bounce.
    /// Selection stroke + write-progress appear: runSelectionMotion, easeInOut.

    /// Clip-row / inspector follow-stroke / write-progress appear. Snap when Reduce Motion is on.
    static func runSelectionMotion(_ reduceMotion: Bool, _ updates: () -> Void) {
        if reduceMotion {
            updates()
        } else {
            withAnimation(.easeInOut(duration: 0.15), updates)
        }
    }

    /// Write-progress line appear. Same ease / snap as selection. Not the preview image.
    static func runAppearMotion(_ reduceMotion: Bool, _ updates: () -> Void) {
        runSelectionMotion(reduceMotion, updates)
    }

    /// One visual slab under the preview. Does not merge process into the IDT picker.
    static func decisionDock<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(spacing: 0) {
            Rectangle()
                .fill(hairline)
                .frame(height: 1)
            content()
        }
        .background(controlMaterial)
    }

    static func inspectorCard<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content()
            .padding(11)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(controlMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(hairline, lineWidth: 1)
            )
    }

    /// Inset slot on the dock (paired IDT picker). Same material family as the dock.
    static func controlSlot<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content()
            .background(controlMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(hairline, lineWidth: 1)
            )
    }

    /// Process cluster under the IDT slot. Same material family. Not a second process path.
    static func processModule<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content()
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(controlMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(hairline, lineWidth: 1)
            )
    }

    /// Sidebar clip row. Same 14pt slot family as process / inspector.
    /// Selection is a stroke, not a lock control.
    static func clipRowSlot<Content: View>(
        selected: Bool,
        accent: Color,
        @ViewBuilder content: () -> Content
    ) -> some View {
        ClipRowSlotView(selected: selected, accent: accent, content: content)
    }
}

/// Local drawnSelected so withAnimation does not leak into the preview host.
private struct ClipRowSlotView<Content: View>: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let selected: Bool
    let accent: Color
    let content: Content
    @State private var drawnSelected: Bool

    init(
        selected: Bool,
        accent: Color,
        @ViewBuilder content: () -> Content
    ) {
        self.selected = selected
        self.accent = accent
        self.content = content()
        _drawnSelected = State(initialValue: selected)
    }

    var body: some View {
        content
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(LBChrome.controlMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(drawnSelected ? accent.opacity(0.10) : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(
                        drawnSelected ? accent.opacity(0.85) : LBChrome.hairline,
                        lineWidth: drawnSelected ? 1.5 : 1
                    )
            )
            .onChange(of: selected) { _, new in
                LBChrome.runSelectionMotion(reduceMotion) {
                    drawnSelected = new
                }
            }
    }
}

/// Center-column empty invitation. Locked phrases only. No Button — tap opens importer.
struct EmptyPreviewHero: View {
    var targeted: Bool
    var onOpen: () -> Void

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "square.and.arrow.down")
                .font(.system(size: 40, weight: .ultraLight))
                .foregroundStyle(LBChrome.locked)
            Text("把混源文件夹拖进来")
                .font(.title3.weight(.semibold))
                .foregroundStyle(.primary)
            Text("每条选成对 Log 与色域")
                .font(.callout)
                .foregroundStyle(.secondary)
            Text("已实现（未验证）")
                .font(.caption.weight(.medium))
                .foregroundStyle(LBChrome.pending)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(LBChrome.pending.opacity(0.12))
                .clipShape(Capsule())
        }
        .padding(.horizontal, 36)
        .padding(.vertical, 28)
        .frame(maxWidth: 420)
        .background(LBChrome.controlMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(targeted ? LBChrome.locked.opacity(0.16) : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(targeted ? LBChrome.locked.opacity(0.55) : LBChrome.hairline, lineWidth: 1)
        )
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(targeted ? LBChrome.locked.opacity(0.08) : LBChrome.canvas)
        .contentShape(Rectangle())
        .onTapGesture { onOpen() }
    }
}

/// Human push + Mac leftover. No new chrome. Linux did not run these.
/// git push cursor/logbridge-ui-895b — token rejected. Keep draft PR 132.
/// Tahoe: controlMaterial may map. Do not call glass-effect view APIs.
/// Reduce Motion: selection stroke + write-progress snap.
/// 达芬奇: open _ACES2065-1_proxy EXR. 灰卡: click on preview.
/// Missing fps: Chinese fail, do not invent a rate.
