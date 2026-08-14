import Foundation
import AVFoundation

/// Detection order:
///  1. Camera-private metadata (ARRI MXF, Sony Acquisition, Canon vendor, RED RMD)
///  2. Filename / model hint
///  3. User picker
///
/// NEVER trust QuickTime nclc / nclx / colr to identify S-Log3 or LogC4.
/// NEVER default S-Log3 to S-Gamut3.Cine.
struct DetectionResult {
    var idt: IDT?
    var curve: String?
    var gamut: String?
    var source: DetectionSource
    var needsUserPicker: Bool
    var note: String
}

enum ClipDetector {
    static func detect(url: URL, modelHint: String? = nil) -> DetectionResult {
        if let meta = detectMetadata(url: url), !meta.needsUserPicker {
            return meta
        }
        if let fn = detectFilename(url: url), !fn.needsUserPicker {
            return fn
        }
        if let model = detectModel(modelHint) {
            return model
        }
        if let partial = detectMetadata(url: url) ?? detectFilename(url: url) {
            return partial
        }
        return DetectionResult(
            idt: nil,
            curve: nil,
            gamut: nil,
            source: .unresolved,
            needsUserPicker: true,
            note: "No camera-private metadata or filename/model hint; user picker required. QuickTime nclc is never used."
        )
    }

    /// Camera-private boxes only. QuickTime nclc is read then discarded.
    static func detectMetadata(url: URL) -> DetectionResult? {
        let asset = AVURLAsset(url: url)
        // Intentionally do not use asset.formatDescriptions / nclc / nclx / colr
        // as an identity for S-Log3 or LogC4. Those tags are often Rec.709 or unset.
        _ = discardQuickTimeNCLC(asset)

        if let arri = readARRIColorSpace(url: url) {
            return locked(.arriLogC4AWG4, source: .metadata, note: "ARRI MXF \(arri)")
        }
        if let sony = readSonyAcquisition(url: url) {
            return sony
        }
        if let canon = readCanonVendor(url: url) {
            return canon
        }
        if let red = readREDRMD(url: url) {
            return red
        }
        return nil
    }

    /// nclc is inspected only so we can prove we did not use it.
    private static func discardQuickTimeNCLC(_ asset: AVURLAsset) -> Void {
        // Do not map nclc color primaries / transfer / matrix to an IDT.
        // Common trap: nclc 1-1-1 (Rec.709) on an S-Log3 file.
        _ = asset
    }

    static func detectFilename(url: URL) -> DetectionResult? {
        let name = url.lastPathComponent.lowercased()
        let cineTokens = ["sgamut3.cine", "s-gamut3.cine", "sgamut3cine", "sgamut3_cine"]
        let venice = name.contains("venice")
        if cineTokens.contains(where: { name.contains($0) }) {
            return locked(venice ? .sonySLog3SGamut3CineVenice : .sonySLog3SGamut3Cine, source: .filename, note: "filename S-Gamut3.Cine")
        }
        if name.contains("sgamut3") || name.contains("s-gamut3") {
            return locked(venice ? .sonySLog3SGamut3Venice : .sonySLog3SGamut3, source: .filename, note: "filename S-Gamut3")
        }
        if name.contains("logc4") || name.contains("awg4") {
            return locked(.arriLogC4AWG4, source: .filename, note: "filename LogC4/AWG4")
        }
        if name.contains("v-log") || name.contains("vlog") || name.contains("vgamut") {
            return locked(.panasonicVLogVGamut, source: .filename, note: "filename V-Log")
        }
        if name.contains("f-log2") || name.contains("flog2") {
            return locked(.fujiFLog2BT2020, source: .filename, note: "filename F-Log2")
        }
        if name.contains("n-log") || name.contains("nlog") {
            return locked(.nikonNLogBT2020, source: .filename, note: "filename N-Log")
        }
        if name.contains("log3g10") || name.contains("redwidegamut") {
            return locked(.redLog3G10RWG, source: .filename, note: "filename Log3G10")
        }
        if name.contains("s-log3") || name.contains("slog3") {
            return DetectionResult(
                idt: nil,
                curve: "S-Log3",
                gamut: nil,
                source: .filename,
                needsUserPicker: true,
                note: "S-Log3 in filename without gamut; user must pick S-Gamut3 or S-Gamut3.Cine (never default Cine)."
            )
        }
        return nil
    }

    static func detectModel(_ model: String?) -> DetectionResult? {
        guard let model else { return nil }
        let m = model.lowercased()
        if m.contains("venice") {
            return DetectionResult(
                idt: nil,
                curve: "S-Log3",
                gamut: nil,
                source: .model,
                needsUserPicker: true,
                note: "Venice camera detected; user must pick S-Gamut3 or S-Gamut3.Cine (Venice Builtin). Never default."
            )
        }
        if m.contains("alexa 35") || m.contains("alexa35") || m.contains("alexa 265") {
            return locked(.arriLogC4AWG4, source: .model, note: "model hint")
        }
        if m.contains("varicam") {
            return locked(.panasonicVLogVGamut, source: .model, note: "model hint")
        }
        if m.contains("komodo") || m.contains("v-raptor") || m.contains("dsmc2") {
            return locked(.redLog3G10RWG, source: .model, note: "model hint")
        }
        return nil
    }

    private static func locked(_ idt: IDT, source: DetectionSource, note: String) -> DetectionResult {
        DetectionResult(
            idt: idt,
            curve: idt.curve,
            gamut: idt.gamut,
            source: source,
            needsUserPicker: false,
            note: note
        )
    }

    // MARK: Camera-private readers (scaffolded; return nil until parsers land)

    /// ARRI MXF camera metadata (AS-11 / ARRI specific). Not QuickTime nclc.
    private static func readARRIColorSpace(url: URL) -> String? {
        // M1 scaffold: look for a sidecar or MXF essence descriptor in a later slice.
        _ = url
        return nil
    }

    /// Sony Acquisition Metadata (RDD 18 / XML in MXF). Distinguishes S-Gamut3 vs Cine.
    private static func readSonyAcquisition(url: URL) -> DetectionResult? {
        _ = url
        return nil
    }

    /// Canon vendor metadata. C-Log2/3 are stubs: do not invent a C-Log2 toe.
    private static func readCanonVendor(url: URL) -> DetectionResult? {
        _ = url
        return nil
    }

    /// RED RMD sidecar / header. Log3G10 + REDWideGamutRGB.
    private static func readREDRMD(url: URL) -> DetectionResult? {
        let sidecar = url.deletingPathExtension().appendingPathExtension("rmd")
        if FileManager.default.fileExists(atPath: sidecar.path) {
            // Presence of RMD is a hint, not a parse. Later slice reads color_space.
            return locked(.redLog3G10RWG, source: .metadata, note: "RED RMD sidecar present")
        }
        return nil
    }
}
