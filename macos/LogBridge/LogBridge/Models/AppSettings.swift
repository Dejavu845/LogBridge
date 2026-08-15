import Foundation
import Combine

/// User-facing settings. Chinese copy. No color-number changes.
///
/// Defaults (调研):
///   - Preview ODT: Rec.709 (DIY OETF, 预览·非成片)
///   - Prompt estimate WB after import: off (on = prompt only, never write CAT)
///   - Block process when IDT unlocked: always on, not user-toggleable
final class AppSettings: ObservableObject {
    static let shared = AppSettings()

    private enum Key {
        static let defaultPreviewODT = "logbridge.defaultPreviewODT"
        static let promptEstimateWB = "logbridge.promptEstimateWBOnImport"
    }

    /// Settings default for the preview pane. Export stays ACEScct.
    @Published var defaultPreviewODT: ODTMode {
        didSet { UserDefaults.standard.set(defaultPreviewODT.rawValue, forKey: Key.defaultPreviewODT) }
    }

    /// Off by default. When on, import only *prompts* 白平衡（估计）. Never writes CAT. Never 5600.
    @Published var promptEstimateWBOnImport: Bool {
        didSet { UserDefaults.standard.set(promptEstimateWBOnImport, forKey: Key.promptEstimateWB) }
    }

    /// Cannot be turned off. Pending IDT always blocks 处理已锁定片段.
    let blockUnlockedIDT: Bool = true

    private init() {
        let raw = UserDefaults.standard.string(forKey: Key.defaultPreviewODT) ?? ODTMode.rec709.rawValue
        defaultPreviewODT = ODTMode(rawValue: raw) ?? .rec709
        promptEstimateWBOnImport = UserDefaults.standard.bool(forKey: Key.promptEstimateWB)
    }
}
