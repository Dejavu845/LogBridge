import Foundation
import simd

/// DaVinci Resolve export: a real bypassable WB node, not a prose sidecar.
///
/// Serial graph on an ACEScct timeline (ACES2065-1 interchange):
///   1. IDT  — camera log → ACES2065-1 → ACEScct (`.cube` and/or ACES IDT / CST)
///   2. WB   — scene-linear Bradford/CAT02 (CCT + tint) in ACEScg. Own LUT / CDL / DCTL.
///             Bypass this node → IDT → ACEScct → optional Rec.709 ODT.
///   3. ODT  — Rec.709 (later node, not the only deliverable)
///
/// Export ACEScct or ACES2065-1 EXR / ACES workflow. Do not bake DWG.
/// WB is never baked into the IDT or ODT cubes. Status: implemented (unverified).
enum ResolveExporter {
    static let lutSize = 17

    static func exportNote(clips: [Clip], includeWBNode: Bool, cct: Double, tint: Double) -> String {
        var lines: [String] = []
        lines.append("LogBridge M1 Resolve export (implemented, unverified)")
        lines.append("Working space: ACEScct (ACES2065-1 interchange). Do not bake DWG.")
        lines.append("WB node: \(includeWBNode ? "ON (scene-linear Bradford CAT, \(Int(cct)) K, tint \(tint))" : "present, bypassed by default")")
        lines.append("ODT: Rec.709 is a separate output, not the only deliverable.")
        lines.append("Files: graph.xml, graph.dot, 01_IDT_*.cube, 02_WB.{cube,cdl,ccc,dctl}, 03_ODT_Rec709.cube, README_RESOLVE.md")
        lines.append("Bypass WB in Resolve: disable serial node 2 (or DCTL Bypass WB). Remaining graph is IDT → ACEScct → optional Rec.709 ODT.")
        lines.append("Clips:")
        for clip in clips {
            let name = clip.idt?.ocioName ?? clip.lockedPairLabel
            lines.append("  - \(clip.url.lastPathComponent): \(name) [\(clip.verificationBadge)]")
        }
        return lines.joined(separator: "\n")
    }

    /// Write a Resolve-importable node graph into `directory`.
    @discardableResult
    static func export(
        to directory: URL,
        clips: [Clip],
        includeWBNode: Bool,
        cct: Double,
        tint: Double,
        lutSize: Int = lutSize,
        odtEnabled: Bool = true
    ) throws -> [URL] {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let idts = uniqueImplementedIDTs(clips)
        var written: [URL] = []

        func write(_ name: String, _ body: String) throws {
            let url = directory.appendingPathComponent(name)
            try body.write(to: url, atomically: true, encoding: .utf8)
            written.append(url)
        }

        try write("README_RESOLVE.md", readme(idts: idts, cct: cct, tint: tint, includeWB: includeWBNode))
        try write("graph.xml", graphXML(idts: idts, cct: cct, tint: tint, includeWB: includeWBNode, odtEnabled: odtEnabled))
        try write("graph.dot", graphDOT(idts: idts, cct: cct, tint: tint, includeWB: includeWBNode))
        try write("02_WB.cdl", cdlXML(cct: cct, tint: tint, collection: false))
        try write("02_WB.ccc", cdlXML(cct: cct, tint: tint, collection: true))
        try write("02_WB.dctl", dctl(cct: cct, tint: tint))
        try write("02_WB.cube", wbCube(cct: cct, tint: tint, size: lutSize))
        try write("03_ODT_Rec709.cube", odtCube(size: lutSize))
        for idt in idts {
            try write("01_IDT_\(idt.rawValue).cube", idtCube(idt: idt, size: lutSize))
        }
        return written
    }

    /// Placeholder on-disk export kept for callers that still pass a single URL.
    /// Writes the full graph into the file's parent directory (or creates a folder
    /// next to it). Prefer `export(to:clips:...)`.
    static func writeSidecar(to url: URL, includeWBNode: Bool) throws {
        let dir: URL
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue {
            dir = url
        } else {
            dir = url.deletingPathExtension()
        }
        _ = try export(
            to: dir,
            clips: [],
            includeWBNode: includeWBNode,
            cct: 6504,
            tint: 0
        )
    }

