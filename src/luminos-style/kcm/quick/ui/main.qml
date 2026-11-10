// [CHANGE: claude-code | 2026-11-10] R25 — Luminos Quick Settings, to Shawn's approved mock
// (docs/windowstyle/mock/system-settings-nexus.html). Responsive: one column that keeps its parts at any width;
// the two theme pills sit side by side when there is room and stack when the window is narrow.
// Everything saves the moment it changes (C++ module `kcm`).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.luminos.style as LxS

KCM.SimpleKCM {
    id: page
    readonly property bool narrow: page.availableWidth < 460
    readonly property real side: narrow ? 4 : 10

    ColumnLayout {
        width: Math.min(page.availableWidth - 2 * page.side, 720)
        x: (page.availableWidth - width) / 2
        spacing: 3

        // ---- hero: the desktop as it looks now
        Item {
            Layout.fillWidth: true
            Layout.bottomMargin: 10
            implicitHeight: Math.round(width * 7 / 16)
            Rectangle { // no picture to show (web / live scene wallpapers): the accent colours instead
                anchors.fill: parent
                radius: LxS.Style.cornerOuterPx
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.tint(Kirigami.Theme.backgroundColor, Qt.alpha(Kirigami.Theme.highlightColor, 0.55)) }
                    GradientStop { position: 1; color: Qt.tint(Kirigami.Theme.backgroundColor, Qt.alpha(Kirigami.Theme.focusColor, 0.25)) }
                }
                visible: !wall.visible
            }
            Kirigami.ShadowedImage {
                id: wall
                anchors.fill: parent
                radius: LxS.Style.cornerOuterPx
                source: kcm.wallpaper
                visible: status === Image.Ready
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 1440
                asynchronous: true
            }
            Rectangle { // small window drawn on the desktop, in the current colours
                anchors.centerIn: parent
                width: parent.width * 0.52; height: parent.height * 0.6
                radius: 12
                color: Qt.alpha(Kirigami.Theme.backgroundColor, 0.92)
                RowLayout {
                    anchors { fill: parent; margins: 8 }
                    spacing: 6
                    Rectangle { Layout.fillHeight: true; Layout.preferredWidth: parent.width * 0.3; radius: 8; color: Kirigami.Theme.alternateBackgroundColor }
                    Rectangle { Layout.fillHeight: true; Layout.fillWidth: true; radius: 8; color: Qt.tint(Kirigami.Theme.backgroundColor, Qt.alpha(Kirigami.Theme.textColor, 0.06)) }
                }
            }
            QQC2.Label { // which wallpaper it is
                anchors { left: parent.left; bottom: parent.bottom; margins: 14 }
                visible: kcm.wallpaperName.length > 0 && !page.narrow
                text: kcm.wallpaperName
                color: "white"
                font.pixelSize: 13 * LxS.Style.textScale
                background: Rectangle { radius: height / 2; color: Qt.rgba(0, 0, 0, 0.45) }
                leftPadding: 10; rightPadding: 10; topPadding: 3; bottomPadding: 3
            }
        }

        // ---- Light / Dark
        GridLayout {
            Layout.fillWidth: true
            columns: page.narrow ? 1 : 2
            columnSpacing: 10; rowSpacing: 8
            Repeater {
                model: [{ dark: false, t: i18n("Light"), icon: "weather-clear" }, { dark: true, t: i18n("Dark"), icon: "weather-clear-night" }]
                QQC2.AbstractButton {
                    id: pill
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: 60
                    checked: kcm.dark === modelData.dark
                    onClicked: kcm.setDark(modelData.dark)
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: modelData.t
                    background: Rectangle {
                        radius: height / 2
                        color: pill.checked ? Kirigami.Theme.focusColor
                             : pill.hovered ? Qt.tint(Kirigami.Theme.alternateBackgroundColor, Qt.alpha(Kirigami.Theme.textColor, 0.06))
                             : Kirigami.Theme.alternateBackgroundColor
                        border.width: pill.visualFocus ? 2 : 0
                        border.color: Kirigami.Theme.focusColor
                        Behavior on color { ColorAnimation { duration: LxS.Style.animationShortMs } }
                    }
                    contentItem: RowLayout {
                        spacing: 10
                        Item { Layout.fillWidth: true }
                        Kirigami.Icon {
                            implicitWidth: 20; implicitHeight: 20; isMask: true; source: pill.modelData.icon
                            color: pill.checked ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                        }
                        QQC2.Label {
                            text: pill.modelData.t
                            font.pixelSize: 16 * LxS.Style.textScale
                            color: pill.checked ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                        }
                        Item { Layout.fillWidth: true }
                    }
                }
            }
        }

        // ---- Animations
        Rows.Section { text: i18nc("@title:group", "Animations") }
        Rows.Card {
            contentItem: ColumnLayout {
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.Label { Layout.fillWidth: true; text: i18n("Animation speed"); elide: Text.ElideRight; font.pixelSize: 16 * LxS.Style.textScale }
                    QQC2.Label {
                        text: [i18n("Very slow"), i18n("Slow"), i18n("A bit slow"), i18n("Normal"), i18n("A bit fast"), i18n("Fast"), i18n("Very fast"), i18n("Instant")][speed.value]
                        color: Kirigami.Theme.focusColor
                    }
                }
                QQC2.Slider {
                    id: speed
                    Layout.fillWidth: true
                    from: 0; to: kcm.animSteps - 1; stepSize: 1; snapMode: QQC2.Slider.SnapAlways
                    value: kcm.animStep
                    onMoved: kcm.animStep = value
                }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.Label { Layout.fillWidth: true; text: i18n("Slow"); opacity: 0.7; font.pixelSize: 13 * LxS.Style.textScale }
                    QQC2.Label { text: i18n("Instant"); opacity: 0.7; font.pixelSize: 13 * LxS.Style.textScale }
                }
            }
        }

        // ---- Clicking
        Rows.Section { text: i18nc("@title:group", "Clicking files or folders") }
        Rows.Card {
            contentItem: ColumnLayout {
                spacing: 8
                Rectangle { // two halves that always fill the card, so it never spills out of a narrow window
                    Layout.fillWidth: true
                    implicitHeight: 48
                    radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.07)
                    RowLayout {
                        anchors { fill: parent; margins: 4 }
                        spacing: 4
                        Repeater {
                            model: [{ single: true, t: i18n("Opens them") }, { single: false, t: i18n("Selects them") }]
                            QQC2.AbstractButton {
                                id: half
                                required property var modelData
                                Layout.fillWidth: true; Layout.fillHeight: true
                                checked: kcm.singleClick === modelData.single
                                onClicked: kcm.singleClick = modelData.single
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: modelData.t
                                background: Rectangle {
                                    radius: height / 2
                                    color: half.checked ? Kirigami.Theme.focusColor : (half.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.06) : "transparent")
                                    border.width: half.visualFocus ? 2 : 0
                                    border.color: Kirigami.Theme.focusColor
                                    Behavior on color { ColorAnimation { duration: LxS.Style.animationShortMs } }
                                }
                                contentItem: QQC2.Label {
                                    text: half.modelData.t
                                    elide: Text.ElideRight
                                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    color: half.checked ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                                }
                            }
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: 0.7
                    font.pixelSize: 13.5 * LxS.Style.textScale
                    text: kcm.singleClick ? i18n("One click opens. Select with the round marker on each item.")
                                          : i18n("One click selects. Double-click to open.")
                }
            }
        }

        // ---- More
        Rows.Section { text: i18nc("@title:group", "More") }
        Repeater {
            model: [
                { t: i18n("Wallpaper"), s: i18n("Change the desktop picture, video or live scene"), act: "wallpaper" },
                { t: i18n("Colours"), s: kcm.schemeName, act: "kcm_colors" },
                { t: i18n("Global theme"), s: i18n("The whole look in one go"), act: "kcm_lookandfeel" },
                { t: i18n("Fine-tune the look"), s: i18n("Style Tuner: sizes, corners, spacing, live"), act: "tuner" },
                { t: i18n("General behaviour"), s: i18n("Scrolling, tooltips, feedback"), act: "kcm_workspace" }
            ]
            Rows.Card {
                id: row
                required property var modelData
                required property int index
                first: index === 0
                last: index === 4
                clickable: true
                onClicked: modelData.act === "wallpaper" ? kcm.openWallpaper() : modelData.act === "tuner" ? kcm.openTuner() : kcm.openModule(modelData.act)
                contentItem: RowLayout {
                    spacing: 12
                    Rows.TitleText { title: row.modelData.t; subtitle: row.modelData.s }
                    Kirigami.Icon { implicitWidth: 20; implicitHeight: 20; source: "go-next-symbolic"; isMask: true; color: Kirigami.Theme.textColor; opacity: 0.6 }
                }
            }
        }
        Item { implicitHeight: 12 }
    }
}
