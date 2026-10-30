/*
   SPDX-FileCopyrightText: 2017 Marco Martin <mart@kde.org>

   SPDX-License-Identifier: LGPL-2.0-only
*/

pragma ComponentBehavior: Bound

import QtQuick 2.15
import QtQuick.Controls 2.5 as QQC2
import QtQuick.Layouts 1.1

import org.kde.kirigami 2.5 as Kirigami

import org.kde.systemsettings

Kirigami.ScrollablePage {
    id: subCategoryColumn
    title: systemsettings.subCategoryModel.title

    Kirigami.Theme.colorSet: Kirigami.Theme.Window // [CHANGE: claude-code | 2026-10-11] Luminos DECISION 140
    Kirigami.Theme.inherit: false
    verticalScrollBarPolicy: QQC2.ScrollBar.AlwaysOff // [CHANGE: claude-code | 2026-10-12] Luminos: no scrollbar (mock)

    header: Kirigami.AbstractApplicationHeader {
        id: pageHeader
        minimumHeight: 48 + 16 + 8 // [CHANGE: claude-code | 2026-10-12] Luminos: same header as the categories page
        preferredHeight: minimumHeight; maximumHeight: minimumHeight; separatorVisible: false
        leftPadding: subCategoryColumn.width < 160 ? 14 : 16; rightPadding: 16; topPadding: 16; bottomPadding: 8
        background: Item {}

        contentItem: RowLayout {
            id: rowLayout
            // FIXME: left and right anchors shouldn't be needed here, but if
            // they're removed, the layout doesn't span the full width
            anchors.fill: parent
            spacing: Kirigami.Units.smallSpacing

            Keys.onDownPressed: event => {
                subCategoryView.currentIndex = 0;
                event.accepted = false; // Pass to KeyNavigation.down
            }

            // Show a back Button when only one column is visible
            QQC2.ToolButton {
                id: backButton

                implicitHeight: 48
                visible: !applicationWindow().wideScreen

                padding: Kirigami.Units.smallSpacing
                leftPadding: subCategoryColumn.width < 160 ? 10 : 12; rightPadding: leftPadding + 2
                background: Rectangle { // Luminos: standalone tonal pill
                    radius: height / 2; Kirigami.Theme.colorSet: Kirigami.Theme.Button; Kirigami.Theme.inherit: false
                    color: backButton.hovered ? Qt.tint(Kirigami.Theme.backgroundColor, Qt.alpha(Kirigami.Theme.textColor, 0.08)) : Kirigami.Theme.backgroundColor
                }

                // Uncomment once QQC2.ToolButton can force-left-align its contents
                // text: subCategoryColumn.title
                // icon.name: LayoutMirroring.enabled ? "go-previous-symbolic-rtl" : "go-previous-symbolic"
                onClicked: systemsettings.openEdgeDrawer("left") // [CHANGE: claude-code | 2026-10-12] Luminos: "All settings" chip

                Accessible.name: buttonLabel.text

                // Need a custom content item to left-align everything, because
                // ToolButtons center everything when you force the width to be
                // higher than normal, which looks bad here
                contentItem: RowLayout {
                    Kirigami.Icon {
                        id: backIcon
                        source: "sidebar-expand-left"
                        fallback: "view-left-new"
                        Layout.leftMargin: Kirigami.Units.smallSpacing
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                        Layout.alignment: Qt.AlignCenter
                    }
                    QQC2.Label {
                        id: buttonLabel
                        visible: subCategoryColumn.width >= 160
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: i18nc("@action:button open the drawer with all settings", "All settings")
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }
                }

                KeyNavigation.right: hamburgerMenuButton
                KeyNavigation.down: subCategoryView
                KeyNavigation.tab: KeyNavigation.right
                Keys.onBacktabPressed: event => {
                    systemsettings.focusPrevious();
                }
                Keys.onDownPressed: event => {
                    rowLayout.Keys.downPressed(event);
                }
            }

            // Show a non-interactive heading when both columns are visible
            Kirigami.Heading {
                visible: subCategoryColumn.width >= 160
                Layout.fillWidth: true
                Layout.fillHeight: true
                // Don't be too short when the back and burger buttons aren't visible
                Layout.minimumHeight: Math.max(backButton.implicitHeight, hamburgerMenuButton.implicitHeight)
                Layout.leftMargin: backIcon.visible ? 0 : Kirigami.Units.smallSpacing
                level: 3
                text: subCategoryColumn.title
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                textFormat: Text.PlainText
            }

            HamburgerMenuButton {
                id: hamburgerMenuButton

                visible: !applicationWindow().wideScreen && subCategoryColumn.width >= 160

                KeyNavigation.left: backButton
                KeyNavigation.down: subCategoryView
                KeyNavigation.backtab: KeyNavigation.left
                KeyNavigation.tab: KeyNavigation.down

                Keys.onDownPressed: event => {
                    rowLayout.Keys.downPressed(event);
                }
            }
        }
    }

    ListView {
        id: subCategoryView

        anchors.fill: parent
        leftMargin: subCategoryColumn.width < 160 ? 14 : 16
        rightMargin: leftMargin < 16 ? 14 : 0 // wide: the ScrollablePage already keeps ~16 px on the right
        bottomMargin: 16
        model: systemsettings.subCategoryModel
        currentIndex: systemsettings.activeSubCategoryRow
        activeFocusOnTab: true
        keyNavigationWraps: true
        Accessible.role: Accessible.List

        KeyNavigation.up: backButton
        KeyNavigation.backtab: hamburgerMenuButton

        Keys.onUpPressed: event => {
            if (subCategoryView.currentIndex === 0) {
                subCategoryView.currentIndex = -1;
            }
            event.accepted = false; // Pass to KeyNavigation.up
        }
        Keys.onTabPressed: event => {
            systemsettings.focusNext();
        }

        onCountChanged: {
            if (count > 1) {
                if (root.pageStack.depth < 2) {
                    root.pageStack.push(subCategoryColumn);
                }
            } else {
                root.pageStack.pop(mainColumn)
            }
        }

        Connections {
            target: systemsettings
            function onActiveSubCategoryRowChanged() {
                subCategoryView.currentIndex = systemsettings.activeSubCategoryRow
                if (systemsettings.activeSubCategoryRow >= 0) {
                    if (subCategoryView.count > 1) {
                        subCategoryView.forceActiveFocus();
                    }
                    root.pageStack.currentIndex = 1;
                } else if (root.pageStack.currentIndex > 0) {
                    root.pageStack.currentIndex = 0;
                    if (root.pageStack.depth > 1) {
                        root.pageStack.pop();
                    }
                }
            }
        }

        delegate: CategoryItem {
            id: delegate

            required property int index
            required property var model
            required property int depth
            required property string iconName

            text: model.display
            icon.name: model.iconName
            description: model.comment ?? ""
            groupStart: index === 0
            groupEnd: index === ListView.view.count - 1

            // Indent items that are children of other KCMs within the same group
            leadingPadding: depth > 2 ? (( depth - 2 ) * Kirigami.Units.iconSizes.smallMedium) + Kirigami.Units.largeSpacing : 0

            highlighted: ListView.isCurrentItem

            onClicked: {
                systemsettings.loadModule(subCategoryView.model.index(index, 0));
            }
            onFocusChanged: {
                if (focus) {
                    onCurrentIndexChanged: subCategoryView.positionViewAtIndex(index, ListView.Contain);
                }
            }
            Keys.onEnterPressed: clicked();
            Keys.onReturnPressed: clicked();

            Keys.onEscapePressed: root.pageStack.currentIndex = 0;

            Keys.onLeftPressed: {
                if (LayoutMirroring.enabled) {
                    clicked();
                } else {
                    root.pageStack.currentIndex = 0;
                }
            }
            Keys.onRightPressed: {
                if (!LayoutMirroring.enabled) {
                    clicked();
                } else {
                    root.pageStack.currentIndex = 0;
                }
            }
        }
    }
}
