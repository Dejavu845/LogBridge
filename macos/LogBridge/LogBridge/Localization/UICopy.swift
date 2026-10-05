// Canonical Chinese UI copy. Keep in sync with locale/ui_zh.json.
// Prefer editing the JSON and this enum together; do not re-lock
// every phrase into pytest source assertions.
import Foundation

enum UICopy {
    static let PROCESS_BUTTON = "处理已锁定片段"
    static let HONEST_PROXY_NOTE = "整段代理，代理精度"
    static let REASON_PICK_LOG_GAMUT = "先选择 Log 与色域"
    static let REASON_PICK_PAIRED_IDT = "先选择成对 IDT"
    static let SKIPPED_BUCKET = "待选跳过"
    static let FAILED_BUCKET = "失败原因"
    static let CANCEL_BUTTON = "取消"
    static let CANCELLED_NOTE = "已取消"
    static let WRITTEN_CHIP = "已写出代理"
    static let WRITE_FAILED_CHIP = "写出失败"
    static let DECODE_FAILED_CHIP = "解码失败"
    static let FRAME_MISMATCH_CHIP = "帧数对不上"
    static let DISK_SHORT_STATUS = "磁盘空间不足，未写出"
    static let ADVANCED_DISCLOSURE = "高级"
    static let REVEAL_IN_FINDER = "在 Finder 中显示"
    static let EMPTY_STATE_STEP_1 = "把混源文件夹拖进来"
    static let EMPTY_STATE_STEP_2 = "每条选成对 Log 与色域"
    static let EMPTY_STATE_STEP_3 = "点处理已锁定片段。得到的是 EXR 图序列，不是视频。"
    static let PROCESS_BUTTON_HELP_UI = "写出的是图片序列（EXR），不是 mp4/mov"
    static let PROCESS_DELIVERABLE_NOTE_UI = "代理 EXR，不是视频。整段代理，代理精度。"
    static let FOLDER_PICKER_MESSAGE_UI = "每条素材一个 _ACES2065-1_proxy 夹，里面逐帧图片，给达芬奇用。整段代理，代理精度。未锁定的跳过（先选择 Log 与色域 / 先选择成对 IDT）。已实现（未验证）。"
    static let ADVANCED_EXPORT_HELP = "只处理已锁定片段。待选跳过。写出整段代理，代理精度 EXR，以及 cube 节点。不必全部锁定。"
    static let ADVANCED_DISCLOSURE_HELP = "节点与导出 ACEScct / EXR。展开状态会记住。整段代理，代理精度。"
    static let PROGRESS_STATUS_HELP = "按每一帧出一张图，不是一条视频"
    static let EMPTY_STATE_STEPS = "1 把混源文件夹拖进来  2 每条选成对 Log 与色域  3 点处理已锁定片段。得到的是 EXR 图序列，不是视频。"
    static let PROGRESS_PREFIX = "写出代理"
    static let MISSING_YCBCR_TAGS_CHIP_UI = "读不出片源色彩标签，没法写出"
}

