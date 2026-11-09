/*
    Luminos Live Wallpaper — one tile in the installed-wallpaper gallery.
    SPEC §3.3.  SPDX-License-Identifier: GPL-3.0-or-later
    [CHANGE: claude-code | 2026-09-20]  BUG-185 — selected / hover / press live here, as one thing to read.
    [CHANGE: claude-code | 2026-11-09]  DECISION 183 — Luminos look: rounded 16:10 picture, accent ring +
    tick on the one in use, a kind tag (Video / Web / Shader…), name and kind under it. `tileData.add`
    makes the last tile an "Add wallpaper" button.

    Kept deliberately dumb — it renders a row and emits a tap. `currentEntry` is handed down because
    which wallpaper is showing is a question only config.qml can answer (it owns the cfg_ keys).
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Effects
import org.kde.kirigami as Kirigami

Item {
    id: tile

    property var tileData: ({})
    // The entry path the wallpaper is ACTUALLY showing. Empty means "nothing here".
    property string currentEntry: ""

    signal picked(string type, string entryPath)
    signal addRequested()

    readonly property bool isAdd: tileData.add === true
    readonly property bool playable: isAdd || tileData.playable === true
    readonly property bool current: !isAdd && tile.currentEntry.length > 0
                                 && ("" + tileData.entryPath) === tile.currentEntry
    readonly property string label: isAdd ? i18n("Add wallpaper…") : (tileData.title || tileData.id || "")
    readonly property string kind: {
        if (isAdd) return i18n("Video, web page or Lively .zip");
        const t = ("" + tileData.type).toLowerCase();
        return t === "video" ? i18n("Video") : t === "web" ? i18n("Web page") : t === "shader" ? i18n("Shader")
             : t === "js" ? i18n("Canvas script") : t === "scene" ? i18n("Scene") : t === "gif" ? i18n("Animated GIF")
             : t === "image" ? i18n("Picture") : t;
    }

    opacity: tile.playable ? 1.0 : 0.45

    Rectangle { // hover / press wash behind the whole tile
        anchors.fill: parent
        anchors.margins: 3
        radius: 16
        color: Kirigami.Theme.textColor
        opacity: tap.pressed ? 0.12 : hover.hovered ? 0.06 : 0
        Behavior on opacity { NumberAnimation { duration: 90 } }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 9
        spacing: 2

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Rectangle { // accent ring on the one in use
                anchors.fill: parent
                anchors.margins: -4
                radius: 15
                color: "transparent"
                border.width: tile.current ? 3 : 0
                border.color: Kirigami.Theme.focusColor
            }
            Rectangle {
                id: pic
                anchors.fill: parent
                radius: 12
                color: tile.isAdd ? "transparent" : Qt.alpha(Kirigami.Theme.textColor, 0.08)
                border.width: tile.isAdd ? 2 : 0
                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.18)
                Image {
                    anchors.fill: parent
                    anchors.margins: 0
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    visible: !tile.isAdd
                    source: !tile.isAdd && tile.tileData.previewPath ? "file://" + tile.tileData.previewPath : ""
                    layer.enabled: true
                    layer.effect: MultiEffect { maskEnabled: true; maskSource: picMask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 }
                }
                Rectangle { id: picMask; anchors.fill: parent; radius: 12; visible: false; layer.enabled: true }
                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: 28; height: 28
                    visible: tile.isAdd || !tile.tileData.previewPath
                    source: tile.isAdd ? "list-add" : "image-x-generic-symbolic"
                    opacity: 0.6
                }
                Rectangle { // kind tag
                    visible: !tile.isAdd
                    x: 6; y: 6
                    radius: height / 2
                    color: "#b0000000"
                    width: tagText.implicitWidth + 14; height: tagText.implicitHeight + 4
                    QQC2.Label { id: tagText; anchors.centerIn: parent; text: tile.kind.split(" ")[0]; color: "white"; font.pixelSize: 11 }
                }
            }
            Rectangle { // tick
                visible: tile.current
                anchors.top: parent.top; anchors.right: parent.right; anchors.margins: 6
                width: 22; height: 22; radius: 11
                color: Kirigami.Theme.focusColor
                Kirigami.Icon { anchors.centerIn: parent; width: 14; height: 14; source: "checkmark"; isMask: true; color: Kirigami.Theme.backgroundColor }
            }
        }
        QQC2.Label {
            Layout.fillWidth: true
            Layout.topMargin: 5
            elide: Text.ElideRight
            text: tile.label
            font.weight: tile.current ? Font.Medium : Font.Normal
        }
        QQC2.Label {
            Layout.fillWidth: true
            elide: Text.ElideRight
            text: tile.kind
            opacity: 0.55
            font.pointSize: Kirigami.Theme.smallFont.pointSize
        }
    }

    QQC2.ToolTip.visible: hover.hovered && !tile.isAdd
    QQC2.ToolTip.text: !hover.hovered || tile.isAdd ? ""
                     : !tile.playable ? i18n("Cannot be shown yet: %1", tile.tileData.why)
                     : tile.current  ? i18n("%1 — showing now", tile.label)
                     : i18n("%1 — click to use it, then Apply", tile.label)

    HoverHandler { id: hover; cursorShape: tile.playable ? Qt.PointingHandCursor : Qt.ArrowCursor }
    TapHandler {
        id: tap
        enabled: tile.playable
        onTapped: tile.isAdd ? tile.addRequested() : tile.picked("" + tile.tileData.type, "" + tile.tileData.entryPath)
    }
}
