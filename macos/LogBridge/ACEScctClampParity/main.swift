import Foundation

/// Numeric check of ACEScctMath against tests/fixtures/acescct_clamp_parity.json.
/// Expected values are computed by Python. The runner does not compare sources.

struct EncodeRow: Decodable {
    let lin: Double
    let acescct: Double
}

struct ExposureRow: Decodable {
    let enc: Double
    let stops: Double
    let acescct: Double
}

struct Fixture: Decodable {
    let encode: [EncodeRow]
    let exposure: [ExposureRow]
}

guard CommandLine.arguments.count == 2 else {
    fputs("usage: acescct-clamp-parity <fixture.json>\n", stderr)
    exit(2)
}

let url = URL(fileURLWithPath: CommandLine.arguments[1])
let data = try Data(contentsOf: url)
let fixture = try JSONDecoder().decode(Fixture.self, from: data)
let tol = 1e-8
var worst = 0.0
var failed = 0

for row in fixture.encode {
    let got = ACEScctMath.encode(row.lin)
    let err = abs(got - row.acescct)
    worst = max(worst, err)
    if err > tol {
        failed += 1
        fputs("encode lin=\(row.lin) got=\(got) expected=\(row.acescct) err=\(err)\n", stderr)
    }
}

for row in fixture.exposure {
    let got = ACEScctMath.exposureChannel(row.enc, stops: row.stops)
    let err = abs(got - row.acescct)
    worst = max(worst, err)
    if err > tol {
        failed += 1
        fputs(
            "exposure enc=\(row.enc) stops=\(row.stops) got=\(got) expected=\(row.acescct) err=\(err)\n",
            stderr
        )
    }
}

if failed != 0 {
    fputs("swift parity failed \(failed) worst=\(worst)\n", stderr)
    exit(1)
}
print("swift parity ok encode=\(fixture.encode.count) exposure=\(fixture.exposure.count) worst=\(worst)")
