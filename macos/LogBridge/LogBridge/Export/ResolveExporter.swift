import Foundation

/// DaVinci Resolve export.
///
/// WB is a **toggleable** node, not baked into Rec.709 as the only deliverable.
/// The exporter writes (conceptually) an IDT assignment plus an optional
/// Color Space Transform / RGB matrix node for Bradford CAT, then a Rec.709
/// output transform the user can bypass.
enum ResolveExporter {
    static func exportNote(clips: [Clip], includeWBNode: Bool, cct: Double, tint: Double) -> String {
        var lines: [String] = []
        lines.append("LogBridge M1 Resolve export (implemented, unverified)")
        lines.append("Working space: DaVinci Wide Gamut / DaVinci Intermediate (D65)")
        lines.append("WB node: \(includeWBNode ? "ON (scene-linear Bradford CAT, \(Int(cct)) K, tint \(tint))" : "OFF — not baked")")
        lines.append("ODT: Rec.709 is a separate output, not the only deliverable.")
        lines.append("Clips:")
        for clip in clips {
            lines.append("  - \(clip.url.lastPathComponent): \(clip.idt.ocioName) [\(clip.verificationBadge)]")
        }
        return lines.joined(separator: "\n")
    }

    /// Placeholder on-disk export. A later slice writes a .drp / DCTL / CST chain.
    static func writeSidecar(to url: URL, includeWBNode: Bool) throws {
        let body = """
        # LogBridge M1 — Resolve node graph (scaffold)
        # 1. Input Color Space: camera IDT (per-clip locked pair)
        # 2. WB node: \(includeWBNode ? "enabled" : "disabled / bypassed")
        #    Scene-linear Bradford CAT. Not baked into the Rec.709 ODT.
        # 3. Output: Rec.709 (toggleable) AND DWG Intermediate timeline.
        # Status: implemented (unverified)
        """
        try body.write(to: url, atomically: true, encoding: .utf8)
    }
}
