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
    var veniceDetected: Bool = false
    var asShotCCT: Double? = nil
    var asShotTint: Double = 0
    /// Camera-reported rate from the sidecar `fps` key. Nil when absent or unparsable.
    var fps: Double? = nil
}

enum ClipDetector {
    static func detect(url: URL, modelHint: String? = nil) -> DetectionResult {
        var result: DetectionResult
        if let meta = detectMetadata(url: url), !meta.needsUserPicker {
            result = meta
        } else if let fn = detectFilename(url: url), !fn.needsUserPicker {
            result = fn
        } else if let model = detectModel(modelHint) {
            result = model
        } else if let partial = detectMetadata(url: url) ?? detectFilename(url: url) {
            result = partial
        } else {
            result = DetectionResult(
                idt: nil,
                curve: nil,
                gamut: nil,
                source: .unresolved,
                needsUserPicker: true,
                note: "读不到元数据，先选择 Log 与色域。"
            )
        }
        let shot = readAsShotWB(url: url)
        result.asShotCCT = shot.cct
        result.asShotTint = shot.tint
        result.fps = readSidecarFrameRate(url: url)
        return result
    }

    /// Camera-private CCT/tint only. QuickTime nclc is never an illuminant.
    /// Missing CCT/tint → pending / identity. Do not guess 5600 or 6504.
    static func readAsShotWB(from meta: [String: Any]) -> (cct: Double?, tint: Double) {
        let forbidden: Set<String> = [
            "nclc", "nclx", "colr", "quicktime_nclc", "qt_nclc",
            "quicktime_nclx", "qt_nclx", "quicktime_colr", "qt_colr"
        ]
        var cleaned: [String: Any] = [:]
        for (k, v) in meta {
            if !forbidden.contains(k.lowercased()) {
                cleaned[k.lowercased()] = v
            }
        }
        // Same order as color/as_shot.py `_CCT_KEYS` / `_TINT_KEYS`, then existing aliases.
        let cctKeys = [
            "as_shot_cct", "as_shot_kelvin", "white_balance_kelvin", "wb_kelvin",
            "color_temperature", "colour_temperature", "cct", "kelvin",
            "arri_white_balance", "arri_wb_kelvin", "sony_white_balance", "sony_wb_kelvin",
            "red_kelvin", "red_color_temperature", "canon_color_temperature", "canon_wb_kelvin",
            "arri_white_balance_kelvin", "arri_color_temperature", "arri_cct",
            "sony_acquisition_white_balance", "sony_acquisition_cct", "sony_colortemp", "sony_color_temperature",
            "canon_white_balance", "canon_cct",
            "red_wb_kelvin", "red_color_temp", "red_rmd_kelvin", "red_rmd_wb_kelvin",
            "apple_wb_kelvin", "apple_white_balance", "apple_color_temperature",
            "dji_wb_kelvin", "dji_white_balance", "dji_color_temperature"
        ]
        let tintKeys = [
            "as_shot_tint", "white_balance_tint", "wb_tint", "tint",
            "arri_tint", "arri_wb_tint", "sony_tint", "sony_wb_tint",
            "red_tint", "canon_tint", "canon_wb_tint",
            "arri_cc_shift", "red_wb_tint", "red_rmd_tint", "apple_tint", "dji_tint"
        ]
        var cct: Double?
        for key in cctKeys {
            if let v = cleaned[key], let parsed = parseCCT(v) {
                cct = parsed
                break
            }
        }
        var tint: Double = 0
        for key in tintKeys {
            if let v = cleaned[key], let parsed = parseTint(v) {
                tint = parsed
                break
            }
        }
        return (cct, tint)
    }

    private static func parseCCT(_ value: Any) -> Double? {
        let n: Double?
        if let d = value as? Double { n = d }
        else if let i = value as? Int { n = Double(i) }
        else if let s = value as? String {
            let digits = s.split(whereSeparator: { !$0.isNumber && $0 != "." })
            n = digits.first.flatMap { Double($0) }
        } else { n = nil }
        guard let cct = n, cct >= 1000, cct <= 25000 else { return nil }
        return cct
    }

