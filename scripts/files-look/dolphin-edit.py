#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-11-09] DECISION 182 — turns a pristine dolphin-26.08.1 tree into the Luminos one.
# usage: dolphin-edit.py <dolphin-src-dir> <path to luminosfilesstyle_p.h>
# What it changes (approved prototype: docs/windowstyle/mock/files-page.html):
#   1. rounded selection / hover in the file view (kitemlistwidget.cpp)
#   2. grouping by Name shows "Folders" / "Files" (kfileitemmodel.cpp)
#   3. the View button opens one panel: Icons/Compact/List, S-M-L-XL, sort, groups, toggles, this folder / all folders
#   4. the ☰ menu: quick row (New folder, New tab, Window, Terminal) + Create new / Select / This folder / Undo / Redo / Filter / Panels / Configure
#   5. selecting files shows the action bar at the bottom (without entering "selection mode")
#   6. after Move to Trash / Move: a message with an Undo button that hides by itself
# All looks read ~/.config/luminos/style.json (keys files*) so the Style Tuner can change them later.
import shutil, sys
root, hdr = sys.argv[1], sys.argv[2]
src = f'{root}/src'
shutil.copy(hdr, f'{src}/luminosfilesstyle_p.h')

def edit(path, pairs):
    p = f'{src}/{path}'
    s = open(p).read()
    for a, b in pairs:
        c = s.count(a)
        if c != 1:
            sys.exit(f'{path}: expected 1 got {c}: {a[:90]!r}')
        s = s.replace(a, b)
    open(p, 'w').write(s)

TAG = '// [CHANGE: claude-code | 2026-11-09] DECISION 182'

# ---------------------------------------------------------------- 1. rounded selection
edit('kitemviews/kitemlistwidget.cpp', [
 ('#include <QStyleOption>\n', '#include <QStyleOption>\n#include <QPainterPath>\n#include <KColorScheme>\n#include <KColorUtils>\n#include "luminosfilesstyle_p.h" ' + TAG + '\n'),
 ('''    if (style()->name() == QStringLiteral("breeze")) {
        QColor backgroundColor{widget->palette().color(QPalette::Highlight)};''',
  '''    if (LuminosFiles::Style::self().flag("filesRoundSelection", true)) {
        ''' + TAG + ''': soft rounded tiles for hover / selection (prototype look)
        const auto &lx = LuminosFiles::Style::self();
        const QPalette pal = widget->palette();
        const QColor base = pal.color(QPalette::Base);
        QColor bg = Qt::transparent;
        if (m_clickHighlighted) {
            bg = KColorUtils::mix(base, pal.color(QPalette::Highlight), 0.55);
        } else if (m_selected) {
            bg = KColorUtils::mix(base, pal.color(QPalette::Highlight), lx.num("filesItemSelMix", 100, 0, 100) / 100.0);
            if (m_hovered) {
                bg = KColorUtils::mix(bg, pal.color(QPalette::Text), 0.05);
            }
        } else if (m_hovered) {
            bg = KColorUtils::mix(base, pal.color(QPalette::Text), lx.num("filesItemHoverMix", 7, 0, 100) / 100.0);
        }
        painter->setRenderHint(QPainter::Antialiasing);
        const QRectF r = selectionRectFull();
        const qreal rad = qMin<qreal>(lx.num("filesItemRadiusPx", 14, 0, 40), qMin(r.width(), r.height()) / 2.0);
        QPainterPath path;
        path.addRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad);
        if (bg.alpha() > 0) {
            painter->fillPath(path, bg);
        }
        if (current && !m_selected) {
            QColor focusColor = KColorScheme(QPalette::Active, KColorScheme::View).decoration(KColorScheme::FocusColor).color();
            focusColor.setAlphaF(0.35);
            QPen pen{focusColor, 1.25};
            pen.setCosmetic(true);
            painter->strokePath(path, pen);
        }
    } else if (style()->name() == QStringLiteral("breeze")) {
        QColor backgroundColor{widget->palette().color(QPalette::Highlight)};'''),
])

# ---------------------------------------------------------------- 2. Folders / Files groups
edit('kitemviews/kfileitemmodel.cpp', [
 ('#include "views/draganddrophelper.h"\n', '#include "views/draganddrophelper.h"\n#include "luminosfilesstyle_p.h" ' + TAG + '\n'),
 ('''    const int maxIndex = count() - 1;
    QList<QPair<int, QVariant>> groups;

    QString groupValue;
    QChar firstChar;''', '''    const int maxIndex = count() - 1;
    QList<QPair<int, QVariant>> groups;

    ''' + TAG + ''': grouping by Name = two plain groups, "Folders" and "Files"
    if (LuminosFiles::Style::self().flag("filesFolderFileGroups", true)) {
        QString last;
        for (int i = 0; i <= maxIndex; ++i) {
            if (isChildItem(i)) {
                continue;
            }
            const QString g = m_itemData.at(i)->item.isDir() ? i18nc("@title:group", "Folders") : i18nc("@title:group", "Files");
            if (g != last) {
                last = g;
                groups.append(QPair<int, QVariant>(i, g));
            }
        }
        return groups;
    }

    QString groupValue;
    QChar firstChar;'''),
])