    private static func uniqueImplementedIDTs(_ clips: [Clip]) -> [IDT] {
        var seen = Set<IDT>()
        var out: [IDT] = []
        for clip in clips {
            guard let idt = clip.idt, !idt.isStub else { continue }
            if seen.insert(idt).inserted {
                out.append(idt)
            }
        }
        return out
    }

    // MARK: - Matrices (row-major, match ocio/matrices/*.spimtx)

    private static let ap1ToXYZ = simd_double3x3(rows: [
        SIMD3(0.662454181109, 0.134004206456, 0.156187687005),
        SIMD3(0.272228716781, 0.674081765811, 0.053689517408),
        SIMD3(-0.005574649490, 0.004060733529, 1.010339100313)
    ])

    private static let ap0ToAP1 = simd_double3x3(rows: [
        SIMD3(1.451439316146, -0.236510746894, -0.214928569252),
        SIMD3(-0.076553773396, 1.176229699834, -0.099675926438),
        SIMD3(0.008316148426, -0.006032449791, 0.997716301365)
    ])

    private static let ap1ToRec709 = simd_double3x3(rows: [
        SIMD3(1.705050992658, -0.621792120657, -0.083258872001),
        SIMD3(-0.130256417507, 1.140804736575, -0.010548319068),
        SIMD3(-0.024003356805, -0.128968976065, 1.152972332870)
    ])

    private static func cameraToAP0(_ idt: IDT) -> simd_double3x3? {
        switch idt {
        case .arriLogC4AWG4:
            return simd_double3x3(rows: [
                SIMD3(0.751244868485, 0.143007909499, 0.105747222016),
                SIMD3(0.001403392600, 1.005384442231, -0.006787834830),
                SIMD3(-0.000803152607, 0.003263851374, 0.997539301233)
            ])
        case .sonySLog3SGamut3, .sonySLog3SGamut3Venice:
            return simd_double3x3(rows: [
                SIMD3(0.753230840311, 0.141947913791, 0.104821245898),
                SIMD3(0.022234917350, 1.013293794080, -0.035528711431),
                SIMD3(-0.009600262790, 0.007505931314, 1.002094331476)
            ])
        case .sonySLog3SGamut3Cine, .sonySLog3SGamut3CineVenice:
            return simd_double3x3(rows: [
                SIMD3(0.639008308411, 0.270840678932, 0.090151012656),
                SIMD3(-0.003450727728, 1.085955398170, -0.082504670442),
                SIMD3(-0.030074188115, -0.021937342610, 1.052011530726)
            ])
        case .panasonicVLogVGamut:
            return simd_double3x3(rows: [
                SIMD3(0.724616704132, 0.166915288194, 0.108468007675),
                SIMD3(0.021390245413, 0.984908155703, -0.006298401116),
                SIMD3(-0.009235562871, -0.001056905639, 1.010292468510)
            ])
        case .fujiFLog2BT2020, .nikonNLogBT2020:
            return simd_double3x3(rows: [
                SIMD3(0.679085634707, 0.157700914643, 0.163213450650),
                SIMD3(0.046002003080, 0.859054673003, 0.094943323917),
                SIMD3(-0.000573943188, 0.028467768408, 0.972106174780)
            ])
        case .redLog3G10RWG:
            return simd_double3x3(rows: [
                SIMD3(0.785058804068, 0.083858756544, 0.131082439388),
                SIMD3(0.023173834845, 1.087897549192, -0.111071384038),
                SIMD3(-0.073760435368, -0.314590072290, 1.388350507658)
            ])
        default:
            return nil
        }
    }