    private static func parseTint(_ value: Any) -> Double? {
        if let d = value as? Double { return d }
        if let i = value as? Int { return Double(i) }
        if let s = value as? String { return Double(s) }
        return nil
    }

    /// Sidecar JSON next to the clip: `{stem}.json`. Camera-private keys. Not nclc.
    static func sidecarJSONURL(for url: URL) -> URL {
        url.deletingPathExtension().appendingPathExtension("json")
    }

    /// Missing file, non-object JSON, or unreadable bytes → nil. Do not guess.
    private static func loadSidecarJSON(url: URL) -> [String: Any]? {
        let jsonURL = sidecarJSONURL(for: url)
        guard let data = try? Data(contentsOf: jsonURL),
              let obj = try? JSONSerialization.jsonObject(with: data),
              let dict = obj as? [String: Any] else {
            return nil
        }
        return dict
    }

    /// Sidecar JSON next to the clip (camera-private keys). Not nclc. Not a demo reel.
    static func readAsShotWB(url: URL) -> (cct: Double?, tint: Double) {
        guard let dict = loadSidecarJSON(url: url) else {
            return (nil, 0)
        }
        return readAsShotWB(from: dict)
    }

    /// `fps` only (same field as Python `BatchClip.fps`). Absent / bad → nil.
    private static func readSidecarFrameRate(url: URL) -> Double? {
        guard let meta = loadSidecarJSON(url: url) else { return nil }
        guard let raw = meta["fps"] else { return nil }
        return parsePositiveRate(raw)
    }

    private static func parsePositiveRate(_ value: Any) -> Double? {
        if let n = value as? NSNumber {
            if CFGetTypeID(n) == CFBooleanGetTypeID() { return nil }
            let d = n.doubleValue
            if d.isFinite, d > 0 { return d }
            return nil
        }
        if let s = value as? String {
            let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
            guard let d = Double(trimmed), d.isFinite, d > 0 else { return nil }
            return d
        }
        return nil
    }

