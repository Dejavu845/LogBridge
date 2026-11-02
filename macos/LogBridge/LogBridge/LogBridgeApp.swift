import SwiftUI

/// LogBridge — local grade and delivery. Single window, not an editor.
/// Serial graph: IDT → exposure → WB → Off / Rec.709 preview / Rec.2100 HLG / PQ.
/// Not a general node editor. IDTs are implemented (unverified) until golden samples.

/// The window's session, published for menu commands.
/// Sidebar buttons call the same `showImporter` / `showSettings` flags.
/// A focused-scene value keeps working when that sidebar is not in the tree,
/// and still targets only the focused window.
struct SessionFocus: Hashable {
    weak var session: SessionModel?

    static func == (lhs: SessionFocus, rhs: SessionFocus) -> Bool {
        lhs.session === rhs.session
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(session.map { ObjectIdentifier($0) })
    }
}

private struct LogBridgeSessionKey: FocusedValueKey {
    typealias Value = SessionFocus
}

extension FocusedValues {
    var logBridgeSession: SessionFocus? {
        get { self[LogBridgeSessionKey.self] }
        set { self[LogBridgeSessionKey.self] = newValue }
    }
}

@main
struct LogBridgeApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .defaultSize(width: 1440, height: 900)
        .commands {
            LogBridgeCommands()
        }
    }
}

/// App menu, not the sidebar. ⌘, stays on this command (no Settings scene),
/// so the existing settings sheet is the only presentation.
private struct LogBridgeCommands: Commands {
    @FocusedValue(\.logBridgeSession) private var sessionFocus