    /// Scene-linear ACEScg (AP1) RGB CAT: XYZ_to_AP1 * Bradford_XYZ * AP1_to_XYZ.
    private static func wbRGBMatrix(cct: Double, tint: Double) -> simd_double3x3 {
        let cat = WhiteBalanceNode.catMatrix(cct: cct, tint: tint)
        return ap1ToXYZ.inverse * cat * ap1ToXYZ
    }

    // MARK: - Working-space / OETF

    private static let acescctLoS = 10.5402377416545
    private static let acescctLoO = 0.0729055341958355
    private static let acescctBreakLin = 0.0078125
    private static let acescctBreakLog = acescctLoS * acescctBreakLin + acescctLoO
    private static let rec709Beta = 0.018053968510807
    private static let rec709Alpha = 1.09929682680944

    private static func acescctEncode(_ lin: Double) -> Double {
        if lin <= acescctBreakLin {
            return acescctLoS * lin + acescctLoO
        }
        return (log2(max(lin, 1e-10)) + 9.72) / 17.52
    }

    private static func acescctDecode(_ enc: Double) -> Double {
        if enc <= acescctBreakLog {
            return (enc - acescctLoO) / acescctLoS
        }
        return pow(2.0, enc * 17.52 - 9.72)
    }

    private static func rec709OETF(_ lin: Double) -> Double {
        if lin < rec709Beta { return 4.5 * lin }
        return rec709Alpha * pow(max(lin, 0.0), 0.45) - (rec709Alpha - 1.0)
    }

    // MARK: - Log decode (0-1 buffers; N-Log expands to 10-bit codes)

    private static func decodeLog(_ x: Double, idt: IDT) -> Double {
        switch idt {
        case .arriLogC4AWG4:
            let a = (pow(2.0, 18.0) - 16.0) / 117.45
            let b = (1023.0 - 95.0) / 1023.0
            let c = 95.0 / 1023.0
            let p = 14.0 * (x - c) / b + 6.0
            return (pow(2.0, p) - 64.0) / a
        case .sonySLog3SGamut3, .sonySLog3SGamut3Cine, .sonySLog3SGamut3Venice, .sonySLog3SGamut3CineVenice:
            let cut = 171.2102946929 / 1023.0
            let cv = x * 1023.0
            if x >= cut {
                return pow(10.0, (cv - 420.0) / 261.5) * (0.18 + 0.01) - 0.01
            }
            return (cv - 95.0) * 0.01125000 / (171.2102946929 - 95.0)
        case .panasonicVLogVGamut:
            if x >= 0.181 {
                return pow(10.0, (x - 0.598206) / 0.241514) - 0.00873
            }
            return (x - 0.125) / 5.6
        case .fujiFLog2BT2020:
            let a = 5.555556
            if x >= 0.100686685370811 {
                return pow(10.0, (x - 0.384316) / 0.245281) / a - 0.064829 / a
            }
            return (x - 0.092864) / 8.799461
        case .nikonNLogBT2020:
            // White-paper x is 10-bit 0-1023. LUT domain is 0-1 = code/1023.
            let cv = x * 1023.0
            if cv < 452.0 {
                return pow(cv / 650.0, 3.0) - 0.0075
            }
            return exp((cv - 619.0) / 150.0)
        case .redLog3G10RWG:
            if x >= 0.0 {
                return (pow(10.0, x / 0.224282) - 1.0) / 155.975327 - 0.01
            }
            return x / 15.1927 - 0.01
        default:
            return x
        }
    }

    private static func apply3(_ m: simd_double3x3, _ v: SIMD3<Double>) -> SIMD3<Double> {
        m * v
    }

    private static func idtToACEScct(_ logRGB: SIMD3<Double>, idt: IDT) -> SIMD3<Double> {
        let cam = SIMD3(decodeLog(logRGB.x, idt: idt),
                        decodeLog(logRGB.y, idt: idt),
                        decodeLog(logRGB.z, idt: idt))
        let ap0 = cameraToAP0(idt).map { apply3($0, cam) } ?? cam
        let ap1 = apply3(ap0ToAP1, ap0)
        return SIMD3(acescctEncode(ap1.x), acescctEncode(ap1.y), acescctEncode(ap1.z))
    }

