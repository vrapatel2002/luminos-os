/*
    SPDX-FileCopyrightText: 2013 Marco Martin <mart@kde.org>
    SPDX-FileCopyrightText: 2020 Nicolas Fella <nicolas.fella@gmx.de>
    SPDX-FileCopyrightText: 2020 Carl Schwan <carlschwan@kde.org>
    SPDX-FileCopyrightText: 2022-2023 ivan tkachenko <me@ratijas.tk>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kcmutils as KCMUtils
import org.kde.kirigami as Kirigami
import org.kde.kitemmodels as KItemModels
import org.kde.plasma.configuration
import org.kde.plasma.plasmoid
import QtQuick.Effects

Rectangle {
    id: root

    implicitWidth: Kirigami.Units.gridUnit * 60 // [CHANGE: claude-code | 2026-11-09] DECISION 183: room for the sidebar + a two-column page
    implicitHeight: Kirigami.Units.gridUnit * 42

    Layout.minimumWidth: Kirigami.Units.gridUnit * 30
    Layout.minimumHeight: Kirigami.Units.gridUnit * 21

    LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    color: Kirigami.Theme.backgroundColor

    property bool isContainment: false

    property ConfigModel globalConfigModel:  globalAppletConfigModel

    property url currentSource

    property bool wasConfigurationChangedSignalSent: false

    // [CHANGE: claude-code | 2026-11-09] DECISION 183: sidebar search text + the item of the page that is open (for Undo)
    property string filterText: ""
    property var currentItemModel: null

    function closing() {
        if (applyButton.enabled) {
            messageDialog.item = null;
            messageDialog.open();
            return false;
        }
        return true;
    }

    function saveConfig() {
        const config = Plasmoid.configuration; // type: KConfigPropertyMap

        // call applet's own config handling first so it can set cfg_ properties if needed
        if (app.pageStack.currentItem.saveConfig) {
            app.pageStack.currentItem.saveConfig()
        }

        config.keys().forEach(key => {
            const cfgKey = "cfg_" + key;
            if (cfgKey in app.pageStack.currentItem) {
                config[key] = app.pageStack.currentItem[cfgKey];
            }
        })

        plasmoid.configuration.writeConfig();
    }

    function isConfigurationChanged() {
        const config = Plasmoid.configuration;
        return config.keys().some(key => {
            const cfgKey = "cfg_" + key
            if (!app.pageStack.currentItem.hasOwnProperty(cfgKey))
                return false
            return config[key] != app.pageStack.currentItem[cfgKey] &&
                   config[key].toString() != app.pageStack.currentItem[cfgKey].toString()
        })
    }

    Connections {
        target: configDialog
        function onClosing(event) {
            event.accepted = closing();
        }
    }

    ConfigModel {
        id: globalAppletConfigModel
        ConfigCategory {
            name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@title:group for configuration dialog page", "Keyboard Shortcuts")
            icon: "preferences-desktop-keyboard"
            source: Qt.resolvedUrl("ConfigurationShortcuts.qml")
        }
    }

    KItemModels.KSortFilterProxyModel {
        id: configDialogFilterModel
        sourceModel: configDialog.configModel
        filterRowCallback: (row, parent) => {
            return sourceModel.data(sourceModel.index(row, 0), ConfigModel.VisibleRole);
        }
    }

    function settingValueChanged() {
        applyButton.enabled = wasConfigurationChangedSignalSent || isConfigurationChanged() || (app?.pageStack?.currentItem?.unsavedChanges ?? false);
    }

    function pushReplace(item, config) {
        let page;
        if (app.pageStack.depth === 0) {
            page = app.pageStack.push(item, config);
        } else {
            page = app.pageStack.replace(item, config);
        }
        app.currentConfigPage = page;
        // [CHANGE: claude-code | 2026-11-09] DECISION 183: pages show the hole's colour, so the cards stand out
        if (page && page.background !== undefined) {
            page.background = null;
        }
    }

    function open(item) {
        root.currentItemModel = item; // [CHANGE: claude-code | 2026-11-09] DECISION 183
        app.isAboutPage = false;
        root.currentSource = item.source

        if (item.configUiModule && item.configUiComponent) {
            root.currentSource = item.configUiModule + item.configUiComponent; // Just for the highlight status
            const config = Plasmoid.configuration; // type: KConfigPropertyMap

            const props = {
                "title": item.name,
            };

            config.keys().forEach(key => {
                props["cfg_" + key] = config[key];
            });

            pushReplace(Qt.createComponent(item.configUiModule, item.configUiComponent), props);
        } else if (item.source) {
            app.isAboutPage = item.source === Qt.resolvedUrl("AboutPlugin.qml");

            const config = Plasmoid.configuration; // type: KConfigPropertyMap

            const props = { "title": item.name };

            config.keys().forEach(key => {
                props["cfg_" + key] = config[key];
            });

            pushReplace(Qt.resolvedUrl(item.source), props);
        } else {
            app.pageStack.pop();
        }

        applyButton.enabled = false
    }

    Connections {
        target: app.currentConfigPage
        ignoreUnknownSignals: true

        // This is an artifact of old internal architecture. If control beyond the automated
        // monitoring based on cfg_ properties is required, plasmoids should not emit
        // settingValueChanged() but configurationChanged() to force prompting the user
        // for saving changes, or use the unsavedChanges property to dynamically indicate
        // whether saving is needed in the current state).
        // We keep it around for now as third-party plasmoids might use it (even though they
        // really shouldn't as it's not documented).
        // TODO Plasma 7: remove and document in porting guide.
        function onSettingValueChanged() {
            wasConfigurationChangedSignalSent = true;
        }

        function onUnsavedChangesChanged() {
            root.settingValueChanged()
        }
    }

    Connections {
        target: app.pageStack

        function onCurrentItemChanged() {
            if (app.pageStack.currentItem !== null) {
                const config = Plasmoid.configuration; // type: KConfigPropertyMap

                config.keys().forEach(key => {
                    const changedSignal = app.pageStack.currentItem["cfg_" + key + "Changed"];
                    if (changedSignal) {
                        changedSignal.connect(() => root.settingValueChanged());
                    }
                });

                const configurationChangedSignal = app.pageStack.currentItem.configurationChanged;
                if (configurationChangedSignal) {
                    configurationChangedSignal.connect(() => {
                        root.wasConfigurationChangedSignalSent = true
                        root.settingValueChanged()
                    });
                }

                const configurationUnsavedChangesSignal = app.pageStack.currentItem.unsavedChangesChanged
                if (configurationUnsavedChangesSignal) {
                    configurationUnsavedChangesSignal.connect(() => root.settingValueChanged())
                }
            }
        }
    }

    // [CHANGE: claude-code | 2026-11-09] DECISION 183 test aid: with QML_XHR_ALLOW_FILE_READ=1, /tmp/luminos-deskcfg-test = "page=N" opens sidebar entry N
    Timer {
        interval: 1500; running: true
        onTriggered: {
            const xhr = new XMLHttpRequest();
            try { xhr.open("GET", "file:///tmp/luminos-deskcfg-test", false); xhr.send(); } catch (e) { return; }
            const m = ("" + xhr.responseText).match(/page=(\d+)/);
            if (!m) return;
            const rows = categories.children.filter(c => c.hasOwnProperty("highlighted") && c.visible);
            if (rows[+m[1]]) categories.openCategory(rows[+m[1]].item);
            testStep.text = "" + xhr.responseText;
            testStep.start();
        }
    }
    Timer { // test aid, second step: "scroll=PX", "surprise=1" (wallpaper page), "apply=1"
        id: testStep
        property string text: ""
        interval: 2500
        onTriggered: {
            const page = app.pageStack.currentItem;
            const sc = text.match(/scroll=(\d+)/);
            if (sc && page && page.flickable) page.flickable.contentY = +sc[1];
            if (/surprise=1/.test(text) && page && page.children) {
                const inner = page.flickable ? page.flickable.contentItem : page;
                const find = (it) => { if (!it) return null; if (typeof it.surprise === "function") return it;
                    for (let i = 0; i < (it.children || []).length; ++i) { const r = find(it.children[i]); if (r) return r; } return null; };
                const w = find(page);
                if (w) w.surprise();
                console.warn("[LUMINOS-DESKCFG] surprise", !!w, "dirty", applyButton.enabled);
            }
            if (/apply=1/.test(text)) {
                Qt.callLater(() => { console.warn("[LUMINOS-DESKCFG] before apply dirty", applyButton.enabled); applyAction.trigger(); console.warn("[LUMINOS-DESKCFG] after apply dirty", applyButton.enabled); });
            }
        }
    }

    Component.onCompleted: {
        // if we are a containment then the first item will be ConfigurationContainmentAppearance
        // if the applet does not have own configs then the first item will be Shortcuts
        if (isContainment || !configDialog.configModel || configDialog.configModel.count === 0) {
            open(root.globalConfigModel.get(0))
        } else {
            open(configDialog.configModel.get(0))
        }
    }

    function applicationWindow() {
        return app;
    }


    QQC2.ScrollView {
        id: categoriesScroll
        anchors {
            left: parent.left
            top: parent.top
            bottom: parent.bottom
        }
        // [CHANGE: claude-code | 2026-11-09] DECISION 183: System Settings style sidebar — search, grey label, rows with a round icon + hint
        width: Kirigami.Units.gridUnit * 15
        leftPadding: 14; rightPadding: 10; topPadding: 4; bottomPadding: 14
        contentWidth: availableWidth
        activeFocusOnTab: true
        focus: true
        Accessible.role: Accessible.PageTabList
        background: null

        Keys.onUpPressed: {
            const buttons = categories.children

            let foundPrevious = false
            for (let i = buttons.length - 1; i >= 0; --i) {
                const button = buttons[i];
                if (!button.hasOwnProperty("highlighted")) {
                    // not a ConfigCategoryDelegate
                    continue;
                }

                if (foundPrevious) {
                    categories.openCategory(button.item)
                    categoriesScroll.forceActiveFocus(Qt.TabFocusReason)
                    return
                } else if (button.highlighted) {
                    foundPrevious = true
                }
            }

            event.accepted = false
        }

        Keys.onDownPressed: {
            const buttons = categories.children

            let foundNext = false
            for (let i = 0, length = buttons.length; i < length; ++i) {
                const button = buttons[i];
                if (!button.hasOwnProperty("highlighted")) {
                    continue;
                }

                if (foundNext) {
                    categories.openCategory(button.item)
                    categoriesScroll.forceActiveFocus(Qt.TabFocusReason)
                    return
                } else if (button.highlighted) {
                    foundNext = true
                }
            }

            event.accepted = false
        }

        ColumnLayout {
            id: categories

            spacing: 3
            width: categoriesScroll.contentWidth
            focus: true

            // [CHANGE: claude-code | 2026-11-09] DECISION 183: which rows start / end the group (for the joined corners)
            property var firstRow: null
            property var lastRow: null
            function refreshEnds() {
                const rows = categories.children.filter(c => c.hasOwnProperty("highlighted") && c.visible);
                categories.firstRow = rows.length ? rows[0] : null;
                categories.lastRow = rows.length ? rows[rows.length - 1] : null;
            }
            Timer { id: endsTimer; interval: 0; onTriggered: categories.refreshEnds() }
            onChildrenChanged: endsTimer.restart()

            Kirigami.SearchField {
                id: sideSearch
                Layout.fillWidth: true
                Layout.bottomMargin: 10
                implicitHeight: 44
                placeholderText: i18nd("plasma_shell_org.kde.plasma.desktop", "Search settings")
                onTextChanged: { root.filterText = text.toLowerCase(); endsTimer.restart(); }
                background: Rectangle { radius: height / 2; color: Qt.alpha(Kirigami.Theme.textColor, 0.07) }
            }
            QQC2.Label {
                Layout.leftMargin: 14
                Layout.bottomMargin: 4
                text: root.isContainment ? i18nd("plasma_shell_org.kde.plasma.desktop", "Desktop & wallpaper") : i18nd("plasma_shell_org.kde.plasma.desktop", "Settings")
                opacity: 0.55
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }

            function openCategory(item) {
                if (applyButton.enabled) {
                    messageDialog.item = item;
                    messageDialog.open();
                    return;
                }
                open(item)
            }

            Component {
                id: categoryDelegate
                ConfigCategoryDelegate {
                    id: delegate
                    onActivated: categories.openCategory(model);
                    first: categories.firstRow === delegate
                    last: categories.lastRow === delegate
                    visible: root.filterText.length === 0 || ("" + model.name).toLowerCase().indexOf(root.filterText) >= 0
                    onVisibleChanged: endsTimer.restart()
                    highlighted: {
                        if (app.pageStack.currentItem) {
                            if (model.configUiModule && model.configUiComponent) {
                                return root.currentSource == (model.configUiModule + model.configUiComponent)
                            } else {
                                return root.currentSource == model.source
                            }
                        }
                        return false
                    }
                    item: model
                }
            }

            Repeater {
                Layout.fillWidth: true
                model: root.isContainment ? globalConfigModel : undefined
                delegate: categoryDelegate
            }
            Repeater {
                Layout.fillWidth: true
                model: configDialogFilterModel
                delegate: categoryDelegate
            }
            Repeater {
                Layout.fillWidth: true
                model: !root.isContainment ? globalConfigModel : undefined
                delegate: categoryDelegate
            }
            Repeater {
                Layout.fillWidth: true
                model: ConfigModel {
                    ConfigCategory{
                        name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@title:group for About dialog page", "About")
                        icon: "help-about"
                        source: Qt.resolvedUrl("AboutPlugin.qml")
                    }
                }
                delegate: categoryDelegate
            }
        }
    }

    Kirigami.Separator {
        visible: false // [CHANGE: claude-code | 2026-11-09] DECISION 183: no lines
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
        }
        z: 1
    }
    Kirigami.Separator {
        id: verticalSeparator
        visible: false
        anchors {
            top: parent.top
            left: categoriesScroll.right
            bottom: parent.bottom
        }
        z: 1
    }

    // [CHANGE: claude-code | 2026-11-09] DECISION 183: the pages sit in a rounded "hole" (View colour), like System Settings
    Rectangle {
        id: holeMask
        anchors.fill: hole
        radius: 24
        visible: false
        layer.enabled: true
    }
    Rectangle {
        id: holeBack
        anchors.fill: hole
        radius: 24
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false
        color: Kirigami.Theme.backgroundColor
    }
    Item {
        id: hole
        anchors {
            top: parent.top
            left: categoriesScroll.right
            right: parent.right
            bottom: parent.bottom
            leftMargin: 2; rightMargin: 12; bottomMargin: 12; topMargin: 2
        }
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: holeMask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }

    Kirigami.ApplicationItem {
        id: app
        anchors.fill: parent
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false

        pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.Auto
        wideScreen: true
        pageStack.globalToolBar.separatorVisible: false
        pageStack.globalToolBar.colorSet: Kirigami.Theme.View

        property var currentConfigPage: null
        property bool isAboutPage: false

        Kirigami.PromptDialog {
            id: messageDialog
            property var item
            title: i18ndc("plasma_shell_org.kde.plasma.desktop", "@title:window dialog title", "Apply Settings")
            subtitle: i18ndc("plasma_shell_org.kde.plasma.desktop", "@label dialog body", "The current page has unsaved changes. Apply the changes or discard them?")
            standardButtons: Kirigami.Dialog.Apply | Kirigami.Dialog.Discard | Kirigami.Dialog.Cancel
            onApplied: {
                applyAction.trigger()
                discarded();
            }
            onDiscarded: {
                wasConfigurationChangedSignalSent = false;
                if (item) {
                    root.open(item);
                    messageDialog.close();
                } else {
                    applyButton.enabled = false;
                    configDialog.close();
                }
            }
        }

        // [CHANGE: claude-code | 2026-11-09] DECISION 183: no OK / Apply / Cancel row. A small "Unsaved changes · Undo · Apply" bar appears only
        // when something changed; Close (or the window's ×) asks first if there are unsaved changes.
        footer: QQC2.Pane {
            padding: 12
            leftPadding: 22; rightPadding: 16
            background: Item {
                Item { id: bottomSeparator; visible: false } // kept: the page toolbar used to read it
            }
            contentItem: RowLayout {
                id: buttonsRow
                spacing: 8

                QQC2.Button { // the stock logic drives Apply through this button's "enabled"
                    id: applyButton
                    enabled: false
                    visible: false
                    onClicked: applyAction.trigger()
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !applyButton.enabled && !app.isAboutPage
                    text: i18nd("plasma_shell_org.kde.plasma.desktop", "Changes need Apply")
                    opacity: 0.5
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
                Item { Layout.fillWidth: true; visible: applyButton.enabled || app.isAboutPage }

                Rectangle {
                    visible: applyButton.enabled && !app.isAboutPage
                    radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.08)
                    implicitHeight: changedRow.implicitHeight + 10
                    implicitWidth: changedRow.implicitWidth + 24
                    RowLayout {
                        id: changedRow
                        anchors.centerIn: parent
                        spacing: 8
                        QQC2.Label { text: i18nd("plasma_shell_org.kde.plasma.desktop", "Unsaved changes"); Layout.rightMargin: 4 }
                        QQC2.Button {
                            text: i18nd("plasma_shell_org.kde.plasma.desktop", "Undo")
                            icon.name: "edit-undo"
                            onClicked: {
                                root.wasConfigurationChangedSignalSent = false;
                                const page = app.pageStack.currentItem;
                                if (page && page.originalWallpaper !== undefined && page.originalWallpaper.length > 0) {
                                    configDialog.currentWallpaper = page.originalWallpaper;
                                }
                                if (root.currentItemModel) {
                                    root.open(root.currentItemModel);
                                }
                            }
                        }
                        QQC2.Button {
                            text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "Apply")
                            icon.name: "dialog-ok-apply"
                            onClicked: applyAction.trigger()
                        }
                    }
                }
                QQC2.Button {
                    text: i18nd("plasma_shell_org.kde.plasma.desktop", "Close")
                    icon.name: "window-close"
                    onClicked: cancelAction.trigger()
                    KeyNavigation.tab: categories
                }
            }
        }

        QQC2.Action {
            id: acceptAction
            onTriggered: {
                applyAction.trigger();
                configDialog.close();
            }
        }

        QQC2.Action {
            id: applyAction
            onTriggered: {
                root.saveConfig()
                wasConfigurationChangedSignalSent = false
                applyButton.enabled = false;
            }
        }

        QQC2.Action {
            id: cancelAction
            onTriggered: {
                if (root.closing()) {
                    configDialog.close();
                }
            }
        }

        Keys.onReturnPressed: acceptAction.trigger();
        Keys.onEscapePressed: cancelAction.trigger();
    }
    } // hole
}
