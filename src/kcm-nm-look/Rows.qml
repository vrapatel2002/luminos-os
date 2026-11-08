// [CHANGE: claude-code | 2026-11-08] DECISION 178 — building blocks for the Luminos Wi-Fi page.
// Card rows that join into groups (big outer corners, small corners where rows touch), as in the approved prototype.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.luminos.style as LxS

QtObject {
    // [CHANGE: claude-code | 2026-11-08] R15: leading icon in the same round disc as the sidebar,
    // same size knobs (iconCirclePx / iconGlyphPx) so the tuner moves both together.
    component Disc: Rectangle {
        property alias source: glyph.source
        property bool accent: false // connected network: highlighted disc
        property bool dim: false
        // R16: the Wi-Fi wedge only fills ~60% of its icon box (20x13 px vs the sidebar globe's 20x20),
        // so it is drawn larger to look the same size as the sidebar glyphs.
        property real glyphScale: String(source).indexOf("wireless") >= 0 ? 1.35 : 1
        Layout.alignment: Qt.AlignVCenter
        implicitWidth: LxS.Style.iconCirclePx; implicitHeight: implicitWidth; radius: implicitWidth / 2
        color: accent ? Kirigami.Theme.focusColor : (LxS.Style.iconDiscColor || Kirigami.Theme.highlightColor)
        opacity: dim ? 0.45 : 1
        Kirigami.Icon {
            id: glyph
            anchors.centerIn: parent; width: Math.round(LxS.Style.iconGlyphPx * parent.glyphScale); height: width; isMask: true
            roundToIconSize: false // else Kirigami snaps 27 px back down to 22
            color: parent.accent ? Kirigami.Theme.highlightColor : (LxS.Style.iconGlyphColor || Kirigami.Theme.highlightedTextColor)
        }
    }

    // one card row; put any content in it
    component Card: QQC2.ItemDelegate {
        id: card
        property bool first: true
        property bool last: true
        property bool clickable: false
        property real minHeight: Math.max(56, LxS.Style.rowHeightPx + 4)
        Layout.fillWidth: true
        hoverEnabled: clickable
        down: clickable && pressed
        leftPadding: 22; rightPadding: 20
        topPadding: 10; bottomPadding: 10
        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
        implicitHeight: Math.max(minHeight, implicitContentHeight + topPadding + bottomPadding)
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false
        focusPolicy: clickable ? Qt.StrongFocus : Qt.NoFocus
        background: Rectangle {
            color: (card.clickable && (card.hovered || card.visualFocus)) ? Qt.tint(Kirigami.Theme.alternateBackgroundColor, Qt.alpha(Kirigami.Theme.textColor, 0.06))
                 : Kirigami.Theme.alternateBackgroundColor
            topLeftRadius: card.first ? LxS.Style.cornerOuterPx : LxS.Style.cornerInnerPx
            topRightRadius: topLeftRadius
            bottomLeftRadius: card.last ? LxS.Style.cornerOuterPx : LxS.Style.cornerInnerPx
            bottomRightRadius: bottomLeftRadius
            border.width: card.visualFocus ? 2 : 0
            border.color: Kirigami.Theme.focusColor
            Behavior on color { ColorAnimation { duration: LxS.Style.animationShortMs } }
        }
    }

    // title + optional grey line under it
    component TitleText: ColumnLayout {
        property string title
        property string subtitle
        property bool dim: false
        spacing: 1
        Layout.fillWidth: true
        QQC2.Label {
            Layout.fillWidth: true
            text: parent.title
            elide: Text.ElideRight
            textFormat: Text.PlainText
            font.pixelSize: 16 * LxS.Style.textScale
            opacity: parent.dim ? 0.6 : 1
        }
        QQC2.Label {
            Layout.fillWidth: true
            visible: text.length > 0
            text: parent.subtitle
            elide: Text.ElideRight
            textFormat: Text.PlainText
            opacity: 0.7
            font.pixelSize: 13.5 * LxS.Style.textScale
        }
    }

    // grey section label above a group
    component Section: QQC2.Label {
        Layout.fillWidth: true
        Layout.leftMargin: 22
        Layout.topMargin: 14
        Layout.bottomMargin: 2
        opacity: 0.6
        font.pixelSize: LxS.Style.groupLabelPx + 1
        font.weight: Font.Medium
        elide: Text.ElideRight
    }

    // "Automatic | Manual | Off" pill switcher
    component Segmented: Rectangle {
        id: seg
        property var options: []
        property int current: 0
        signal picked(int index)
        implicitHeight: 38
        implicitWidth: segRow.implicitWidth + 6
        radius: height / 2
        color: Qt.alpha(Kirigami.Theme.textColor, 0.07)
        Row {
            id: segRow
            anchors.centerIn: parent
            spacing: 2
            Repeater {
                model: seg.options
                QQC2.AbstractButton {
                    id: opt
                    required property string modelData
                    required property int index
                    height: 32
                    width: optText.implicitWidth + 28
                    checked: seg.current === index
                    onClicked: if (seg.current !== index) seg.picked(index)
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: modelData
                    background: Rectangle {
                        radius: height / 2
                        color: opt.checked ? Kirigami.Theme.highlightColor : (opt.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.06) : "transparent")
                        border.width: opt.visualFocus ? 2 : 0
                        border.color: Kirigami.Theme.focusColor
                        Behavior on color { ColorAnimation { duration: LxS.Style.animationShortMs } }
                    }
                    contentItem: QQC2.Label {
                        id: optText
                        text: opt.modelData
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        opacity: opt.checked ? 1 : 0.75
                    }
                }
            }
        }
    }

    // read-only "label .......... value" row content
    component ValueRow: RowLayout {
        property string label
        property string value
        property bool mono: false
        spacing: 16
        Layout.fillWidth: true
        QQC2.Label { text: parent.label; font.pixelSize: 16 * LxS.Style.textScale; Layout.fillWidth: true; elide: Text.ElideRight }
        QQC2.Label {
            text: parent.value
            opacity: 0.75
            font.family: parent.mono ? "monospace" : Kirigami.Theme.defaultFont.family
            font.pixelSize: 14.5 * LxS.Style.textScale
            horizontalAlignment: Text.AlignRight
            Layout.maximumWidth: parent.width * 0.6
            elide: Text.ElideMiddle
        }
    }
}
