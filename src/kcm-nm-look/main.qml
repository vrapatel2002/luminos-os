/*
    SPDX-FileCopyrightText: 2016 Jan Grulich <jgrulich@redhat.com>
    SPDX-License-Identifier: LGPL-2.1-only OR LGPL-3.0-only OR LicenseRef-KDE-Accepted-LGPL

    [CHANGE: claude-code | 2026-11-08] LUMINOS DECISION 178 — the Wi-Fi page, rebuilt to Shawn's approved prototype
    (docs/windowstyle/mock/wifi-page.html): ONE column. Page "list": Wi-Fi switch card, the connected network as a big card,
    Saved networks, Other networks, More. Page "details": one network as grouped rows (Status, Connection, Security,
    IP settings, Advanced) written through org.luminos.network, with a Save bar that appears only after a change.
    Page "extra": wired / VPN / other connections. The classic plasma-nm tab editor stays reachable (Advanced).
    Upstream entry points the C++ calls are kept: selectConnection(), deselectConnections(), activateConnectionWithDialog().
*/
import QtQuick
import QtQml.Models
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.networkmanagement as PlasmaNM
import org.kde.kirigami as Kirigami
import org.luminos.style as LxS
import org.luminos.network as LxN

QQC2.Page {
    id: root
    focus: true
    Kirigami.Theme.colorSet: Kirigami.Theme.Window
    background: Rectangle { // the same dark "hole" colour other settings pages sit on; cards are a shade lighter
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false
        color: Kirigami.Theme.backgroundColor
    }

    property string view: "list"          // "list" | "details" | "extra"
    property string detailPath: ""
    property string detailDevice: ""
    property string detailName: ""
    property bool detailExportable: false
    property string classicPath: ""       // classic tab editor open on the right
    property bool settled: false          // ignore the KCM's own selectConnection() at start-up
    property bool dirty: false

    Timer { interval: 1500; running: true; onTriggered: root.settled = true }

    Connections {
        target: PlasmaNM.Configuration
        function onManageVirtualConnectionsChanged() { editorProxyModel.invalidate() }
    }
    PlasmaNM.Handler { id: handler }
    PlasmaNM.KcmIdentityModel { id: connectionModel }
    PlasmaNM.EditorProxyModel { id: editorProxyModel; sourceModel: connectionModel }
    PlasmaNM.EnabledConnections { id: enabledConnections }

    // upstream dialogs read these
    QtObject {
        id: connectionView
        property string currentConnectionPath
        property string currentConnectionName
        property bool currentConnectionExportable: false
    }

    // ---------- sorting the one model into groups ----------
    function classify(m) {
        if (m.Type !== PlasmaNM.Enums.Wireless) return m.ConnectionPath ? "extra" : ""
        if (m.ConnectionState === PlasmaNM.Enums.Activated || m.ConnectionState === PlasmaNM.Enums.Activating) return "connected"
        if (m.ConnectionPath) return "saved"
        return m.ItemType === PlasmaNM.NetworkModelItem.AvailableAccessPoint ? "other" : ""
    }
    function shortSecurity(s) { return (s || "").replace(/[- ](PSK|SAE|Personal|Enterprise|EAP)\b.*$/i, "") }
    function secured(m) { return m.SecurityType !== PlasmaNM.Enums.NoneSecurity && m.SecurityType !== undefined }
    function signalWord(sig) { return sig >= 75 ? i18n("Excellent") : sig >= 50 ? i18n("Good") : sig >= 25 ? i18n("Fair") : i18n("Weak") }

    Timer { id: regroupTimer; interval: 120; onTriggered: { heroModel.regroup(); savedModel.regroup(); otherModel.regroup(); extraModel.regroup() } }
    Connections {
        target: editorProxyModel
        function onDataChanged() { regroupTimer.restart() }
        function onRowsInserted() { regroupTimer.restart() }
        function onRowsRemoved() { regroupTimer.restart() }
        function onModelReset() { regroupTimer.restart() }
        function onLayoutChanged() { regroupTimer.restart() }
    }
    Component.onCompleted: {
        regroupTimer.start()
        const t = net.testOpenPath()
        if (t === "hidden") Qt.callLater(() => root.view = "hidden")   // test aid
        else if (t.length > 0) Qt.callLater(() => {
            root.openDetails(t.split("#")[0], "", "", false)
            const y = parseInt(t.split("#")[1] || "0")   // test aid: "<path>#<scroll px>" also opens Advanced
            if (y > 0) { advToggle.checked = true; Qt.callLater(() => detailsFlick.contentY = y) }
        })
    }

    component GroupModel: DelegateModel {
        id: gm
        property string want
        property alias shownCount: shownGroup.count
        model: editorProxyModel
        groups: [ DelegateModelGroup { id: shownGroup; name: "shown" } ]
        filterOnGroup: "shown"
        function regroup() {
            for (let i = 0; i < items.count; ++i) {
                const it = items.get(i)
                const yes = root.classify(it.model) === want
                if (it.inShown !== yes) it.inShown = yes
            }
        }
    }

    // R12: several manual addresses ("address/prefix" each) + one router
    component AddressList: ColumnLayout {
        id: al
        property var addresses: []
        property string example
        property string router
        property string routerExample
        signal addressesEdited(var list)
        signal routerEdited(string r)
        Layout.fillWidth: true
        spacing: 8
        Repeater {
            model: al.addresses
            RowLayout {
                required property string modelData
                required property int index
                Layout.fillWidth: true
                spacing: 6
                QQC2.TextField {
                    Layout.fillWidth: true
                    text: modelData
                    placeholderText: i18n("Address/prefix, e.g. %1", al.example)
                    onTextEdited: dcol.edit()
                    onEditingFinished: if (text !== modelData) { const l = al.addresses.slice(); l[index] = text.trim(); al.addressesEdited(l) }
                    Accessible.name: i18n("Address %1", index + 1)
                }
                QQC2.ToolButton {
                    visible: al.addresses.length > 1
                    icon.name: "list-remove"
                    display: QQC2.AbstractButton.IconOnly
                    text: i18n("Remove this address")
                    onClicked: { const l = al.addresses.slice(); l.splice(index, 1); al.addressesEdited(l) }
                    QQC2.ToolTip.text: text
                    QQC2.ToolTip.visible: hovered
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            QQC2.Button { text: i18n("Add another address"); icon.name: "list-add"; onClicked: al.addressesEdited(al.addresses.concat([""])) }
            QQC2.TextField {
                Layout.fillWidth: true
                text: al.router
                placeholderText: i18n("Router, e.g. %1", al.routerExample)
                onTextEdited: dcol.edit()
                onEditingFinished: if (text !== al.router) al.routerEdited(text.trim())
                Accessible.name: i18n("Router")
            }
        }
    }

    // ---------- actions ----------
    function openDetails(path, name, device, exportable) {
        detailPath = path; detailName = name; detailDevice = device || ""; detailExportable = !!exportable
        net.path = ""; net.path = path   // force a fresh read
        dirty = false
        view = "details"
        detailsFlick.contentY = 0
    }
    function backToList() {
        if (classicPath.length > 0) closeClassic()
        view = detailPath.length > 0 && net.kind !== "wifi" ? "extra" : "list"
        detailPath = ""
        net.path = ""
        dirty = false
    }
    function openClassic() { classicPath = detailPath; kcm.onSelectedConnectionChanged(detailPath) }
    function closeClassic() { classicPath = ""; kcm.onSelectedConnectionChanged("") }
    function tapNetwork(m) {
        const kind = classify(m)
        if (kind === "saved" && m.ItemType === PlasmaNM.NetworkModelItem.AvailableConnection) {
            handler.activateConnection(m.ConnectionPath, m.DevicePath, m.SpecificPath)
        } else if (kind === "saved") {
            openDetails(m.ConnectionPath, m.Name, m.DevicePath, m.KcmVpnConnectionExportable)
        } else if (kind === "other") {
            const predictable = m.SecurityType === PlasmaNM.Enums.StaticWep || m.SecurityType === PlasmaNM.Enums.WpaPsk
                             || m.SecurityType === PlasmaNM.Enums.Wpa2Psk || m.SecurityType === PlasmaNM.Enums.SAE
            if (predictable) root.activateConnectionWithDialog(m.ItemUniqueName, m.DevicePath, m.SpecificPath, m.SecurityType)
            else handler.addAndActivateConnection(m.DevicePath, m.SpecificPath)
        } else {
            openDetails(m.ConnectionPath, m.Name, m.DevicePath, m.KcmVpnConnectionExportable)
        }
    }

    LxN.NetworkConnection {
        id: net
        onSaveFinished: (ok, message) => {
            if (ok) { root.dirty = false; saveMessage.text = ""; savedToast.restart() }
            else saveMessage.text = i18nc("@info", "Couldn't save: %1", message)
        }
        onForgotten: root.backToList()
        onJoinFinished: (ok, message) => {
            if (ok) { root.view = "list"; regroupTimer.restart() }
            else hiddenMessage.text = i18n("Couldn't join: %1", message)
        }
    }
    Timer { interval: 3000; repeat: true; running: root.view === "details" && root.visible; onTriggered: net.refreshStatus() }

    // ================= page: list =================
    QQC2.ScrollView {
        id: listPage
        anchors.fill: parent
        background: null
        visible: opacity > 0
        opacity: root.view === "list" ? 1 : 0
        x: root.view === "list" ? 0 : -40
        Behavior on opacity { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        Behavior on x { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

        ColumnLayout {
            width: Math.min(listPage.availableWidth - 8, 720)
            x: (listPage.availableWidth - width) / 2
            spacing: 3

            Rows.Card { // Wi-Fi on/off
                first: true; last: true
                contentItem: RowLayout {
                    spacing: 16
                    Kirigami.Icon { source: "network-wireless-symbolic"; isMask: true; color: Kirigami.Theme.focusColor; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth }
                    Rows.TitleText {
                        title: i18nc("@title", "Wi-Fi")
                        subtitle: enabledConnections.wirelessEnabled ? i18nc("@info", "On · %1 networks nearby", otherModel.shownCount + savedModel.shownCount + heroModel.shownCount) : i18nc("@info", "Off")
                    }
                    QQC2.Switch {
                        checked: enabledConnections.wirelessEnabled
                        onToggled: handler.enableWireless(checked)
                        Accessible.name: i18nc("@title", "Wi-Fi")
                    }
                }
            }

            ColumnLayout {
                visible: enabledConnections.wirelessEnabled
                Layout.fillWidth: true
                spacing: 3

                Rows.Section { text: i18nc("@title:group", "Connected"); visible: heroModel.shownCount > 0 }
                Repeater {
                    model: GroupModel {
                        id: heroModel
                        want: "connected"
                        delegate: Rows.Card {
                            id: hero
                            required property var model
                            clickable: true
                            minHeight: 92
                            topPadding: 16; bottomPadding: 16
                            onClicked: root.openDetails(model.ConnectionPath, model.Name, model.DevicePath, model.KcmVpnConnectionExportable)
                            Accessible.name: i18nc("@action", "%1 details", model.Name)
                            contentItem: RowLayout {
                                spacing: 18
                                Rectangle {
                                    implicitWidth: 52; implicitHeight: 52; radius: 26
                                    color: Qt.alpha(Kirigami.Theme.focusColor, 0.18)
                                    Kirigami.Icon { anchors.centerIn: parent; width: 28; height: 28; source: hero.model.KcmConnectionIcon; isMask: true; color: Kirigami.Theme.focusColor }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    QQC2.Label { Layout.fillWidth: true; text: hero.model.Name; elide: Text.ElideRight; textFormat: Text.PlainText; font.pixelSize: 19 * LxS.Style.textScale }
                                    RowLayout {
                                        spacing: 8
                                        Rectangle { implicitWidth: 8; implicitHeight: 8; radius: 4; color: hero.model.ConnectionState === PlasmaNM.Enums.Activated ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor }
                                        QQC2.Label {
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                            opacity: 0.75
                                            font.pixelSize: 14 * LxS.Style.textScale
                                            text: hero.model.ConnectionState === PlasmaNM.Enums.Activated
                                                  ? i18nc("@info", "Connected · %1 · %2", root.shortSecurity(hero.model.SecurityTypeString) || i18n("Open"), root.signalWord(hero.model.Signal))
                                                  : i18n("Connecting…")
                                        }
                                    }
                                }
                                Kirigami.Icon {
                                    implicitWidth: 24; implicitHeight: 24
                                    source: "emblem-system-symbolic"; isMask: true; color: Kirigami.Theme.focusColor
                                    Accessible.name: i18nc("@action:button", "Network settings")
                                }
                            }
                        }
                    }
                }

                Rows.Section { text: i18nc("@title:group", "Saved networks"); visible: savedModel.shownCount > 0 }
                Repeater {
                    model: GroupModel {
                        id: savedModel
                        want: "saved"
                        delegate: Rows.Card {
                            id: srow
                            required property var model
                            readonly property bool inRange: model.ItemType === PlasmaNM.NetworkModelItem.AvailableConnection
                            first: DelegateModel.shownIndex === 0
                            last: DelegateModel.shownIndex === savedModel.shownCount - 1
                            clickable: true
                            onClicked: root.tapNetwork(model)
                            contentItem: RowLayout {
                                spacing: 16
                                Kirigami.Icon { source: srow.model.KcmConnectionIcon; isMask: true; color: Kirigami.Theme.textColor; opacity: srow.inRange ? 1 : 0.4; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth }
                                Rows.TitleText {
                                    title: srow.model.Name
                                    dim: !srow.inRange
                                    subtitle: (root.shortSecurity(srow.model.SecurityTypeString) || i18n("Open")) + " · "
                                              + (srow.inRange ? i18nc("@info", "tap to connect") : (srow.model.LastUsed || i18n("Out of range")))
                                }
                                QQC2.ToolButton {
                                    display: QQC2.AbstractButton.IconOnly
                                    text: i18nc("@action:button", "Settings for %1", srow.model.Name)
                                    onClicked: root.openDetails(srow.model.ConnectionPath, srow.model.Name, srow.model.DevicePath, srow.model.KcmVpnConnectionExportable)
                                    contentItem: Kirigami.Icon { implicitWidth: 22; implicitHeight: 22; source: "emblem-system-symbolic"; isMask: true; color: Kirigami.Theme.textColor; opacity: 0.8 }
                                    background: Rectangle { radius: height / 2; color: parent.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.08) : "transparent" }
                                    QQC2.ToolTip.text: text
                                    QQC2.ToolTip.visible: hovered
                                }
                            }
                        }
                    }
                }

                Rows.Section { text: i18nc("@title:group", "Other networks"); visible: otherModel.shownCount > 0 }
                Repeater {
                    model: GroupModel {
                        id: otherModel
                        want: "other"
                        delegate: Rows.Card {
                            id: orow
                            required property var model
                            first: DelegateModel.shownIndex === 0
                            last: DelegateModel.shownIndex === otherModel.shownCount - 1
                            clickable: true
                            onClicked: root.tapNetwork(model)
                            contentItem: RowLayout {
                                spacing: 16
                                Kirigami.Icon { source: orow.model.KcmConnectionIcon; isMask: true; color: Kirigami.Theme.textColor; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth }
                                Rows.TitleText { title: orow.model.Name; subtitle: root.shortSecurity(orow.model.SecurityTypeString) || i18n("Open") }
                                Kirigami.Icon { visible: root.secured(orow.model); source: "object-locked"; isMask: true; color: Kirigami.Theme.textColor; opacity: 0.8; implicitWidth: 20; implicitHeight: 20; Layout.rightMargin: 6 }
                            }
                        }
                    }
                }
            }

            Rows.Card {
                visible: !enabledConnections.wirelessEnabled
                Layout.topMargin: 10
                contentItem: Rows.TitleText { title: i18n("Wi-Fi is off"); subtitle: i18n("Turn it on to see networks nearby.") }
            }

            Rows.Section { text: i18nc("@title:group", "More") }
            Rows.Card {
                first: true; last: false; clickable: true
                visible: enabledConnections.wirelessEnabled
                onClicked: { hiddenName.text = ""; hiddenPw.text = ""; hiddenSec.current = 1; hiddenMessage.text = ""; root.view = "hidden" }
                contentItem: RowLayout {
                    spacing: 16
                    Kirigami.Icon { source: "network-wireless-symbolic"; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth; isMask: true; color: Kirigami.Theme.textColor }
                    Rows.TitleText { title: i18n("Join a hidden network"); subtitle: i18n("A network that doesn't show its name") }
                    Kirigami.Icon { source: "go-next-symbolic"; implicitWidth: 18; implicitHeight: 18; opacity: 0.6 }
                }
            }
            Rows.Card {
                first: !enabledConnections.wirelessEnabled; last: false; clickable: true
                onClicked: addNewConnectionDialog.show()
                contentItem: RowLayout {
                    spacing: 16
                    Kirigami.Icon { source: "list-add"; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth; isMask: true; color: Kirigami.Theme.textColor }
                    Rows.TitleText { title: i18n("Add a connection"); subtitle: i18n("VPN, hotspot, wired or anything else") }
                    Kirigami.Icon { source: "go-next-symbolic"; implicitWidth: 18; implicitHeight: 18; opacity: 0.6 }
                }
            }
            Rows.Card {
                first: false; last: false; clickable: true
                onClicked: root.view = "extra"
                contentItem: RowLayout {
                    spacing: 16
                    Kirigami.Icon { source: "network-vpn-symbolic"; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth; isMask: true; color: Kirigami.Theme.textColor }
                    Rows.TitleText { title: i18n("VPN and other connections"); subtitle: extraModel.shownCount > 0 ? i18np("%1 saved", "%1 saved", extraModel.shownCount) : i18n("Wired, VPN, hotspot") }
                    Kirigami.Icon { source: "go-next-symbolic"; implicitWidth: 18; implicitHeight: 18; opacity: 0.6 }
                }
            }
            Rows.Card {
                first: false; last: true; clickable: true
                onClicked: root.showConfigurationDialog()
                contentItem: RowLayout {
                    spacing: 16
                    Kirigami.Icon { source: "configure"; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth; isMask: true; color: Kirigami.Theme.textColor }
                    Rows.TitleText { title: i18n("Network preferences"); subtitle: i18n("Hotspot name and password, connection checks") }
                }
            }
            Item { implicitHeight: 24 }
        }
    }

    // ================= page: other connections =================
    QQC2.ScrollView {
        id: extraPage
        anchors.fill: parent
        background: null
        visible: opacity > 0
        opacity: root.view === "extra" ? 1 : 0
        x: root.view === "extra" ? 0 : 40
        Behavior on opacity { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        Behavior on x { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ColumnLayout {
            width: Math.min(extraPage.availableWidth - 8, 720)
            x: (extraPage.availableWidth - width) / 2
            spacing: 3
            QQC2.Button { text: i18n("Wi-Fi"); icon.name: "go-previous"; onClicked: root.view = "list"; Layout.bottomMargin: 8 }
            Kirigami.Heading { text: i18n("VPN and other connections"); level: 1; Layout.bottomMargin: 6 }
            Repeater {
                model: GroupModel {
                    id: extraModel
                    want: "extra"
                    delegate: Rows.Card {
                        id: xrow
                        required property var model
                        first: DelegateModel.shownIndex === 0
                        last: DelegateModel.shownIndex === extraModel.shownCount - 1
                        clickable: true
                        onClicked: root.openDetails(model.ConnectionPath, model.Name, model.DevicePath, model.KcmVpnConnectionExportable)
                        contentItem: RowLayout {
                            spacing: 16
                            Kirigami.Icon { source: xrow.model.KcmConnectionIcon; isMask: true; color: xrow.model.ConnectionState === PlasmaNM.Enums.Activated ? Kirigami.Theme.focusColor : Kirigami.Theme.textColor; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth }
                            Rows.TitleText { title: xrow.model.Name; subtitle: xrow.model.ConnectionState === PlasmaNM.Enums.Activated ? i18n("Connected") : (xrow.model.LastUsed || "") }
                            Kirigami.Icon { source: "go-next-symbolic"; implicitWidth: 18; implicitHeight: 18; opacity: 0.6 }
                        }
                    }
                }
            }
            Rows.Card {
                visible: extraModel.shownCount === 0
                contentItem: Rows.TitleText { title: i18n("Nothing here yet"); subtitle: i18n("Wired, VPN and hotspot connections you add show up here.") }
            }
            Rows.Card {
                Layout.topMargin: 10
                clickable: true
                onClicked: addNewConnectionDialog.show()
                contentItem: RowLayout {
                    spacing: 16
                    Kirigami.Icon { source: "list-add"; implicitWidth: LxS.Style.iconGlyphPx; implicitHeight: implicitWidth; isMask: true; color: Kirigami.Theme.textColor }
                    Rows.TitleText { title: i18n("Add a connection") }
                }
            }
        }
    }

    // ================= page: join a hidden network (R12) =================
    QQC2.ScrollView {
        id: hiddenPage
        anchors.fill: parent
        background: null
        visible: opacity > 0
        opacity: root.view === "hidden" ? 1 : 0
        x: root.view === "hidden" ? 0 : 40
        Behavior on opacity { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        Behavior on x { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ColumnLayout {
            width: Math.min(hiddenPage.availableWidth - 8, 720)
            id: hiddenCol
            x: (hiddenPage.availableWidth - width) / 2
            spacing: 3
            readonly property bool pwOk: hiddenSec.current === 0 || (hiddenPw.text.length >= 8 && hiddenPw.text.length <= 63)
            QQC2.Button { text: i18n("Wi-Fi"); icon.name: "go-previous"; onClicked: root.view = "list"; Layout.bottomMargin: 8 }
            Kirigami.Heading { text: i18n("Join a hidden network"); level: 1; font.pixelSize: LxS.Style.pageTitlePx; Layout.bottomMargin: 6 }
            Rows.Card { first: true; last: false
                contentItem: RowLayout { spacing: 16
                    QQC2.Label { text: i18n("Network name"); font.pixelSize: 16 * LxS.Style.textScale; Layout.fillWidth: true }
                    QQC2.TextField { id: hiddenName; Layout.preferredWidth: 260; placeholderText: i18n("Exactly as the router spells it") }
                }
            }
            Rows.Card { first: false; last: hiddenSec.current === 0
                contentItem: RowLayout { spacing: 16
                    QQC2.Label { text: i18n("Security"); font.pixelSize: 16 * LxS.Style.textScale; Layout.fillWidth: true }
                    Rows.Segmented { id: hiddenSec; options: [i18n("None"), i18n("WPA2"), i18n("WPA3")]; current: 1; onPicked: (i) => current = i }
                }
            }
            Rows.Card { visible: hiddenSec.current > 0; first: false; last: true
                contentItem: RowLayout { spacing: 16
                    Rows.TitleText { title: i18n("Password"); subtitle: hiddenPw.text.length > 0 && !hiddenCol.pwOk ? i18n("8 to 63 characters") : "" }
                    Kirigami.PasswordField { id: hiddenPw; Layout.preferredWidth: 260; onAccepted: joinButton.clicked() }
                }
            }
            RowLayout {
                Layout.topMargin: 12
                Layout.fillWidth: true
                QQC2.Label { id: hiddenMessage; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Kirigami.Theme.negativeTextColor; visible: text.length > 0 }
                Item { Layout.fillWidth: true; visible: hiddenMessage.text.length === 0 }
                QQC2.Button {
                    id: joinButton
                    text: net.busy ? i18n("Joining…") : i18n("Join")
                    highlighted: true
                    enabled: !net.busy && hiddenName.text.trim().length > 0 && hiddenCol.pwOk
                    onClicked: { hiddenMessage.text = ""; net.joinHidden(hiddenName.text, hiddenSec.current, hiddenPw.text, "") }
                }
            }
        }
    }

    // ================= page: one network =================
    Flickable {
        id: detailsFlick
        anchors.fill: parent
        anchors.bottomMargin: saveBar.visible ? saveBar.height + 24 : 0
        visible: opacity > 0
        opacity: root.view === "details" ? 1 : 0
        x: root.view === "details" ? 0 : 40
        Behavior on opacity { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        Behavior on x { NumberAnimation { duration: LxS.Style.animationMs; easing.type: Easing.OutCubic } }
        clip: true
        contentWidth: width
        contentHeight: dcol.implicitHeight + 24
        boundsBehavior: Flickable.StopAtBounds
        QQC2.ScrollBar.vertical: QQC2.ScrollBar {}

        ColumnLayout {
            id: dcol
            width: Math.min(detailsFlick.width - 16, 720)
            x: (detailsFlick.width - width) / 2
            spacing: 3
            readonly property bool wifi: net.kind === "wifi"
            function edit() { root.dirty = true }

            QQC2.Button { text: dcol.wifi ? i18n("Wi-Fi") : i18n("Back"); icon.name: "go-previous"; onClicked: root.backToList(); Layout.bottomMargin: 8 }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.classicPath.length > 0
                type: Kirigami.MessageType.Information
                text: i18n("The classic editor is open on the right. Use Apply below it to save there.")
                actions: [ Kirigami.Action { text: i18n("Close classic editor"); onTriggered: root.closeClassic() } ]
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: 6
                spacing: 10
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Kirigami.Heading { Layout.fillWidth: true; text: net.name || root.detailName; level: 1; elide: Text.ElideRight; font.pixelSize: LxS.Style.pageTitlePx }
                    RowLayout {
                        spacing: 8
                        Rectangle { implicitWidth: 8; implicitHeight: 8; radius: 4; color: net.active ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor }
                        QQC2.Label { opacity: 0.75; text: net.active ? [net.stateText, net.bandShort, net.interfaceName].filter(s => s.length > 0).join(" · ") : net.stateText }
                    }
                }
                QQC2.Button {
                    text: net.active ? i18nc("@action:button", "Disconnect") : i18nc("@action:button", "Connect")
                    onClicked: net.active ? net.disconnectNow() : net.connectNow(root.detailDevice)
                }
                QQC2.Button {
                    visible: root.detailExportable
                    text: i18nc("@action:button", "Export")
                    onClicked: kcm.onRequestExportConnection(root.detailPath)
                }
                QQC2.Button {
                    text: i18nc("@action:button", "Forget")
                    icon.name: "edit-delete"
                    onClicked: forgetDialog.open()
                }
            }

            // ---- Status (only while connected) ----
            Rows.Section { text: i18nc("@title:group", "Status"); visible: net.active }
            Rows.Card { visible: net.active && dcol.wifi; first: true; last: false
                contentItem: RowLayout {
                    spacing: 16
                    QQC2.Label { text: i18n("Signal"); font.pixelSize: 16 * LxS.Style.textScale; Layout.fillWidth: true }
                    Row {
                        spacing: 3
                        Repeater { model: 5
                            Rectangle { required property int index; width: 5; height: 5 + index * 3; radius: 2; anchors.bottom: parent.bottom
                                color: net.signal >= (index + 1) * 18 ? Kirigami.Theme.positiveTextColor : Qt.alpha(Kirigami.Theme.textColor, 0.2) }
                        }
                    }
                    QQC2.Label { text: net.signal + "% · " + root.signalWord(net.signal); opacity: 0.75 }
                }
            }
            Rows.Card { visible: net.active && dcol.wifi && net.speedText.length > 0; first: false; last: false; contentItem: Rows.ValueRow { label: i18n("Speed"); value: net.speedText } }
            Rows.Card { visible: net.active && dcol.wifi && net.bandText.length > 0; first: false; last: false; contentItem: Rows.ValueRow { label: i18n("Band"); value: net.bandText } }
            Rows.Card { visible: net.active; first: !dcol.wifi; last: false; contentItem: Rows.ValueRow { label: i18n("IP address"); value: net.ipv4Now || "—"; mono: true } }
            Rows.Card { visible: net.active && net.ipv6Now.length > 0; first: false; last: false; contentItem: Rows.ValueRow { label: i18n("IPv6 address"); value: net.ipv6Now; mono: true } }
            Rows.Card { visible: net.active; first: false; last: true; contentItem: Rows.ValueRow { label: i18n("Router"); value: net.gatewayNow || "—"; mono: true } }

            // ---- Connection ----
            Rows.Section { text: i18nc("@title:group", "Connection") }
            Rows.Card { first: true; last: false
                contentItem: RowLayout { spacing: 16
                    Rows.TitleText { title: i18n("Connect automatically"); subtitle: dcol.wifi ? i18n("Join when this network is in range") : i18n("Connect when available") }
                    QQC2.Switch { checked: net.autoconnect; onToggled: { net.autoconnect = checked; dcol.edit() } }
                }
            }
            Rows.Card { first: false; last: false
                contentItem: RowLayout { spacing: 16
                    Rows.TitleText { title: i18n("Available to all users"); subtitle: i18n("Other accounts on this laptop can use it") }
                    QQC2.Switch { checked: net.allUsers; onToggled: { net.allUsers = checked; dcol.edit() } }
                }
            }
            Rows.Card { first: false; last: true
                contentItem: RowLayout { spacing: 16
                    Rows.TitleText { title: i18n("Metered connection"); subtitle: i18n("Limits background downloads") }
                    QQC2.ComboBox {
                        model: [i18n("Automatic"), i18n("Yes"), i18n("No")]
                        currentIndex: net.metered
                        onActivated: (i) => { net.metered = i; dcol.edit() }
                        Layout.preferredWidth: 180
                    }
                }
            }

            // ---- Security (Wi-Fi) ----
            Rows.Section { text: i18nc("@title:group", "Security"); visible: dcol.wifi }
            Rows.Card { visible: dcol.wifi; first: true; last: !net.securityEditable
                contentItem: RowLayout { spacing: 16
                    QQC2.Label { text: i18n("Type"); font.pixelSize: 16 * LxS.Style.textScale; Layout.fillWidth: true }
                    QQC2.ComboBox {
                        visible: net.securityEditable
                        model: [i18n("WPA2 Personal"), i18n("WPA3 Personal")]
                        currentIndex: net.securityKind
                        onActivated: (i) => { net.securityKind = i; dcol.edit() }
                        Layout.preferredWidth: 200
                    }
                    QQC2.Label { visible: !net.securityEditable; text: net.securityText; opacity: 0.75 }
                }
            }
            Rows.Card { visible: dcol.wifi && net.securityEditable; first: false; last: true
                contentItem: RowLayout { spacing: 12
                    QQC2.Label { text: i18n("Password"); font.pixelSize: 16 * LxS.Style.textScale; Layout.fillWidth: true }
                    QQC2.TextField {
                        id: pwField
                        Layout.preferredWidth: 220
                        echoMode: showPw.checked ? TextInput.Normal : TextInput.Password
                        placeholderText: net.passwordEdited || net.password.length > 0 ? "" : "••••••••"
                        text: net.password
                        onTextEdited: { net.password = text; net.passwordEdited = true; dcol.edit() }
                    }
                    QQC2.Button {
                        id: showPw
                        checkable: true
                        text: checked ? i18n("Hide") : i18n("Show")
                        onToggled: if (checked && !net.passwordEdited && net.password.length === 0) net.requestPassword()
                    }
                }
            }

            // ---- IP settings ----
            Rows.Section { text: i18nc("@title:group", "IP settings") }
            Rows.Card { first: true; last: false
                contentItem: ColumnLayout { spacing: 10
                    RowLayout { spacing: 16
                        Rows.TitleText { title: "IPv4"; subtitle: net.ipv4Manual ? i18n("Fixed address you type in") : i18n("Address from the router (DHCP)") }
                        Rows.Segmented { options: [i18n("Automatic"), i18n("Manual")]; current: net.ipv4Manual ? 1 : 0
                            onPicked: (i) => { net.ipv4Manual = i === 1; if (i === 1 && net.ipv4Addresses.length === 0) net.ipv4Addresses = [""]; dcol.edit() } }
                    }
                    AddressList {
                        visible: net.ipv4Manual
                        addresses: net.ipv4Addresses
                        example: "192.168.2.50/24"
                        routerExample: "192.168.2.1"
                        router: net.ipv4Gateway
                        onAddressesEdited: (list) => { net.ipv4Addresses = list; dcol.edit() }
                        onRouterEdited: (r) => { net.ipv4Gateway = r; dcol.edit() }
                    }
                }
            }
            Rows.Card { first: false; last: false
                contentItem: ColumnLayout { spacing: 10
                    RowLayout { spacing: 16
                        Rows.TitleText { title: "DNS"
                            subtitle: net.dnsAuto ? i18n("From the router") : (net.dnsServers.length > 0 ? i18n("Your own servers") : i18n("Not from the router — the system's own DNS is used")) }
                        QQC2.Switch { checked: net.dnsAuto; onToggled: { net.dnsAuto = checked; dcol.edit() }
                            Accessible.name: i18n("DNS from the router") }
                    }
                    QQC2.TextField {
                        visible: !net.dnsAuto
                        Layout.fillWidth: true
                        placeholderText: i18n("Servers, e.g. 1.1.1.1, 9.9.9.9 (empty = system DNS)")
                        text: net.dnsServers
                        onTextEdited: { net.dnsServers = text; dcol.edit() }
                    }
                }
            }
            Rows.Card { first: false; last: true
                contentItem: ColumnLayout { spacing: 10
                    RowLayout { spacing: 16
                        Rows.TitleText { title: "IPv6"; subtitle: [i18n("Automatic"), i18n("Fixed address you type in"), i18n("Off")][net.ipv6Mode] }
                        Rows.Segmented { options: [i18n("Automatic"), i18n("Manual"), i18n("Off")]; current: net.ipv6Mode
                            onPicked: (i) => { net.ipv6Mode = i; if (i === 1 && net.ipv6Addresses.length === 0) net.ipv6Addresses = [""]; dcol.edit() } }
                    }
                    AddressList {
                        visible: net.ipv6Mode === 1
                        addresses: net.ipv6Addresses
                        example: "fd00::5/64"
                        routerExample: "fd00::1"
                        router: net.ipv6Gateway
                        onAddressesEdited: (list) => { net.ipv6Addresses = list; dcol.edit() }
                        onRouterEdited: (r) => { net.ipv6Gateway = r; dcol.edit() }
                    }
                }
            }

            // ---- Advanced (folded) ----
            QQC2.AbstractButton {
                id: advToggle
                checkable: true
                Layout.topMargin: 14
                Layout.leftMargin: 22
                contentItem: RowLayout { spacing: 6
                    QQC2.Label { text: i18nc("@title:group", "Advanced"); opacity: 0.6; font.weight: Font.Medium; font.pixelSize: LxS.Style.groupLabelPx + 1 }
                    Kirigami.Icon { source: advToggle.checked ? "go-down-symbolic" : "go-next-symbolic"; implicitWidth: 16; implicitHeight: 16; opacity: 0.6 }
                }
                background: null
            }
            ColumnLayout {
                visible: advToggle.checked
                Layout.fillWidth: true
                spacing: 3
                Rows.Card { visible: dcol.wifi; first: true; last: false
                    contentItem: RowLayout { spacing: 16
                        Rows.TitleText { title: i18n("Band"); subtitle: i18n("Lock to one band") }
                        QQC2.ComboBox { model: [i18n("Automatic"), "2.4 GHz", "5 GHz"]; currentIndex: net.band; onActivated: (i) => { net.band = i; dcol.edit() }
                            Layout.preferredWidth: 180 }
                    }
                }
                Rows.Card { visible: dcol.wifi; first: false; last: false
                    contentItem: RowLayout { spacing: 16
                        Rows.TitleText { title: i18n("MAC address"); subtitle: i18n("What the router sees") }
                        QQC2.ComboBox {
                            model: net.macMode < 0 ? [i18n("Custom (set in the classic editor)")] : [i18n("Default"), i18n("Laptop's own"), i18n("Random each time"), i18n("Fixed random for this network")]
                            currentIndex: Math.max(0, net.macMode)
                            enabled: net.macMode >= 0
                            onActivated: (i) => { net.macMode = i; dcol.edit() }
                            Layout.preferredWidth: 240
                        }
                    }
                }
                Rows.Card { visible: dcol.wifi; first: false; last: false
                    contentItem: RowLayout { spacing: 16
                        Rows.TitleText { title: i18n("Hidden network"); subtitle: i18n("The router doesn't broadcast its name") }
                        QQC2.Switch { checked: net.hidden; onToggled: { net.hidden = checked; dcol.edit() } }
                    }
                }
                Rows.Card { first: !dcol.wifi; last: false
                    contentItem: RowLayout { spacing: 16
                        Rows.TitleText { title: "MTU"; subtitle: i18n("0 = automatic; leave it unless told otherwise") }
                        QQC2.SpinBox { from: 0; to: 9000; value: net.mtu; onValueModified: { net.mtu = value; dcol.edit() }
                            Accessible.name: "MTU" }
                    }
                }
                Rows.Card { visible: net.bssid.length > 0; first: false; last: false; contentItem: Rows.ValueRow { label: i18n("Router (BSSID)"); value: net.bssid; mono: true } }
                Rows.Card { visible: net.macNow.length > 0; first: false; last: false; contentItem: Rows.ValueRow { label: i18n("This laptop's MAC"); value: net.macNow; mono: true } }
                Rows.Card { visible: net.dnsNow.length > 0; first: false; last: false; contentItem: Rows.ValueRow { label: i18n("DNS in use"); value: net.dnsNow; mono: true } }
                Rows.Card { first: false; last: true; clickable: true
                    onClicked: root.openClassic()
                    contentItem: RowLayout { spacing: 16
                        Rows.TitleText { title: i18n("All settings (classic editor)"); subtitle: i18n("Enterprise Wi-Fi, proxies, routes and everything else") }
                        Kirigami.Icon { source: "go-next-symbolic"; implicitWidth: 18; implicitHeight: 18; opacity: 0.6 }
                    }
                }
            }
            Kirigami.InlineMessage {
                id: saveMessage
                Layout.fillWidth: true
                Layout.topMargin: 8
                visible: text.length > 0
                type: Kirigami.MessageType.Error
            }
        }
    }

    // ---- the Save bar: only after a change ----
    Rectangle {
        id: saveBar
        visible: root.view === "details" && (root.dirty || savedToast.running || net.busy)
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 12 }
        width: barRow.implicitWidth + 28
        height: 52
        radius: height / 2
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false
        color: Qt.tint(Kirigami.Theme.backgroundColor, Qt.alpha(Kirigami.Theme.textColor, 0.08))
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
        RowLayout {
            id: barRow
            anchors.centerIn: parent
            spacing: 10
            QQC2.Label { text: net.busy ? i18n("Saving…") : savedToast.running && !root.dirty ? i18n("Saved") : i18n("Unsaved changes"); opacity: 0.8; Layout.leftMargin: 6 }
            QQC2.Button { visible: root.dirty; enabled: !net.busy; text: i18n("Undo"); onClicked: { net.reload(); root.dirty = false; saveMessage.text = "" } }
            QQC2.Button { visible: root.dirty; enabled: !net.busy; text: i18n("Save"); highlighted: true; onClicked: net.save() }
        }
    }
    Timer { id: savedToast; interval: 1600 }

    Kirigami.PromptDialog {
        id: forgetDialog
        title: i18nc("@title:window", "Forget this network?")
        subtitle: i18n("The laptop will stop joining \"%1\" and its saved password is deleted.", net.name)
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: net.forget()
    }

    // ===== upstream dialogs (unchanged behaviour) =====
    Kirigami.PromptDialog {
        id: deleteConfirmationDialog
        property string connectionName
        property string connectionPath
        function toHtmlEscaped(s) {
            return s.replace(/[&<>]/g, function (tag) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[tag] || tag });
        }
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        title: i18nc("@title:window", "Remove Connection")
        subtitle: i18n("Do you want to remove the connection '%1'?", toHtmlEscaped(connectionName))
        onAccepted: {
            if (connectionPath === connectionView.currentConnectionPath) root.deselectConnections()
            handler.removeConnection(connectionPath)
        }
    }

    QQC2.Dialog {
        id: passwordPrompt
        property string uniqueName
        property string devicePath
        property string specificPath
        property int securityType
        anchors.centerIn: parent
        modal: true
        footer: QQC2.DialogButtonBox {
            QQC2.Button {
                text: i18nc("@action:button Connect to network", "Connect")
                icon.name: "network-connect"
                enabled: passwordField.acceptableInput
                QQC2.DialogButtonBox.buttonRole: QQC2.DialogButtonBox.AcceptRole
            }
            QQC2.Button {
                text: i18nc("@action:button Cancel connecting to network", "Cancel")
                icon.name: "dialog-cancel"
                QQC2.DialogButtonBox.buttonRole: QQC2.DialogButtonBox.RejectRole
            }
        }
        title: i18nc("@title:window", "Enter Password")
        contentItem: ColumnLayout {
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: i18nc("@label %1 is the name of the network the user is connecting to", "Network: %1", passwordPrompt.uniqueName)
                textFormat: Text.PlainText
            }
            Kirigami.PasswordField {
                id: passwordField
                Layout.fillWidth: true
                validator: RegularExpressionValidator {
                    regularExpression: (passwordPrompt.securityType === PlasmaNM.Enums.StaticWep)
                        ? /^(?:.{5}|[0-9a-fA-F]{10}|.{13}|[0-9a-fA-F]{26})$/
                        : /^(?:.{8,64})$/
                }
                onAccepted: passwordPrompt.accept()
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: !passwordField.acceptableInput && passwordField.text.length > 0
                text: (passwordPrompt.securityType === PlasmaNM.Enums.StaticWep)
                    ? i18nc("@label key is a passcode", "Password must be a valid WEP key")
                    : i18nc("@label password invalid length message", "Password must be between 8 and 64 characters")
            }
        }
        onAccepted: {
            handler.addAndActivateConnection(passwordPrompt.devicePath, passwordPrompt.specificPath, passwordField.text)
            passwordField.clear()
        }
        onRejected: passwordField.clear()
    }

    AddConnectionDialog {
        id: addNewConnectionDialog
        onConfigurationDialogRequested: root.showConfigurationDialog()
    }

    ConfigurationDialog {
        id: configurationDialog
        handler: handler
    }

    function showConfigurationDialog() {
        configurationDialog.show();
        configurationDialog.requestActivate();
    }

    // ---- entry points the KCM's C++ calls ----
    function deselectConnections() {
        connectionView.currentConnectionName = ""
        connectionView.currentConnectionPath = ""
    }
    function selectConnection(connectionName, connectionPath) {
        connectionView.currentConnectionName = connectionName
        connectionView.currentConnectionPath = connectionPath
        // start-up selects the active connection: stay on the list. Later calls (e.g. a connection just created) open it.
        if (root.settled && connectionPath && connectionPath !== root.classicPath)
            root.openDetails(connectionPath, connectionName, "", false)
    }
    function activateConnectionWithDialog(uniqueName, devicePath, specificPath, securityType) {
        passwordPrompt.uniqueName = uniqueName
        passwordPrompt.devicePath = devicePath
        passwordPrompt.specificPath = specificPath
        passwordPrompt.securityType = securityType
        passwordPrompt.open()
    }
}
