// [CHANGE: claude-code | 2026-11-08] DECISION 179 — Luminos Connection Preferences page (approved prototype).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.luminos.style as LxS

KCM.SimpleKCM {
    id: page
    ColumnLayout {
        width: Math.min(page.availableWidth, 720)
        x: (page.availableWidth - width) / 2
        spacing: 3
        QQC2.Label {
            Layout.fillWidth: true
            Layout.bottomMargin: 6
            wrapMode: Text.Wrap
            opacity: 0.75
            text: i18n("How Dolphin and other KDE apps copy files to and from other computers (network folders, FTP servers).")
        }
        Rows.Section { text: i18nc("@title:group", "Uploads") }
        Rows.Card {
            contentItem: RowLayout { spacing: 16
                Rows.TitleText { title: i18n("Mark unfinished uploads"); subtitle: i18n("While a file is still copying it is named name.part, so a half-copied file is never mistaken for a finished one.") }
                QQC2.Switch { checked: kcm.markPartial; onToggled: kcm.markPartial = checked }
            }
        }
        Rows.Section { text: i18nc("@title:group", "FTP servers") }
        Rows.Card { first: true; last: false
            contentItem: RowLayout { spacing: 16
                Rows.TitleText { title: i18n("Passive mode"); subtitle: i18n("The laptop opens every connection itself. Works through routers and firewalls; turn off only if a server asks you to.") }
                QQC2.Switch { checked: kcm.ftpPassive; onToggled: kcm.ftpPassive = checked }
            }
        }
        Rows.Card { first: false; last: true
            contentItem: RowLayout { spacing: 16
                Rows.TitleText { title: i18n("Mark unfinished FTP uploads"); subtitle: i18n("Same .part naming for FTP") }
                QQC2.Switch { checked: kcm.ftpMarkPartial; onToggled: kcm.ftpMarkPartial = checked }
            }
        }
    }
}