    private static func wbInACEScct(_ di: SIMD3<Double>, matrix: simd_double3x3) -> SIMD3<Double> {
        let lin = SIMD3(acescctDecode(di.x), acescctDecode(di.y), acescctDecode(di.z))
        let a = apply3(matrix, lin)
        return SIMD3(acescctEncode(a.x), acescctEncode(a.y), acescctEncode(a.z))
    }

    private static func odtFromACEScct(_ di: SIMD3<Double>) -> SIMD3<Double> {
        let lin = SIMD3(acescctDecode(di.x), acescctDecode(di.y), acescctDecode(di.z))
        let rec = apply3(ap1ToRec709, lin)
        return SIMD3(rec709OETF(rec.x), rec709OETF(rec.y), rec709OETF(rec.z))
    }

    // MARK: - .cube (Adobe/IRIDAS: R fastest, then G, then B)

    private static func cubeFile(title: String, size: Int, map: (SIMD3<Double>) -> SIMD3<Double>) -> String {
        var lines: [String] = [
            "TITLE \"\(title)\"",
            "# LogBridge M1 — implemented (unverified). Not a camera-support claim.",
            "LUT_3D_SIZE \(size)",
            "DOMAIN_MIN 0.0 0.0 0.0",
            "DOMAIN_MAX 1.0 1.0 1.0"
        ]
        if size > 1 {
            let den = Double(size - 1)
            for bi in 0..<size {
                for gi in 0..<size {
                    for ri in 0..<size {
                        let rgb = SIMD3(Double(ri) / den, Double(gi) / den, Double(bi) / den)
                        let o = map(rgb)
                        lines.append(String(format: "%.8f %.8f %.8f", o.x, o.y, o.z))
                    }
                }
            }
        }
        return lines.joined(separator: "\n") + "\n"
    }

    private static func idtCube(idt: IDT, size: Int) -> String {
        cubeFile(title: "LogBridge IDT \(idt.rawValue) → ACEScct (no WB)", size: size) {
            idtToACEScct($0, idt: idt)
        }
    }

    private static func wbCube(cct: Double, tint: Double, size: Int) -> String {
        let m = wbRGBMatrix(cct: cct, tint: tint)
        return cubeFile(title: "LogBridge WB Bradford CAT \(Int(cct))K tint \(tint) (ACEScct in/out)", size: size) {
            wbInACEScct($0, matrix: m)
        }
    }

    private static func odtCube(size: Int) -> String {
        cubeFile(title: "LogBridge ODT ACEScct → Rec.709 (no WB)", size: size) {
            odtFromACEScct($0)
        }
    }

    // MARK: - CDL / CCC / DCTL / graph

    private static func cdlSlope(cct: Double, tint: Double) -> SIMD3<Double> {
        wbRGBMatrix(cct: cct, tint: tint) * SIMD3(1.0, 1.0, 1.0)
    }

    private static func fmt3(_ v: SIMD3<Double>) -> String {
        String(format: "%.10f %.10f %.10f", v.x, v.y, v.z)
    }

    private static func cdlXML(cct: Double, tint: Double, collection: Bool) -> String {
        let slope = fmt3(cdlSlope(cct: cct, tint: tint))
        let sop = """
              <SOPNode>
                <Slope>\(slope)</Slope>
                <Offset>0.0000000000 0.0000000000 0.0000000000</Offset>
                <Power>1.0000000000 1.0000000000 1.0000000000</Power>
              </SOPNode>
              <SatNode>
                <Saturation>1.0</Saturation>
              </SatNode>
        """
        if collection {
            return """
            <?xml version="1.0" encoding="UTF-8"?>
            <ColorCorrectionCollection xmlns="urn:ASC:CDL:v1.01">
              <ColorCorrection id="LogBridge_WB">
            \(sop)
              </ColorCorrection>
            </ColorCorrectionCollection>

            """
        }
        return """
        <?xml version="1.0" encoding="UTF-8"?>
        <ColorDecisionList xmlns="urn:ASC:CDL:v1.01">
          <ColorDecision>
            <ColorCorrection id="LogBridge_WB">
        \(sop)
            </ColorCorrection>
          </ColorDecision>
        </ColorDecisionList>

        """
    }

