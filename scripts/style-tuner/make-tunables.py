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
  "src/delegates/IconTitleSubtitle.qml": [R("Math.max(40, root.icon.width + 16)", f"Math.max({S}iconCirclePx, root.icon.width + 16)"),
    R("(root.selected ? Platform.Theme.focusColor : Platform.Theme.highlightColor)",
      f"(root.selected ? Platform.Theme.focusColor : ({S}iconDiscColor || Platform.Theme.highlightColor))"),
    R("(root.selected ? root.__luminosOnPrimary : Platform.Theme.highlightedTextColor)",
      f"(root.selected ? root.__luminosOnPrimary : ({S}iconGlyphColor || Platform.Theme.highlightedTextColor))")],
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
    R("font { pixelSize: 12; weight: Font.Medium; letterSpacing: 0.5 }", f"font {{ pixelSize: {S}groupLabelPx; weight: Font.Medium; letterSpacing: 0.5 }}"),
    # R6 (2026-11-08): search bar size/position + sidebar bottom gap
    R("minimumHeight: 48 + 16 + 8", f"minimumHeight: {S}searchHeightPx + {S}searchTopPx + {S}searchBottomPx"),
    R("leftPadding: 16; rightPadding: 16; topPadding: 16; bottomPadding: 8",
      f"leftPadding: {S}searchLeftPx; rightPadding: {S}searchRightPx; topPadding: {S}searchTopPx; bottomPadding: {S}searchBottomPx"),
    R("Layout.preferredHeight: 48\n", f"Layout.preferredHeight: {S}searchHeightPx\n"),
    R("        bottomMargin: 16\n", f"        bottomMargin: {S}sidebarBottomPx\n"),
    # R7: the menu (☰) button can be hidden
    R("            HamburgerMenuButton {\n                id: hamburgerMenuButton\n",
      f"            HamburgerMenuButton {{\n                id: hamburgerMenuButton\n                visible: {S}showMenuButton\n")],
  "app/qml/CategoryItem.qml": [
    R("pressed ? 12 : highlighted ? 32 : groupStart ? 28 : 4", f"pressed ? 12 : highlighted ? {S}cornerSelectedPx : groupStart ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("pressed ? 12 : highlighted ? 32 : groupEnd ? 28 : 4", f"pressed ? 12 : highlighted ? {S}cornerSelectedPx : groupEnd ? {S}cornerOuterPx : {S}cornerInnerPx"),
    R("topInset: 2; bottomInset: 2; topPadding: 18; bottomPadding: 18",
      f"topInset: {S}rowHalfGapPx; bottomInset: {S}rowHalfGapPx; topPadding: Math.max(4, 18 + {S}rowExtraPx / 2); bottomPadding: topPadding"),
    R("Math.max(0, (width - 40) / 2)", f"Math.max(0, (width - {S}iconCirclePx) / 2)"),
    R("implicitWidth: 40; implicitHeight: 40; radius: 20", f"implicitWidth: {S}iconCirclePx; implicitHeight: {S}iconCirclePx; radius: {S}iconCirclePx / 2"),
    R("font.pixelSize: 16 }", f"font.pixelSize: 16 * {S}textScale }}"),
    R("opacity: 0.75; font.pixelSize: 13", f"opacity: 0.75; font.pixelSize: 13 * {S}textScale"),
    # R6: icon colour, glyph size, nudge left/right/up/down
    R("Layout.leftMargin: delegate.compact ? 0 : delegate.leadingPadding",
      f"Layout.leftMargin: (delegate.compact ? 0 : delegate.leadingPadding) + {S}iconOffsetXPx\n            transform: Translate {{ y: {S}iconOffsetYPx }}"),
    R("color: delegate.highlighted ? Kirigami.Theme.focusColor : Kirigami.Theme.highlightColor",
      f"color: delegate.highlighted ? Kirigami.Theme.focusColor : ({S}iconDiscColor || Kirigami.Theme.highlightColor)"),
    R("width: Kirigami.Units.iconSizes.smallMedium; height: width", f"width: {S}iconGlyphPx; height: width"),
    R("color: delegate.highlighted ? Kirigami.Theme.highlightColor : Kirigami.Theme.highlightedTextColor",
      f"color: delegate.highlighted ? Kirigami.Theme.highlightColor : ({S}iconGlyphColor || Kirigami.Theme.highlightedTextColor)")],
  "app/qml/EdgeDrawers.qml": [R("font { pixelSize: 12; weight: Font.Medium }", f"font {{ pixelSize: {S}groupLabelPx; weight: Font.Medium }}")],
  "app/qml/Main.qml": [R("z: 3; width: 340;", f"z: 3; width: {S}sidebarWidthPx + 10;")],
  "app/qml/SideBarItem.qml": [R("? 72 : 330 + 32", f"? 72 : {S}sidebarWidthPx + 32")],
  "app/qml/SubCategoryPage.qml": [
    R("visible: !applicationWindow().wideScreen && subCategoryColumn.width >= 160",
      f"visible: {S}showMenuButton && !applicationWindow().wideScreen && subCategoryColumn.width >= 160"),
    R("minimumHeight: 48 + 16 + 8", f"minimumHeight: {S}searchHeightPx + {S}searchTopPx + {S}searchBottomPx"),
    R("leftPadding: subCategoryColumn.width < 160 ? 14 : 16; rightPadding: 16; topPadding: 16; bottomPadding: 8",
      f"leftPadding: subCategoryColumn.width < 160 ? 14 : {S}searchLeftPx; rightPadding: {S}searchRightPx; topPadding: {S}searchTopPx; bottomPadding: {S}searchBottomPx"),
    R("implicitHeight: 48\n", f"implicitHeight: {S}searchHeightPx\n"),
    R("        bottomMargin: 16\n", f"        bottomMargin: {S}sidebarBottomPx\n")],
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
    R("f.setPixelSize(30);", "f.setPixelSize(luminosStylePx(\"pageTitlePx\", 30));"),
    R("    return v.isDouble() ? qBound(14, qRound(v.toDouble()), 60) : fallback;\n}",
      "    return v.isDouble() ? qBound(14, qRound(v.toDouble()), 60) : fallback;\n}\n"
      "// R6: bottom button bar margins. The base is what the code would set anyway; a key in the file overrides one side.\n"
      "static void luminosApplyButtons(QWidget *w)\n"
      "{\n"
      "    const QVariantList base = w->property(\"_lxBase\").toList();\n"
      "    if (base.size() != 4)\n"
      "        return;\n"
      "    QJsonObject o;\n"
      "    QFile f(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral(\"/luminos/style.json\"));\n"
      "    if (f.open(QIODevice::ReadOnly))\n"
      "        o = QJsonDocument::fromJson(f.readAll()).object();\n"
      "    const char *keys[4] = {\"buttonsLeftPx\", \"buttonsTopPx\", \"buttonsRightPx\", \"buttonsBottomPx\"};\n"
      "    int m[4];\n"
      "    for (int i = 0; i < 4; ++i) {\n"
      "        const QJsonValue v = o.value(QLatin1String(keys[i]));\n"
      "        m[i] = v.isDouble() ? qBound(0, qRound(v.toDouble()), 96) : base.at(i).toInt();\n"
      "    }\n"
      "    w->setContentsMargins(m[0], m[1], m[2], m[3]);\n"
      "}\n"
      "static void luminosSetButtonBase(QWidget *w, const QMargins &b)\n"
      "{\n"
      "    w->setProperty(\"_lxBase\", QVariantList{b.left(), b.top(), b.right(), b.bottom()});\n"
      "    luminosApplyButtons(w);\n"
      "}\n"
      "// R8 (BUG-232): some QtWidgets KCMs hard-code a page minimum (Wi-Fi: KCMForm 800x500 in kcm.ui). Our sidebar\n"
      "// leaves ~690 px for the page, so the scroll area grew a sideways scrollbar and clipped the right side.\n"
      "// Drop only big fixed minimum widths (>= 600 px); real content minimums (tabs, lists, labels) stay.\n"
      "// R9 (DECISION 177): Shawn wants the Wi-Fi Status details left aligned: labels left, section titles left, and the\n"
      "// form at the left edge instead of centred between two stretches. Each step checks first, so repeat passes are no-ops.\n"
      "static void luminosLeftAlign(QWidget *w)\n"
      "{\n"
      "    for (QFormLayout *f : w->findChildren<QFormLayout *>()) {\n"
      "        if (f->labelAlignment() != (Qt::AlignLeft | Qt::AlignVCenter))\n"
      "            f->setLabelAlignment(Qt::AlignLeft | Qt::AlignVCenter);\n"
      "    }\n"
      "    for (QLabel *l : w->findChildren<QLabel *>()) {\n"
      "        if (l->alignment() & Qt::AlignHCenter)\n"
      "            l->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);\n"
      "    }\n"
      "    QList<QHBoxLayout *> rows = w->findChildren<QHBoxLayout *>();\n"
      "    if (w->parentWidget())\n"
      "        if (auto *outer = qobject_cast<QHBoxLayout *>(w->parentWidget()->layout()))\n"
      "            rows.append(outer); // the tab's centring container (stretch | content | stretch)\n"
      "    for (QHBoxLayout *h : std::as_const(rows)) {\n"
      "        if (h->count() > 0 && h->itemAt(0)->spacerItem() && h->itemAt(0)->spacerItem()->sizeHint().width() >= 0\n"
      "            && !h->property(\"_lxLeft\").toBool()) {\n"
      "            h->itemAt(0)->spacerItem()->changeSize(0, 0, QSizePolicy::Fixed, QSizePolicy::Minimum);\n"
      "            h->setProperty(\"_lxLeft\", true);\n"
      "            h->invalidate();\n"
      "        }\n"
      "    }\n"
      "}\n"
      "static void luminosFitWidth(QWidget *root)\n"
      "{\n"
      "    if (!root)\n"
      "        return;\n"
      "    QList<QWidget *> all = root->findChildren<QWidget *>();\n"
      "    all.prepend(root);\n"
      "    for (QWidget *w : std::as_const(all)) {\n"
      "        if (w->minimumWidth() >= 600 && !w->isWindow())\n"
      "            w->setMinimumWidth(0);\n"
      "        if (auto *tb = qobject_cast<QTabBar *>(w); tb && !tb->usesScrollButtons())\n"
      "            tb->setUsesScrollButtons(true); // tabs scroll instead of forcing the page wider\n"
      "        if (w->objectName() == QLatin1String(\"connectionView\") && w->minimumWidth() > 240)\n"
      "            w->setMinimumWidth(240); // Wi-Fi list: upstream 300 px; 240 still fits names, frees room for the editor\n"
      "        if (w->objectName() == QLatin1String(\"connectionView\") && w->parentWidget()) // R9: list shares spare room 2:3\n"
      "            if (auto *box = qobject_cast<QBoxLayout *>(w->parentWidget()->layout()); box && box->count() == 2\n"
      "                && box->indexOf(w) == 0 && box->stretch(0) == 0 && box->stretch(1) == 0) {\n"
      "                box->setStretch(0, 2);\n"
      "                box->setStretch(1, 3);\n"
      "            }\n"
      "        if (QByteArray(w->metaObject()->className()) == \"ConnectionStatusWidget\")\n"
      "            luminosLeftAlign(w); // R9: Wi-Fi Status tab, everything left aligned\n"
      "    }\n"
      "}\n"
      "// KCMs build and rebuild widgets long after load (Wi-Fi recreates its editor tabs per connection, each tab content\n"
      "// with setMinimumWidth(600)). A size change posts LayoutRequest up the tree, so re-check the open KCMs then, once per\n"
      "// event-loop turn. Only widgets that still have a >= 600 px minimum are touched, so a pass that finds none is cheap.\n"
      "class LuminosFitFilter : public QObject\n"
      "{\n"
      "public:\n"
      "    static LuminosFitFilter *self()\n"
      "    {\n"
      "        static LuminosFitFilter *f = [] { auto *x = new LuminosFitFilter; qApp->installEventFilter(x); return x; }();\n"
      "        return f;\n"
      "    }\n"
      "    void add(QWidget *root)\n"
      "    {\n"
      "        m_roots.append(root);\n"
      "        luminosFitWidth(root);\n"
      "    }\n"
      "protected:\n"
      "    bool eventFilter(QObject *o, QEvent *e) override\n"
      "    {\n"
      "        if (e->type() == QEvent::LayoutRequest && o->isWidgetType() && !m_pending) {\n"
      "            m_pending = true;\n"
      "            QTimer::singleShot(0, this, [this] {\n"
      "                m_pending = false;\n"
      "                m_roots.removeAll(nullptr);\n"
      "                for (const auto &r : std::as_const(m_roots))\n"
      "                    luminosFitWidth(r);\n"
      "            });\n"
      "        }\n"
      "        return false;\n"
      "    }\n"
      "private:\n"
      "    QList<QPointer<QWidget>> m_roots;\n"
      "    bool m_pending = false;\n"
      "};"),
    R("    d->mButtons->setContentsMargins(16, 8, 16, 12);",
      "    luminosSetButtonBase(d->mButtons, QMargins(16, 8, 16, 12));\n"
      "    { // R6 (DECISION 176): re-apply the bar margins the moment the style tuner file changes\n"
      "        const QString lxDir = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral(\"/luminos\");\n"
      "        const QString lxFile = lxDir + QStringLiteral(\"/style.json\");\n"
      "        QDir().mkpath(lxDir);\n"
      "        auto *lxWatch = new QFileSystemWatcher(QStringList{lxDir}, this);\n"
      "        if (QFile::exists(lxFile))\n"
      "            lxWatch->addPath(lxFile);\n"
      "        auto lxReload = [this, lxWatch, lxFile] {\n"
      "            if (QFile::exists(lxFile) && !lxWatch->files().contains(lxFile))\n"
      "                lxWatch->addPath(lxFile);\n"
      "            luminosApplyButtons(d->mButtons);\n"
      "        };\n"
      "        connect(lxWatch, &QFileSystemWatcher::directoryChanged, this, lxReload);\n"
      "        connect(lxWatch, &QFileSystemWatcher::fileChanged, this, lxReload);\n"
      "    }"),
    R("    d->mButtons->setVisible(buttons != KCModule::NoAdditionalButton);\n}",
      "    d->mButtons->setVisible(buttons != KCModule::NoAdditionalButton);\n"
      "    // R12 (DECISION 178): the Wi-Fi page saves through its own Save bar. Apply/Reset only mean something while the\n"
      "    // classic editor holds unsaved changes, so they are hidden until then (and the empty bar with them).\n"
      "    if (activeModule && activeModule->metaData().pluginId() == QLatin1String(\"kcm_networkmanagement\") && !change) {\n"
      "        d->mApply->setVisible(false);\n"
      "        d->mReset->setVisible(false);\n"
      "        d->mButtons->setVisible(!d->mDefault->isHidden() || !d->mHelp->isHidden());\n"
      "    }\n"
      "}"),
    R("d->mButtons->setContentsMargins(style()->pixelMetric(QStyle::PM_LayoutLeftMargin),",
      "luminosSetButtonBase(d->mButtons, QMargins(style()->pixelMetric(QStyle::PM_LayoutLeftMargin),"),
    R("        moduleScroll->setWidget(kcm->widget());\n", "        moduleScroll->setWidget(kcm->widget());\n        LuminosFitFilter::self()->add(kcm->widget()); // R8 BUG-232\n"),
    R("PM_LayoutRightMargin),\n                                    style()->pixelMetric(QStyle::PM_LayoutBottomMargin));",
      "PM_LayoutRightMargin),\n                                    style()->pixelMetric(QStyle::PM_LayoutBottomMargin)));")],
 },
}
CPP_INCLUDES = {"systemsettings": {"app/ModuleView.cpp": ["#include <QFile>", "#include <QJsonDocument>", "#include <QJsonObject>", "#include <QStandardPaths>",
                                                          "#include <QDir>", "#include <QFileSystemWatcher>", "#include <QMargins>",
                                                          "#include <QTabBar>", "#include <QPointer>", "#include <QApplication>",
                                                          "#include <QFormLayout>", "#include <QHBoxLayout>", "#include <QLabel>"]}}

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