    var body: some Commands {
        CommandGroup(replacing: .newItem) {
            Button("添加…") {
                sessionFocus?.session?.presentImporter()
            }
            .keyboardShortcut("o")
            .disabled(sessionFocus?.session?.openingExportFolder == true
                      || sessionFocus?.session?.showImporter == true)
            Button("从列表拿掉（不删文件）") {
                sessionFocus?.session?.removeSelectedClipFromSession(respectTextInput: false)
            }
            .disabled(sessionFocus?.session?.canRemoveSelectedClip != true)
        }
        CommandGroup(replacing: .appSettings) {
            Button("设置…") {
                sessionFocus?.session?.presentSettings()
            }
            .keyboardShortcut(",")
            .disabled(sessionFocus?.session?.openingExportFolder == true
                      || sessionFocus?.session?.showImporter == true)
        }
        CommandGroup(after: .newItem) {
            Button("写出…") {
                guard let session = sessionFocus?.session,
                      session.showsProcessLockedButton,
                      !session.isWritingDeliverables,
                      !session.openingExportFolder,
                      !session.showImporter else { return }
                session.presentDeliverSheet()
            }
            .keyboardShortcut("e")
            .disabled(sessionFocus?.session?.showsProcessLockedButton != true
                      || sessionFocus?.session?.isWritingDeliverables == true
                      || sessionFocus?.session?.openingExportFolder == true
                      || sessionFocus?.session?.showImporter == true)
        }
        CommandMenu("调色") {
            Button("跟当前这一步") {
                sessionFocus?.session?.followLoopWithReturn()
            }
            .disabled(sessionFocus?.session?.canFollowLoopWithReturn != true)
            .help("没有素材时和「添加…」一样。待选时滚到成对 IDT，不替你选。已锁定时滚到曝光，不改数字。回车是同一套，菜单不标快捷键。查找框、手填和跳到仍吃回车。不打开写出说明。")
            Divider()
            Button("曝光 +0.10") {
                sessionFocus?.session?.nudgeExposureStops(0.10)
            }
            .keyboardShortcut("=", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeExposure != true)
            Button("曝光 −0.10") {
                sessionFocus?.session?.nudgeExposureStops(-0.10)
            }
            .keyboardShortcut("-", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeExposure != true)
            Button("曝光归零") {
                sessionFocus?.session?.resetExposureStops()
            }
            .keyboardShortcut("0", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeExposure != true)
            Divider()
            Button("色温 +100") {
                sessionFocus?.session?.nudgeWBCCT(100)
            }
            .keyboardShortcut("]", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWB != true)
            Button("色温 −100") {
                sessionFocus?.session?.nudgeWBCCT(-100)
            }
            .keyboardShortcut("[", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWB != true)
            Button("回到机内") {
                sessionFocus?.session?.restoreAsShotWB()
            }
            .keyboardShortcut("9", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canRestoreAsShotWB != true)
            Divider()
            Button("绿品 +1") {
                sessionFocus?.session?.nudgeWBTint(1)
            }
            .keyboardShortcut(".", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWBTint != true)
            Button("绿品 −1") {
                sessionFocus?.session?.nudgeWBTint(-1)
            }
            .keyboardShortcut(";", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWBTint != true)
            Button("绿品归零") {
                sessionFocus?.session?.resetWBTint()
            }
            .keyboardShortcut("'", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canNudgeWBTint != true)
            Divider()
            Button("下一条待选") {
                sessionFocus?.session?.selectNextPendingFromMenu()
            }
            .keyboardShortcut("]", modifiers: [.command])
            .disabled(sessionFocus?.session?.canSelectNextPending != true)
            Button("这一对给下一条待选") {
                sessionFocus?.session?.applyLockedPairToNextPending()
            }
            .keyboardShortcut("]", modifiers: [.command, .shift])
            .disabled(sessionFocus?.session?.canApplyLockedPairToNextPending != true)
            Button("这一对给后面连续的待选") {
                sessionFocus?.session?.applyLockedPairToFollowingPending()
            }
            .keyboardShortcut("]", modifiers: [.command, .control])
            .disabled(sessionFocus?.session?.canApplyLockedPairToFollowingPending != true)
            .help("从下一条起，自己的列表里已有这一对就写上，并继续。碰到没有这一对的就停在那一条，不替它选，也不再往后。不往回写。不改曝光和白平衡。⌃⌘] 是同一套。")
            Divider()
            Button("锁定第 1 对") {
                sessionFocus?.session?.lockShortListPair(at: 1)
            }
            .disabled(sessionFocus?.session?.canLockShortListPair(at: 1) != true)
            Button("锁定第 2 对") {
                sessionFocus?.session?.lockShortListPair(at: 2)
            }
            .disabled(sessionFocus?.session?.canLockShortListPair(at: 2) != true)
            Button("锁定第 3 对") {
                sessionFocus?.session?.lockShortListPair(at: 3)
            }
            .disabled(sessionFocus?.session?.canLockShortListPair(at: 3) != true)
            Button("锁定第 4 对") {
                sessionFocus?.session?.lockShortListPair(at: 4)
            }
            .disabled(sessionFocus?.session?.canLockShortListPair(at: 4) != true)
            Divider()
            Button("回到开头") {
                sessionFocus?.session?.jumpPreviewToStart()
            }
            .disabled(sessionFocus?.session?.canJumpPreviewToStart != true)
            Button("退 1 秒") {
                sessionFocus?.session?.stepPreviewBySecond(-1)
            }
            .disabled(sessionFocus?.session?.canStepPreviewSecondBackward != true)
            Button("上一帧") {
                sessionFocus?.session?.stepPreviewFrame(-1)
            }
            .disabled(sessionFocus?.session?.canStepPreviewBackward != true)
            Button("下一帧") {
                sessionFocus?.session?.stepPreviewFrame(1)
            }
            .disabled(sessionFocus?.session?.canStepPreviewForward != true)
            Button("进 1 秒") {
                sessionFocus?.session?.stepPreviewBySecond(1)
            }
            .disabled(sessionFocus?.session?.canStepPreviewSecondForward != true)
            Button("到结尾") {
                sessionFocus?.session?.jumpPreviewToEnd()
            }
            .disabled(sessionFocus?.session?.canJumpPreviewToEnd != true)
            Button(sessionFocus?.session?.isPreviewPlaying == true ? "暂停预览" : "播放预览") {
                sessionFocus?.session?.togglePreviewPlayback()
            }
            .disabled(sessionFocus?.session?.canTogglePreviewPlayback != true)
            Button(sessionFocus?.session?.isPreviewPlaying == true && sessionFocus?.session?.previewPlaysBackward == true ? "暂停倒放" : "倒放预览") {
                sessionFocus?.session?.playPreviewBackward()
            }
            .disabled(sessionFocus?.session?.canTogglePreviewReverse != true)
            Button(sessionFocus?.session?.previewLoops == true ? "关掉循环" : "循环播放") {
                sessionFocus?.session?.togglePreviewLoop()
            }
            .keyboardShortcut("l", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canTogglePreviewLoop != true)
            Divider()
            Button(sessionFocus?.session?.previewShowsGradeBefore == true ? "回到调色" : "看调色前") {
                sessionFocus?.session?.togglePreviewGradeBefore()
            }
            .keyboardShortcut("\\", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canTogglePreviewGradeBefore != true)
            Button(sessionFocus?.session?.monitorLayout == .compare ? "关掉对照" : "对照调色前后") {
                sessionFocus?.session?.togglePreviewCompare()
            }
            .keyboardShortcut("/", modifiers: [.command, .option])
            .disabled(sessionFocus?.session?.canTogglePreviewCompare != true)
            Button("分屏与预览") {
                sessionFocus?.session?.toggleSplitAndGrade()
            }
            .disabled(sessionFocus?.session?.canToggleSplitAndGrade != true)
            .help("在分屏和预览之间换。V 是同一套，菜单不标快捷键。正在看源或对照时不起作用。查找框、手填和跳到仍吃 V。不改这一套曝光和白平衡，不改预览帧，也不参与写出。")
            Divider()
            Button("撤销这一套") {
                sessionFocus?.session?.undoSharedGrade()
            }
            .disabled(sessionFocus?.session?.canUndoSharedGrade != true)
            Button("重做这一套") {
                sessionFocus?.session?.redoSharedGrade()
            }
            .disabled(sessionFocus?.session?.canRedoSharedGrade != true)
        }
    }
}