    private static func dctl(cct: Double, tint: Double) -> String {
        let m = wbRGBMatrix(cct: cct, tint: tint)
        // simd_double3x3 is column-major. Flatten row-major for the DCTL 3x3.
        let r0c0 = m.columns.0.x, r0c1 = m.columns.1.x, r0c2 = m.columns.2.x
        let r1c0 = m.columns.0.y, r1c1 = m.columns.1.y, r1c2 = m.columns.2.y
        let r2c0 = m.columns.0.z, r2c1 = m.columns.1.z, r2c2 = m.columns.2.z
        let list = [r0c0, r0c1, r0c2, r1c0, r1c1, r1c2, r2c0, r2c1, r2c2]
            .map { String(format: "%.10ff", $0) }
            .joined(separator: ", ")
        return """
        // LogBridge M1 WB node — scene-linear Bradford/CAT02 in ACEScg (AP1).
        // Timeline: ACEScct / ACES2065-1 (D65).
        // Bypass this DCTL in Resolve to restore IDT → working space → optional Rec.709 ODT.
        // CCT \(Int(cct)) K  tint \(tint)  method bradford
        // Implemented (unverified). Not a camera-support claim.

        DEFINE_UI_PARAMS(bypass_wb, Bypass WB, DCTLUI_CHECK_BOX, 0, 0, 1)

        __DEVICE__ float acescct_decode(float x)
        {
            const float LO_S = 10.5402377416545f;
            const float LO_O = 0.0729055341958355f;
            const float BREAK_LIN = 0.0078125f;
            const float BREAK_LOG = LO_S * BREAK_LIN + LO_O;
            if (x <= BREAK_LOG)
                return (x - LO_O) / LO_S;
            return _exp2f(x * 17.52f - 9.72f);
        }

        __DEVICE__ float acescct_encode(float lin)
        {
            const float LO_S = 10.5402377416545f;
            const float LO_O = 0.0729055341958355f;
            const float BREAK_LIN = 0.0078125f;
            if (lin <= BREAK_LIN)
                return LO_S * lin + LO_O;
            if (lin < 1.0e-10f) lin = 1.0e-10f;
            return (_log2f(lin) + 9.72f) / 17.52f;
        }

        __DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
        {
            if (bypass_wb)
                return make_float3(p_R, p_G, p_B);

            float r = acescct_decode(p_R);
            float g = acescct_decode(p_G);
            float b = acescct_decode(p_B);

            const float m[9] = { \(list) };
            float or_ = m[0] * r + m[1] * g + m[2] * b;
            float og  = m[3] * r + m[4] * g + m[5] * b;
            float ob  = m[6] * r + m[7] * g + m[8] * b;

            return make_float3(acescct_encode(or_), acescct_encode(og), acescct_encode(ob));
        }
        """
    }

    private static func resolveCST(_ idt: IDT) -> (space: String, gamma: String) {
        switch idt {
        case .arriLogC4AWG4: return ("ARRI Wide Gamut 4", "ARRI LogC4")
        case .sonySLog3SGamut3, .sonySLog3SGamut3Venice: return ("Sony S-Gamut3", "Sony S-Log3")
        case .sonySLog3SGamut3Cine, .sonySLog3SGamut3CineVenice: return ("Sony S-Gamut3.Cine", "Sony S-Log3")
        case .panasonicVLogVGamut: return ("Panasonic V-Gamut", "Panasonic V-Log")
        case .fujiFLog2BT2020: return ("Rec.2020", "Fujifilm F-Log2")
        case .nikonNLogBT2020: return ("Rec.2020", "Nikon N-Log")
        case .redLog3G10RWG: return ("REDWideGamutRGB", "RED Log3G10")
        default: return (idt.ocioName, idt.curve)
        }
    }

