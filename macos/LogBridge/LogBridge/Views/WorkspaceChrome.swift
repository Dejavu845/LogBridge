import SwiftUI

/// Team B workspace chrome. Product copy stays locked Chinese.
/// No extra process path. No 一键还原. No ultraThinMaterial in ContentView.

enum WorkspaceStep: Int, CaseIterable {
    case importFolder = 1
    case pickPairs = 2
    case writeProxy = 3

    var title: String {
        switch self {
        case .importFolder: return "导入"
        case .pickPairs: return "选对"
        case .writeProxy: return "写出代理"
        }
    }

    var detail: String {
        switch self {
        case .importFolder: return "把混源文件夹拖进来"
        case .pickPairs: return "每条选成对 Log 与色域"
        case .writeProxy: return "点处理已锁定片段"
        }
    }
}

enum ClipSidebarFilter: String, CaseIterable, Identifiable {
    case all
    case pending
    case locked

    var id: String { rawValue }

    var title: String {
        switch self {
        case .all: return "全部"
        case .pending: return "待选"
        case .locked: return "已锁定"
        }
    }
}

/// Top command strip: where you are in the three steps, plus preview output.
/// Preview output used to live only in 设置 — that hid a daily control.
struct WorkspaceHeader: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        HStack(alignment: .center, spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                Text("LogBridge")
                    .font(.headline)
                Text("已实现（未验证）")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .frame(minWidth: 88, alignment: .leading)

            WorkspaceStepStrip(current: session.workspaceStep)

            Spacer(minLength: 12)

            VStack(alignment: .trailing, spacing: 4) {
                Text("预览输出")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Picker("预览输出", selection: Binding(
                    get: { session.graph.odt },
                    set: { session.setODT($0) }
                )) {
                    ForEach(ODTMode.allCases) { mode in
                        Text(mode.title).tag(mode)
                    }
                }
                .labelsHidden()
                .pickerStyle(.menu)
                .frame(maxWidth: 220)
                .help("预览·非成片")
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.primary.opacity(0.04))
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color.primary.opacity(0.08))
                .frame(height: 1)
        }
    }
}

struct WorkspaceStepStrip: View {
    let current: Int

    var body: some View {
        HStack(spacing: 0) {
            ForEach(WorkspaceStep.allCases, id: \.rawValue) { step in
                if step != .importFolder {
                    Rectangle()
                        .fill(step.rawValue <= current ? Color.accentColor.opacity(0.55) : Color.primary.opacity(0.12))
                        .frame(width: 28, height: 2)
                        .padding(.horizontal, 4)
                }
                WorkspaceStepChip(step: step, current: current)
            }
        }
    }
}

private struct WorkspaceStepChip: View {
    let step: WorkspaceStep
    let current: Int

    var body: some View {
        let active = step.rawValue == current
        let done = step.rawValue < current
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
                Text("\(step.rawValue)")
                    .font(.caption2.monospacedDigit().weight(.bold))
                    .frame(width: 18, height: 18)
                    .background(active || done ? Color.accentColor : Color.primary.opacity(0.12))
                    .foregroundStyle(active || done ? Color.white : Color.secondary)
                    .clipShape(Circle())
                Text(step.title)
                    .font(.subheadline.weight(active ? .semibold : .regular))
                    .foregroundStyle(active ? Color.primary : Color.secondary)
            }
            Text(step.detail)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(active ? Color.accentColor.opacity(0.10) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

/// First-run canvas. Same importer as 「添加…」. No second process path.
struct EmptyPreviewStage: View {
    @ObservedObject var session: SessionModel

    var body: some View {
        VStack(spacing: 22) {
            Image(systemName: "film.stack")
                .font(.system(size: 42, weight: .regular))
                .foregroundStyle(Color.accentColor)
            VStack(spacing: 8) {
                Text("把混源文件夹拖进来")
                    .font(.title2.weight(.semibold))
                Text("或点这里选文件夹。得到的是 EXR 图序列，不是视频。")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            HStack(alignment: .top, spacing: 16) {
                EmptyStepCard(index: 1, title: "导入", detail: "把混源文件夹拖进来")
                EmptyStepCard(index: 2, title: "选对", detail: "每条选成对 Log 与色域")
                EmptyStepCard(index: 3, title: "写出代理", detail: "点处理已锁定片段。得到的是 EXR 图序列，不是视频。")
            }
            .frame(maxWidth: 720)
            Text("已实现（未验证）。整段代理，不是全精度成片。")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(36)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(session.dropTargeted ? Color.accentColor.opacity(0.10) : Color.primary.opacity(0.03))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(
                    style: StrokeStyle(lineWidth: session.dropTargeted ? 2 : 1, dash: [7])
                )
                .foregroundStyle(session.dropTargeted ? Color.accentColor : Color.secondary.opacity(0.35))
        )
        .padding(18)
        .contentShape(Rectangle())
        .onTapGesture {
            session.showImporter = true
        }
    }
}

private struct EmptyStepCard: View {
    let index: Int
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("\(index)")
                .font(.caption.monospacedDigit().weight(.bold))
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.accentColor.opacity(0.16))
                .foregroundStyle(Color.accentColor)
                .clipShape(Capsule())
            Text(title)
                .font(.headline)
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

struct InspectorCard<Content: View>: View {
    let title: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.weight(.semibold))
            content()
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
