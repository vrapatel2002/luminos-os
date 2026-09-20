/*
    Luminos Live Wallpaper — one tile in the installed-wallpaper gallery.
    SPEC §3.3.  SPDX-License-Identifier: GPL-3.0-or-later
    [CHANGE: claude-code | 2026-09-20]  BUG-185.

    Its own file for one reason and it is not line count: the grid had NO selected
    state, so clicking a tile changed a config key and nothing on screen. "I click
    them and nothing happens" was an accurate description of a gallery that was
    working. Selection, hover and press all live here now, where they are one
    thing to read rather than three conditions buried in a delegate.

    Kept deliberately dumb — it renders a row and emits a tap. `currentEntry` is
    handed down rather than worked out here, because which wallpaper is showing is
    a question only config.qml can answer (it owns the cfg_ keys), and a tile that
    guessed would be a second, drifting copy of that answer.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: tile

    property var modelData: ({})
    // The entry path the wallpaper is ACTUALLY showing. Empty means "nothing here".
    property string currentEntry: ""

    signal picked(string type, string entryPath)

    readonly property bool playable: modelData.playable === true
    readonly property bool current: tile.currentEntry.length > 0
                                 && ("" + modelData.entryPath) === tile.currentEntry
    readonly property string label: modelData.title || modelData.id || ""

    opacity: tile.playable ? 1.0 : 0.45

    // The whole tile, so the highlight reads as "this one" rather than as a
    // border drawn around a picture.
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: 4
        color: tap.pressed || tile.current ? Kirigami.Theme.highlightColor
             : hover.hovered ? Kirigami.Theme.alternateBackgroundColor
             : "transparent"
        opacity: tap.pressed ? 0.55 : tile.current ? 0.30 : 0.60
        border.width: tile.current ? 2 : 0
        border.color: Kirigami.Theme.highlightColor
        Behavior on opacity { NumberAnimation { duration: 80 } }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        spacing: 2
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Kirigami.Theme.alternateBackgroundColor
            radius: 3
            Image {
                anchors.fill: parent
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                source: tile.modelData.previewPath ? "file://" + tile.modelData.previewPath : ""
            }
            QQC2.Label {
                anchors.centerIn: parent
                visible: !tile.modelData.previewPath
                text: "▦"
                opacity: 0.4
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 2
            Kirigami.Icon {
                visible: tile.current
                source: "checkmark"
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: Kirigami.Units.iconSizes.small
            }
            QQC2.Label {
                Layout.fillWidth: true
                elide: Text.ElideRight
                // Not `font:` plus `font.bold:` — QML rejects a grouped property
                // that is also assigned whole.
                font.family: Kirigami.Theme.smallFont.family
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                font.bold: tile.current
                text: tile.label
            }
        }
    }

    QQC2.ToolTip.visible: hover.hovered
    // Built only while hovered. A grid of forty tiles otherwise formats forty
    // strings nobody asked for, and it keeps the text out of contexts that have
    // no KLocalizedContext (a bare qml6 harness) where it would only be noise.
    QQC2.ToolTip.text: !hover.hovered ? ""
                     : !tile.playable ? i18n("Cannot be shown yet: %1", tile.modelData.why)
                     : tile.current  ? i18n("%1 — %2 (showing now)", tile.label, tile.modelData.type)
                     : i18n("%1 — %2 · click to use it, then Apply", tile.label, tile.modelData.type)

    HoverHandler { id: hover }
    TapHandler {
        id: tap
        enabled: tile.playable
        onTapped: tile.picked("" + tile.modelData.type, "" + tile.modelData.entryPath)
    }
}