    private static func xmlEscape(_ s: String) -> String {
        s.replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
    }

    private static func graphXML(idts: [IDT], cct: Double, tint: Double, includeWB: Bool, odtEnabled: Bool = true) -> String {
        let enabled = includeWB ? "true" : "false"
        let odtOn = odtEnabled ? "true" : "false"
        var idtNodes = ""
        if idts.isEmpty {
            idtNodes = "    <IDT idt=\"(user picker)\" file=\"\" resolveOutputColorSpace=\"ACEScct\" resolveOutputGamma=\"ACEScct\"/>\n"
        } else {
            for idt in idts {
                let cst = resolveCST(idt)
                idtNodes += "    <IDT idt=\"\(xmlEscape(idt.rawValue))\" file=\"01_IDT_\(idt.rawValue).cube\" resolveInputColorSpace=\"\(xmlEscape(cst.space))\" resolveInputGamma=\"\(xmlEscape(cst.gamma))\" resolveOutputColorSpace=\"ACEScct\" resolveOutputGamma=\"ACEScct\"/>\n"
            }
        }
        return """
        <?xml version="1.0" encoding="UTF-8"?>
        <LogBridgeResolveGraph version="1" status="implemented (unverified)">
          <WorkingSpace gamut="AP1" encoding="ACEScct" white="ACES" interchange="ACES2065-1"/>
          <Node index="1" name="IDT" type="LUT_or_CST" bypassable="false">
            <Description>Camera log to ACES2065-1 then ACEScct. No white balance. Do not bake DWG.</Description>
        \(idtNodes)  </Node>
          <Node index="2" name="WB" type="Corrector" bypassable="true" enabled="\(enabled)" method="bradford">
            <Description>Scene-linear Bradford/CAT02 (CCT + tint). Bypass this node in Resolve (Color page: disable node 2, or DCTL Bypass WB, or skip 02_WB.cube). Remaining graph is IDT → ACEScct → optional Rec.709 ODT.</Description>
            <CCT>\(String(format: "%.4f", cct))</CCT>
            <Tint>\(String(format: "%.6f", tint))</Tint>
            <File role="lut">02_WB.cube</File>
            <File role="cdl">02_WB.cdl</File>
            <File role="ccc">02_WB.ccc</File>
            <File role="dctl">02_WB.dctl</File>
          </Node>
          <Node index="3" name="ODT_Rec709" type="LUT_or_CST" bypassable="true" enabled="\(odtOn)">
            <Description>Optional Rec.709 ODT. Not the only deliverable; timeline stays ACEScct (or ACES2065-1 EXR) when this node is off.</Description>
            <File role="lut">03_ODT_Rec709.cube</File>
            <ResolveCST inputColorSpace="ACEScct" inputGamma="ACEScct" outputColorSpace="Rec.709" outputGamma="Rec.709"/>
          </Node>
        </LogBridgeResolveGraph>

        """
    }

    private static func graphDOT(idts: [IDT], cct: Double, tint: Double, includeWB: Bool) -> String {
        let idtLabel = idts.isEmpty ? "(per clip CST/LUT)" : idts.map(\.rawValue).joined(separator: ", ")
        let wbStyle = includeWB ? "solid" : "dashed"
        let wbFill = includeWB ? "lightgrey" : "white"
        return """
        digraph LogBridgeResolve {
          rankdir=LR;
          labelloc="t";
          label="LogBridge M1 Resolve graph — implemented (unverified)";
          node [shape=box, fontname="Helvetica"];

          clip [label="Clip\\ncamera log"];
          idt  [label="IDT\\n\(idtLabel)\\n01_IDT_<idt>.cube\\nor ACES IDT / CST → ACEScct"];
          wb   [label="WB (bypassable)\\nscene-linear Bradford/CAT02\\n\(Int(cct)) K  tint \(tint)\\n02_WB.cube / .cdl / .ccc / .dctl", style="filled,\(wbStyle)", fillcolor="\(wbFill)"];
          odt  [label="Rec.709 ODT (later node)\\n03_ODT_Rec709.cube\\nor CST ACEScct → Rec.709"];
          timeline [shape=oval, label="Timeline\\nACEScct"];

          clip -> idt -> wb -> odt;
          idt -> timeline [style=dashed, label="working space"];
        }

        """
    }