    /// Camera-private boxes only. QuickTime nclc is read then discarded.
    static func detectMetadata(url: URL) -> DetectionResult? {
        let asset = AVURLAsset(url: url)
        // Intentionally do not use asset.formatDescriptions / nclc / nclx / colr
        // as an identity for S-Log3 or LogC4. Those tags are often Rec.709 or unset.
        _ = discardQuickTimeNCLC(asset)

        if let arri = readARRIColorSpace(url: url), isLogC4(arri) {
            return locked(.arriLogC4AWG4, source: .metadata, note: "元数据 ARRI MXF")
        }
        if let sony = readSonyAcquisition(url: url) {
            return sony
        }
        if let canon = readCanonVendor(url: url) {
            return canon
        }
        if let red = readREDSidecarColor(url: url) {
            return red
        }
        if let other = readOtherVendorSidecar(url: url) {
            return other
        }
        if let arri = readARRIColorSpace(url: url), isLogC3(arri) {
            return locked(.arriLogC3EI800AWG3, source: .metadata, note: "元数据 LogC3 EI800 + AWG3")
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
            return locked(venice ? .sonySLog3SGamut3CineVenice : .sonySLog3SGamut3Cine, source: .filename, note: "文件名 S-Gamut3.Cine")
        }
        if name.contains("sgamut3") || name.contains("s-gamut3") {
            return locked(venice ? .sonySLog3SGamut3Venice : .sonySLog3SGamut3, source: .filename, note: "文件名 S-Gamut3")
        }
        if name.contains("logc4") || name.contains("awg4") {
            return locked(.arriLogC4AWG4, source: .filename, note: "文件名 LogC4/AWG4")
        }
        if name.contains("v-log") || name.contains("vlog") || name.contains("vgamut") {
            return locked(.panasonicVLogVGamut, source: .filename, note: "文件名 V-Log")
        }
        if name.contains("f-log2") || name.contains("flog2") {
            return locked(.fujiFLog2BT2020, source: .filename, note: "文件名 F-Log2")
        }
        if name.contains("n-log") || name.contains("nlog") {
            return locked(.nikonNLogBT2020, source: .filename, note: "文件名 N-Log")
        }
        if name.contains("log3g10") || name.contains("redwidegamut") {
            return locked(.redLog3G10RWG, source: .filename, note: "文件名 Log3G10")
        }
        if name.contains("d-log m") || name.contains("dlog m") || name.contains("dlogm") || name.contains("d-logm") {
            return DetectionResult(
                idt: nil, curve: nil, gamut: nil, source: .filename, needsUserPicker: true,
                note: "D-Log M 暂不能处理，请用 D-Log + D-Gamut"
            )
        }
        if name.contains("apple log 2") || name.contains("applelog2") || name.contains("apple-log-2") {
            return locked(.appleLog2AWG, source: .filename, note: "文件名 Apple Log 2 + Apple Wide Gamut")
        }
        if name.contains("logc3") && !name.contains("logc4") {
            return locked(.arriLogC3EI800AWG3, source: .filename, note: "文件名 LogC3 EI800 + AWG3")
        }
        if name.contains("awg3") && !name.contains("awg4") {
            return locked(.arriLogC3EI800AWG3, source: .filename, note: "文件名 AWG3 (LogC3 EI800 + AWG3)")
        }
        if name.contains("c-log2") || name.contains("clog2") {
            if name.contains("cinema") || name.contains("cgamut") || name.contains("c-gamut") {
                return locked(.canonCLog2CGamut, source: .filename, note: "文件名 C-Log2 + Cinema Gamut")
            }
            if name.contains("bt.2020") || name.contains("bt2020") || name.contains("rec2020") || name.contains("rec.2020") {
                return locked(.canonCLog2BT2020, source: .filename, note: "文件名 C-Log2 + BT.2020")
            }
            return DetectionResult(
                idt: nil,
                curve: "C-Log2",
                gamut: nil,
                source: .filename,
                needsUserPicker: true,
                note: "C-Log2 没有色域，先选择成对 IDT"
            )
        }
        if name.contains("c-log3") || name.contains("clog3") {
            if name.contains("cinema") || name.contains("cgamut") || name.contains("c-gamut") {
                return locked(.canonCLog3CGamut, source: .filename, note: "文件名 C-Log3 + Cinema Gamut")
            }
            if name.contains("bt.2020") || name.contains("bt2020") || name.contains("rec2020") || name.contains("rec.2020") {
                return locked(.canonCLog3BT2020, source: .filename, note: "文件名 C-Log3 + BT.2020")
            }
            return DetectionResult(
                idt: nil,
                curve: "C-Log3",
                gamut: nil,
                source: .filename,
                needsUserPicker: true,
                note: "C-Log3 没有色域，先选择成对 IDT"
            )
        }
        if name.contains("apple log") || name.contains("applelog") {
            return locked(.appleLogBT2020, source: .filename, note: "文件名 Apple Log")
        }
        if name.contains("d-log") || name.contains("dlog") || name.contains("d-gamut") || name.contains("dgamut") {
            return locked(.djiDLogDGamut, source: .filename, note: "文件名 D-Log")
        }
        if name.contains("s-log3") || name.contains("slog3") {
            return DetectionResult(
                idt: nil,
                curve: "S-Log3",
                gamut: nil,
                source: .filename,
                needsUserPicker: true,
                note: venice
                    ? "S-Log3 没有色域，检测到 Venice，先选择成对 IDT"
                    : "S-Log3 没有色域，先选择成对 IDT",
                veniceDetected: venice
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
                note: "检测到 Venice，先选择成对 IDT",
                veniceDetected: true
            )
        }
        if m.contains("alexa 35") || m.contains("alexa35") || m.contains("alexa 265") {
            return locked(.arriLogC4AWG4, source: .model, note: "机型提示")
        }
        if m.contains("varicam") {
            return locked(.panasonicVLogVGamut, source: .model, note: "机型提示")
        }
        if m.contains("komodo") || m.contains("v-raptor") || m.contains("dsmc2") {
            return locked(.redLog3G10RWG, source: .model, note: "机型提示")
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
            note: note,
            veniceDetected: idt.isVenice
        )
    }

    // MARK: Camera-private sidecar ({stem}.json). Keys match color/detect.py.

