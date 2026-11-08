// [CHANGE: claude-code | 2026-11-08] DECISION 179 — Luminos Proxy page, to Shawn's approved prototype
// (docs/windowstyle/mock/net-pages.html). Values live in the C++ module (`kcm`); Apply saves.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.luminos.style as LxS

KCM.SimpleKCM {
    id: page
    readonly property var statusText: [i18n("No proxy · apps connect directly"), i18n("Looking for the network's proxy automatically"),
                                       i18n("Using a setup script"), i18n("Using your proxy server"), i18n("Using the proxy from environment variables")]
    ColumnLayout {
        width: Math.min(page.availableWidth, 720)
        x: (page.availableWidth - width) / 2
        spacing: 3

        QQC2.Label {
            Layout.fillWidth: true
            Layout.bottomMargin: 10
            wrapMode: Text.Wrap
            opacity: 0.75
            text: i18n("A proxy sends your apps' web traffic through another server first — usually only needed at a school or office network. Most people leave this off.")
        }
        Rectangle { // status
            Layout.fillWidth: true
            Layout.bottomMargin: 6
            implicitHeight: 52
            radius: LxS.Style.cornerOuterPx
            color: Qt.tint(Kirigami.Theme.alternateBackgroundColor, Qt.alpha(kcm.mode === 0 ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor, 0.10))
            Kirigami.Theme.colorSet: Kirigami.Theme.View
            Kirigami.Theme.inherit: false
            RowLayout {
                anchors { fill: parent; leftMargin: 22; rightMargin: 22 }
                spacing: 10
                Rectangle { implicitWidth: 8; implicitHeight: 8; radius: 4; color: kcm.mode === 0 ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor }
                QQC2.Label { Layout.fillWidth: true; text: page.statusText[kcm.mode]; elide: Text.ElideRight }
            }
        }

        Rows.Section { text: i18nc("@title:group", "How apps connect") }
        Repeater {
            model: [
                { m: 0, t: i18n("Off"), s: i18n("Connect directly. Right for home networks.") },
                { m: 1, t: i18n("Find it automatically"), s: i18n("Ask the network if it has a proxy (WPAD). Used by some office networks.") },
                { m: 2, t: i18n("Use a setup script"), s: i18n("Your IT team gave you an address ending in .pac") },
                { m: 3, t: i18n("Set it up myself"), s: i18n("Type the proxy server's address and port") },
                { m: 4, t: i18n("Use environment variables"), s: i18n("Take the proxy from http_proxy / https_proxy, as terminal tools do") }
            ]
            Rows.Card {
                id: choice
                required property var modelData
                required property int index
                visible: modelData.m !== 4 || kcm.mode === 4
                first: index === 0
                last: index === 3 && kcm.mode !== 4 || index === 4
                clickable: true
                onClicked: kcm.mode = modelData.m
                Accessible.role: Accessible.RadioButton
                Accessible.checkable: true
                Accessible.checked: kcm.mode === modelData.m
                Accessible.name: modelData.t
                contentItem: RowLayout {
                    spacing: 16
                    Rectangle {
                        implicitWidth: 22; implicitHeight: 22; radius: 11
                        color: kcm.mode === choice.modelData.m ? Kirigami.Theme.focusColor : "transparent"
                        border.width: kcm.mode === choice.modelData.m ? 0 : 2
                        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.55)
                        Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; visible: kcm.mode === choice.modelData.m; color: Kirigami.Theme.backgroundColor }
                    }
                    Rows.TitleText { title: choice.modelData.t; subtitle: choice.modelData.s }
                }
            }
        }

        // ---- setup script ----
        Rows.Section { text: i18nc("@title:group", "Setup script"); visible: kcm.mode === 2 }
        Rows.Card { visible: kcm.mode === 2
            contentItem: ColumnLayout { spacing: 8
                Rows.TitleText { title: i18n("Script address"); subtitle: i18n("Example: http://proxy.school.ca/proxy.pac") }
                QQC2.TextField { Layout.fillWidth: true; text: kcm.pacUrl; placeholderText: "http://…/proxy.pac"; onTextEdited: kcm.pacUrl = text }
            }
        }

        // ---- manual ----
        Rows.Section { text: i18nc("@title:group", "Proxy server"); visible: kcm.mode === 3 }
        Rows.Card { visible: kcm.mode === 3; first: true; last: false
            contentItem: RowLayout { spacing: 16
                Rows.TitleText { title: i18n("Same server for everything"); subtitle: i18n("Use one address for web, secure web and file transfers") }
                QQC2.Switch { checked: kcm.sameForAll; onToggled: kcm.sameForAll = checked }
            }
        }
        component HostPort: RowLayout {
            property string label
            property string host
            property int port
            property string example
            property int examplePort: 8080
            signal hostEdited(string h)
            signal portEdited(int p)
            Layout.fillWidth: true
            spacing: 8
            QQC2.Label { text: parent.label; Layout.preferredWidth: 110; opacity: 0.8 }
            QQC2.TextField { Layout.fillWidth: true; text: parent.host; placeholderText: parent.example; onTextEdited: parent.hostEdited(text); Accessible.name: parent.label }
            QQC2.TextField {
                Layout.preferredWidth: 90
                text: parent.port > 0 ? String(parent.port) : ""
                placeholderText: String(parent.examplePort)
                inputMethodHints: Qt.ImhDigitsOnly
                validator: IntValidator { bottom: 0; top: 65535 }
                onTextEdited: parent.portEdited(parseInt(text) || 0)
                Accessible.name: i18n("%1 port", parent.label)
            }
        }
        Rows.Card { visible: kcm.mode === 3; first: false; last: false
            contentItem: ColumnLayout { spacing: 8
                HostPort { label: kcm.sameForAll ? i18n("All traffic") : i18n("Web"); host: kcm.httpHost; port: kcm.httpPort; example: "proxy.example.com"
                    onHostEdited: (h) => kcm.httpHost = h; onPortEdited: (p) => kcm.httpPort = p }
                HostPort { visible: !kcm.sameForAll; label: i18n("Secure web"); host: kcm.httpsHost; port: kcm.httpsPort; example: "proxy.example.com"
                    onHostEdited: (h) => kcm.httpsHost = h; onPortEdited: (p) => kcm.httpsPort = p }
                HostPort { visible: !kcm.sameForAll; label: i18n("File transfer"); host: kcm.ftpHost; port: kcm.ftpPort; example: "proxy.example.com"
                    onHostEdited: (h) => kcm.ftpHost = h; onPortEdited: (p) => kcm.ftpPort = p }
                HostPort { visible: !kcm.sameForAll; label: "SOCKS"; host: kcm.socksHost; port: kcm.socksPort; example: "socks.example.com"; examplePort: 1080
                    onHostEdited: (h) => kcm.socksHost = h; onPortEdited: (p) => kcm.socksPort = p }
            }
        }
        Rows.Card { visible: kcm.mode === 3; first: false; last: false
            contentItem: ColumnLayout { spacing: 8
                Rows.TitleText { title: kcm.onlyForList ? i18n("Use the proxy only for") : i18n("Skip the proxy for"); subtitle: i18n("Comma separated, e.g. localhost, 192.168.2.0/24, .example.com") }
                QQC2.TextField { Layout.fillWidth: true; text: kcm.noProxyFor; placeholderText: "localhost, 127.0.0.1"; onTextEdited: kcm.noProxyFor = text }
            }
        }
        Rows.Card { visible: kcm.mode === 3; first: false; last: true
            contentItem: RowLayout { spacing: 16
                Rows.TitleText { title: i18n("Flip the list"); subtitle: i18n("Send ONLY the addresses above through the proxy") }
                QQC2.Switch { checked: kcm.onlyForList; onToggled: kcm.onlyForList = checked }
            }
        }

        // ---- environment ----
        Rows.Section { text: i18nc("@title:group", "Environment variables"); visible: kcm.mode === 4 }
        Rows.Card { visible: kcm.mode === 4
            contentItem: Rows.TitleText { title: i18n("Values right now"); subtitle: kcm.envSummary || i18n("Not set in this session") }
        }

        Rows.Section { text: i18nc("@title:group", "Good to know") }
        Rows.Card {
            contentItem: Rows.TitleText { title: i18n("Which apps use this"); subtitle: i18n("KDE apps, Chrome and anything that reads the system proxy. Terminal tools and games usually ignore it.") }
        }
        Item { implicitHeight: 16 }
    }
}
