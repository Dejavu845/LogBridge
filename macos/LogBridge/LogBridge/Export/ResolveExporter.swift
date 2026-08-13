import Foundation
import simd

/// DaVinci Resolve export: a real bypassable WB node, not a prose sidecar.
///
/// Serial graph on a DaVinci Wide Gamut / DaVinci Intermediate (D65) timeline:
///   1. IDT  — camera log → DWG Intermediate (`.cube` and/or Resolve CST)
///   2. WB   — scene-linear Bradford/CAT02 (CCT + tint). Own LUT / CDL / DCTL.
///             Bypass this node → IDT → working space → optional Rec.709 ODT.
///   3. ODT  — Rec.709 (later node, not the only deliverable)
///
/// WB is never baked into the IDT or ODT cubes. Status: implemented (unverified).
enum ResolveExporter {
    static let lutSize = 17

    static func exportNote(clips: [Clip], includeWBNode: Bool, cct: Double, tint: Double) -> String {
        var lines: [String] = []
        lines.append("LogBridge M1 Resolve export (implemented, unverified)")
        lines.append("Working space: DaVinci Wide Gamut / DaVinci Intermediate (D65)")
        lines.append("WB node: \(includeWBNode ? "ON (scene-linear Bradford CAT, \(Int(cct)) K, tint \(tint))" : "present, bypassed by default")")
        lines.append("ODT: Rec.709 is a separate output, not the only deliverable.")
        lines.append("Files: graph.xml, graph.dot, 01_IDT_*.cube, 02_WB.{cube,cdl,ccc,dctl}, 03_ODT_Rec709.cube, README_RESOLVE.md")
        lines.append("Bypass WB in Resolve: disable serial node 2 (or DCTL Bypass WB). Remaining graph is IDT → DWG Intermediate → optional Rec.709 ODT.")
        lines.append("Clips:")
        for clip in clips {
            lines.append("  - \(clip.url.lastPathComponent): \(clip.idt.ocioName) [\(clip.verificationBadge)]")
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
        lutSize: Int = lutSize
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
        try write("graph.xml", graphXML(idts: idts, cct: cct, tint: tint, includeWB: includeWBNode))
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
        for clip in clips where !clip.idt.isStub {
            if seen.insert(clip.idt).inserted {
                out.append(clip.idt)
            }
        }
        return out
    }

    // MARK: - Matrices (row-major, match ocio/matrices/*.spimtx)

    private static let dwgToXYZ = simd_double3x3(rows: [
        SIMD3(0.700622392094, 0.148774815123, 0.101058719835),
        SIMD3(0.274118510907, 0.873631895940, -0.147750406847),
        SIMD3(-0.098962912883, -0.137895325076, 1.325915988719)
    ])

    private static let dwgToRec709 = simd_double3x3(rows: [
        SIMD3(1.898614899306, -0.792176183404, -0.106438715902),
        SIMD3(-0.168948786476, 1.488975754118, -0.320026967642),
        SIMD3(-0.121539160604, -0.315675853052, 1.437215013657)
    ])

    private static func cameraToDWG(_ idt: IDT) -> simd_double3x3? {
        switch idt {
        case .arriLogC4AWG4:
            return simd_double3x3(rows: [
                SIMD3(0.997395939837, -0.023165014815, 0.025769074977),
                SIMD3(-0.009183081266, 0.917632034596, 0.091551046670),
                SIMD3(0.073487991967, 0.093704798362, 0.832807209671)
            ])
        case .sonySLog3SGamut3:
            return simd_double3x3(rows: [
                SIMD3(0.996650041836, -0.026739524102, 0.030089482265),
                SIMD3(0.008962001489, 0.925300630159, 0.065737368353),
                SIMD3(0.068020421169, 0.097704868626, 0.834274710205)
            ])
        case .sonySLog3SGamut3Cine:
            return simd_double3x3(rows: [
                SIMD3(0.852787225200, 0.132475794312, 0.014736980487),
                SIMD3(-0.014981188523, 0.987029009978, 0.027952178545),
                SIMD3(0.037907848534, 0.091678874858, 0.870413276608)
            ])
        case .panasonicVLogVGamut:
            return simd_double3x3(rows: [
                SIMD3(0.958788766787, 0.013416877789, 0.027794355424),
                SIMD3(0.008621548181, 0.898149016914, 0.093229434905),
                SIMD3(0.065436425015, 0.090930238374, 0.843633336611)
            ])
        case .fujiFLog2BT2020, .nikonNLogBT2020:
            return simd_double3x3(rows: [
                SIMD3(0.892112120946, 0.024369175871, 0.083518703182),
                SIMD3(0.032616601764, 0.786137516904, 0.181245881332),
                SIMD3(0.069977051186, 0.104749491904, 0.825273456911)
            ])
        case .redLog3G10RWG:
            return simd_double3x3(rows: [
                SIMD3(1.046183501418, -0.082175324998, 0.035991823580),
                SIMD3(0.002998821038, 0.962281459766, 0.034719719196),
                SIMD3(0.018301335409, -0.168020759769, 1.149719424360)
            ])
        default:
            return nil
        }
    }

    /// Scene-linear DWG RGB CAT: XYZ_to_DWG * Bradford_XYZ * DWG_to_XYZ.
    private static func wbRGBMatrix(cct: Double, tint: Double) -> simd_double3x3 {
        let cat = WhiteBalanceNode.catMatrix(cct: cct, tint: tint)
        return dwgToXYZ.inverse * cat * dwgToXYZ
    }

    // MARK: - Working-space / OETF

    private static let diA = 0.0075
    private static let diB = 7.0
    private static let diC = 0.07329248
    private static let diM = 10.44426855
    private static let diLinCut = 0.00262409
    private static let diLogCut = 0.02740668
    private static let rec709Beta = 0.018053968510807
    private static let rec709Alpha = 1.09929682680944

    private static func diEncode(_ lin: Double) -> Double {
        if lin > diLinCut {
            return (log2(lin + diA) + diB) * diC
        }
        return lin * diM
    }

    private static func diDecode(_ enc: Double) -> Double {
        if enc > diLogCut {
            return pow(2.0, enc / diC - diB) - diA
        }
        return enc / diM
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
        case .sonySLog3SGamut3, .sonySLog3SGamut3Cine:
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

    private static func idtToDI(_ logRGB: SIMD3<Double>, idt: IDT) -> SIMD3<Double> {
        let cam = SIMD3(decodeLog(logRGB.x, idt: idt),
                        decodeLog(logRGB.y, idt: idt),
                        decodeLog(logRGB.z, idt: idt))
        let dwg = cameraToDWG(idt).map { apply3($0, cam) } ?? cam
        return SIMD3(diEncode(dwg.x), diEncode(dwg.y), diEncode(dwg.z))
    }

    private static func wbInDI(_ di: SIMD3<Double>, matrix: simd_double3x3) -> SIMD3<Double> {
        let lin = SIMD3(diDecode(di.x), diDecode(di.y), diDecode(di.z))
        let a = apply3(matrix, lin)
        return SIMD3(diEncode(a.x), diEncode(a.y), diEncode(a.z))
    }

    private static func odtFromDI(_ di: SIMD3<Double>) -> SIMD3<Double> {
        let lin = SIMD3(diDecode(di.x), diDecode(di.y), diDecode(di.z))
        let rec = apply3(dwgToRec709, lin)
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
        cubeFile(title: "LogBridge IDT \(idt.rawValue) → DWG Intermediate (no WB)", size: size) {
            idtToDI($0, idt: idt)
        }
    }

    private static func wbCube(cct: Double, tint: Double, size: Int) -> String {
        let m = wbRGBMatrix(cct: cct, tint: tint)
        return cubeFile(title: "LogBridge WB Bradford CAT \(Int(cct))K tint \(tint) (DI in/out)", size: size) {
            wbInDI($0, matrix: m)
        }
    }

    private static func odtCube(size: Int) -> String {
        cubeFile(title: "LogBridge ODT DWG Intermediate → Rec.709 (no WB)", size: size) {
            odtFromDI($0)
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
        // LogBridge M1 WB node — scene-linear Bradford/CAT02 in DWG.
        // Timeline: DaVinci Wide Gamut / DaVinci Intermediate (D65).
        // Bypass this DCTL in Resolve to restore IDT → working space → optional Rec.709 ODT.
        // CCT \(Int(cct)) K  tint \(tint)  method bradford
        // Implemented (unverified). Not a camera-support claim.

        DEFINE_UI_PARAMS(bypass_wb, Bypass WB, DCTLUI_CHECK_BOX, 0, 0, 1)

        __DEVICE__ float di_decode(float x)
        {
            const float A = 0.0075f;
            const float B = 7.0f;
            const float C = 0.07329248f;
            const float M = 10.44426855f;
            const float LOG_CUT = 0.02740668f;
            if (x > LOG_CUT)
                return _exp2f(x / C - B) - A;
            return x / M;
        }

        __DEVICE__ float di_encode(float lin)
        {
            const float A = 0.0075f;
            const float B = 7.0f;
            const float C = 0.07329248f;
            const float M = 10.44426855f;
            const float LIN_CUT = 0.00262409f;
            if (lin > LIN_CUT)
                return (_log2f(lin + A) + B) * C;
            return lin * M;
        }

        __DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
        {
            if (bypass_wb)
                return make_float3(p_R, p_G, p_B);

            float r = di_decode(p_R);
            float g = di_decode(p_G);
            float b = di_decode(p_B);

            const float m[9] = { \(list) };
            float or_ = m[0] * r + m[1] * g + m[2] * b;
            float og  = m[3] * r + m[4] * g + m[5] * b;
            float ob  = m[6] * r + m[7] * g + m[8] * b;

            return make_float3(di_encode(or_), di_encode(og), di_encode(ob));
        }
        """
    }

    private static func resolveCST(_ idt: IDT) -> (space: String, gamma: String) {
        switch idt {
        case .arriLogC4AWG4: return ("ARRI Wide Gamut 4", "ARRI LogC4")
        case .sonySLog3SGamut3: return ("Sony S-Gamut3", "Sony S-Log3")
        case .sonySLog3SGamut3Cine: return ("Sony S-Gamut3.Cine", "Sony S-Log3")
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

    private static func graphXML(idts: [IDT], cct: Double, tint: Double, includeWB: Bool) -> String {
        let enabled = includeWB ? "true" : "false"
        var idtNodes = ""
        if idts.isEmpty {
            idtNodes = "    <IDT idt=\"(user picker)\" file=\"\" resolveOutputColorSpace=\"DaVinci Wide Gamut\" resolveOutputGamma=\"DaVinci Intermediate\"/>\n"
        } else {
            for idt in idts {
                let cst = resolveCST(idt)
                idtNodes += "    <IDT idt=\"\(xmlEscape(idt.rawValue))\" file=\"01_IDT_\(idt.rawValue).cube\" resolveInputColorSpace=\"\(xmlEscape(cst.space))\" resolveInputGamma=\"\(xmlEscape(cst.gamma))\" resolveOutputColorSpace=\"DaVinci Wide Gamut\" resolveOutputGamma=\"DaVinci Intermediate\"/>\n"
            }
        }
        return """
        <?xml version="1.0" encoding="UTF-8"?>
        <LogBridgeResolveGraph version="1" status="implemented (unverified)">
          <WorkingSpace gamut="DaVinci Wide Gamut" encoding="DaVinci Intermediate" white="D65"/>
          <Node index="1" name="IDT" type="LUT_or_CST" bypassable="false">
            <Description>Camera log to DWG Intermediate. No white balance.</Description>
        \(idtNodes)  </Node>
          <Node index="2" name="WB" type="Corrector" bypassable="true" enabled="\(enabled)" method="bradford">
            <Description>Scene-linear Bradford/CAT02 (CCT + tint). Bypass this node in Resolve (Color page: disable node 2, or DCTL Bypass WB, or skip 02_WB.cube). Remaining graph is IDT → DWG Intermediate → optional Rec.709 ODT.</Description>
            <CCT>\(String(format: "%.4f", cct))</CCT>
            <Tint>\(String(format: "%.6f", tint))</Tint>
            <File role="lut">02_WB.cube</File>
            <File role="cdl">02_WB.cdl</File>
            <File role="ccc">02_WB.ccc</File>
            <File role="dctl">02_WB.dctl</File>
          </Node>
          <Node index="3" name="ODT_Rec709" type="LUT_or_CST" bypassable="true" enabled="true">
            <Description>Optional Rec.709 ODT. Not the only deliverable; timeline stays DWG Intermediate when this node is off.</Description>
            <File role="lut">03_ODT_Rec709.cube</File>
            <ResolveCST inputColorSpace="DaVinci Wide Gamut" inputGamma="DaVinci Intermediate" outputColorSpace="Rec.709" outputGamma="Rec.709"/>
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
          idt  [label="IDT\\n\(idtLabel)\\n01_IDT_<idt>.cube\\nor Resolve CST → DWG Intermediate"];
          wb   [label="WB (bypassable)\\nscene-linear Bradford/CAT02\\n\(Int(cct)) K  tint \(tint)\\n02_WB.cube / .cdl / .ccc / .dctl", style="filled,\(wbStyle)", fillcolor="\(wbFill)"];
          odt  [label="Rec.709 ODT (later node)\\n03_ODT_Rec709.cube\\nor CST DWG Intermediate → Rec.709"];
          timeline [shape=oval, label="Timeline\\nDWG Intermediate"];

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

        Timeline color management: **DaVinci Wide Gamut / DaVinci Intermediate**, D65.

        1. **IDT** — `01_IDT_<idt>.cube` or Color Space Transform
           - Input: camera log / camera gamut (`\(idtList)`)
           - Output: DaVinci Wide Gamut, DaVinci Intermediate
           - Contains **no** white balance.

        2. **WB** — own corrector, **\(wbState)**
           - `02_WB.cube` — 3D LUT of the Bradford/CAT02 3×3 in scene-linear DWG, wrapped in DaVinci Intermediate so it sits on the DI timeline.
           - `02_WB.dctl` — same 3×3 as a DCTL (Decode DI → matrix → Encode DI). Checkbox **Bypass WB** inside the DCTL, or disable the node.
           - `02_WB.cdl` / `02_WB.ccc` — ASC CDL Color Corrector for the same serial slot (slope = CAT × (1,1,1); offset 0; power 1). Prefer the cube/DCTL for the full 3×3; the CDL is the bypassable corrector form.
           - CCT \(Int(cct)) K, tint \(tint), method Bradford. Scene-linear only.

        3. **Rec.709 ODT** — `03_ODT_Rec709.cube` or CST
           - Input: DaVinci Wide Gamut / DaVinci Intermediate
           - Output: Rec.709 encoded (BT.709 OETF, no RRT)
           - Contains **no** white balance. Optional later node.

        ## How to bypass WB in Resolve

        Color page, serial node graph:

        - Apply **IDT** (node 1: LUT `01_IDT_*.cube`, or CST camera → DWG Intermediate).
        - Apply **WB** (node 2: LUT `02_WB.cube`, **or** DCTL `02_WB.dctl`, **or** import `02_WB.cdl` onto a Color Corrector).
        - Apply **ODT** (node 3: LUT `03_ODT_Rec709.cube`, or CST DWG Intermediate → Rec.709) if you need a 709 viewing/output node.

        To bypass WB: disable node 2 (or tick DCTL **Bypass WB**, or skip the CDL/LUT). The remaining graph is **IDT → working space (DWG Intermediate) → optional Rec.709 ODT**. Camera linear after IDT is uncorrected.

        Do not use a single Rec.709 file as the only deliverable. Rec.709 is a later node.

        ## Files

        | File | Role |
        | --- | --- |
        | `graph.xml` | Machine-readable node graph (bypassable WB) |
        | `graph.dot` | Graphviz of the same graph |
        | `01_IDT_<idt>.cube` | IDT LUT (no WB) |
        | `02_WB.cube` | WB LUT (Bradford CAT, DI-wrapped) |
        | `02_WB.cdl` / `02_WB.ccc` | WB as ASC CDL Color Corrector |
        | `02_WB.dctl` | WB as DCTL (exact 3×3) |
        | `03_ODT_Rec709.cube` | Rec.709 ODT (no WB) |
        | `README_RESOLVE.md` | This file |

        M1 is a fixed pipeline, not a node editor. Golden grey-card samples are required before any accuracy claim.
        """
    }
}
