/*
   SPDX-FileCopyrightText: 2017 Marco Martin <mart@kde.org>
   SPDX-FileCopyrightText: 2023 ivan tkachenko <me@ratijas.tk>

   SPDX-License-Identifier: LGPL-2.0-only
*/

import QtQuick 2.15

import org.kde.kirigami 2.20 as Kirigami

Item {
    id: root

    // properties, signals and methods used by C++ backend

    readonly property real headerHeight: sideBar.headerHeight

    implicitHeight: sideBar.implicitHeight
    implicitWidth: sideBar.implicitWidth + separator.implicitWidth

    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    // This is the background of the missing part of the sidebar's header
    Rectangle {
        anchors {
            top: parent.top
            right: parent.right
        }
        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Header
        visible: false // [CHANGE: claude-code | 2026-10-11] Luminos (DECISION 140): no strip, no separators
        color: Kirigami.Theme.backgroundColor
        width: separator.width
        height: sideBar.pageStack.currentItem?.header.height
    }

    SideBarItem {
        id: sideBar

        anchors.fill: parent
    }

    // [CHANGE: claude-code | 2026-10-12] Luminos left-edge drawer (Phase 5): the full main list over the
    // sub-page sidebar; opened by the edge hot zone or the "All settings" chip, closes 220 ms after leaving.
    readonly property alias pageStack: sideBar.pageStack // the drawer's CategoriesPage navigates through it
    property bool drawerOpen: false
    function setDrawerOpen(open) { drawerOpen = open && sideBar.pageStack.depth > 1 }
    Timer { id: drawerClose; interval: 220; onTriggered: if (!drawerHover.hovered) root.drawerOpen = false } // never close under the pointer (BUG-202 hover loop)
    Shortcut { sequence: "Escape"; enabled: root.drawerOpen; onActivated: root.drawerOpen = false }
    MouseArea { // 14 px hot zone with a 4x56 hint line (outline, 35 % / 90 % under the pointer)
        x: 0; y: 52; z: 2; width: 14; height: parent.height - 104; visible: sideBar.pageStack.depth > 1; hoverEnabled: true
        onEntered: systemsettings.openEdgeDrawer("left")
        onExited: if (!drawerHover.hovered) drawerClose.restart() // the drawer sliding over this zone is not "leaving"
        Rectangle { x: 4; width: 4; height: 56; radius: 2; y: (parent.height - height) / 2; color: Kirigami.Theme.disabledTextColor; opacity: parent.containsMouse ? 0.9 : 0.35 }
    }
    Kirigami.ShadowedRectangle {
        z: 3; width: 340; height: parent.height - 12
        x: root.drawerOpen ? 0 : -width - 32; opacity: root.drawerOpen ? 1 : 0; visible: opacity > 0
        Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on opacity { NumberAnimation { duration: 120 } }
        color: Kirigami.Theme.backgroundColor
        corners { topRightRadius: 24; bottomRightRadius: 24 }
        shadow { size: 24; color: Qt.rgba(0, 0, 0, 0.55) }
        HoverHandler { id: drawerHover; onHoveredChanged: hovered ? drawerClose.stop() : drawerClose.restart() }
        CategoriesPage { anchors.fill: parent; onPicked: root.drawerOpen = false }
    }

    Kirigami.Separator {
        visible: false
        z: 1
        anchors {
            top: parent.top
            topMargin: Kirigami.Units.largeSpacing
            right: parent.right
        }
        height: sideBar.pageStack.currentItem?.header.height - Kirigami.Units.largeSpacing * 2
        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Header
    }

    Kirigami.Separator {
        id: separator
        visible: false
        z: 1
        anchors {
            top: parent.top
            topMargin: sideBar.pageStack.currentItem?.header.height - Math.round(separator.width * systemsettings.devicePixelRatio) / systemsettings.devicePixelRatio
            right: parent.right
            bottom: parent.bottom
        }

        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Header
    }
}
