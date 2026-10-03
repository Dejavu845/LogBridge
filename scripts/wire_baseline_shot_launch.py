#!/usr/bin/env python3
"""Point a disposable 28066d5 checkout at the current shot-launch sources.

Copies UIShotLaunch.swift and the XCUITest file, then patches that checkout's
app entry, project, and scheme. Does not commit. HEAD already has these wires.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SHOT_BUILD = (
    "\t\tA1000000000000000000001A /* UIShotLaunch.swift in Sources */ = "
    "{isa = PBXBuildFile; fileRef = A2000000000000000000001C /* UIShotLaunch.swift */; };\n"
)
TEST_BUILD = (
    "\t\tB10000000000000000000001 /* LogBridgeUIShots.swift in Sources */ = "
    "{isa = PBXBuildFile; fileRef = B20000000000000000000001 /* LogBridgeUIShots.swift */; };\n"
)
FILE_REFS = """\
\t\tA2000000000000000000001C /* UIShotLaunch.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = UIShotLaunch.swift; sourceTree = "<group>"; };
\t\tB20000000000000000000001 /* LogBridgeUIShots.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = LogBridgeUIShots.swift; sourceTree = "<group>"; };
\t\tB30000000000000000000001 /* LogBridgeUITests.xctest */ = {isa = PBXFileReference; explicitFileType = wrapper.cfbundle; includeInIndex = 0; path = LogBridgeUITests.xctest; sourceTree = BUILT_PRODUCTS_DIR; };
"""
UITEST_GROUP = """\
\t\tB50000000000000000000002 /* LogBridgeUITests */ = {
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\tB20000000000000000000001 /* LogBridgeUIShots.swift */,
\t\t\t);
\t\t\tpath = LogBridgeUITests;
\t\t\tsourceTree = "<group>";
\t\t};
"""
NATIVE_AND_DEPS = """\
\t\tB60000000000000000000001 /* LogBridgeUITests */ = {
\t\t\tisa = PBXNativeTarget;
\t\t\tbuildConfigurationList = B80000000000000000000003 /* Build configuration list for PBXNativeTarget "LogBridgeUITests" */;
\t\t\tbuildPhases = (
\t\t\t\tB70000000000000000000001 /* Sources */,
\t\t\t\tB40000000000000000000002 /* Frameworks */,
\t\t\t);
\t\t\tbuildRules = (
\t\t\t);
\t\t\tdependencies = (
\t\t\t\tB10000000000000000000003 /* PBXTargetDependency */,
\t\t\t);
\t\t\tname = LogBridgeUITests;
\t\t\tproductName = LogBridgeUITests;
\t\t\tproductReference = B30000000000000000000001 /* LogBridgeUITests.xctest */;
\t\t\tproductType = "com.apple.product-type.bundle.ui-testing";
\t\t};
/* End PBXNativeTarget section */

/* Begin PBXContainerItemProxy section */
\t\tB10000000000000000000002 /* PBXContainerItemProxy */ = {
\t\t\tisa = PBXContainerItemProxy;
\t\t\tcontainerPortal = A90000000000000000000001 /* Project object */;
\t\t\tproxyType = 1;
\t\t\tremoteGlobalIDString = A60000000000000000000001;
\t\t\tremoteInfo = LogBridge;
\t\t};
/* End PBXContainerItemProxy section */

/* Begin PBXTargetDependency section */
\t\tB10000000000000000000003 /* PBXTargetDependency */ = {
\t\t\tisa = PBXTargetDependency;
\t\t\ttarget = A60000000000000000000001 /* LogBridge */;
\t\t\ttargetProxy = B10000000000000000000002 /* PBXContainerItemProxy */;
\t\t};
/* End PBXTargetDependency section */
"""
TEST_SOURCES = """\
\t\tB70000000000000000000001 /* Sources */ = {
\t\t\tisa = PBXSourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t\tB10000000000000000000001 /* LogBridgeUIShots.swift in Sources */,
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t};
"""
TEST_FRAMEWORKS = """\
\t\tB40000000000000000000002 /* Frameworks */ = {
\t\t\tisa = PBXFrameworksBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t};
"""
TEST_CONFIGS = """\
\t\tBA0000000000000000000005 /* Debug */ = {
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tENABLE_HARDENED_RUNTIME = NO;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tMACOSX_DEPLOYMENT_TARGET = 14.0;
\t\t\t\tMARKETING_VERSION = 0.1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = app.logbridge.LogBridgeUITests;
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_VERSION = 5.0;
\t\t\t\tTEST_TARGET_NAME = LogBridge;
\t\t\t};
\t\t\tname = Debug;
\t\t};
\t\tBA0000000000000000000006 /* Release */ = {
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tENABLE_HARDENED_RUNTIME = NO;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tMACOSX_DEPLOYMENT_TARGET = 14.0;
\t\t\t\tMARKETING_VERSION = 0.1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = app.logbridge.LogBridgeUITests;
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_VERSION = 5.0;
\t\t\t\tTEST_TARGET_NAME = LogBridge;
\t\t\t};
\t\t\tname = Release;
\t\t};
"""
TEST_LIST = """\
\t\tB80000000000000000000003 /* Build configuration list for PBXNativeTarget "LogBridgeUITests" */ = {
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\tBA0000000000000000000005 /* Debug */,
\t\t\t\tBA0000000000000000000006 /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t};
"""
APP_OLD = """\
@main
struct LogBridgeApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
"""
APP_NEW = """\
@main
struct LogBridgeApp: App {
    init() {
        UIShotLaunch.prepareProcessIfNeeded()
    }

