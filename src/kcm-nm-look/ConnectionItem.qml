/*
    SPDX-FileCopyrightText: 2016 Jan Grulich <jgrulich@redhat.com>

    SPDX-License-Identifier: LGPL-2.1-only OR LGPL-3.0-only OR LicenseRef-KDE-Accepted-LGPL
*/

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.networkmanagement as PlasmaNM
import org.luminos.style as LxS // [CHANGE: claude-code | 2026-11-08] LUMINOS (DECISION 177): Network-panel look: flat rows in one card,
// plain Wi-Fi glyph, "Security: WPA2 • Connected", gear on the active network, lock on secured ones.

QQC2.ItemDelegate {
    id: delegate

    required property var model
    required property string currentConnectionPath

    icon.name: model.KcmConnectionIcon

    property bool passwordIsStatic: (model.SecurityType === PlasmaNM.Enums.StaticWep || model.SecurityType == PlasmaNM.Enums.WpaPsk ||
                                     model.SecurityType === PlasmaNM.Enums.Wpa2Psk || model.SecurityType == PlasmaNM.Enums.SAE)
    property bool predictableWirelessPassword: !model.Uuid && model.Type === PlasmaNM.Enums.Wireless && passwordIsStatic
    property bool isUnknownNewConnection: model.ItemType !== PlasmaNM.NetworkModelItem.UnavailableConnection && delegate.isConnectionDeactivated() && !model.ConnectionPath

    // QQC2.ItemDelegate exposes the label text property, but not textFormat, so it's possible for model.Name to contain unescaped HTML.
    // Therefore we need to escape it manually. Going via i18n is a way to use something pre-exposed to QML.
    text: xi18nc("@label/rich", "%1", model.Name)

    property string subtitle: model.Type === PlasmaNM.Enums.Wireless ? wifiText() : itemText()
    readonly property bool lxActive: model.ConnectionState === PlasmaNM.Enums.Activated
    readonly property bool lxSecured: model.Type === PlasmaNM.Enums.Wireless && model.SecurityType !== PlasmaNM.Enums.NoneSecurity
    leftPadding: 24; rightPadding: 24
    topPadding: Math.max(8, 14 + LxS.Style.rowExtraPx / 2); bottomPadding: topPadding
    topInset: 0; bottomInset: 0
    background: Rectangle { // [CHANGE: claude-code | 2026-11-08] LUMINOS (DECISION 177): flat row, the selected one a shade lighter
        color: delegate.highlighted ? Qt.alpha(Kirigami.Theme.textColor, 0.07)
             : delegate.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.04) : "transparent"
        Behavior on color { ColorAnimation { duration: LxS.Style.animationShortMs } }
    }
    Accessible.description: subtitle

    checked: model.ConnectionPath && model.ConnectionPath === currentConnectionPath
    highlighted: checked || pressed

    signal aboutToChangeConnection(bool exportable, string name, string path)
    signal aboutToRemoveConnection(string name, string path)

    onClicked: {
        if (isUnknownNewConnection) {
            changeState()
        } else {
            aboutToChangeConnection(model.KcmVpnConnectionExportable, model.Name, model.ConnectionPath)
        }
    }
    Keys.onSpacePressed: aboutToChangeConnection(model.KcmVpnConnectionExportable, model.Name, model.ConnectionPath)

    TapHandler {
        id: mouseArea
        acceptedButtons: Qt.RightButton
        onTapped: connectionItemMenu.popup()
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.smallSpacing
        width: delegate.availableWidth
        implicitHeight: Math.max(iconTitleSubtitle.implicitHeight, Kirigami.Units.iconSizes.medium)

        Kirigami.Icon { // [CHANGE: claude-code | 2026-11-08] LUMINOS (DECISION 177): plain glyph, accent when connected
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth
            source: delegate.model.KcmConnectionIcon
            isMask: true
            color: delegate.lxActive ? Kirigami.Theme.focusColor : Kirigami.Theme.textColor
        }
        ColumnLayout {
            id: iconTitleSubtitle
            Layout.fillWidth: true
            Layout.leftMargin: 14
            spacing: 2
            QQC2.Label {
                Layout.fillWidth: true
                text: delegate.text
                textFormat: Text.StyledText
                elide: Text.ElideRight
                font.pixelSize: 16 * LxS.Style.textScale
                font.italic: delegate.model.ConnectionState === PlasmaNM.Enums.Activating
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: text.length > 0
                text: delegate.subtitle
                elide: Text.ElideRight
                opacity: 0.7
                font.pixelSize: 14 * LxS.Style.textScale
            }
        }
        Kirigami.Icon { // [CHANGE: claude-code | 2026-11-08] LUMINOS (DECISION 177): gear = edit this connection (connected one only)
            id: gearIcon
            visible: delegate.lxActive
            implicitWidth: Kirigami.Units.iconSizes.smallMedium + 2; implicitHeight: implicitWidth
            Layout.rightMargin: 5
            source: "emblem-system-symbolic" // a plain gear (YAMIS "configure" is a sliders glyph)
            isMask: true
            color: Kirigami.Theme.focusColor
            opacity: gearTap.pressed ? 0.6 : 1
            Accessible.role: Accessible.Button
            Accessible.name: i18nc("@action:button", "Configure")
            QQC2.ToolTip.text: Accessible.name
            QQC2.ToolTip.visible: gearHover.hovered
            HoverHandler { id: gearHover; cursorShape: Qt.PointingHandCursor }
            TapHandler {
                id: gearTap
                onTapped: delegate.aboutToChangeConnection(delegate.model.KcmVpnConnectionExportable, delegate.model.Name, delegate.model.ConnectionPath)
            }
        }
        Kirigami.Icon { // [CHANGE: claude-code | 2026-11-08] LUMINOS (DECISION 177): lock = needs a password
            visible: !delegate.lxActive && delegate.lxSecured && !connectingIndicator.visible
            implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth
            Layout.rightMargin: 6
            source: "object-locked"
            isMask: true
            color: Kirigami.Theme.textColor
            opacity: 0.85
        }

        PlasmaComponents3.BusyIndicator {
            id: connectingIndicator
            height: Kirigami.Units.iconSizes.medium
            width: Kirigami.Units.iconSizes.medium
            running: model.ConnectionState === PlasmaNM.Enums.Activating
            visible: running
        }
    }

    QQC2.Menu {
        id: connectionItemMenu

        QQC2.MenuItem {
            icon.name: delegate.isConnectionDeactivated() ? "network-connect-symbolic" : "network-disconnect-symbolic"
            text: delegate.isConnectionDeactivated() ? i18n("Connect") : i18n("Disconnect")
            enabled: model.ItemType === PlasmaNM.NetworkModelItem.AvailableConnection || model.ItemType === PlasmaNM.NetworkModelItem.AvailableAccessPoint
            onTriggered: changeState()
            QQC2.ToolTip.visible: !enabled && hovered
            QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            QQC2.ToolTip.text: i18nc("@info:tooltip", "Cannot connect to this network because it was not detected.")
        }
        QQC2.MenuItem {
            icon.name: "edit-copy"
            text: i18nc("@action:inmenu duplicate network connection", "Duplicate")
            visible: !delegate.isUnknownNewConnection

            onTriggered: kcm.onRequestDuplicateConnection(model.ConnectionPath)
        }

        QQC2.MenuItem {
            icon.name: "list-remove-symbolic"
            text: i18n("Delete");
            visible: !delegate.isUnknownNewConnection

            onTriggered: {
                delegate.aboutToRemoveConnection(delegate.model.Name, delegate.model.ConnectionPath)
            }
        }

        QQC2.MenuItem {
            icon.name: "document-export-symbolic"
            visible: model.KcmVpnConnectionExportable
            text: i18n("Export");

            onTriggered: kcm.onRequestExportConnection(model.ConnectionPath)
        }
    }

    function isConnectionDeactivated(): bool {
        return model.ConnectionState === PlasmaNM.Enums.Deactivated;
    }

    /* This generates the status description under each connection
       in the list at the left side of the applet. */
    function itemText() {
        if (model.ConnectionState === PlasmaNM.Enums.Activated) {
            return i18n("Connected")
        } else if (model.ConnectionState === PlasmaNM.Enums.Activating) {
            return i18n("Connecting")
        } else if (model.ItemType === PlasmaNM.NetworkModelItem.AvailableAccessPoint) {
            return i18nc("@title:column Available networks", "Available")
        } else {
            return model.LastUsed
        }
    }

    function wifiText() { // [CHANGE: claude-code | 2026-11-08] LUMINOS (DECISION 177): "Security: WPA2 • Connected / Saved"
        // short names like the Network panel: "WPA2-PSK" -> "WPA2", "WPA3-SAE" -> "WPA3"
        const short = (model.SecurityTypeString || "").replace(/[- ](PSK|SAE|Personal|Enterprise|EAP)\b.*$/i, "")
        const sec = short ? i18nc("@info", "Security: %1", short) : i18nc("@info", "Open")
        let state = ""
        if (model.ConnectionState === PlasmaNM.Enums.Activated) state = i18n("Connected")
        else if (model.ConnectionState === PlasmaNM.Enums.Activating) state = i18n("Connecting")
        else if (model.ConnectionPath) state = i18nc("@info a known network", "Saved")
        return state.length > 0 ? sec + " • " + state : sec
    }

    function changeState() {
        if (!predictableWirelessPassword && (model.ConnectionState == PlasmaNM.Enums.Deactivated || model.ConnectionState === PlasmaNM.Enums.Deactivating)) {
            if (!predictableWirelessPassword && !model.Uuid) {
                handler.addAndActivateConnection(model.DevicePath, model.SpecificPath)
            } else {
                handler.activateConnection(model.ConnectionPath, model.DevicePath, model.SpecificPath)
            }
        } else if (!predictableWirelessPassword) {
            handler.deactivateConnection(model.ConnectionPath, model.DevicePath)
        } else if (predictableWirelessPassword) {
            root.activateConnectionWithDialog(model.ItemUniqueName, model.DevicePath, model.SpecificPath, model.SecurityType)
        }
    }
}
