#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-11-08] DECISION 176 — generates the *-luminos-tunables.patch for each fork.
# Input: a source tree that already has the fork's own patches applied (makepkg -o).
# It swaps the look literals (corners, gaps, paddings, widths, text px, durations) for
# org.luminos.style bindings whose defaults are the SAME numbers, then writes a diff.
# Every rule must match the expected number of times, or the script stops (no silent drift).
import difflib, os, re, shutil, sys

S = "LxS.Style."
IMPORT = "import org.luminos.style as LxS"

def R(old, new, n=1):
    return (old, new, n)

RULES = {
 "qqc2-desktop-style": {
  "org.kde.desktop/Frame.qml": [
    R("padding: 12 // luminos: room for the r28 corners", f"padding: Math.round({S}cardPaddingPx * 0.6) // luminos: room for the r28 corners"),
    R("radius: Math.min(28, width / 2, height / 2)", f"radius: Math.min({S}cornerOuterPx, width / 2, height / 2)")],
  "org.kde.desktop/ScrollView.qml": [
    R("radius: Math.min(28, width / 2, height / 2)", f"radius: Math.min({S}cornerOuterPx, width / 2, height / 2)")],
  "org.kde.desktop/Menu.qml": [R("        radius: 16\n", f"        radius: {S}cornerButtonPx\n")],
  "org.kde.desktop/MenuItem.qml": [R("        radius: 10\n", f"        radius: {S}cornerMenuItemPx\n")],
  "org.kde.desktop/private/DefaultListItemBackground.qml": [
    R("selected ? 32 : view === null ? 12 : first ? 28 : 4", f"selected ? {S}cornerSelectedPx : view === null ? 12 : first ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("selected ? 32 : view === null ? 12 : last ? 28 : 4", f"selected ? {S}cornerSelectedPx : view === null ? 12 : last ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("topMargin: 2 - background.control.topInset", f"topMargin: {S}rowHalfGapPx - background.control.topInset"),
    R("bottomMargin: 2 - background.control.bottomInset", f"bottomMargin: {S}rowHalfGapPx - background.control.bottomInset")],
 },
 "kirigami": {
  "src/forms/flat/FormEntry.qml": [
    R("Math.min(root.lxPrev instanceof FT.FormEntry ? 4 : 28, height / 2)", f"Math.min(root.lxPrev instanceof FT.FormEntry ? {S}cornerInnerPx : {S}cornerOuterPx, height / 2)"),
    R("Math.min(root.lxNext instanceof FT.FormEntry ? 4 : 28, height / 2)", f"Math.min(root.lxNext instanceof FT.FormEntry ? {S}cornerInnerPx : {S}cornerOuterPx, height / 2)"),
    R("anchors.topMargin: root.lxJoined ? -2 : 0", f"anchors.topMargin: root.lxJoined ? -{S}rowHalfGapPx : 0"),
    R("Layout.minimumHeight: lxJoined ? 0 : 60", f"Layout.minimumHeight: lxJoined ? 0 : {S}rowHeightPx"),
    R("leftMargin: 20\n", f"leftMargin: {S}cardPaddingPx\n"),
    R("rightMargin: 20\n", f"rightMargin: {S}cardPaddingPx\n"),
    R("leftMargin: root.lxStack || !formGroup ? 20 : 20 + ", f"leftMargin: root.lxStack || !formGroup ? {S}cardPaddingPx : {S}cardPaddingPx + ")],
  "src/forms/flat/FormGroup.qml": [
    R("spacing: 2 // LUMINOS", f"spacing: {S}rowHalfGapPx // LUMINOS"),
    R("leftPadding: 20\n", f"leftPadding: {S}cardPaddingPx\n")],
  "src/forms/templates/Form.qml": [R("Platform.Units.gridUnit * 42", f"{S}pageWidthPx")],
  "src/layouts/FormLayout.qml": [
    R("Platform.Units.gridUnit * 42", f"{S}pageWidthPx"),
    R("rowSpacing: 2 //", f"rowSpacing: {S}rowHalfGapPx //"),
    R("Layout.leftMargin: lxInline || lxSection ? 0 : 20", f"Layout.leftMargin: lxInline || lxSection ? 0 : {S}cardPaddingPx"),
    R("Layout.rightMargin: lxSection ? 0 : 20", f"Layout.rightMargin: lxSection ? 0 : {S}cardPaddingPx"),
    R("Layout.leftMargin: 20\n", f"Layout.leftMargin: {S}cardPaddingPx\n"),
    R("Layout.rightMargin: lxInline ? 0 : 20", f"Layout.rightMargin: lxInline ? 0 : {S}cardPaddingPx"),
    R("Math.max(implicitHeight, 36); // 60 px card row", f"Math.max(implicitHeight, 36 + {S}rowExtraPx); // 60 px card row"),
    R("Platform.Theme.defaultFont.pointSize * (lxSection ? 1.0 : 1.2)", f"Platform.Theme.defaultFont.pointSize * (lxSection ? {S}groupLabelPx / 12 : 1.2)"),
    R("Math.min(firstInGroup ? 28 : 4, height / 2)", f"Math.min(firstInGroup ? {S}cornerOuterPx : {S}cornerInnerPx, height / 2)"),
    R("Math.min(lastInGroup ? 28 : 4, height / 2)", f"Math.min(lastInGroup ? {S}cornerOuterPx : {S}cornerInnerPx, height / 2)")],
  "src/delegates/IconTitleSubtitle.qml": [R("Math.max(40, root.icon.width + 16)", f"Math.max({S}iconCirclePx, root.icon.width + 16)")],
 },
 "kirigami-addons": {
  "src/formcard/FormButtonDelegate.qml": [R("Math.max(40, iconSize + 16)", f"Math.max({S}iconCirclePx, iconSize + 16)")],
  "src/formcard/FormTextDelegate.qml": [R("Math.max(40, iconSize + 16)", f"Math.max({S}iconCirclePx, iconSize + 16)")],
  "src/formcard/FormCard.qml": [
    R("topLeftRadius: isFirst ? 28 : 4", f"topLeftRadius: isFirst ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("topRightRadius: isFirst ? 28 : 4", f"topRightRadius: isFirst ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("bottomLeftRadius: isLast ? 28 : 4", f"bottomLeftRadius: isLast ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("bottomRightRadius: isLast ? 28 : 4", f"bottomRightRadius: isLast ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("            spacing: 2\n", f"            spacing: {S}rowHalfGapPx\n")],
  "src/formcard/FormDelegateBackground.qml": [
    R("_luminos ? 28 : Kirigami.Units.cornerRadius", f"_luminos ? {S}cornerOuterPx : Kirigami.Units.cornerRadius"),
    R("_luminos ? 4 : 0", f"_luminos ? {S}cornerInnerPx : 0")],
 },
 "kcmutils": {
  "src/qml/components/ScrollViewKCM.qml": [
    R("radius: Math.min(28, height / 2)", f"radius: Math.min({S}cornerOuterPx, height / 2)"),
    R("Kirigami.Units.gridUnit * 42", f"{S}pageWidthPx")],
 },
 "systemsettings": {
  "app/qml/CategoriesPage.qml": [
    R("font.pixelSize: 16", f"font.pixelSize: 16 * {S}textScale"),
    R("font { pixelSize: 12; weight: Font.Medium; letterSpacing: 0.5 }", f"font {{ pixelSize: {S}groupLabelPx; weight: Font.Medium; letterSpacing: 0.5 }}")],
  "app/qml/CategoryItem.qml": [
    R("pressed ? 12 : highlighted ? 32 : groupStart ? 28 : 4", f"pressed ? 12 : highlighted ? {S}cornerSelectedPx : groupStart ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("pressed ? 12 : highlighted ? 32 : groupEnd ? 28 : 4", f"pressed ? 12 : highlighted ? {S}cornerSelectedPx : groupEnd ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("topInset: 2; bottomInset: 2; topPadding: 18; bottomPadding: 18",
      f"topInset: {S}rowHalfGapPx; bottomInset: {S}rowHalfGapPx; topPadding: Math.max(4, 18 + {S}rowExtraPx / 2); bottomPadding: topPadding"),
    R("Math.max(0, (width - 40) / 2)", f"Math.max(0, (width - {S}iconCirclePx) / 2)"),
    R("implicitWidth: 40; implicitHeight: 40; radius: 20", f"implicitWidth: {S}iconCirclePx; implicitHeight: {S}iconCirclePx; radius: {S}iconCirclePx / 2"),
    R("font.pixelSize: 16 }", f"font.pixelSize: 16 * {S}textScale }}"),
    R("opacity: 0.75; font.pixelSize: 13", f"opacity: 0.75; font.pixelSize: 13 * {S}textScale")],
  "app/qml/EdgeDrawers.qml": [R("font { pixelSize: 12; weight: Font.Medium }", f"font {{ pixelSize: {S}groupLabelPx; weight: Font.Medium }}")],
  "app/qml/Main.qml": [R("z: 3; width: 340;", f"z: 3; width: {S}sidebarWidthPx + 10;")],
  "app/qml/SideBarItem.qml": [R("? 72 : 330 + 32", f"? 72 : {S}sidebarWidthPx + 32")],
  "app/qml/SubCategoryPage.qml": [],
 },
}
# durations: our motion numbers in every file a luminos patch touched
DURATION_FILES = {
 "qqc2-desktop-style": ["org.kde.desktop/Menu.qml", "org.kde.desktop/MenuItem.qml", "org.kde.desktop/ToolTip.qml",
    "org.kde.desktop/private/DefaultListItemBackground.qml", "org.kde.desktop/private/M3RadioIndicator.qml",
    "org.kde.desktop/private/SwitchIndicator.qml"],
 "kirigami": ["src/delegates/IconTitleSubtitle.qml", "src/controls/InlineMessage.qml"],
 "kirigami-addons": [],
 "kcmutils": [],
 "systemsettings": ["app/qml/CategoryItem.qml", "app/qml/EdgeDrawers.qml", "app/qml/Main.qml"],
}
CPP = {
 "systemsettings": {
  "app/ModuleView.cpp": [
    R("static constexpr int LuminosHoleInset = 12;",
      "static constexpr int LuminosHoleInset = 12;\n"
      "// [CHANGE: claude-code | 2026-11-08] DECISION 176: page title size from the style tuner file (read per page load)\n"
      "static int luminosStylePx(const char *key, int fallback)\n"
      "{\n"
      "    QFile f(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral(\"/luminos/style.json\"));\n"
      "    if (!f.open(QIODevice::ReadOnly))\n"
      "        return fallback;\n"
      "    const QJsonValue v = QJsonDocument::fromJson(f.readAll()).object().value(QLatin1String(key));\n"
      "    return v.isDouble() ? qBound(14, qRound(v.toDouble()), 60) : fallback;\n"
      "}"),
    R("f.setPixelSize(30);", "f.setPixelSize(luminosStylePx(\"pageTitlePx\", 30));")],
 },
}
CPP_INCLUDES = {"systemsettings": {"app/ModuleView.cpp": ["#include <QFile>", "#include <QJsonDocument>", "#include <QJsonObject>", "#include <QStandardPaths>"]}}

def main(pkg, tree, out):
    orig = tree + ".orig-tunables"
    if os.path.exists(orig):
        shutil.rmtree(orig)
    shutil.copytree(tree, orig, symlinks=True)
    files = set(RULES.get(pkg, {})) | set(DURATION_FILES.get(pkg, [])) | set(CPP.get(pkg, {}))
    for rel in sorted(files):
        p = os.path.join(tree, rel)
        s = open(p).read()
        for old, new, n in RULES.get(pkg, {}).get(rel, []) + CPP.get(pkg, {}).get(rel, []):
            c = s.count(old)
            if c != n:
                sys.exit(f"FAIL {pkg}:{rel}: expected {n}x, found {c}x: {old!r}")
            s = s.replace(old, new)
        if rel in DURATION_FILES.get(pkg, []):
            s, k1 = re.subn(r"duration: 180\b", f"duration: {S}animationMs", s)
            s, k2 = re.subn(r"duration: 120\b", f"duration: {S}animationShortMs", s)
            print(f"  {rel}: durations 180x{k1} 120x{k2}")
        if rel.endswith(".qml") and S in s and IMPORT not in s:
            lines = s.split("\n")
            i = next(i for i, l in enumerate(lines) if l.startswith("import "))
            lines.insert(i, IMPORT + " // [CHANGE: claude-code | 2026-11-08] DECISION 176: live style values")
            s = "\n".join(lines)
        for inc in CPP_INCLUDES.get(pkg, {}).get(rel, []):
            if inc not in s:
                first = s.index("#include")
                s = s[:first] + inc + "\n" + s[first:]
        open(p, "w").write(s)
    # diff
    diff = []
    for rel in sorted(files):
        a = open(os.path.join(orig, rel)).read().splitlines(keepends=True)
        b = open(os.path.join(tree, rel)).read().splitlines(keepends=True)
        diff += difflib.unified_diff(a, b, "a/" + rel, "b/" + rel)
    open(out, "w").write("".join(diff))
    shutil.rmtree(orig)
    print(f"OK {pkg}: {len(files)} files -> {out} ({sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))} added lines)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
