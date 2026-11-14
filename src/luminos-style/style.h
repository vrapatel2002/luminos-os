// [CHANGE: claude-code | 2026-11-08] Luminos style tuner (DECISION 176).
// One shared set of look values for the forked KDE QML (qqc2-desktop-style, kirigami,
// kirigami-addons, kcmutils, systemsettings). Values come from ~/.config/luminos/style.json,
// the file is watched (inotify, no polling), and every QML binding that reads Style.x
// updates the moment the file changes. A missing or broken file = the built-in defaults,
// which are exactly the numbers the forks had before, so nothing changes until Shawn tunes.
#pragma once
#include <QObject>
#include <QQmlEngine>

class StyleBackend;

class Style : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
#define LX_PROP(type, name) Q_PROPERTY(type name READ name NOTIFY changed)
    LX_PROP(qreal, textSizePt)
    LX_PROP(qreal, textScale)        // textSizePt / 10 — multiplies the pixel text sizes in the forks
    LX_PROP(qreal, pageTitlePx)
    LX_PROP(qreal, groupLabelPx)
    LX_PROP(qreal, cornerOuterPx)
    LX_PROP(qreal, cornerInnerPx)
    LX_PROP(qreal, cornerSelectedPx) // outer + 4
    LX_PROP(qreal, cornerButtonPx)
    LX_PROP(qreal, cornerMenuItemPx) // button * 0.625
    LX_PROP(qreal, rowHeightPx)
    LX_PROP(qreal, rowExtraPx)       // rowHeightPx - 60: added to every row
    LX_PROP(qreal, rowGapPx)
    LX_PROP(qreal, rowHalfGapPx)     // gap / 2: spacing between connected rows
    LX_PROP(qreal, cardPaddingPx)
    LX_PROP(qreal, sidebarWidthPx)
    LX_PROP(qreal, pageWidthPx)
    LX_PROP(qreal, iconCirclePx)
    LX_PROP(int, animationMs)
    LX_PROP(int, animationShortMs)   // animationMs * 2/3
    // [CHANGE: claude-code | 2026-11-08] R6: search bar, icons, sidebar bottom gap
    LX_PROP(qreal, searchHeightPx)
    LX_PROP(qreal, searchLeftPx)
    LX_PROP(qreal, searchRightPx)
    LX_PROP(qreal, searchTopPx)
    LX_PROP(qreal, searchBottomPx)
    LX_PROP(qreal, iconGlyphPx)
    LX_PROP(qreal, iconOffsetXPx)
    LX_PROP(qreal, iconOffsetYPx)
    LX_PROP(qreal, sidebarBottomPx)
    // [CHANGE: claude-code | 2026-11-13] R29: list boxes on settings pages (−1 = follow the Shape value)
    LX_PROP(qreal, listCardRadiusPx)
    LX_PROP(qreal, listCardPadPx)
    LX_PROP(qreal, listRowOuterPx)
    LX_PROP(qreal, listRowInnerPx)
    LX_PROP(qreal, listRowSelectedPx)
    LX_PROP(qreal, listRowGapPx)
    LX_PROP(qreal, listRowHalfGapPx)
    LX_PROP(qreal, listIndicatorPct)
    LX_PROP(qreal, listVisibleRows)   // R32: rows a page list shows when options sit under it (0 = fill)
    LX_PROP(bool, showMenuButton)    // R7: the ☰ button next to the search box
    LX_PROP(QString, iconDiscColor)  // "" = theme colour, else #rrggbb
    LX_PROP(QString, iconGlyphColor) // "" = theme colour, else #rrggbb
#undef LX_PROP
public:
    explicit Style(QObject *parent = nullptr);
    static Style *create(QQmlEngine *, QJSEngine *) { return new Style; }

    qreal textSizePt() const;
    qreal textScale() const { return textSizePt() / 10.0; }
    qreal pageTitlePx() const;
    qreal groupLabelPx() const;
    qreal cornerOuterPx() const;
    qreal cornerInnerPx() const;
    qreal cornerSelectedPx() const { return cornerOuterPx() + 4; }
    qreal cornerButtonPx() const;
    qreal cornerMenuItemPx() const { return qRound(cornerButtonPx() * 0.625); }
    qreal rowHeightPx() const;
    qreal rowExtraPx() const { return rowHeightPx() - 60; }
    qreal rowGapPx() const;
    qreal rowHalfGapPx() const { return rowGapPx() / 2.0; }
    qreal cardPaddingPx() const;
    qreal sidebarWidthPx() const;
    qreal pageWidthPx() const;
    qreal iconCirclePx() const;
    int animationMs() const;
    int animationShortMs() const { return qRound(animationMs() * 2.0 / 3.0); }
    qreal searchHeightPx() const;
    qreal searchLeftPx() const;
    qreal searchRightPx() const;
    qreal searchTopPx() const;
    qreal searchBottomPx() const;
    qreal iconGlyphPx() const;
    qreal iconOffsetXPx() const;
    qreal iconOffsetYPx() const;
    qreal sidebarBottomPx() const;
    qreal listCardRadiusPx() const;
    qreal listCardPadPx() const;
    qreal listRowOuterPx() const;
    qreal listRowInnerPx() const;
    qreal listRowSelectedPx() const;
    qreal listRowGapPx() const;
    qreal listRowHalfGapPx() const { return listRowGapPx() / 2.0; }
    qreal listIndicatorPct() const;
    qreal listVisibleRows() const;
    bool showMenuButton() const;
    QString iconDiscColor() const;
    QString iconGlyphColor() const;

Q_SIGNALS:
    void changed();

private:
    StyleBackend *m_backend;
};