# ---------------------------------------------------------------- 3. View panel
VIEW_PANEL_CLASSES = r'''
''' + TAG + r''': small painted controls for the Luminos View panel (no moc needed)
namespace
{
QColor lxMix(const QColor &a, const QColor &b, qreal t)
{
    return KColorUtils::mix(a, b, t);
}
// the colour scheme's focus colour = Luminos accent (lavender)
QColor lxAccent()
{
    return KColorScheme(QPalette::Active, KColorScheme::Window).decoration(KColorScheme::FocusColor).color();
}

// rounded pill button; seg = part of a segmented control (filled accent when on)
class LxChip : public QAbstractButton
{
public:
    LxChip(const QString &text, QWidget *parent, bool seg = false, const QIcon &icon = QIcon())
        : QAbstractButton(parent)
        , m_seg(seg)
    {
        setText(text);
        setIcon(icon);
        setCheckable(true);
        setCursor(Qt::PointingHandCursor);
        setAttribute(Qt::WA_Hover);
        setFocusPolicy(Qt::TabFocus);
    }
    QSize sizeHint() const override
    {
        const QFontMetrics fm(font());
        const int iw = icon().isNull() ? 0 : 22;
        return QSize(fm.horizontalAdvance(text()) + iw + 26, fm.height() + 14);
    }
    QSize minimumSizeHint() const override
    {
        return sizeHint();
    }

protected:
    void paintEvent(QPaintEvent *) override
    {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        const QPalette pal = palette();
        const QColor win = pal.color(QPalette::Window), txt = pal.color(QPalette::WindowText), hi = lxAccent();
        const bool on = isChecked();
        QColor bg = on ? (m_seg ? hi : pal.color(QPalette::Active, QPalette::Highlight)) : (m_seg ? QColor(Qt::transparent) : lxMix(win, txt, 0.12));
        if (underMouse() && !on) {
            bg = lxMix(win, txt, 0.18);
        }
        const QColor fg = (on && m_seg) ? lxMix(win, hi, 0.12) : (on ? txt : lxMix(win, txt, 0.72));
        const QRectF r = QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5);
        p.setPen(Qt::NoPen);
        p.setBrush(bg);
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2);
        if (hasFocus()) {
            QPen pen(hi, 1.2);
            p.setPen(pen);
            p.setBrush(Qt::NoBrush);
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2);
        }
        QFont f = font();
        if (on && m_seg) {
            f.setWeight(QFont::Medium);
        }
        p.setFont(f);
        const QFontMetrics fm(f);
        const int iw = icon().isNull() ? 0 : 22;
        const int total = fm.horizontalAdvance(text()) + iw;
        int x = (width() - total) / 2;
        if (iw) {
            QImage img = icon().pixmap(QSize(16, 16), devicePixelRatioF()).toImage().convertToFormat(QImage::Format_ARGB32_Premultiplied);
            {
                QPainter ip(&img);
                ip.setCompositionMode(QPainter::CompositionMode_SourceIn);
                ip.fillRect(img.rect(), fg);
            }
            p.drawImage(QRectF(x, (height() - 16) / 2.0, 16, 16), img);
            x += iw;
        }
        p.setPen(fg);
        p.drawText(QRect(x, 0, width() - x, height()), Qt::AlignVCenter | Qt::AlignLeft, text());
    }

private:
    bool m_seg;
};

// on/off switch
class LxSwitch : public QAbstractButton
{
public:
    explicit LxSwitch(QWidget *parent)
        : QAbstractButton(parent)
    {
        setCheckable(true);
        setCursor(Qt::PointingHandCursor);
        setFocusPolicy(Qt::TabFocus);
    }
    QSize sizeHint() const override
    {
        return QSize(38, 22);
    }

protected:
    void paintEvent(QPaintEvent *) override
    {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        const QPalette pal = palette();
        const QColor win = pal.color(QPalette::Window), txt = pal.color(QPalette::WindowText), hi = lxAccent();
        const QRectF track(0.5, (height() - 22) / 2.0 + 0.5, 37, 21);
        p.setPen(Qt::NoPen);
        p.setBrush(isChecked() ? hi : lxMix(win, txt, 0.18));
        p.drawRoundedRect(track, 10.5, 10.5);
        p.setBrush(isChecked() ? lxMix(win, hi, 0.12) : lxMix(win, txt, 0.55));
        const qreal kx = isChecked() ? track.right() - 18.5 : track.left() + 2.5;
        p.drawEllipse(QRectF(kx, track.top() + 2.5, 16, 16));
        if (hasFocus()) {
            p.setPen(QPen(hi, 1.2));
            p.setBrush(Qt::NoBrush);
            p.drawRoundedRect(track, 10.5, 10.5);
        }
    }
};

// pill-shaped tray behind a segmented control
class LxTray : public QWidget
{
public:
    explicit LxTray(QWidget *parent)
        : QWidget(parent)
    {
    }

protected:
    void paintEvent(QPaintEvent *) override
    {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        const QPalette pal = palette();
        p.setPen(Qt::NoPen);
        p.setBrush(lxMix(pal.color(QPalette::Window), pal.color(QPalette::WindowText), 0.09));
        const QRectF r = QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5);
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2);
    }
};

// a whole row that flips its switch when clicked anywhere
class LxToggleRow : public QWidget
{
public:
    LxToggleRow(const QString &label, const QString &hint, QWidget *parent)
        : QWidget(parent)
    {
        setCursor(Qt::PointingHandCursor);
        auto *h = new QHBoxLayout(this);
        h->setContentsMargins(4, 3, 2, 3);
        auto *l = new QLabel(label, this);
        h->addWidget(l);
        if (!hint.isEmpty()) {
            auto *k = new QLabel(hint, this);
            QPalette kp = k->palette();
            kp.setColor(QPalette::WindowText, lxMix(kp.color(QPalette::Window), kp.color(QPalette::WindowText), 0.5));
            k->setPalette(kp);
            QFont f = k->font();
            f.setPointSizeF(f.pointSizeF() * 0.85);
            k->setFont(f);
            h->addWidget(k);
        }
        h->addStretch(1);
        sw = new LxSwitch(this);
        h->addWidget(sw);
    }
    LxSwitch *sw;

protected:
    void mouseReleaseEvent(QMouseEvent *e) override
    {
        if (e->button() == Qt::LeftButton && rect().contains(e->position().toPoint())) {
            sw->click();
        }
    }
};

QLabel *lxHeader(const QString &text, QWidget *parent)
{
    auto *l = new QLabel(text.toUpper(), parent);
    QFont f = l->font();
    f.setPointSizeF(f.pointSizeF() * 0.78);
    f.setWeight(QFont::Medium);
    f.setLetterSpacing(QFont::PercentageSpacing, 106);
    l->setFont(f);
    QPalette pl = l->palette();
    pl.setColor(QPalette::WindowText, lxMix(pl.color(QPalette::Window), pl.color(QPalette::WindowText), 0.5));
    l->setPalette(pl);
    l->setContentsMargins(4, 8, 0, 2);
    return l;
}
}
'''

