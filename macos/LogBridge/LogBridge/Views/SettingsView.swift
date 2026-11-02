import SwiftUI

/// 全局偏好（⌘,）。改完即写入，没有保存或取消。
/// 本片的成对 IDT、曝光、白平衡在右侧检查器。
/// 不写已经测准 / 自动还原 / 全自动校准。
struct SettingsView: View {
    @ObservedObject var settings: AppSettings
    @ObservedObject var session: SessionModel

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("改完即生效。这里只记全局偏好。本片的成对 IDT、曝光和白平衡在主窗口右侧检查器，不在这里。")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }

                Section {
                    Picker("外观", selection: $settings.windowAppearance) {
                        ForEach(WindowAppearance.allCases) { mode in
                            Text(mode.labelZH).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)
                    Text("只改窗口明暗。预览画面仍是深色底，角标仍是仅预览。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } header: {
                    Text("外观")
                }

                Section {
                    Picker("默认预览", selection: Binding(
                        get: { settings.defaultPreviewODT },
                        set: { newValue in
                            settings.defaultPreviewODT = newValue
                            session.setODT(newValue)
                        }
                    )) {
                        Text("Rec.709 仅预览").tag(ODTMode.rec709)
                        Text("Rec.2100 HLG 仅预览").tag(ODTMode.hlg)
                        Text("Rec.2100 PQ 仅预览").tag(ODTMode.pq)
                    }
                    Text("默认 Rec.709（角标仅预览）。只作预览，未与 HDR 匹配。默认写出 ProRes；EXR 在高级选项。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("这是全局默认，当前预览会一起换。主窗口监视器上的「这次预览」只改当前这次，不改这里的默认，也不改写出。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } header: {
                    Text("预览")
                }

                Section {
                    Picker("默认写出格式", selection: $settings.exportFormat) {
                        ForEach(ExportFormat.allCases) { fmt in
                            Text(fmt.labelZH).tag(fmt)
                        }
                    }
                    .pickerStyle(.radioGroup)
                    Text("和主窗口「高级」里的写出格式是同一项，会记住。写出本身用预览下方的按钮，不在这里开始。整段代理，代理精度。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } header: {
                    Text("写出")
                }

                Section {
                    Toggle("导入后提示估计白平衡", isOn: $settings.promptEstimateWBOnImport)
                    Text("默认关。打开后只提示「白平衡（估计）」，不会自动写入白平衡，不猜 5600。确认后才写。灰卡覆盖估计。不是校准。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } header: {
                    Text("白平衡")
                }

                Section {
                    Toggle("未锁 IDT 挡住处理", isOn: .constant(settings.blockUnlockedIDT))
                        .disabled(true)
                    Text("不能关。「处理已锁定片段」只在已锁定条数 > 0 时出现。未锁定的片段跳过（先选择 Log 与色域 / 先选择成对 IDT），不猜 IDT。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } header: {
                    Text("处理")
                }

                Text("已实现（未验证）。不写已经测准 / 自动还原 / 全自动校准。")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .formStyle(.grouped)
            .navigationTitle("设置")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("关闭") { session.showSettings = false }
                }
            }
        }
        .frame(minWidth: 560, minHeight: 560)
    }
}
