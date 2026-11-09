/*
    SPDX-FileCopyrightText: 2014 Eike Hein <hein@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.kde.private.desktopcontainment.folder as Folder
import org.kde.kitemmodels as KItemModels
import org.kde.kcmutils as KCM

KCM.ScrollViewKCM {
    id: configIcons

    property alias cfg_filterMode: filterMode.currentIndex
    property alias cfg_filterPattern: filterPattern.text
    property alias cfg_filterMimeTypes: mimeTypesModel.checkedTypes
    property alias cfg_showHiddenFiles: showHiddenFiles.checked

    KItemModels.KSortFilterProxyModel {
        id: filteredMimeTypesModel

        sourceModel: Folder.MimeTypesModel {
            id: mimeTypesModel
        }

        filterRegularExpression: RegExp(mimeFilter.text, "i")
        filterRoleName: "name"

        sortRoleName: "name"
        sortOrder: Qt.AscendingOrder

        function checkFiltered() {
            var types = [];

            for (var i = 0; i < count; ++i) {
                types.push(index(i, 0).data(Qt.UserRole));
            }

            mimeTypesModel.checkedTypes = types;
        }

        function uncheckFiltered() {
            var types = [];

            for (var i = 0; i < count; ++i) {
                types.push(index(i, 0).data(Qt.UserRole));
            }

            mimeTypesModel.checkedTypes = mimeTypesModel.checkedTypes
                .filter(x => types.indexOf(x) === -1);
        }
    }

    // [CHANGE: claude-code | 2026-11-09] DECISION 183 — Luminos look: "Which files" as a three-way switch, hidden
    // files as a switch; the pattern, search and type list only appear when they do something (not on "Show all").
    // Type rows are card rows with a tick box; ticking reassigns checkedTypes so Apply lights up (stock spliced the
    // array in place, which never told the window anything changed).
    // the Luminos kcmutils card behind the list (it has a "headerH" property) only shows while there is a list
    Component.onCompleted: {
        const walk = (it, depth) => {
            if (!it || depth > 4) return;
            for (const c of (it.children || [])) {
                if (c.hasOwnProperty("headerH")) { c.visible = Qt.binding(() => configIcons.filtering); return; }
                walk(c, depth + 1);
            }
        };
        walk(configIcons, 0);
        walk(configIcons.contentItem, 0);
    }
    readonly property bool filtering: filterMode.currentIndex > 0
    readonly property real pageWidth: Math.min(width - 48, Kirigami.Units.gridUnit * 40)

    function toggleType(name) {
        const list = mimeTypesModel.checkedTypes.slice();
        const idx = list.indexOf(name);
        if (idx >= 0) list.splice(idx, 1); else list.push(name);
        mimeTypesModel.checkedTypes = list;
    }

    header: Item {
        implicitHeight: headerColumn.implicitHeight + 8
        ColumnLayout {
            id: headerColumn
            width: configIcons.pageWidth
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 3

            ComboBox { // keeps the stock config binding; the segmented switch below drives it
                id: filterMode
                visible: false
                model: [i18nc("@item:inlistbox filter mode", "Show all"), i18nc("@item:inlistbox filter mode", "Show matching"), i18nc("@item:inlistbox filter mode", "Hide matching")]
            }

            LxRows.Card {
                first: true; last: false
                contentItem: RowLayout {
                    spacing: 12
                    LxRows.TitleText {
                        title: i18n("Which files")
                        subtitle: filterMode.currentIndex === 0 ? i18n("Every file in the folder is shown")
                                : filterMode.currentIndex === 1 ? i18n("Only files that match are shown")
                                : i18n("Files that match are hidden")
                    }
                    LxRows.Segmented {
                        options: [i18n("Show all"), i18n("Only these"), i18n("All except these")]
                        current: filterMode.currentIndex
                        onPicked: index => filterMode.currentIndex = index
                    }
                }
            }
            LxRows.Card {
                first: false; last: !configIcons.filtering; clickable: true
                onClicked: showHiddenFiles.toggle()
                contentItem: RowLayout {
                    spacing: 12
                    LxRows.TitleText { title: i18nc("@option:check prefix", "Show hidden files"); subtitle: i18n("Files whose name starts with a dot") }
                    Switch { id: showHiddenFiles }
                }
            }
            LxRows.Card {
                visible: configIcons.filtering
                first: false; last: true
                contentItem: RowLayout {
                    spacing: 12
                    LxRows.TitleText { title: i18nc("@label:textbox", "Name pattern"); subtitle: i18n("e.g. *.png *.jpg — separate with spaces") }
                    TextField {
                        id: filterPattern
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                        inputMethodHints: Qt.ImhNoPredictiveText
                        placeholderText: "*"
                    }
                }
            }

            RowLayout {
                visible: configIcons.filtering
                Layout.fillWidth: true
                Layout.topMargin: 14
                LxRows.Section {
                    Layout.topMargin: 0
                    Layout.fillWidth: true
                    text: i18n("File types · %1 ticked", mimeTypesModel.checkedTypes.length)
                }
            }
            Kirigami.SearchField {
                id: mimeFilter
                visible: configIcons.filtering
                Layout.fillWidth: true
                Layout.bottomMargin: 6
                placeholderText: i18n("Search file types…")
            }
            Label {
                visible: !configIcons.filtering
                Layout.fillWidth: true
                Layout.topMargin: 14
                Layout.leftMargin: 22
                wrapMode: Text.WordWrap
                opacity: 0.6
                text: i18n("Pick \"Only these\" or \"All except these\" to choose file types and a name pattern.")
            }
        }
    }

    view: ListView {
        id: mimeTypesView
        clip: true
        visible: configIcons.filtering
        spacing: 0
        topMargin: 8; bottomMargin: 8
        model: filteredMimeTypesModel
        // Signal the delegates listen to when user presses space to toggle current row.
        signal toggleCurrent()
        Keys.onSpacePressed: toggleCurrent()

        delegate: Item {
            id: delegate
            required property int index
            required property string name
            required property string comment
            required property var decoration
            width: mimeTypesView.width
            implicitHeight: row.implicitHeight
            ItemDelegate { // plain row on the list's card
                id: row
                width: configIcons.pageWidth - 16
                anchors.horizontalCenter: parent.horizontalCenter
                leftPadding: 16; rightPadding: 16; topPadding: 6; bottomPadding: 6
                background: Rectangle { radius: 14; color: row.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.06) : "transparent" }
                onClicked: configIcons.toggleType(delegate.name)
                contentItem: RowLayout {
                    spacing: 12
                    CheckBox {
                        checked: mimeTypesModel.checkedTypes.indexOf(delegate.name) >= 0
                        onToggled: configIcons.toggleType(delegate.name)
                    }
                    Kirigami.Icon {
                        implicitWidth: 28; implicitHeight: 28
                        animated: false // reused delegates, avoid animation when sorting/filtering
                        source: delegate.decoration
                    }
                    LxRows.TitleText { title: delegate.comment || delegate.name; subtitle: delegate.comment ? delegate.name : "" }
                }
            }
            Connections {
                target: mimeTypesView
                function onToggleCurrent() { if (mimeTypesView.currentIndex === delegate.index) configIcons.toggleType(delegate.name) }
            }
        }
    }

    footer: Item {
        implicitHeight: footRow.implicitHeight + 12
        visible: configIcons.filtering
        RowLayout {
            id: footRow
            width: configIcons.pageWidth
            anchors.centerIn: parent
            spacing: 8
            Button {
                icon.name: "edit-select-all"
                text: i18nc("@action:button", "Tick all shown")
                onClicked: filteredMimeTypesModel.checkFiltered()
            }
            Button {
                icon.name: "edit-select-none"
                text: i18nc("@action:button", "Untick all shown")
                onClicked: filteredMimeTypesModel.uncheckFiltered()
            }
            Item { Layout.fillWidth: true }
            Button {
                icon.name: filteredMimeTypesModel.sortOrder === Qt.AscendingOrder ? "view-sort-ascending-symbolic" : "view-sort-descending-symbolic"
                text: filteredMimeTypesModel.sortOrder === Qt.AscendingOrder ? i18n("A → Z") : i18n("Z → A")
                onClicked: {
                    filteredMimeTypesModel.sortOrder = filteredMimeTypesModel.sortOrder === Qt.AscendingOrder ? Qt.DescendingOrder : Qt.AscendingOrder;
                    filteredMimeTypesModel.sort(0, filteredMimeTypesModel.sortOrder);
                }
            }
        }
    }
}
