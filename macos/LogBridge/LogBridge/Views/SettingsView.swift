import SwiftUI

/// 设置页。中文。不写精准 / 一键还原 / 全自动校准。
struct SettingsView: View {
    @ObservedObject var settings: AppSettings
    @ObservedObject var session: SessionModel

    var body: some View {
        // Sections stay system grouped Form. Not 14pt inspector / process cards.
        Form {
            Section {
                Picker("默认预览", selection: Binding(
                    get: { settings.defaultPreviewODT },
                    set: { newValue in
                        settings.defaultPreviewODT = newValue
                        session.setODT(newValue)
                    }
                )) {
                    Text("Rec.709 预览·非成片").tag(ODTMode.rec709)
                    Text("Rec.2100 HLG 预览·非成片").tag(ODTMode.hlg)
                    Text("Rec.2100 PQ 预览·非成片").tag(ODTMode.pq)
                }
                Text("默认 Rec.709（角标预览·非成片）。不是成片，未与 HDR 匹配。导出仍是 ACEScct / EXR。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("预览窗下拖时间轴。轴按片源时长。默认落到片源帧率对应的那一帧；设置里指定了工作帧率就落到那个。读不到时长或帧率（又没指定）就不做轴，不猜帧率。静帧没有时间轴。命中缓存只重跑预览输出。预览·非成片。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } header: {
                Text("预览")
            }

            Section {
                Picker("工作帧率", selection: Binding(
                    get: { settings.frameRatePolicy },
                    set: { newValue in
                        settings.frameRatePolicy = newValue
                        session.applyFrameRateSettings()
                    }
                )) {
                    ForEach(FrameRatePolicy.allCases) { policy in
                        Text(policy.menuLabel).tag(policy)
                    }
                }
                if settings.frameRatePolicy == .user {
                    Picker("指定帧率", selection: Binding(
                        get: { settings.userFrameRate },
                        set: { newValue in
                            settings.userFrameRate = newValue
                            session.applyFrameRateSettings()
                        }
                    )) {
                        Text("— 先选择工作帧率 —").tag(Optional<NamedFrameRate>.none)
                        ForEach(NamedFrameRate.allCases) { rate in
                            Text(rate.menuLabel).tag(Optional(rate))
                        }
                    }
                }
                Text("默认只用片源帧率。导入读数、时间轴、预览落帧都按这个。读不到片源帧率就不做轴；写出核对也不做，不猜帧率。选「用户指定」并选定一个数之后，时间轴和预览用这个数。片源读不到帧率时，写出核对才用这个数。写出仍是片源一帧一张 EXR，不是转帧。指定不是检测。静帧没有帧率。预览·非成片。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } header: {
                Text("帧率")
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

            Text("已实现（未验证）。不写精准 / 一键还原 / 全自动校准。")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .formStyle(.grouped)
        .scrollContentBackground(.hidden)
        .background(LBChrome.controlMaterial)
        .tint(LBChrome.locked)
        .preferredColorScheme(.dark)
        .frame(minWidth: 420, minHeight: 420)
        .navigationTitle("设置")
    }
}