VIEW_PANEL_BUILD = r'''
    ''' + TAG + r''': the View button opens one Luminos panel instead of a long menu
    if (LuminosFiles::Style::self().flag("filesViewPanel", true)) {
        auto *panel = new QWidget;
        panel->setMinimumWidth(LuminosFiles::Style::self().px("filesViewPanelWidth", 330, 260, 520));
        auto *v = new QVBoxLayout(panel);
        v->setContentsMargins(12, 6, 12, 10);
        v->setSpacing(4);
        KActionCollection *ac = m_actionCollection;
        auto syncing = std::make_shared<bool>(false);
        auto sync = std::make_shared<std::function<void()>>();

        // View as
        v->addWidget(lxHeader(i18nc("@title:group", "View as"), panel));
        auto *modeTray = new LxTray(panel);
        auto *mh = new QHBoxLayout(modeTray);
        mh->setContentsMargins(3, 3, 3, 3);
        mh->setSpacing(2);
        const QList<QPair<QString, QString>> modes = {{QStringLiteral("icons"), i18nc("@action view mode", "Icons")},
                                                     {QStringLiteral("compact"), i18nc("@action view mode", "Compact")},
                                                     {QStringLiteral("details"), i18nc("@action view mode", "List")}};
        QList<LxChip *> modeChips;
        for (const auto &m : modes) {
            auto *c = new LxChip(m.second, modeTray, true, ac->action(m.first)->icon());
            c->setToolTip(ac->action(m.first)->shortcut().toString(QKeySequence::NativeText));
            mh->addWidget(c, 1);
            modeChips << c;
            connect(c, &QAbstractButton::clicked, this, [ac, m, sync] {
                ac->action(m.first)->trigger();
                (*sync)();
            });
        }
        v->addWidget(modeTray);

        // Size
        v->addWidget(lxHeader(i18nc("@title:group", "Size"), panel));
        auto *sizeRow = new QWidget(panel);
        auto *sh = new QHBoxLayout(sizeRow);
        sh->setContentsMargins(4, 0, 4, 0);
        auto *slider = new QSlider(Qt::Horizontal, sizeRow);
        slider->setRange(0, 3);
        slider->setPageStep(1);
        slider->setTickPosition(QSlider::TicksBelow);
        slider->setTickInterval(1);
        auto *sizeLabel = new QLabel(sizeRow);
        sizeLabel->setMinimumWidth(QFontMetrics(sizeLabel->font()).horizontalAdvance(QStringLiteral("XL")) + 6);
        sizeLabel->setAlignment(Qt::AlignCenter);
        QFont slf = sizeLabel->font();
        slf.setWeight(QFont::DemiBold);
        sizeLabel->setFont(slf);
        sh->addWidget(slider, 1);
        sh->addWidget(sizeLabel);
        v->addWidget(sizeRow);
        // zoom level per S/M/L/XL for each view mode (style.json can override: filesZoom<Mode><n>)
        auto stops = [](int mode) -> QList<int> {
            const auto &lx = LuminosFiles::Style::self();
            if (mode == DolphinView::IconsView) {
                return {lx.px("filesZoomIcons0", 3, 0, 16), lx.px("filesZoomIcons1", 4, 0, 16), lx.px("filesZoomIcons2", 5, 0, 16), lx.px("filesZoomIcons3", 7, 0, 16)};
            }
            if (mode == DolphinView::CompactView) {
                return {lx.px("filesZoomCompact0", 1, 0, 16), lx.px("filesZoomCompact1", 2, 0, 16), lx.px("filesZoomCompact2", 3, 0, 16), lx.px("filesZoomCompact3", 4, 0, 16)};
            }
            return {lx.px("filesZoomList0", 0, 0, 16), lx.px("filesZoomList1", 1, 0, 16), lx.px("filesZoomList2", 2, 0, 16), lx.px("filesZoomList3", 3, 0, 16)};
        };
        const QStringList sizeNames = {QStringLiteral("S"), QStringLiteral("M"), QStringLiteral("L"), QStringLiteral("XL")};
        connect(slider, &QSlider::valueChanged, this, [this, slider, sizeLabel, sizeNames, stops, syncing](int val) {
            sizeLabel->setText(sizeNames.value(val));
            if (*syncing || !m_currentView) {
                return;
            }
            m_currentView->setZoomLevel(stops(m_currentView->viewMode()).value(val));
            Q_UNUSED(slider);
        });

        // Sort by
        v->addWidget(lxHeader(i18nc("@title:group", "Sort by"), panel));
        auto *sortRow = new QWidget(panel);
        auto *srh = new QHBoxLayout(sortRow);
        srh->setContentsMargins(0, 0, 0, 0);
        srh->setSpacing(6);
        const QList<QPair<QString, QString>> sorts = {{QStringLiteral("text"), i18nc("@action sort", "Name")},
                                                     {QStringLiteral("modificationtime"), i18nc("@action sort", "Date")},
                                                     {QStringLiteral("size"), i18nc("@action sort", "Size")},
                                                     {QStringLiteral("type"), i18nc("@action sort", "Kind")}};
        QList<LxChip *> sortChips;
        for (const auto &so : sorts) {
            auto *c = new LxChip(so.second, sortRow);
            srh->addWidget(c);
            sortChips << c;
            connect(c, &QAbstractButton::clicked, this, [ac, so, sync] {
                QAction *a = ac->action(QStringLiteral("sort_by_") + so.first);
                if (a && a->isChecked()) { // tapping the active one flips the order
                    QAction *asc = ac->action(QStringLiteral("ascending"));
                    ac->action(asc->isChecked() ? QStringLiteral("descending") : QStringLiteral("ascending"))->trigger();
                } else if (a) {
                    a->trigger();
                }
                (*sync)();
            });
        }
        srh->addStretch(1);
        v->addWidget(sortRow);

        // Group
        v->addWidget(lxHeader(i18nc("@title:group", "Group"), panel));
        const QList<QPair<QString, QString>> groupsList = {{QStringLiteral("group_text"), i18nc("@action group", "Folders & files")},
                                                          {QStringLiteral("group_type"), i18nc("@action group", "By kind")},
                                                          {QStringLiteral("group_modificationtime"), i18nc("@action group", "By date")},
                                                          {QStringLiteral("group_by_none"), i18nc("@action group", "None")}};
        QList<LxChip *> groupChips;
        QHBoxLayout *grh = nullptr;
        for (int gi = 0; gi < groupsList.size(); ++gi) {
            if (gi % 2 == 0) {
                auto *row = new QWidget(panel);
                grh = new QHBoxLayout(row);
                grh->setContentsMargins(0, 0, 0, gi == 0 ? 4 : 0);
                grh->setSpacing(6);
                v->addWidget(row);
            }
            const auto g = groupsList.at(gi);
            auto *c = new LxChip(g.second, panel);
            grh->addWidget(c);
            if (gi % 2 == 1) {
                grh->addStretch(1);
            }
            groupChips << c;
            connect(c, &QAbstractButton::clicked, this, [ac, g, sync] {
                if (QAction *a = ac->action(g.first)) {
                    a->trigger();
                }
                (*sync)();
            });
        }

        // Show
        v->addWidget(lxHeader(i18nc("@title:group", "Show"), panel));
        struct ToggleDef {
            QString action;
            QString label;
            QString hint;
        };
        const QList<ToggleDef> toggles = {{QStringLiteral("folders_first"), i18nc("@option", "Folders first"), QString()},
                                          {QStringLiteral("show_hidden_files"), i18nc("@option", "Hidden files"), ac->action(QStringLiteral("show_hidden_files"))->shortcut().toString(QKeySequence::NativeText)},
                                          {QStringLiteral("show_preview"), i18nc("@option", "Picture previews"), QString()},
                                          {QStringLiteral("show_size"), i18nc("@option", "Size / item count under names"), QString()},
                                          {QStringLiteral("luminos_colour"), i18nc("@option", "Colour by file type"), QString()}};
        QList<LxToggleRow *> toggleRows;
        for (const auto &t : toggles) {
            auto *row = new LxToggleRow(t.label, t.hint, panel);
            v->addWidget(row);
            toggleRows << row;
            connect(row->sw, &QAbstractButton::clicked, this, [ac, t, sync, row] {
                if (t.action == QLatin1String("luminos_colour")) {
                    // switch the icon theme between the coloured Luminos pack and the plain monochrome one
                    KConfigGroup icons(KSharedConfig::openConfig(QStringLiteral("kdeglobals")), QStringLiteral("Icons"));
                    icons.writeEntry("Theme", row->sw->isChecked() ? QStringLiteral("luminos-files") : QStringLiteral("yet-another-monochrome-icon-set"), KConfigBase::Normal | KConfigBase::Notify);
                    icons.sync();
                    KIconLoader::emitChange(KIconLoader::Desktop);
                } else if (QAction *a = ac->action(t.action)) {
                    a->trigger();
                }
                (*sync)();
            });
        }

        // Remember for
        v->addWidget(lxHeader(i18nc("@title:group", "Remember these for"), panel));
        auto *scopeTray = new LxTray(panel);
        auto *sch = new QHBoxLayout(scopeTray);
        sch->setContentsMargins(3, 3, 3, 3);
        sch->setSpacing(2);
        auto *thisFolder = new LxChip(i18nc("@option", "This folder"), scopeTray, true);
        auto *allFolders = new LxChip(i18nc("@option", "All folders"), scopeTray, true);
        sch->addWidget(thisFolder, 1);
        sch->addWidget(allFolders, 1);
        v->addWidget(scopeTray);
        auto setScope = [this, sync](bool global) {
            if (!m_currentView || GeneralSettings::globalViewProps() == global) {
                (*sync)();
                return;
            }
            const QUrl url = m_currentView->url();
            if (global) {
                // what this folder looks like now becomes the look for every folder
                ViewProperties current(url);
                GeneralSettings::setGlobalViewProps(true);
                ViewProperties globalProps(url);
                globalProps.setDirProperties(current);
                globalProps.save();
            } else {
                GeneralSettings::setGlobalViewProps(false);
            }
            GeneralSettings::self()->save();
            (*sync)();
        };
        connect(thisFolder, &QAbstractButton::clicked, this, [setScope] {
            setScope(false);
        });
        connect(allFolders, &QAbstractButton::clicked, this, [setScope] {
            setScope(true);
        });

        *sync = [this, ac, modes, modeChips, sorts, sortChips, groupsList, groupChips, toggles, toggleRows, slider, sizeLabel, sizeNames, stops, thisFolder,
                 allFolders, syncing] {
            *syncing = true;
            for (int i = 0; i < modes.size(); ++i) {
                modeChips[i]->setChecked(ac->action(modes[i].first)->isChecked());
            }
            const bool asc = ac->action(QStringLiteral("ascending"))->isChecked();
            for (int i = 0; i < sorts.size(); ++i) {
                QAction *a = ac->action(QStringLiteral("sort_by_") + sorts[i].first);
                const bool on = a && a->isChecked();
                sortChips[i]->setChecked(on);
                sortChips[i]->setText(sorts[i].second + (on ? (asc ? QStringLiteral(" ↑") : QStringLiteral(" ↓")) : QString()));
                sortChips[i]->updateGeometry();
            }
            for (int i = 0; i < groupsList.size(); ++i) {
                QAction *a = ac->action(groupsList[i].first);
                groupChips[i]->setChecked(a && a->isChecked());
            }
            for (int i = 0; i < toggles.size(); ++i) {
                bool on = false;
                if (toggles[i].action == QLatin1String("luminos_colour")) {
                    on = KConfigGroup(KSharedConfig::openConfig(QStringLiteral("kdeglobals")), QStringLiteral("Icons")).readEntry("Theme", QString()) == QLatin1String("luminos-files");
                } else if (QAction *a = ac->action(toggles[i].action)) {
                    on = a->isChecked();
                }
                toggleRows[i]->sw->setChecked(on);
            }
            if (m_currentView) {
                const QList<int> s = stops(m_currentView->viewMode());
                const int z = m_currentView->zoomLevel();
                int best = 0;
                for (int i = 1; i < s.size(); ++i) {
                    if (std::abs(s[i] - z) < std::abs(s[best] - z)) {
                        best = i;
                    }
                }
                slider->setValue(best);
                sizeLabel->setText(sizeNames.value(best));
            }
            const bool global = GeneralSettings::globalViewProps();
            thisFolder->setChecked(!global);
            allFolders->setChecked(global);
            *syncing = false;
        };

        viewSettings->menu()->clear();
        auto *panelAction = new QWidgetAction(viewSettings);
        panelAction->setDefaultWidget(panel);
        viewSettings->addAction(panelAction);
        viewSettings->setPopupMode(QToolButton::InstantPopup);
        connect(viewSettings->menu(), &QMenu::aboutToShow, panel, [sync] {
            (*sync)();
        });
        // keep it right while open (keyboard shortcuts / Ctrl+wheel change the view underneath)
        connect(this, &DolphinViewActionHandler::luminosViewStateChanged, panel, [sync, panel] {
            if (panel->isVisible()) {
                (*sync)();
            }
        });
    }
'''