    private static func readme(idts: [IDT], cct: Double, tint: Double, includeWB: Bool) -> String {
        let idtList = idts.isEmpty ? "(none — assign IDT in Resolve CST)" : idts.map(\.rawValue).joined(separator: ", ")
        let wbState = includeWB ? "enabled by default" : "present but bypassed by default"
        return """
        # LogBridge Resolve export

        Status: **implemented (unverified)**. This is not a camera-support claim.

        ## Graph (serial nodes)

        Timeline color management: **ACEScct** (Academy grading). Interchange: **ACES2065-1**. Do not bake DWG.

        1. **IDT** — `01_IDT_<idt>.cube` or Color Space Transform
           - Input: camera log / camera gamut (`\(idtList)`)
           - Output: ACEScct (via ACES2065-1)
           - Contains **no** white balance.

        2. **WB** — own corrector, **\(wbState)**
           - `02_WB.cube` — 3D LUT of the Bradford/CAT02 3×3 in scene-linear ACEScg, wrapped in ACEScct so it sits on the ACEScct timeline.
           - `02_WB.dctl` — same 3×3 as a DCTL (Decode ACEScct → matrix → Encode ACEScct). Checkbox **Bypass WB** inside the DCTL, or disable the node.
           - `02_WB.cdl` / `02_WB.ccc` — ASC CDL Color Corrector for the same serial slot (slope = CAT × (1,1,1); offset 0; power 1). Prefer the cube/DCTL for the full 3×3; the CDL is the bypassable corrector form.
           - CCT \(Int(cct)) K, tint \(tint), method Bradford. Scene-linear only.

        3. **Rec.709 ODT** — `03_ODT_Rec709.cube` or CST
           - Input: ACEScct / ACES2065-1
           - Output: Rec.709 encoded (BT.709 OETF, no RRT)
           - Contains **no** white balance. Optional later node.

        ## How to bypass WB in Resolve

        Color page, serial node graph:

        - Apply **IDT** (node 1: LUT `01_IDT_*.cube`, or ACES IDT / CST camera → ACEScct).
        - Apply **WB** (node 2: LUT `02_WB.cube`, **or** DCTL `02_WB.dctl`, **or** import `02_WB.cdl` onto a Color Corrector).
        - Apply **ODT** (node 3: LUT `03_ODT_Rec709.cube`, or CST ACEScct → Rec.709) if you need a 709 viewing/output node.

        To bypass WB: disable node 2 (or tick DCTL **Bypass WB**, or skip the CDL/LUT). The remaining graph is **IDT → working space (ACEScct) → optional Rec.709 ODT**. Camera linear after IDT is uncorrected.

        Do not use a single Rec.709 file as the only deliverable. Rec.709 is a later node.

        ## Files

        | File | Role |
        | --- | --- |
        | `graph.xml` | Machine-readable node graph (bypassable WB) |
        | `graph.dot` | Graphviz of the same graph |
        | `01_IDT_<idt>.cube` | IDT LUT (no WB) |
        | `02_WB.cube` | WB LUT (Bradford CAT, ACEScct-wrapped) |
        | `02_WB.cdl` / `02_WB.ccc` | WB as ASC CDL Color Corrector |
        | `02_WB.dctl` | WB as DCTL (exact 3×3) |
        | `03_ODT_Rec709.cube` | Rec.709 ODT (no WB) |
        | `README_RESOLVE.md` | This file |

        M1 is a serial node graph (IDT → WB → ODT), not a general node editor. Golden grey-card samples are required before any accuracy claim. Implemented (unverified).
        """
    }
}