    /// Present key wins. Missing key may use the fallback. Values are lowercased.
    private static func metaString(_ meta: [String: Any], _ key: String, fallback: String? = nil) -> String {
        if let value = meta[key] {
            return loweredScalar(value)
        }
        if let fallback, let value = meta[fallback] {
            return loweredScalar(value)
        }
        return ""
    }

    private static func loweredScalar(_ value: Any) -> String {
        if value is NSNull { return "" }
        if let s = value as? String { return s.lowercased() }
        if let n = value as? NSNumber {
            if CFGetTypeID(n) == CFBooleanGetTypeID() {
                return n.boolValue ? "true" : "false"
            }
            return n.stringValue.lowercased()
        }
        return ""
    }

    private static func isLogC4(_ arri: String) -> Bool {
        arri.contains("logc4") || arri.contains("awg4") || arri.contains("wide gamut 4")
    }

    private static func isLogC3(_ arri: String) -> Bool {
        arri.contains("logc3") && !arri.contains("logc4")
    }

    private static func veniceHit(_ parts: [String]) -> Bool {
        parts.joined(separator: " ").lowercased().contains("venice")
    }

    /// ARRI MXF camera metadata. Not QuickTime nclc. LogC4 before LogC3.
    private static func readARRIColorSpace(url: URL) -> String? {
        guard let meta = loadSidecarJSON(url: url) else { return nil }
        let arri = metaString(meta, "arri_mxf_color_space", fallback: "arri_color_space")
        if arri.isEmpty { return nil }
        if isLogC4(arri) || isLogC3(arri) { return arri }
        return nil
    }

    /// Sony Acquisition. S-Gamut3.Cine only when the gamut string says cine.
    private static func readSonyAcquisition(url: URL) -> DetectionResult? {
        guard let meta = loadSidecarJSON(url: url) else { return nil }
        let sony = metaString(meta, "sony_acquisition_gamut", fallback: "sony_color_gamut")
        let sonyCurve = metaString(meta, "sony_acquisition_gamma")
        let venice = veniceHit([
            sony,
            sonyCurve,
            metaString(meta, "sony_camera_model"),
            metaString(meta, "camera_model"),
            metaString(meta, "sony_model"),
        ])
        let curveKnown = sonyCurve.contains("s-log3") || sonyCurve.contains("slog3") || sony.contains("s-log3")
        if !curveKnown { return nil }
        if sony.contains("cine") {
            return locked(
                venice ? .sonySLog3SGamut3CineVenice : .sonySLog3SGamut3Cine,
                source: .metadata,
                note: venice ? "元数据 Sony（Venice）" : "元数据 Sony"
            )
        }
        if sony.contains("s-gamut3") || sony.contains("sgamut3") {
            return locked(
                venice ? .sonySLog3SGamut3Venice : .sonySLog3SGamut3,
                source: .metadata,
                note: venice ? "元数据 Sony（Venice）" : "元数据 Sony"
            )
        }
        return DetectionResult(
            idt: nil,
            curve: "S-Log3",
            gamut: nil,
            source: .metadata,
            needsUserPicker: true,
            note: venice
                ? "S-Log3 没有色域，检测到 Venice，先选择成对 IDT"
                : "S-Log3 没有色域，先选择成对 IDT",
            veniceDetected: venice
        )
    }

    /// Canon vendor metadata. C-Log2 / C-Log3 without gamut stay pending.
    private static func readCanonVendor(url: URL) -> DetectionResult? {
        guard let meta = loadSidecarJSON(url: url) else { return nil }
        let canon = metaString(meta, "canon_vendor_gamma", fallback: "canon_log")
        let gamut = metaString(meta, "canon_vendor_gamut", fallback: "canon_gamut")
        if canon.contains("c-log2") || canon.contains("clog2") {
            if gamut.contains("cinema") || gamut.contains("cgamut") || gamut.contains("c-gamut") {
                return locked(.canonCLog2CGamut, source: .metadata, note: "元数据 C-Log2 + Cinema Gamut")
            }
            if gamut.contains("2020") || gamut.contains("bt.2020") || gamut.contains("bt2020") {
                return locked(.canonCLog2BT2020, source: .metadata, note: "元数据 C-Log2 + BT.2020")
            }
            return DetectionResult(
                idt: nil,
                curve: "C-Log2",
                gamut: nil,
                source: .metadata,
                needsUserPicker: true,
                note: "C-Log2 没有色域，先选择成对 IDT"
            )
        }
        if canon.contains("c-log3") || canon.contains("clog3") {
            if gamut.contains("cinema") || gamut.contains("cgamut") || gamut.contains("c-gamut") {
                return locked(.canonCLog3CGamut, source: .metadata, note: "元数据 C-Log3 + Cinema Gamut")
            }
            if gamut.contains("2020") || gamut.contains("bt.2020") || gamut.contains("bt2020") {
                return locked(.canonCLog3BT2020, source: .metadata, note: "元数据 C-Log3 + BT.2020")
            }
            return DetectionResult(
                idt: nil,
                curve: "C-Log3",
                gamut: nil,
                source: .metadata,
                needsUserPicker: true,
                note: "C-Log3 没有色域，先选择成对 IDT"
            )
        }
        return nil
    }