edit('views/dolphinviewactionhandler.cpp', [
 ('#include <QPointer>\n', '''#include <QPointer>
#include <QAbstractButton>
#include <QHBoxLayout>
#include <QLabel>
#include <QMouseEvent>
#include <QPainter>
#include <QSlider>
#include <QVBoxLayout>
#include <QWidgetAction>
#include <KColorScheme>
#include <KColorUtils>
#include <KConfigGroup>
#include <KIconLoader>
#include <KSharedConfig>
#include "dolphin_generalsettings.h"
#include "views/viewproperties.h"
#include "luminosfilesstyle_p.h" ''' + TAG + '''
#include <functional>
#include <memory>
''' + VIEW_PANEL_CLASSES),
 ('''    // HACK KActionMenu doesn't set a parent for its menu() causing accessibility traversal issues
    viewSettings->menu()->setParent(QApplication::activeWindow());
}''', '''    // HACK KActionMenu doesn't set a parent for its menu() causing accessibility traversal issues
    viewSettings->menu()->setParent(QApplication::activeWindow());
''' + VIEW_PANEL_BUILD + '''}'''),
 # tell the panel when the view changes underneath it
 ('''    connect(view, &DolphinView::zoomLevelChanged, this, &DolphinViewActionHandler::slotZoomLevelChanged);''',
  '''    connect(view, &DolphinView::zoomLevelChanged, this, &DolphinViewActionHandler::slotZoomLevelChanged);
    ''' + TAG + '''
    connect(view, &DolphinView::modeChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::zoomLevelChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::sortRoleChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::sortOrderChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::groupRoleChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::groupedSortingChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::hiddenFilesShownChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::previewsShownChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::visibleRolesChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);
    connect(view, &DolphinView::sortFoldersFirstChanged, this, &DolphinViewActionHandler::luminosViewStateChanged);'''),
])

