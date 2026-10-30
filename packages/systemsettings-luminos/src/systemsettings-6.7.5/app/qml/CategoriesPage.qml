/*
   SPDX-FileCopyrightText: 2017 Marco Martin <mart@kde.org>

   SPDX-License-Identifier: LGPL-2.0-only
*/

pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.systemsettings

Kirigami.ScrollablePage {
    id: mainColumn
    readonly property bool searchMode: searchField.text.length > 0
    signal picked() // [CHANGE: claude-code | 2026-10-12] Luminos: closes the left drawer

    // [CHANGE: claude-code | 2026-10-11] Luminos Nexus sidebar (DECISION 140): on the Window colour; only the page "hole" is View
    Kirigami.Theme.colorSet: Kirigami.Theme.Window
    Kirigami.Theme.inherit: false
    verticalScrollBarPolicy: QQC2.ScrollBar.AlwaysOff // [CHANGE: claude-code | 2026-10-12] Luminos: no scrollbar (mock)

    header: Kirigami.AbstractApplicationHeader {
        id: pageHeader

        // TODO Plasma 6.6 align size to grid
        minimumHeight: 48 + 16 + 8
        preferredHeight: minimumHeight; maximumHeight: minimumHeight; separatorVisible: false
        leftPadding: 16; rightPadding: 16; topPadding: 16; bottomPadding: 8
        background: Item {}

        // Not visible; just to get its size so we can match this custom header
        // with the height of a standard header
        QQC2.ToolButton {
            id: sizeHelper
            visible: false
            icon.name: "go-previous"
        }

        contentItem: RowLayout {
            id: rowLayout
            // FIXME: left and right anchors shouldn't be needed here, but if
            // they're removed, the layout doesn't span the full width
            anchors.fill: parent
            spacing: 8

            Keys.onDownPressed: event => {
                categoryView.currentIndex = 0;
                event.accepted = false; // Pass to KeyNavigation.down
            }

            Kirigami.SearchField {
                id: searchField

                focus: !Kirigami.InputMethod.willShowOnActive
                visible: mainColumn.width >= 160
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                font.pixelSize: 16
                background: Rectangle {
                    radius: height / 2; Kirigami.Theme.colorSet: Kirigami.Theme.View; color: Qt.darker(Kirigami.Theme.backgroundColor, 1.35)
                    border.color: searchField.activeFocus ? Kirigami.Theme.focusColor : Qt.alpha(Kirigami.Theme.disabledTextColor, 0.45)
                }
                onTextChanged: {
                    systemsettings.searchModel.filterRegExp = text;
                }

                KeyNavigation.right: hamburgerMenuButton

                KeyNavigation.down: categoryView

                KeyNavigation.backtab: KeyNavigation.left
                KeyNavigation.tab: KeyNavigation.right

                Keys.onDownPressed: event => rowLayout.Keys.downPressed(event)
                onActiveFocusChanged: {
                    if (activeFocus) {
                        systemsettings.giveFocus();
                    }
                }
            }

            HamburgerMenuButton {
                id: hamburgerMenuButton

                KeyNavigation.left: searchField

                KeyNavigation.down: categoryView

                KeyNavigation.backtab: KeyNavigation.left
                KeyNavigation.tab: KeyNavigation.down

                Keys.onDownPressed: event => rowLayout.Keys.downPressed(event)
            }
        }
    }

    // We don't want it to go into default property and be reparented to a
    // ScrollView, otherwise after clearing search term the scrollbar would
    // appear and shift the fading out placeholder to the left.
    property Item __placeholder: Loader {
        parent: mainColumn
        anchors.centerIn: parent
        width: parent.width - (Kirigami.Units.gridUnit * 4)
        opacity: categoryView.count === 0 ? 1 : 0
        active: opacity > 0
        visible: active
        Behavior on opacity {
            NumberAnimation {
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
        }
        sourceComponent: Kirigami.PlaceholderMessage {
            width: parent.width
            icon.name: "edit-none"
            text: i18nc("A search yielded no results", "No items matching your search")
        }
    }

    Binding {
        target: categoryView
        property: "currentIndex"
        value: mainColumn.searchMode
            ? systemsettings.activeSearchRow
            : systemsettings.activeCategoryRow
    }

    ListView {
        id: categoryView

        model: mainColumn.searchMode ? systemsettings.searchModel : systemsettings.categoryModel

        activeFocusOnTab: true
        keyNavigationWraps: true
        Accessible.role: Accessible.List
        leftMargin: mainColumn.width < 160 ? 14 : 16
        rightMargin: leftMargin < 16 ? 14 : 0 // wide: the ScrollablePage already keeps ~16 px on the right
        bottomMargin: 16

        KeyNavigation.up: searchField
        KeyNavigation.backtab: hamburgerMenuButton
        Keys.onUpPressed: event => {
            if (categoryView.currentIndex === 0) {
                categoryView.currentIndex = -1;
            }
            event.accepted = false; // Pass to KeyNavigation.up
        }
        Keys.onTabPressed: {
            systemsettings.focusNext();
        }

        section {
            property: "categoryDisplayRole"
            delegate: QQC2.Label {
                required property string section

                width: ListView.view.width
                text: section
                visible: section.length > 0
                opacity: ListView.view.width >= 160 ? 1 : 0
                height: visible ? implicitHeight : 0
                topPadding: 14; bottomPadding: 4; leftPadding: 18
                font { pixelSize: 12; weight: Font.Medium; letterSpacing: 0.5 }
                color: Kirigami.Theme.disabledTextColor
            }
        }

        delegate: CategoryItem {
            id: delegate

            required property int index
            required property var model
            required property bool isCategory
            required property int depth
            required property bool isKCM
            required property string iconName

            text: model.display
            icon.name: iconName
            description: model.comment ?? ""
            groupStart: index === 0 || ListView.previousSection !== ListView.section
            groupEnd: index === ListView.view.count - 1 || ListView.nextSection !== ListView.section

            showArrow: {
                if (!isCategory) {
                    return false;
                }
                const modelIndex = delegate.ListView.view.model.index(index, 0)
                return delegate.ListView.view.model.rowCount(modelIndex) > 1
            }
            // Only indent subcategory icons in the search view
            leadingPadding: (depth > 1 && searchField.text.length > 0) ? (( depth - 1 ) * Kirigami.Units.iconSizes.smallMedium) + Kirigami.Units.largeSpacing : 0

            hoverEnabled: !isCategory || !mainColumn.searchMode
            enabled: !isCategory || !mainColumn.searchMode

            highlighted: ListView.isCurrentItem

            onClicked: {
                if (!enabled) { return; }
                if (isKCM || mainColumn.searchMode || systemsettings.activeCategoryRow !== index) {
                    systemsettings.loadModule(categoryView.model.index(index, 0));
                }
                if (!mainColumn.searchMode && root.pageStack.depth > 1) {
                    root.pageStack.currentIndex = 1;
                }
                mainColumn.picked();
            }
            onFocusChanged: {
                if (isCategory && mainColumn.searchMode) {
                    return;
                }
                if (focus) {
                    categoryView.positionViewAtIndex(index, ListView.Contain);
                }
            }
            Keys.onEnterPressed: clicked();
            Keys.onReturnPressed: clicked();

            Keys.onLeftPressed: {
                if (LayoutMirroring.enabled) {
                    clicked();
                }
            }
            Keys.onRightPressed: {
                if (!LayoutMirroring.enabled) {
                    clicked();
                }
            }
        }
    }
}