    /// RED color keys in the JSON sidecar. A bare .rmd file is not this path.
    private static func readREDSidecarColor(url: URL) -> DetectionResult? {
        guard let meta = loadSidecarJSON(url: url) else { return nil }
        let rmd = metaString(meta, "red_rmd_colorspace", fallback: "red_color_space")
        let gamma = metaString(meta, "red_rmd_gamma")
        let parsed = rmd.contains("log3g10") || gamma.contains("log3g10") || rmd.contains("redwidegamut")
        if !parsed { return nil }
        return locked(.redLog3G10RWG, source: .metadata, note: "元数据 RED RMD")
    }

    private static func readOtherVendorSidecar(url: URL) -> DetectionResult? {
        guard let meta = loadSidecarJSON(url: url) else { return nil }
        let fuji = metaString(meta, "fuji_film_simulation", fallback: "fuji_log")
        if fuji.contains("f-log2") || fuji.contains("flog2") {
            return locked(.fujiFLog2BT2020, source: .metadata, note: "元数据 Fujifilm")
        }
        let nikon = metaString(meta, "nikon_gamma", fallback: "nikon_nlog")
        if nikon.contains("n-log") || nikon.contains("nlog") {
            return locked(.nikonNLogBT2020, source: .metadata, note: "元数据 Nikon")
        }
        let pana = metaString(meta, "panasonic_gamma")
        if pana.contains("v-log") || pana.contains("vlog") {
            return locked(.panasonicVLogVGamut, source: .metadata, note: "元数据 Panasonic")
        }
        let apple = metaString(meta, "apple_log", fallback: "apple_gamma")
        if apple.contains("apple log 2") || apple.contains("applelog2") {
            return locked(.appleLog2AWG, source: .metadata, note: "元数据 Apple Log 2 + Apple Wide Gamut")
        }
        if apple.contains("apple log") || apple.contains("applelog") {
            return locked(.appleLogBT2020, source: .metadata, note: "元数据 Apple Log")
        }
        let dji = metaString(meta, "dji_gamma", fallback: "dji_log")
        if dji.contains("d-log m") || dji.contains("dlog m") || dji.contains("dlogm") || dji.contains("d-logm") {
            return DetectionResult(
                idt: nil,
                curve: nil,
                gamut: nil,
                source: .metadata,
                needsUserPicker: true,
                note: "D-Log M 暂不支持，请用 D-Log + D-Gamut"
            )
        }
        if dji.contains("d-log") || dji.contains("dlog") {
            return locked(.djiDLogDGamut, source: .metadata, note: "元数据 D-Log")
        }
        return nil
    }

    /// RED RMD sidecar / header. Presence alone is not a lock — parse later.
    /// Do not silently assume Log3G10 + REDWideGamutRGB from a bare .rmd file.
    private static func readREDRMD(url: URL) -> DetectionResult? {
        let sidecar = url.deletingPathExtension().appendingPathExtension("rmd")
        if FileManager.default.fileExists(atPath: sidecar.path) {
            return DetectionResult(
                idt: nil,
                curve: "Log3G10",
                gamut: nil,
                source: .metadata,
                needsUserPicker: true,
                note: "检测到 RED RMD，先选择成对 IDT"
            )
        }
        return nil
    }
}
