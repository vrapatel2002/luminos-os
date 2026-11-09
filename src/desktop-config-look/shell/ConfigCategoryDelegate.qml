/*
    SPDX-FileCopyrightText: 2013 Marco Martin <mart@kde.org>
    SPDX-FileCopyrightText: 2020 Carl Schwan <carlschwan@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later

    [CHANGE: claude-code | 2026-11-09] DECISION 183 — Luminos look: a sidebar row like System Settings
    (round accent disc + title + one-line hint, rows joined into one group, selected = pill).
    Same signals / properties as stock, so AppletConfiguration.qml drives it unchanged.
*/

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Window

import org.kde.kirigami as Kirigami
import org.luminos.style as LxS

QQC2.ItemDelegate {
    id: delegate

    signal activated()

//BEGIN properties
    Layout.fillWidth: true
    hoverEnabled: true

    Accessible.role: Accessible.PageTab
    Accessible.name: model.name
    Accessible.description: i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:whatsthis Accessible description for sidebar entries opening configuration page", "Open configuration page")
    Accessible.onPressAction: delegate.clicked()

    focus: highlighted // need to actually focus highlighted items for the screen reader to see them

    property var item
    property bool first: false
    property bool last: false

    // one-line hint under the known page names; other pages (widgets) just show their name
    readonly property string hint: {
        const n = ("" + model.name).toLowerCase();
        if (n === "wallpaper") return i18nd("plasma_shell_org.kde.plasma.desktop", "Picture, video or live scene");
        if (n === "mouse actions") return i18nd("plasma_shell_org.kde.plasma.desktop", "What each click on the desktop does");
        if (n === "location") return i18nd("plasma_shell_org.kde.plasma.desktop", "Which folder the desktop shows");
        if (n === "icons") return i18nd("plasma_shell_org.kde.plasma.desktop", "Size, layout and sorting");
        if (n === "filter") return i18nd("plasma_shell_org.kde.plasma.desktop", "Which files appear");
        if (n === "about") return i18nd("plasma_shell_org.kde.plasma.desktop", "Version and credits");
        if (n === "keyboard shortcuts") return i18nd("plasma_shell_org.kde.plasma.desktop", "Keys that open this widget");
        if (n === "general" || n === "appearance") return i18nd("plasma_shell_org.kde.plasma.desktop", "How it looks and behaves");
        return "";
    }
//END properties

    onClicked: {
        if (highlighted) {
            return;
        }
        activated()
    }

    leftPadding: 10; rightPadding: 12; topPadding: 9; bottomPadding: 9
    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0

    background: Rectangle {
        readonly property real outer: 22
        readonly property real inner: 6
        color: delegate.highlighted ? Kirigami.Theme.highlightColor
             : (delegate.hovered || delegate.visualFocus) ? Qt.alpha(Kirigami.Theme.textColor, 0.10)
             : Qt.alpha(Kirigami.Theme.textColor, 0.05)
        topLeftRadius: delegate.highlighted ? height / 2 : (delegate.first ? outer : inner)
        topRightRadius: topLeftRadius
        bottomLeftRadius: delegate.highlighted ? height / 2 : (delegate.last ? outer : inner)
        bottomRightRadius: bottomLeftRadius
        border.width: delegate.visualFocus ? 2 : 0
        border.color: Kirigami.Theme.focusColor
        Behavior on color { ColorAnimation { duration: LxS.Style.animationShortMs } }
    }

    contentItem: RowLayout {
        spacing: 14
        Rectangle {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 40; implicitHeight: 40; radius: 20
            color: delegate.highlighted ? Kirigami.Theme.focusColor : (LxS.Style.iconDiscColor || Kirigami.Theme.focusColor)
            Kirigami.Icon {
                anchors.centerIn: parent
                width: 20; height: 20
                source: model.icon
                isMask: true
                roundToIconSize: false
                color: LxS.Style.iconGlyphColor || Kirigami.Theme.backgroundColor
            }
        }
        ColumnLayout {
            spacing: 1
            Layout.fillWidth: true
            QQC2.Label {
                id: nameLabel
                Layout.fillWidth: true
                text: model.name
                textFormat: Text.PlainText
                elide: Text.ElideRight
                font.weight: Font.Medium
                Accessible.ignored: true
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: delegate.hint.length > 0
                text: delegate.hint
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                opacity: 0.6
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                Accessible.ignored: true
            }
        }
    }
}