hp = f'{src}/views/dolphinviewactionhandler.h'
h = open(hp).read()
anchor = 'Q_SIGNALS:\n'
assert h.count(anchor) == 1, 'handler Q_SIGNALS'
h = h.replace(anchor, anchor + '    ' + TAG + ': the View panel re-reads the view when this fires\n    void luminosViewStateChanged();\n\n')
open(hp, 'w').write(h)

# ---------------------------------------------------------------- 4. ☰ menu
QUICK_CLASSES = r'''
''' + TAG + r''': square buttons for the quick row at the top of the ☰ menu
namespace
{
class LxQuickButton : public QToolButton
{
public:
    explicit LxQuickButton(QWidget *parent)
        : QToolButton(parent)
    {
        setToolButtonStyle(Qt::ToolButtonTextUnderIcon);
        setAutoRaise(true);
        setAttribute(Qt::WA_Hover);
        setCursor(Qt::PointingHandCursor);
        setIconSize(QSize(20, 20));
        setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    }
    QSize sizeHint() const override
    {
        const QFontMetrics fm(font());
        return QSize(qMax(64, fm.horizontalAdvance(text()) + 14), 20 + fm.height() + 24);
    }

protected:
    void paintEvent(QPaintEvent *) override
    {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        const QPalette pal = palette();
        const QColor win = pal.color(QPalette::Window), txt = pal.color(QPalette::WindowText);
        p.setPen(Qt::NoPen);
        p.setBrush(KColorUtils::mix(win, txt, underMouse() ? 0.17 : 0.10));
        p.drawRoundedRect(QRectF(rect()).adjusted(1, 1, -1, -1), 14, 14);
        const QColor fg = underMouse() ? txt : KColorUtils::mix(win, txt, 0.78);
        QImage img = icon().pixmap(QSize(20, 20), devicePixelRatioF()).toImage().convertToFormat(QImage::Format_ARGB32_Premultiplied);
        {
            QPainter ip(&img);
            ip.setCompositionMode(QPainter::CompositionMode_SourceIn);
            ip.fillRect(img.rect(), fg);
        }
        p.drawImage(QRectF((width() - 20) / 2.0, 10, 20, 20), img);
        QFont f = font();
        f.setPointSizeF(f.pointSizeF() * 0.82);
        p.setFont(f);
        p.setPen(fg);
        p.drawText(QRect(2, 34, width() - 4, height() - 38), Qt::AlignHCenter | Qt::AlignTop | Qt::TextWordWrap, text());
    }
};
}
'''