    var body: some Scene {
        WindowGroup {
            if UIShotLaunch.isActive {
                ContentView(session: UIShotLaunch.sessionIfRequested())
                    .modifier(UIShotChrome())
            } else {
                ContentView()
            }
        }
"""
SCHEME_BUILD = """\
         <BuildActionEntry
            buildForTesting = "YES"
            buildForRunning = "NO"
            buildForProfiling = "NO"
            buildForArchiving = "NO"
            buildForAnalyzing = "NO">
            <BuildableReference
               BuildableIdentifier = "primary"
               BlueprintIdentifier = "B60000000000000000000001"
               BuildableName = "LogBridgeUITests.xctest"
               BlueprintName = "LogBridgeUITests"
               ReferencedContainer = "container:LogBridge.xcodeproj">
            </BuildableReference>
         </BuildActionEntry>
"""
SCHEME_TEST = """\
      shouldAutocreateTestPlan = "NO">
      <Testables>
         <TestableReference
            skipped = "NO"
            parallelizable = "NO">
            <BuildableReference
               BuildableIdentifier = "primary"
               BlueprintIdentifier = "B60000000000000000000001"
               BuildableName = "LogBridgeUITests.xctest"
               BlueprintName = "LogBridgeUITests"
               ReferencedContainer = "container:LogBridge.xcodeproj">
            </BuildableReference>
         </TestableReference>
      </Testables>
"""


def _must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"wire_baseline_shot_launch: missing anchor: {label}")
    return text.replace(old, new, 1)


def wire_project(text: str) -> str:
    if "LogBridgeUITests" in text and "UIShotLaunch.swift" in text:
        return text
    text = _must_replace(
        text,
        "/* End PBXBuildFile section */",
        SHOT_BUILD + TEST_BUILD + "/* End PBXBuildFile section */",
        "PBXBuildFile",
    )
    text = _must_replace(
        text,
        "/* End PBXFileReference section */",
        FILE_REFS + "/* End PBXFileReference section */",
        "PBXFileReference",
    )
    text = _must_replace(
        text,
        "\t\t\t\tA50000000000000000000002 /* LogBridge */,\n",
        "\t\t\t\tA50000000000000000000002 /* LogBridge */,\n"
        "\t\t\t\tB50000000000000000000002 /* LogBridgeUITests */,\n",
        "root group",
    )
    text = _must_replace(
        text,
        "\t\t\t\tA20000000000000000000002 /* ContentView.swift */,\n",
        "\t\t\t\tA20000000000000000000002 /* ContentView.swift */,\n"
        "\t\t\t\tA2000000000000000000001C /* UIShotLaunch.swift */,\n",
        "LogBridge group",
    )
    text = _must_replace(
        text,
        "\t\t\t\tA30000000000000000000001 /* LogBridge.app */,\n",
        "\t\t\t\tA30000000000000000000001 /* LogBridge.app */,\n"
        "\t\t\t\tB30000000000000000000001 /* LogBridgeUITests.xctest */,\n",
        "products",
    )
    text = _must_replace(
        text,
        "/* End PBXGroup section */",
        UITEST_GROUP + "/* End PBXGroup section */",
        "PBXGroup",
    )
    text = _must_replace(
        text,
        '\t\t\tproductType = "com.apple.product-type.application";\n'
        "\t\t};\n"
        "/* End PBXNativeTarget section */",
        '\t\t\tproductType = "com.apple.product-type.application";\n'
        "\t\t};\n"
        + NATIVE_AND_DEPS,
        "native target",
    )
    text = _must_replace(
        text,
        "\t\t\t\t\tA60000000000000000000001 = {\n"
        "\t\t\t\t\t\tCreatedOnToolsVersion = 15.4;\n"
        "\t\t\t\t\t};",
        "\t\t\t\t\tA60000000000000000000001 = {\n"
        "\t\t\t\t\t\tCreatedOnToolsVersion = 15.4;\n"
        "\t\t\t\t\t};\n"
        "\t\t\t\t\tB60000000000000000000001 = {\n"
        "\t\t\t\t\t\tCreatedOnToolsVersion = 15.4;\n"
        "\t\t\t\t\t\tTestTargetID = A60000000000000000000001;\n"
        "\t\t\t\t\t};",
        "target attributes",
    )
    text = _must_replace(
        text,
        "\t\t\ttargets = (\n"
        "\t\t\t\tA60000000000000000000001 /* LogBridge */,\n"
        "\t\t\t);",
        "\t\t\ttargets = (\n"
        "\t\t\t\tA60000000000000000000001 /* LogBridge */,\n"
        "\t\t\t\tB60000000000000000000001 /* LogBridgeUITests */,\n"
        "\t\t\t);",
        "targets",
    )
    text = _must_replace(
        text,
        "\t\t\t\tA10000000000000000000002 /* ContentView.swift in Sources */,\n",
        "\t\t\t\tA10000000000000000000002 /* ContentView.swift in Sources */,\n"
        "\t\t\t\tA1000000000000000000001A /* UIShotLaunch.swift in Sources */,\n",
        "app sources",
    )
    text = _must_replace(
        text,
        "/* End PBXSourcesBuildPhase section */",
        TEST_SOURCES + "/* End PBXSourcesBuildPhase section */",
        "test sources",
    )
    text = _must_replace(
        text,
        "/* End PBXFrameworksBuildPhase section */",
        TEST_FRAMEWORKS + "/* End PBXFrameworksBuildPhase section */",
        "test frameworks",
    )
    text = _must_replace(
        text,
        "/* End XCBuildConfiguration section */",
        TEST_CONFIGS + "/* End XCBuildConfiguration section */",
        "test configs",
    )
    text = _must_replace(
        text,
        "/* End XCConfigurationList section */",
        TEST_LIST + "/* End XCConfigurationList section */",
        "test config list",
    )
    return text


def wire_app(text: str) -> str:
    if "UIShotLaunch.isActive" in text:
        return text
    return _must_replace(text, APP_OLD, APP_NEW, "LogBridgeApp")


def wire_scheme(text: str) -> str:
    if "LogBridgeUITests.xctest" in text:
        return text
    text = _must_replace(
        text,
        "      </BuildActionEntries>",
        SCHEME_BUILD + "      </BuildActionEntries>",
        "scheme build",
    )
    text = _must_replace(
        text,
        '      shouldAutocreateTestPlan = "YES">\n   </TestAction>',
        SCHEME_TEST + "   </TestAction>",
        "scheme test",
    )
    return text


def wire_tree(worktree: Path, head: Path) -> None:
    app_src = worktree / "macos/LogBridge/LogBridge"
    project = worktree / "macos/LogBridge/LogBridge.xcodeproj/project.pbxproj"
    scheme = worktree / "macos/LogBridge/LogBridge.xcodeproj/xcshareddata/xcschemes/LogBridge.xcscheme"
    tests = worktree / "macos/LogBridge/LogBridgeUITests"
    if not project.is_file() or not scheme.is_file():
        raise SystemExit(f"wire_baseline_shot_launch: {worktree} is not a LogBridge checkout")
    shutil.copy2(head / "macos/LogBridge/LogBridge/UIShotLaunch.swift", app_src / "UIShotLaunch.swift")
    tests.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        head / "macos/LogBridge/LogBridgeUITests/LogBridgeUIShots.swift",
        tests / "LogBridgeUIShots.swift",
    )
    project.write_text(wire_project(project.read_text(encoding="utf-8")), encoding="utf-8")
    app = app_src / "LogBridgeApp.swift"
    app.write_text(wire_app(app.read_text(encoding="utf-8")), encoding="utf-8")
    scheme.write_text(wire_scheme(scheme.read_text(encoding="utf-8")), encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: wire_baseline_shot_launch.py WORKTREE HEAD", file=sys.stderr)
        return 2
    wire_tree(Path(argv[1]), Path(argv[2]))
    print("wire_baseline_shot_launch: checkout can launch injected sample shots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
