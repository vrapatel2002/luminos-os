/*
 *   SPDX-FileCopyrightText: 2021 Jan Blackquill <uhhadd@gmail.com>
 *
 *   SPDX-License-Identifier: LGPL-2.0-only
 */
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.kirigami as Kirigami

ItemDelegate {
    id: delegate

    property bool showArrow: false
    property bool selected: delegate.highlighted || delegate.pressed
    property bool isSearching: false
    property real leadingPadding: 0
    required property bool showDefaultIndicator
    required property QtObject /*QAction*/ auxiliaryAction
    // [CHANGE: claude-code | 2026-10-11] Luminos Nexus row (DECISION 140): 2nd line; corners 28 outer / 4 touching / 32 selected / 12 pressed
    property string description: ""
    property bool groupStart: true
    property bool groupEnd: true
    // Narrow (squeezed) sidebar: icon-only tile, corners clamped to the tile's size.
    readonly property bool compact: width < 120
    readonly property real cornerMax: Math.min(width, height - topInset - bottomInset) / 2
    readonly property real cornerTop: Math.min(cornerMax, pressed ? 12 : highlighted ? 32 : groupStart ? 28 : 4)
    readonly property real cornerBottom: Math.min(cornerMax, pressed ? 12 : highlighted ? 32 : groupEnd ? 28 : 4)

    width: (ListView.view?.width ?? 0) - (ListView.view?.leftMargin ?? 0) - (ListView.view?.rightMargin ?? 0)

    Kirigami.Theme.colorSet: Kirigami.Theme.Button
    Kirigami.Theme.inherit: false

    topInset: 2; bottomInset: 2; topPadding: 18; bottomPadding: 18
    leftPadding: compact ? Math.max(0, (width - 40) / 2) : 16; rightPadding: leftPadding

    Accessible.name: text
    Accessible.onPressAction: clicked()

    background: Rectangle {
        readonly property color base: delegate.highlighted ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
        color: delegate.hovered && !delegate.highlighted ? Qt.tint(base, Qt.alpha(Kirigami.Theme.textColor, 0.08)) : base
        topLeftRadius: delegate.cornerTop; topRightRadius: delegate.cornerTop
        bottomLeftRadius: delegate.cornerBottom; bottomRightRadius: delegate.cornerBottom
        Behavior on topLeftRadius { enabled: !(delegate.ListView.view?.moving ?? false); NumberAnimation { duration: 180; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on topRightRadius { enabled: !(delegate.ListView.view?.moving ?? false); NumberAnimation { duration: 180; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on bottomLeftRadius { enabled: !(delegate.ListView.view?.moving ?? false); NumberAnimation { duration: 180; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on bottomRightRadius { enabled: !(delegate.ListView.view?.moving ?? false); NumberAnimation { duration: 180; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] } }
        Behavior on color { ColorAnimation { duration: 180 } }
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.smallSpacing

        Rectangle { // icon disc
            Layout.leftMargin: delegate.compact ? 0 : delegate.leadingPadding
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 40; implicitHeight: 40; radius: 20
            color: delegate.highlighted ? Kirigami.Theme.focusColor : Kirigami.Theme.highlightColor
            Behavior on color { ColorAnimation { duration: 180 } }
            Kirigami.Icon {
                anchors.centerIn: parent; width: Kirigami.Units.iconSizes.smallMedium; height: width
                source: delegate.icon.name; isMask: true
                color: delegate.highlighted ? Kirigami.Theme.highlightColor : Kirigami.Theme.highlightedTextColor
            }
        }

        ColumnLayout {
            id: titleItem
            visible: !delegate.compact
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            spacing: 1
            Label { Layout.fillWidth: true; text: delegate.text; elide: Text.ElideRight; textFormat: Text.PlainText; color: Kirigami.Theme.textColor; font.pixelSize: 16 }
            Label {
                Layout.fillWidth: true; visible: text.length > 0; text: delegate.description; elide: Text.ElideRight
                textFormat: Text.PlainText; color: Kirigami.Theme.textColor; opacity: 0.75; font.pixelSize: 13
            }
        }

        Kirigami.Badge {
            Layout.alignment: Qt.AlignVCenter
            Layout.preferredWidth: Kirigami.Units.largeSpacing
            Layout.preferredHeight: Kirigami.Units.largeSpacing

            visible: delegate.showDefaultIndicator && systemsettings.defaultsIndicatorsVisible
            type: Kirigami.Badge.Type.Warning
        }

        Component {
            id: auxiliaryButtonActionComponent

            ToolButton {
                implicitWidth: height
                implicitHeight: titleItem.height
                icon.color: Kirigami.Theme.textColor

                display: AbstractButton.IconOnly
                text: delegate.auxiliaryAction.text
                icon.name: systemsettings.actionIconName(delegate.auxiliaryAction)
                onClicked: {
                    delegate.auxiliaryAction.trigger();
                }

                ToolTip.text: delegate.auxiliaryAction.tooltip || delegate.auxiliaryAction.text
                ToolTip.delay: Kirigami.Units.toolTipDelay
                ToolTip.visible: ToolTip.text !== "" && (Kirigami.Settings.tabletMode ? pressed : hovered)
            }
        }

        Component {
            id: auxiliarySwitchActionComponent

            Switch {
                Accessible.name: delegate.auxiliaryAction.text
                checked: delegate.auxiliaryAction.checked
                onToggled: {
                    delegate.auxiliaryAction.trigger();
                }

                ToolTip.text: delegate.auxiliaryAction.tooltip || delegate.auxiliaryAction.text
                ToolTip.delay: Kirigami.Units.toolTipDelay
                ToolTip.visible: ToolTip.text !== "" && (Kirigami.Settings.tabletMode ? pressed : hovered)
            }
        }

        Loader {
            Layout.fillHeight: true
            Layout.topMargin: -delegate.topPadding + delegate.topInset
            Layout.bottomMargin: -delegate.bottomPadding + delegate.bottomInset
            Layout.rightMargin: -delegate.rightPadding + delegate.rightInset

            enabled: delegate.auxiliaryAction?.enabled ?? false
            visible: status === Loader.Ready && !delegate.compact
            sourceComponent: {
                const action = delegate.auxiliaryAction;
                if (action && action.visible) {
                    if (action.checkable) {
                        return auxiliarySwitchActionComponent;
                    } else {
                        return auxiliaryButtonActionComponent;
                    }
                }
                return null;
            }
        }

        Shape { // Material chevron_right, drawn so it does not depend on the icon theme
            Layout.alignment: Qt.AlignVCenter
            Layout.preferredWidth: 20; Layout.preferredHeight: 20
            opacity: delegate.showArrow ? 1 : 0
            visible: !delegate.compact && !(delegate.auxiliaryAction?.visible ?? false)
            transform: Scale { origin.x: 10; xScale: delegate.mirrored ? -1 : 1 }
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Kirigami.Theme.textColor; strokeWidth: 1.8; fillColor: "transparent"
                capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; startX: 8; startY: 5
                PathLine { x: 13; y: 10 } PathLine { x: 8; y: 15 }
            }
        }
    }
}