edit('dolphinmainwindow.cpp', [
 ('#include <QToolButton>\n', '#include <QToolButton>\n#include <QWidgetAction>\n#include <QAbstractButton>\n#include <QSlider>\n#include <QHBoxLayout>\n#include <QPainter>\n#include <KColorUtils>\n#include "luminosfilesstyle_p.h" ' + TAG + '\n'),
 ('#include <KStartupInfo>\n', '#include <KStartupInfo>\n' + QUICK_CLASSES),
 # menu body
 ('''    // This group of actions (until the next separator) contains all the most basic actions
    // necessary to use Dolphin effectively.
    menu->addAction(ac->action(QStringLiteral("go_back")));
    menu->addAction(ac->action(QStringLiteral("go_forward")));

    menu->addMenu(m_newFileMenu->menu());
    if (!toolBar()->isVisible() || !toolbarActions.contains(ac->action(QStringLiteral("toggle_selection_mode_tool_bar")))) {
        menu->addAction(ac->action(QStringLiteral("toggle_selection_mode")));
    }
    menu->addAction(ac->action(QStringLiteral("basic_actions")));
    menu->addAction(ac->action(KStandardAction::name(KStandardAction::Undo)));
    menu->addAction(ac->action(KStandardAction::name(KStandardAction::Redo)));''',
 '''    if (LuminosFiles::Style::self().flag("filesHamburgerLayout", true)) {
        ''' + TAG + ''': quick row of big buttons, then grouped sub-menus (approved prototype)
        auto *quick = new QWidget(menu);
        auto *qh = new QHBoxLayout(quick);
        qh->setContentsMargins(8, 6, 8, 6);
        qh->setSpacing(4);
        const QList<QPair<QString, QString>> quickActions = {{QStringLiteral("create_dir"), i18nc("@action quick button", "New folder")},
                                                            {QStringLiteral("new_tab"), i18nc("@action quick button", "New tab")},
                                                            {QStringLiteral("file_new"), i18nc("@action quick button", "Window")},
                                                            {QStringLiteral("show_terminal_panel"), i18nc("@action quick button", "Terminal")}};
        for (const auto &qa : quickActions) {
            QAction *a = ac->action(qa.first);
            if (!a) {
                continue;
            }
            auto *b = new LxQuickButton(quick);
            b->setIcon(a->icon());
            b->setText(qa.second);
            b->setToolTip(a->text().remove(QLatin1Char('&')));
            qh->addWidget(b);
            connect(b, &QToolButton::clicked, this, [a, menu] {
                menu->close();
                a->trigger();
            });
        }
        auto *quickAction = new QWidgetAction(menu);
        quickAction->setDefaultWidget(quick);
        menu->addAction(quickAction);

        menu->addMenu(m_newFileMenu->menu());
        auto *selectMenu = menu->addMenu(QIcon::fromTheme(QStringLiteral("edit-select")), i18nc("@action:inmenu", "Select"));
        selectMenu->addAction(ac->action(KStandardAction::name(KStandardAction::SelectAll)));
        selectMenu->addAction(ac->action(QStringLiteral("invert_selection")));
        selectMenu->addSeparator();
        selectMenu->addAction(ac->action(QStringLiteral("toggle_selection_mode")));
        auto *folderMenu = menu->addMenu(QIcon::fromTheme(QStringLiteral("folder")), i18nc("@action:inmenu actions for the folder you are in", "This folder"));
        for (const char *name : {"open_terminal_here", "add_to_places", "view_properties", "properties"}) {
            if (QAction *a = ac->action(QLatin1String(name))) {
                folderMenu->addAction(a);
            }
        }
        folderMenu->addSeparator();
        folderMenu->addAction(ac->action(QStringLiteral("basic_actions")));
        menu->addSeparator();
        menu->addAction(ac->action(KStandardAction::name(KStandardAction::Undo)));
        menu->addAction(ac->action(KStandardAction::name(KStandardAction::Redo)));
        if (!toolBar()->isVisible()
            || (!toolbarActions.contains(ac->action(QStringLiteral("toggle_search")))
                && !toolbarActions.contains(ac->action(QStringLiteral("open_preferred_search_tool"))))) {
            menu->addAction(ac->action(KStandardAction::name(KStandardAction::Find)));
        }
        if (!toolBar()->isVisible() || !toolbarActions.contains(ac->action(QStringLiteral("toggle_filter")))) {
            menu->addAction(ac->action(QStringLiteral("show_filter_bar")));
        }
        if (ac->action(QStringLiteral("undo_close_tab"))->isEnabled()) {
            menu->addAction(ac->action(QStringLiteral("closed_tabs")));
        }
        menu->addSeparator();
        if (!toolBar()->isVisible() || !toolbarActions.contains(ac->action(QStringLiteral("view_settings")))) {
            menu->addAction(ac->action(QStringLiteral("view_settings")));
        }
        menu->addAction(ac->action(QStringLiteral("panels")));
        auto *configureMenu = menu->addMenu(QIcon::fromTheme(QStringLiteral("configure")), i18nc("@action:inmenu menu for configure actions", "Configure"));
        configureMenu->addAction(ac->action(KStandardAction::name(KStandardAction::Preferences)));
        configureMenu->addAction(ac->action(KStandardAction::name(KStandardAction::KeyBindings)));
        configureMenu->addAction(ac->action(KStandardAction::name(KStandardAction::ConfigureToolbars)));
        configureMenu->addAction(ac->action(KStandardAction::name(KStandardAction::ShowMenubar)));
        configureMenu->addSeparator();
        configureMenu->addAction(actionCollection()->action(QStringLiteral("window_color_sheme")));
        configureMenu->addAction(ac->action(KStandardAction::name(KStandardAction::SwitchApplicationLanguage)));
        hamburgerMenu->hideActionsOf(configureMenu);
        return;
    }

    // This group of actions (until the next separator) contains all the most basic actions
    // necessary to use Dolphin effectively.
    menu->addAction(ac->action(QStringLiteral("go_back")));
    menu->addAction(ac->action(QStringLiteral("go_forward")));

    menu->addMenu(m_newFileMenu->menu());
    if (!toolBar()->isVisible() || !toolbarActions.contains(ac->action(QStringLiteral("toggle_selection_mode_tool_bar")))) {
        menu->addAction(ac->action(QStringLiteral("toggle_selection_mode")));
    }
    menu->addAction(ac->action(QStringLiteral("basic_actions")));
    menu->addAction(ac->action(KStandardAction::name(KStandardAction::Undo)));
    menu->addAction(ac->action(KStandardAction::name(KStandardAction::Redo)));'''),
 # test aid (like LUMINOS_SS_OPEN_DRAWER in systemsettings)
 ('''    connect(hamburgerMenu, &KHamburgerMenu::aboutToShowMenu, this, &DolphinMainWindow::updateHamburgerMenu);''',
  '''    connect(hamburgerMenu, &KHamburgerMenu::aboutToShowMenu, this, &DolphinMainWindow::updateHamburgerMenu);
    ''' + TAG + ''' test aid: LUMINOS_FILES_TEST=view|menu|select|undo opens that part once, 3.5 s after start
    if (const QByteArray luminosTest = qgetenv("LUMINOS_FILES_TEST"); !luminosTest.isEmpty()) {
        QTimer::singleShot(3500, this, [this, luminosTest] {
            // Wayland refuses pop-ups that no click opened, so the menus are also saved as pictures
            const QString out = qEnvironmentVariable("LUMINOS_FILES_TEST_OUT", QStringLiteral("/tmp/luminos-files-test.png"));
            auto grabMenu = [out](QMenu *m) {
                if (!m) {
                    return;
                }
                Q_EMIT m->aboutToShow();
                m->ensurePolished();
                m->adjustSize();
                m->grab().save(out);
            };
            if (luminosTest == "view") {
                grabMenu(qobject_cast<KActionMenu *>(actionCollection()->action(QStringLiteral("view_settings")))->menu());
            } else if (luminosTest == "menu") {
                updateHamburgerMenu();
                grabMenu(static_cast<KHamburgerMenu *>(actionCollection()->action(KStandardAction::name(KStandardAction::HamburgerMenu)))->menu());
            } else if (luminosTest == "panel" && m_activeViewContainer) {
                // click through the View panel and report what the view did (proves every control works)
                QMenu *m = qobject_cast<KActionMenu *>(actionCollection()->action(QStringLiteral("view_settings")))->menu();
                Q_EMIT m->aboutToShow();
                auto click = [m](const QString &t) {
                    for (auto *b : m->findChildren<QAbstractButton *>()) {
                        if (b->text() == t || b->text().startsWith(t + QLatin1Char(' '))) {
                            b->click();
                            return true;
                        }
                    }
                    return false;
                };
                QList<QAbstractButton *> switches;
                for (auto *b : m->findChildren<QAbstractButton *>()) {
                    if (b->text().isEmpty() && b->isCheckable()) {
                        switches << b;
                    }
                }
                DolphinView *v = m_activeViewContainer->view();
                QSlider *sl = m->findChild<QSlider *>();
                QStringList r;
                click(QStringLiteral("List"));
                r << QStringLiteral("list:mode=%1").arg(int(v->viewMode()));
                if (sl) {
                    sl->setValue(3);
                    r << QStringLiteral("XL:zoom=%1").arg(v->zoomLevel());
                }
                click(QStringLiteral("Date"));
                r << QStringLiteral("date:sort=%1,order=%2").arg(QString::fromLatin1(v->sortRole())).arg(int(v->sortOrder()));
                click(QStringLiteral("Date"));
                r << QStringLiteral("date-again:order=%1").arg(int(v->sortOrder()));
                click(QStringLiteral("By kind"));
                r << QStringLiteral("bykind:group=%1,grouped=%2").arg(QString::fromLatin1(v->groupRole())).arg(v->groupedSorting());
                click(QStringLiteral("None"));
                r << QStringLiteral("none:grouped=%1").arg(v->groupedSorting());
                if (switches.size() >= 4) {
                    switches[1]->click();
                    r << QStringLiteral("hidden:%1").arg(v->hiddenFilesShown());
                    switches[1]->click();
                    switches[0]->click();
                    r << QStringLiteral("foldersfirst:%1").arg(v->sortFoldersFirst());
                    switches[0]->click();
                    switches[3]->click();
                    r << QStringLiteral("sizeline:%1").arg(v->visibleRoles().contains("size"));
                    switches[3]->click();
                }
                click(QStringLiteral("This folder"));
                r << QStringLiteral("thisfolder:global=%1").arg(GeneralSettings::globalViewProps());
                click(QStringLiteral("All folders"));
                r << QStringLiteral("allfolders:global=%1").arg(GeneralSettings::globalViewProps());
                // put everything back
                click(QStringLiteral("Name"));
                if (v->sortOrder() != Qt::AscendingOrder) {
                    click(QStringLiteral("Name"));
                }
                click(QStringLiteral("Folders & files"));
                click(QStringLiteral("Compact"));
                r << QStringLiteral("compact:mode=%1").arg(int(v->viewMode()));
                click(QStringLiteral("Icons"));
                if (sl) {
                    sl->setValue(1);
                }
                r << QStringLiteral("restored:mode=%1,zoom=%2,sort=%3,group=%4,grouped=%5")
                         .arg(int(v->viewMode()))
                         .arg(v->zoomLevel())
                         .arg(QString::fromLatin1(v->sortRole()))
                         .arg(QString::fromLatin1(v->groupRole()))
                         .arg(v->groupedSorting());
                qWarning().noquote() << "LUMINOS_FILES_TEST panel" << r.join(QLatin1Char(' '));
                grabMenu(m);
            } else if (luminosTest == "select") {
                actionCollection()->action(KStandardAction::name(KStandardAction::SelectAll))->trigger();
            } else if (luminosTest == "undo" && m_activeViewContainer) {
                m_activeViewContainer->luminosUndoMessage(i18nc("@info", "Moved to Trash"), actionCollection()->action(KStandardAction::name(KStandardAction::Undo)));
            }
        });
    }'''),
 # 5. selection bar follows the selection
 ('''void DolphinMainWindow::slotSelectionChanged(const KFileItemList &selection)
{
    updateFileAndEditActions();
''', '''void DolphinMainWindow::slotSelectionChanged(const KFileItemList &selection)
{
    updateFileAndEditActions();
    ''' + TAG + ''': selecting files shows the action bar at the bottom
    if (m_activeViewContainer) {
        m_activeViewContainer->luminosSelectionBar(selection, actionCollection());
    }
'''),
 # 6. undo message after trashing / moving
 ('''    connect(undoManager, &KIO::FileUndoManager::redoTextChanged, this, &DolphinMainWindow::slotRedoTextChanged);''',
  '''    connect(undoManager, &KIO::FileUndoManager::redoTextChanged, this, &DolphinMainWindow::slotRedoTextChanged);
    ''' + TAG + ''': "Moved to Trash · Undo" message that hides by itself
    connect(undoManager, &KIO::FileUndoManager::jobRecordingFinished, this, [this](KIO::FileUndoManager::CommandType type) {
        if (!m_activeViewContainer || !LuminosFiles::Style::self().flag("filesUndoMessage", true)) {
            return;
        }
        QString text;
        if (type == KIO::FileUndoManager::Trash) {
            text = i18nc("@info", "Moved to Trash");
        } else if (type == KIO::FileUndoManager::Move) {
            text = i18nc("@info", "Moved");
        } else {
            return;
        }
        m_activeViewContainer->luminosUndoMessage(text, actionCollection()->action(KStandardAction::name(KStandardAction::Undo)));
    });'''),
])

