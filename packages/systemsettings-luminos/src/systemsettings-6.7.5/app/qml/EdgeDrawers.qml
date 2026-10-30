// SPDX-License-Identifier: LGPL-2.0-only
// [CHANGE: claude-code | 2026-10-12] Luminos edge drawers (Phase 5, DECISION 140): top = search, right = "On this page". In a transparent always-on-top QQuickWidget that SidebarMode sizes to the open drawer; created once.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: root
    property string kind: "top"
    property bool open: false
    property var sections: []
    property alias query: search.text
    Kirigami.Theme.colorSet: Kirigami.Theme.Window
    Kirigami.Theme.inherit: false

    function softClose() { closeTimer.restart() }
    function scrollTo(item) { // the nearest Flickable above the heading scrolls it to the top
        for (let p = item.parent; p; p = p.parent) {
            if (p.flickableDirection !== undefined) { p.contentY = Math.max(p.originY, item.mapToItem(p.contentItem, 0, 0).y - 16); return; }
        }
    }
    onOpenChanged: if (open && kind === "top") search.forceActiveFocus()
    Timer { id: closeTimer; interval: 220; onTriggered: if (!drawerHover.hovered && !(root.kind === "top" && search.text.length > 0)) systemsettings.openEdgeDrawer("") }
    Shortcut { sequence: "Escape"; onActivated: systemsettings.openEdgeDrawer("") }
    HoverHandler { id: drawerHover; onHoveredChanged: hovered ? closeTimer.stop() : closeTimer.restart() }

    Kirigami.ShadowedRectangle {
        id: panel
        readonly property bool isTop: root.kind === "top"
        width: isTop ? 520 : 280
        height: Math.min(column.implicitHeight + 32, root.height - 24)
        x: isTop ? (root.width - width) / 2 : (root.open ? root.width - width : root.width + 24)
        y: isTop ? (root.open ? 0 : -height - 24) : 0
        opacity: root.open ? 1 : 0
        Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on opacity { NumberAnimation { duration: 120 } }
        color: Kirigami.Theme.backgroundColor
        corners { topLeftRadius: panel.isTop ? 0 : 24; bottomLeftRadius: 24; bottomRightRadius: panel.isTop ? 24 : 0; topRightRadius: 0 }
        shadow { size: 24; color: Qt.rgba(0, 0, 0, 0.55) }

        ColumnLayout {
            id: column
            anchors { fill: parent; margins: 16 }
            spacing: 2
            QQC2.Label {
                text: panel.isTop ? "Search settings" : "On this page"
                color: Kirigami.Theme.disabledTextColor
                font { pixelSize: 12; weight: Font.Medium }
                Layout.bottomMargin: 6
            }
            Kirigami.SearchField {
                id: search
                autoAccept: false // accepted = Enter only (it navigates)
                visible: panel.isTop
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                onTextChanged: systemsettings.searchModel.filterRegExp = text
                onAccepted: {
                    for (let i = 0; i < results.count; ++i) {
                        const row = results.itemAtIndex(i);
                        if (row && row.visible) { row.clicked(); break; }
                    }
                }
                background: Rectangle { radius: height / 2; color: Qt.darker(Kirigami.Theme.backgroundColor, 1.6); border.color: search.activeFocus ? Kirigami.Theme.focusColor : Qt.alpha(Kirigami.Theme.disabledTextColor, 0.45) }
            }
            ListView { // up to 6 results, pages and sub-pages, as connected rows
                id: results
                visible: panel.isTop && count > 0
                Layout.fillWidth: true
                Layout.topMargin: 8
                Layout.preferredHeight: Math.min(contentHeight, 6 * 76)
                interactive: false
                clip: true
                model: panel.isTop && search.text.length > 0 ? systemsettings.searchModel : null
                delegate: CategoryItem {
                    required property int index
                    required property var model
                    required property bool isCategory
                    required property string iconName
                    text: model.display
                    icon.name: iconName
                    description: model.comment ?? ""
                    visible: !isCategory
                    height: visible ? implicitHeight : 0
                    groupStart: index <= 1
                    groupEnd: index === ListView.view.count - 1
                    onClicked: { systemsettings.loadModule(results.model.index(index, 0)); systemsettings.openEdgeDrawer(""); }
                }
            }
            Repeater {
                model: panel.isTop ? [] : root.sections
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    implicitHeight: 44
                    topLeftRadius: index === 0 ? 20 : 4; topRightRadius: topLeftRadius
                    bottomLeftRadius: index === root.sections.length - 1 ? 20 : 4; bottomRightRadius: bottomLeftRadius
                    color: area.containsMouse ? Qt.tint(Kirigami.Theme.alternateBackgroundColor, Qt.alpha(Kirigami.Theme.textColor, 0.08)) : Kirigami.Theme.alternateBackgroundColor
                    QQC2.Label { anchors { fill: parent; leftMargin: 14; rightMargin: 14 } verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; text: modelData.text }
                    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; onClicked: root.scrollTo(modelData) }
                }
            }
        }
    }
}
