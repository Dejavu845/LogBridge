import Foundation

/// Locked-batch export format. Default is ProRes 422 HQ (Rec.709 preview).
/// EXR ACES2065-1 sequences stay an advanced option.
enum ExportFormat: String, CaseIterable, Identifiable {
    case prores422HQ = "prores_422_hq"
    case exrACES2065 = "exr_aces2065"

    var id: String { rawValue }

    static let `default`: ExportFormat = .prores422HQ

    var labelZH: String {
        switch self {
        case .prores422HQ: return "ProRes 422 HQ（Rec.709 预览）"
        case .exrACES2065: return "ACES2065-1 EXR 序列（高级）"
        }
    }

    /// Why 422 HQ (not 4444): hardware path on Apple Silicon, no alpha needed,
    /// smaller files, universally accepted in FCP / Premiere / Resolve.
    var pickerHelpZH: String {
        switch self {
        case .prores422HQ:
            return "默认。可直接拖进剪辑软件。整段代理，代理精度。"
        case .exrACES2065:
            return "高级。ACES2065-1 线性图序列，给达芬奇 / VFX。整段代理，代理精度。"
        }
    }
}
