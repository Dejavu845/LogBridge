import Foundation
import SwiftUI
import Combine

/// User-facing settings. Chinese copy. No color-number changes.
///
/// Defaults (调研):
///   - Preview ODT: Rec.709 (DIY OETF, 仅预览)
///   - Prompt estimate WB after import: off (on = prompt only, never write CAT)
///   - Block process when IDT unlocked: always on, not user-toggleable
final class AppSettings: ObservableObject {
    static let shared = AppSettings()

    private enum Key {
        static let defaultPreviewODT = "logbridge.defaultPreviewODT"
        static let promptEstimateWB = "logbridge.promptEstimateWBOnImport"
        static let lastExportDirectory = "logbridge.lastExportDirectory"
        static let lastImportDirectory = "logbridge.lastImportDirectory"
        static let advancedPanelExpanded = "logbridge.advancedPanelExpanded"
        static let exportFormat = "logbridge.exportFormat"
        static let windowAppearance = "logbridge.windowAppearance"
    }

    /// Settings default for the preview pane. Export stays ACEScct.
    @Published var defaultPreviewODT: ODTMode {
        didSet { UserDefaults.standard.set(defaultPreviewODT.rawValue, forKey: Key.defaultPreviewODT) }
    }

    /// Off by default. When on, import only *prompts* 白平衡（估计）. Never writes CAT. Never 5600.
    @Published var promptEstimateWBOnImport: Bool {
        didSet { UserDefaults.standard.set(promptEstimateWBOnImport, forKey: Key.promptEstimateWB) }
    }

    /// 「高级」DisclosureGroup. Default collapsed; survives relaunch via UserDefaults.
    @Published var advancedPanelExpanded: Bool {
        didSet { UserDefaults.standard.set(advancedPanelExpanded, forKey: Key.advancedPanelExpanded) }
    }

    /// Default ProRes 422 HQ. EXR is the advanced option.
    @Published var exportFormat: ExportFormat {
        didSet { UserDefaults.standard.set(exportFormat.rawValue, forKey: Key.exportFormat) }
    }

    /// Chrome only. Does not change color math, preview tags, or the write path.
    @Published var windowAppearance: WindowAppearance {
        didSet { UserDefaults.standard.set(windowAppearance.rawValue, forKey: Key.windowAppearance) }
    }

    /// Cannot be turned off. Pending IDT always blocks 处理已锁定片段.
    let blockUnlockedIDT: Bool = true

    /// Last folder picked for 处理已锁定片段. Next NSOpenPanel starts here.
    /// Parent dest only — never a deleted half `{stem}_ACES2065-1_proxy` folder.
    @Published var lastExportDirectoryPath: String? {
        didSet {
            if let path = lastExportDirectoryPath, !path.isEmpty {
                UserDefaults.standard.set(path, forKey: Key.lastExportDirectory)
            } else {
                UserDefaults.standard.removeObject(forKey: Key.lastExportDirectory)
            }
        }
    }

    /// Existing directory, or nil if the remembered path is gone.
    var lastExportDirectoryURL: URL? {
        guard let path = lastExportDirectoryPath, !path.isEmpty else { return nil }
        let url = URL(fileURLWithPath: path, isDirectory: true)
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue else {
            return nil
        }
        return url
    }

    func rememberExportDirectory(_ url: URL) {
        lastExportDirectoryPath = url.path
    }

    /// Last folder used by 添加… or a drop. The next add panel starts here.
    /// Not a preference row. ⌘, does not edit it.
    @Published var lastImportDirectoryPath: String? {
        didSet {
            if let path = lastImportDirectoryPath, !path.isEmpty {
                UserDefaults.standard.set(path, forKey: Key.lastImportDirectory)
            } else {
                UserDefaults.standard.removeObject(forKey: Key.lastImportDirectory)
            }
        }
    }

    /// Existing directory, or nil if the remembered path is gone.
    var lastImportDirectoryURL: URL? {
        guard let path = lastImportDirectoryPath, !path.isEmpty else { return nil }
        let url = URL(fileURLWithPath: path, isDirectory: true)
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue else {
            return nil
        }
        return url
    }

    func rememberImportDirectory(_ url: URL) {
        lastImportDirectoryPath = url.path
    }

    private init() {
        let raw = UserDefaults.standard.string(forKey: Key.defaultPreviewODT) ?? ODTMode.rec709.rawValue
        defaultPreviewODT = ODTMode(rawValue: raw) ?? .rec709
        promptEstimateWBOnImport = UserDefaults.standard.bool(forKey: Key.promptEstimateWB)
        advancedPanelExpanded = UserDefaults.standard.bool(forKey: Key.advancedPanelExpanded)
        let fmtRaw = UserDefaults.standard.string(forKey: Key.exportFormat) ?? ExportFormat.default.rawValue
        exportFormat = ExportFormat(rawValue: fmtRaw) ?? .default
        let appearanceRaw = UserDefaults.standard.string(forKey: Key.windowAppearance) ?? WindowAppearance.system.rawValue
        windowAppearance = WindowAppearance(rawValue: appearanceRaw) ?? .system
        lastExportDirectoryPath = UserDefaults.standard.string(forKey: Key.lastExportDirectory)
        lastImportDirectoryPath = UserDefaults.standard.string(forKey: Key.lastImportDirectory)
    }
}

/// Window chrome only. Preview panes stay on their own color tags.
enum WindowAppearance: String, CaseIterable, Identifiable {
    case system
    case dark
    case light

    var id: String { rawValue }

    var labelZH: String {
        switch self {
        case .system: return "跟随系统"
        case .dark: return "深色"
        case .light: return "浅色"
        }
    }

    var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .dark: return .dark
        case .light: return .light
        }
    }
}
