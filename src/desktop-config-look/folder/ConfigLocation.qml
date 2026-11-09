/*
    SPDX-FileCopyrightText: 2014 Eike Hein <hein@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import org.kde.plasma.plasmoid
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

import org.kde.private.desktopcontainment.folder as Folder

KCM.SimpleKCM {
    id: configLocation

    property string cfg_url
    property alias cfg_labelMode: labelMode.currentIndex
    property alias cfg_labelText: labelText.text
    property bool titleVisible: Plasmoid.containment != Plasmoid

    onCfg_urlChanged: applyConfig()

    function applyConfig(force) {
        if (!force && locationGroup.checkedButton !== null) {
            return;
        }

        if (cfg_url === "desktop:/") {
            locationDesktop.checked = true;
            locationCustomValue.text = "";
        } else if (cfg_url === "activities:/current/") {
            locationCurrentActivity.checked = true;
            locationCustomValue.text = "";
        } else {
            var placeForUrl = placesModel.indexForUrl(cfg_url);

            if (placeForUrl !== -1) {
                locationPlaceValue.currentIndex = placeForUrl; // needs to happen before checking the radiobutton
                locationPlace.checked = true;
                locationCustomValue.text = "";
            } else {
                locationCustom.checked = true;
                locationCustomValue.text = cfg_url;
            }
        }

        locationPlaceValue.enabled = locationPlace.checked;
    }

    Folder.PlacesModel {
        id: placesModel
        showDesktopEntry: false

        onPlacesChanged: configLocation.applyConfig(true)
    }

    ButtonGroup {
        id: locationGroup

        buttons: [locationDesktop, locationCurrentActivity, locationPlace, locationCustom]

        onCheckedButtonChanged: {
            if (checkedButton === locationDesktop) {
                configLocation.cfg_url = "desktop:/";
            } else if (checkedButton === locationCurrentActivity) {
                configLocation.cfg_url = "activities:/current/";
            }
        }
    }

    // [CHANGE: claude-code | 2026-11-09] DECISION 183 — Luminos look: each choice is its own card row with a
    // one-line explanation; the place list / custom path only appear on their row. Same ids and logic as stock.
    ColumnLayout {
        width: Math.min(parent.width, Kirigami.Units.gridUnit * 40)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 3

        LxRows.Section { text: i18n("The desktop shows"); Layout.topMargin: 0 }

        LxRows.Card {
            first: true; last: false; clickable: true
            onClicked: locationDesktop.checked = true
            contentItem: RowLayout {
                spacing: 14
                RadioButton { id: locationDesktop; Accessible.name: i18nc("@option:radio", "Desktop folder") }
                LxRows.TitleText { title: i18nc("@option:radio", "Desktop folder"); subtitle: i18n("Shows ~/Desktop — the usual choice") }
            }
        }
        LxRows.Card {
            visible: placesModel.activityLinkingEnabled
            first: false; last: false; clickable: true
            onClicked: locationCurrentActivity.checked = true
            contentItem: RowLayout {
                spacing: 14
                RadioButton { id: locationCurrentActivity; Accessible.name: i18nc("@option:radio", "Files linked to the current activity") }
                LxRows.TitleText { title: i18nc("@option:radio", "Files linked to the current activity"); subtitle: i18n("Each activity keeps its own desktop files") }
            }
        }
        LxRows.Card {
            first: false; last: false; clickable: !locationPlace.checked
            onClicked: locationPlace.checked = true
            contentItem: ColumnLayout {
                spacing: 8
                RowLayout {
                    spacing: 14
                    RadioButton {
                        id: locationPlace
                        Accessible.name: i18nc("@option:radio also label for combobox", "Places panel item:")
                        onCheckedChanged: {
                            locationPlaceValue.enabled = checked;
                        }
                    }
                    LxRows.TitleText { title: i18n("A place from the sidebar"); subtitle: i18n("Downloads, Documents, a drive…") }
                }
                ComboBox {
                    id: locationPlaceValue
                    visible: locationPlace.checked
                    Layout.fillWidth: true
                    Layout.leftMargin: 40
                    model: placesModel
                    textRole: "display"
                    enabled: true
                    onEnabledChanged: {
                        if (enabled && currentIndex !== -1) {
                            configLocation.cfg_url = Folder.DesktopSchemeHelper.getDesktopUrl(placesModel.urlForIndex(currentIndex));
                        }
                    }
                    onActivated: index => {
                        configLocation.cfg_url = Folder.DesktopSchemeHelper.getDesktopUrl(placesModel.urlForIndex(index));
                    }
                }
            }
        }
        LxRows.Card {
            first: false; last: true; clickable: !locationCustom.checked
            onClicked: locationCustom.checked = true
            contentItem: ColumnLayout {
                spacing: 8
                RowLayout {
                    spacing: 14
                    RadioButton { id: locationCustom; Accessible.name: i18nc("@option:radio also label for text field", "Custom location:") }
                    LxRows.TitleText { title: i18n("Another folder"); subtitle: i18n("Pick any folder or address") }
                }
                RowLayout {
                    visible: locationCustom.checked
                    Layout.fillWidth: true
                    Layout.leftMargin: 40
                    spacing: 8
                    TextField {
                        id: locationCustomValue
                        enabled: locationCustom.checked
                        Layout.fillWidth: true
                        placeholderText: i18nc("@info:placeholder custom location", "Type path or URL…")
                        inputMethodHints: Qt.ImhNoPredictiveText
                        onEnabledChanged: {
                            if (enabled && text !== "") {
                                configLocation.cfg_url = Folder.DesktopSchemeHelper.getDesktopUrl(text);
                            }
                        }
                        onTextChanged: {
                            if (enabled) {
                                configLocation.cfg_url = Folder.DesktopSchemeHelper.getDesktopUrl(text);
                            }
                        }
                    }
                    Button {
                        icon.name: "document-open"
                        text: i18n("Browse…")
                        enabled: locationCustom.checked
                        onClicked: directoryPicker.open()
                    }
                    Folder.DirectoryPicker {
                        id: directoryPicker
                        onUrlChanged: {
                            locationCustomValue.text = Folder.DesktopSchemeHelper.getDesktopUrl(url);
                        }
                    }
                }
            }
        }

        LxRows.Section { visible: configLocation.titleVisible; text: i18nc("@label:textbox custom widget title", "Title") }
        LxRows.Card {
            visible: configLocation.titleVisible
            first: true; last: true
            contentItem: RowLayout {
                spacing: 8
                ComboBox {
                    id: labelMode
                    visible: configLocation.titleVisible
                    model: [
                        i18nc("@item:inlistbox no title", "None"),
                        i18nc("@item:inlistbox default title", "Default"),
                        i18nc("@item:inlistbox full path as title", "Full path"),
                        i18nc("@item:inlistbox title from text input field", "Custom")
                    ]
                }
                TextField {
                    id: labelText
                    Layout.fillWidth: true
                    enabled: (labelMode.currentIndex === 3)
                    placeholderText: i18nc("@info:placeholder custom window title", "Enter title…")
                }
            }
        }
    }
}
