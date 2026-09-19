/*
    Luminos Live Wallpaper — the eight property controls, one Component each.
    SPEC §3.2, CONTRACTS §4.  [CHANGE: claude-code | 2026-09-19] DECISION 118.
    SPDX-License-Identifier: GPL-3.0-or-later

    Split out of PropertyEditor.qml for the 200-line host budget (SPEC §9), and it
    reads better for it: this file is "what a control IS", PropertyEditor is "what
    a row LOOKS like". Each Component's root declares pkey/pdef, because the editor
    hands them over explicitly in Loader.onLoaded rather than through scope.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs as Dialogs
import org.kde.kquickcontrols as KQuickControls
import org.kde.kirigami as Kirigami

QtObject {
    id: controls

    // The PropertyEditor that owns this: supplies val()/num(), receives changed().
    required property var editor

    property Component slider: Component {
        RowLayout {
            property string pkey: ""
            property var pdef: ({})
            QQC2.Slider {
                id: sl
                Layout.fillWidth: true
                from: controls.editor.num(pdef.min, 0)
                to: controls.editor.num(pdef.max, 1)
                stepSize: controls.editor.num(pdef.step, 0)
                value: controls.editor.num(controls.editor.val(pkey), from)
                onMoved: controls.editor.changed(pkey, value)
            }
            QQC2.Label {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 3
                text: sl.value.toFixed(sl.stepSize >= 1 ? 0 : 2)
            }
        }
    }
    // The odd one out, and it has to be. Every other control writes back from a
    // USER-ACTION signal — onMoved, onActivated, onEditingFinished, onToggled —
    // which a programmatic change does not emit, so a binding on the value is
    // safe. ColorButton has no such signal: onColorChanged fires however the
    // colour got there. Bind `color` to a value our own write-back changes and
    // ColorButton's internal ColorDialog loops on `selectedColor`, and the
    // dialog can then be neither accepted nor cancelled. BUG-174.
    // So the value is set ONCE, imperatively, when the key arrives.
    // [CHANGE: claude-code | 2026-09-19]
    property Component color: Component {
        KQuickControls.ColorButton {
            property string pkey: ""
            property var pdef: ({})
            // False until the initial colour is in place, so loading the panel
            // does not write a value nobody chose.
            property bool armed: false
            onPkeyChanged: {
                color = "" + (controls.editor.val(pkey) || "#ffffff");
                armed = true;
            }
            onColorChanged: {
                if (armed)
                    controls.editor.changed(pkey, "" + color);
            }
        }
    }
    property Component dropdown: Component {
        QQC2.ComboBox {
            property string pkey: ""
            property var pdef: ({})
            model: pdef.items || []
            currentIndex: controls.editor.num(controls.editor.val(pkey), 0)
            onActivated: controls.editor.changed(pkey, currentIndex)
        }
    }
    property Component textbox: Component {
        QQC2.TextField {
            property string pkey: ""
            property var pdef: ({})
            text: "" + (controls.editor.val(pkey) || "")
            onEditingFinished: controls.editor.changed(pkey, text)
        }
    }
    property Component checkbox: Component {
        QQC2.CheckBox {
            property string pkey: ""
            property var pdef: ({})
            checked: !!controls.editor.val(pkey)
            onToggled: controls.editor.changed(pkey, checked)
        }
    }
    property Component file: Component {
        RowLayout {
            property string pkey: ""
            property var pdef: ({})
            QQC2.TextField {
                Layout.fillWidth: true
                text: "" + (controls.editor.val(pkey) || "")
                onEditingFinished: controls.editor.changed(pkey, text)
            }
            QQC2.Button {
                text: i18n("Browse…")
                icon.name: "document-open"
                onClicked: dlg.open()
            }
            Dialogs.FileDialog {
                id: dlg
                onAccepted: {
                    var s = "" + selectedFile;
                    controls.editor.changed(pkey, s.indexOf("file://") === 0 ? s.substring(7) : s);
                }
            }
        }
    }
    property Component button: Component {
        // A button carries an ACTION TOKEN, not a value: props[key] becomes
        // {action, at}. The timestamp is what makes a second press visible.
        QQC2.Button {
            property string pkey: ""
            property var pdef: ({})
            text: "" + (pdef.label || pkey)
            onClicked: controls.editor.changed(pkey, { action: "" + (pdef.value || pkey), at: Date.now() })
        }
    }
    property Component label: Component {
        QQC2.Label {
            property string pkey: ""
            property var pdef: ({})
            wrapMode: Text.WordWrap
            font: Kirigami.Theme.smallFont
            text: "" + (pdef.value || pdef.label || "")
        }
    }
}
