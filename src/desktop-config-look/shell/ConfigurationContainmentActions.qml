/*
    SPDX-FileCopyrightText: 2013 Marco Martin <mart@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kcmutils as KCM
import org.kde.kirigami as Kirigami

KCM.SimpleKCM {
    id: root

    signal configurationChanged

    property var prettyStrings: {
        "LeftButton": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Left-Button"),
        "RightButton": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Right-Button"),
        "MiddleButton": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Middle-Button"),
        "BackButton": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Back-Button"),
        "ForwardButton": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Forward-Button"),

        "wheel:Vertical": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Vertical-Scroll"),
        "wheel:Horizontal": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Horizontal-Scroll"),

        "ShiftModifier": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Shift"),
        "ControlModifier": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Ctrl"),
        "AltModifier": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Alt"),
        "MetaModifier": i18ndc("plasma_shell_org.kde.plasma.desktop", "@label for shortcuts", "Meta")
    }

    function saveConfig() {
        configDialog.currentContainmentActionsModel.save();
    }

    Connections {
        target: configDialog.currentContainmentActionsModel
        function onConfigurationChanged() {
            root.configurationChanged()
        }
    }

    // [CHANGE: claude-code | 2026-11-09] DECISION 183: one card row per mouse action (trigger · action · remove),
    // then an "Add an action" row. Same model calls as stock.
    ColumnLayout {
        id: mainColumn
        width: Math.min(parent.width, Kirigami.Units.gridUnit * 40)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 3

        LxRows.Section { text: i18nd("plasma_shell_org.kde.plasma.desktop", "On the empty desktop"); Layout.topMargin: 0 }

        Repeater {
            id: actionsRepeater
            model: configDialog.currentContainmentActionsModel

            LxRows.Card {
                id: actionRow
                required property int index
                required property var model
                first: index === 0
                last: false
                contentItem: RowLayout {
                    spacing: 12
                    MouseEventInputButton {
                        Layout.minimumWidth: Kirigami.Units.gridUnit * 9
                        icon.name: checked ? "input-mouse-symbolic" : "input-mouse"
                        defaultText: {
                            var splitAction = actionRow.model.action.split(';');
                            var button = splitAction[0];
                            var modifiers = (splitAction[1] || "").split('|').filter(function (item) {
                                return item !== "NoModifier";
                            });
                            var parts = modifiers;
                            modifiers.push(button);
                            return parts.map(function (item) {
                                return root.prettyStrings[item] || item;
                            }).join(i18ndc("plasma_shell_org.kde.plasma.desktop", "Concatenation sign for shortcuts, e.g. Ctrl+Shift", "+"));
                        }
                        eventString: actionRow.model.action
                        onEventStringChanged: {
                            configDialog.currentContainmentActionsModel.update(actionRow.index, eventString, actionRow.model.pluginName);
                        }
                        QQC2.ToolTip.text: i18nd("plasma_shell_org.kde.plasma.desktop", "Click, then press the mouse button (with Ctrl / Shift / Alt) to change it")
                        QQC2.ToolTip.visible: hovered
                    }
                    QQC2.ComboBox {
                        id: pluginsCombo
                        Layout.fillWidth: true
                        model: configDialog.containmentActionConfigModel
                        textRole: "name"
                        valueRole: "pluginName"
                        property bool initialized: false
                        Component.onCompleted: {
                            currentIndex = indexOfValue(actionRow.model.pluginName)
                            pluginsCombo.initialized = true;
                        }
                        onActivated: {
                            if (initialized) {
                                var newPluginName = currentValue;
                                if (newPluginName !== actionRow.model.pluginName) {
                                    configDialog.currentContainmentActionsModel.update(actionRow.index, actionRow.model.action, newPluginName);
                                }
                            }
                        }
                    }
                    QQC2.ToolButton {
                        icon.name: "configure"
                        visible: actionRow.model.hasConfigurationInterface
                        display: QQC2.AbstractButton.IconOnly
                        text: i18nd("plasma_shell_org.kde.plasma.desktop", "Settings for this action")
                        QQC2.ToolTip.text: text
                        QQC2.ToolTip.visible: hovered
                        onClicked: configDialog.currentContainmentActionsModel.showConfiguration(actionRow.index, this)
                    }
                    QQC2.ToolButton {
                        icon.name: "edit-delete-remove"
                        display: QQC2.AbstractButton.IconOnly
                        text: i18nd("plasma_shell_org.kde.plasma.desktop", "Remove this action")
                        QQC2.ToolTip.text: text
                        QQC2.ToolTip.visible: hovered
                        onClicked: configDialog.currentContainmentActionsModel.remove(actionRow.index)
                    }
                }
            }
        }

        LxRows.Card {
            first: actionsRepeater.count === 0
            last: true
            contentItem: RowLayout {
                spacing: 12
                MouseEventInputButton {
                    id: addButton
                    defaultText: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "Add Action")
                    icon.name: checked ? "input-mouse-symbolic" : "list-add"
                    onEventStringChanged: {
                        configDialog.currentContainmentActionsModel.append(eventString, "org.kde.contextmenu");
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.65
                    text: addButton.checked
                        ? i18nd("plasma_shell_org.kde.plasma.desktop", "Now press a mouse button or scroll on the button — hold Ctrl, Shift or Alt for a combination")
                        : i18nd("plasma_shell_org.kde.plasma.desktop", "Click, then press the mouse button you want to use")
                }
            }
        }
    }
}