# neutral grey action bar instead of the tinted one
edit('selectionmode/backgroundcolorhelper.cpp', [
 ('#include "backgroundcolorhelper.h"\n', '#include "backgroundcolorhelper.h"\n#include <KColorUtils>\n#include "luminosfilesstyle_p.h" ' + TAG + '\n'),
 ('''                                        (activeBackgroundColor.alpha() + positiveBackgroundColor.alpha()) / 2);
}''', '''                                        (activeBackgroundColor.alpha() + positiveBackgroundColor.alpha()) / 2);
    ''' + TAG + ''': a calm grey bar that matches the rest of the window
    if (LuminosFiles::Style::self().flag("filesNeutralBars", true)) {
        m_backgroundColor = KColorUtils::mix(colorScheme.background().color(), colorScheme.foreground().color(), LuminosFiles::Style::self().num("filesBarMix", 7, 0, 60) / 100.0);
    }
}'''),
])

# container: helpers
edit('dolphinviewcontainer.h', [
 ('''    bool isSelectionModeEnabled() const;''', '''    bool isSelectionModeEnabled() const;

    ''' + TAG + ''': show / hide the bottom action bar for a plain selection (no selection mode)
    void luminosSelectionBar(const KFileItemList &selection, KActionCollection *actionCollection);
    ''' + TAG + ''': short message with an Undo button that hides by itself
    void luminosUndoMessage(const QString &text, QAction *undoAction);'''),
])
edit('dolphinviewcontainer.cpp', [
 ('#include "statusbar/dolphinstatusbar.h"\n', '#include "statusbar/dolphinstatusbar.h"\n#include "luminosfilesstyle_p.h" ' + TAG + '\n'),
 ('''        connect(m_selectionModeBottomBar, &SelectionMode::BottomBar::selectionModeLeavingRequested, this, [this]() {
            setSelectionModeEnabled(false);
        });
        m_topLayout->addWidget(m_selectionModeBottomBar, positionFor.selectionModeBottomBar, 0);
    }
    m_selectionModeBottomBar->resetContents(bottomBarContents);''',
 '''        connect(m_selectionModeBottomBar, &SelectionMode::BottomBar::selectionModeLeavingRequested, this, [this]() {
            if (!m_view->selectionMode()) { ''' + TAG + ''': bar shown for a plain selection → close = clear selection
                m_view->clearSelection();
                m_selectionModeBottomBar->setVisible(false, WithAnimation);
                return;
            }
            setSelectionModeEnabled(false);
        });
        m_topLayout->addWidget(m_selectionModeBottomBar, positionFor.selectionModeBottomBar, 0);
    }
    m_selectionModeBottomBar->resetContents(bottomBarContents);'''),
 ('''void DolphinViewContainer::slotSplitTabDisabled()''', '''''' + TAG + '''
void DolphinViewContainer::luminosSelectionBar(const KFileItemList &selection, KActionCollection *actionCollection)
{
    if (m_view->selectionMode() || !LuminosFiles::Style::self().flag("filesSelectionBar", true)) {
        return; // real selection mode runs its own bar
    }
    if (selection.isEmpty()) {
        if (m_selectionModeBottomBar && m_selectionModeBottomBar->isVisible()) {
            m_selectionModeBottomBar->setVisible(false, WithAnimation);
        }
        return;
    }
    if (!m_selectionModeBottomBar) {
        m_selectionModeBottomBar = new SelectionMode::BottomBar(actionCollection, this);
        connect(m_view, &DolphinView::selectionChanged, this, [this](const KFileItemList &sel) {
            m_selectionModeBottomBar->slotSelectionChanged(sel, m_view->url());
        });
        connect(m_selectionModeBottomBar, &SelectionMode::BottomBar::error, this, &DolphinViewContainer::showErrorMessage);
        connect(m_selectionModeBottomBar, &SelectionMode::BottomBar::selectionModeLeavingRequested, this, [this]() {
            if (!m_view->selectionMode()) {
                m_view->clearSelection();
                m_selectionModeBottomBar->setVisible(false, WithAnimation);
                return;
            }
            setSelectionModeEnabled(false);
        });
        m_topLayout->addWidget(m_selectionModeBottomBar, positionFor.selectionModeBottomBar, 0);
    }
    if (m_selectionModeBottomBar->contents() != SelectionMode::BottomBar::GeneralContents) {
        m_selectionModeBottomBar->resetContents(SelectionMode::BottomBar::GeneralContents);
    }
    m_selectionModeBottomBar->slotSelectionChanged(selection, m_view->url());
    if (!m_selectionModeBottomBar->isVisible()) {
        m_selectionModeBottomBar->setVisible(true, WithAnimation);
    }
}

''' + TAG + '''
void DolphinViewContainer::luminosUndoMessage(const QString &text, QAction *undoAction)
{
    if (!m_luminosUndo) {
        m_luminosUndo = new QAction(QIcon::fromTheme(QStringLiteral("edit-undo")), i18nc("@action:button", "Undo"), this);
        connect(m_luminosUndo, &QAction::triggered, this, [this] {
            if (m_luminosUndoTarget) {
                m_luminosUndoTarget->trigger();
            }
            m_messageWidget->animatedHide();
        });
    }
    m_luminosUndoTarget = undoAction;
    showMessage(text, KMessageWidget::Information, {m_luminosUndo});
    const int serial = ++m_luminosUndoSerial;
    QTimer::singleShot(LuminosFiles::Style::self().px("filesUndoMessageMs", 6000, 1500, 30000), this, [this, serial] {
        if (serial == m_luminosUndoSerial && m_messageWidget->isVisible() && m_messageWidget->actions().contains(m_luminosUndo)) {
            m_messageWidget->animatedHide();
        }
    });
}

void DolphinViewContainer::slotSplitTabDisabled()'''),
])
ch = f'{src}/dolphinviewcontainer.h'
t = open(ch).read()
# add members at the end of the last private section (before closing of class)
anchor = '    KMessageWidget *m_messageWidget;\n'
assert t.count(anchor) == 1, 'container m_messageWidget anchor'
t = t.replace(anchor, anchor + '    ' + TAG + '\n    QAction *m_luminosUndo = nullptr;\n    QPointer<QAction> m_luminosUndoTarget;\n    int m_luminosUndoSerial = 0;\n')
if '#include <QPointer>' not in t:
    t = t.replace('#include <QWidget>\n', '#include <QWidget>\n#include <QPointer>\n', 1)
open(ch, 'w').write(t)
print('ok')
