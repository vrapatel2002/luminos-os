#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-11-09] DECISION 182 — turns a pristine kio-6.30.0 tree into the Luminos one.
# usage: kio-edit.py <kio-src-dir> <path to luminosfilesstyle_p.h>
import shutil, sys
root, hdr = sys.argv[1], sys.argv[2]
p = f'{root}/src/filewidgets/kfileplacesview.cpp'
s = open(p).read()

def R(a, b, n=1):
    global s
    c = s.count(a)
    if c != n:
        sys.exit(f'expected {n} got {c}: {a[:80]!r}')
    s = s.replace(a, b)

shutil.copy(hdr, f'{root}/src/filewidgets/luminosfilesstyle_p.h')

R('#include "kfileplaceeditdialog.h"\n', '#include "kfileplaceeditdialog.h"\n#include "luminosfilesstyle_p.h" // [CHANGE: claude-code | 2026-11-09] DECISION 182\n')

# constructor: repaint when the tuner changes style.json
R('''    m_pollFreeSpace.setInterval(s_pollFreeSpaceInterval);
    connect(&m_pollFreeSpace, &QTimer::timeout, this, QOverload<>::of(&KFilePlacesViewDelegate::checkFreeSpace));''',
'''    m_pollFreeSpace.setInterval(s_pollFreeSpaceInterval);
    connect(&m_pollFreeSpace, &QTimer::timeout, this, QOverload<>::of(&KFilePlacesViewDelegate::checkFreeSpace));
    // [CHANGE: claude-code | 2026-11-09] DECISION 182: follow ~/.config/luminos/style.json live
    LuminosFiles::Style::self().onChange(this, [this] {
        m_view->doItemsLayout();
        m_view->viewport()->update();
    });''')

# ---- sizeHint
R('''    QStyleOptionViewItem hintOption(option);
    hintOption.features |= QStyleOptionViewItem::HasDecoration;
    hintOption.decorationSize = {m_iconSize, m_iconSize};

    int height = QApplication::style()->sizeFromContents(QStyle::CT_ItemViewItem, &hintOption, {}, option.widget).height();
''', '''    // [CHANGE: claude-code | 2026-11-09] DECISION 182: Luminos row = round icon disc + name (+ free-space bar for drives)
    const auto &lx = LuminosFiles::Style::self();
    int height = qMax(lx.px("filesPlaceRowPx", 44, 24, 96), option.fontMetrics.height() + 12);
    if (index.data(KFilePlacesModel::CapacityBarRecommendedRole).toBool()) {
        height += luminosCapacityExtra(option);
    }
''')

# ---- paint: replace the stock background + icon + capacity + text with the Luminos look
start = s.index('    QApplication::style()->drawPrimitive(QStyle::PE_PanelItemViewItem, &opt, painter);\n')
end = s.index('    painter->drawText(rectText, Qt::AlignLeft | Qt::AlignVCenter, elidedText);\n\n    painter->restore();\n}\n')
end_full = end + len('    painter->drawText(rectText, Qt::AlignLeft | Qt::AlignVCenter, elidedText);\n\n    painter->restore();\n}\n')
new_paint = r'''    // [CHANGE: claude-code | 2026-11-09] DECISION 182: Luminos look — pill background, icon in a
    // round disc, small free-space bar + "x free of y" for drives. Values: ~/.config/luminos/style.json.
    const auto &lx = LuminosFiles::Style::self();
    const int gap = lx.px("filesPlaceGapPx", 2, 0, 12);
    const int discPx = lx.px("filesPlaceDiscPx", 30, 0, 64);
    const int glyphPx = lx.px("filesPlaceGlyphPx", 18, 8, 48);
    const int padL = lx.px("filesPlacePadPx", 9, 0, 40);
    const int radiusSetting = lx.px("filesPlaceRadiusPx", -1, -1, 40);
    const bool isLTR = opt.direction == Qt::LeftToRight;

    QRect body = opt.rect.adjusted(2, gap / 2, -2, -(gap - gap / 2));
    const bool selected = opt.state & QStyle::State_Selected;
    const bool hovered = opt.state & QStyle::State_MouseOver;
    const QPalette::ColorGroup cgp = !(opt.state & QStyle::State_Enabled) ? QPalette::Disabled
        : m_view->isActiveWindow()                                       ? QPalette::Active
                                                                          : QPalette::Inactive;
    const QColor winC = opt.palette.color(cgp, QPalette::Window);
    const QColor textC = opt.palette.color(cgp, QPalette::WindowText);
    const QColor hiC = opt.palette.color(cgp, QPalette::Highlight);
    if (selected || hovered) {
        const qreal mixAmt = selected ? lx.num("filesPlaceSelMix", 100, 0, 100) / 100.0 : lx.num("filesPlaceHoverMix", 8, 0, 100) / 100.0;
        const QColor bg = KColorUtils::mix(winC, selected ? hiC : textC, mixAmt);
        const qreal r = radiusSetting < 0 ? body.height() / 2.0 : qMin<qreal>(radiusSetting, body.height() / 2.0);
        painter->save();
        painter->setRenderHint(QPainter::Antialiasing, true);
        painter->setPen(Qt::NoPen);
        painter->setBrush(bg);
        painter->drawRoundedRect(QRectF(body), r, r);
        painter->restore();
    }

    const auto accessibility = placesModel->deviceAccessibility(index);
    const bool isBusy = (accessibility == KFilePlacesModel::SetupInProgress || accessibility == KFilePlacesModel::TeardownInProgress)
        || (m_emptyingTrashIndex.isValid() && m_emptyingTrashIndex == index);

    QIcon actionIcon;
    if (isBusy) {
        actionIcon = QIcon::fromTheme(QStringLiteral("view-refresh"));
    } else if (placesModel->isTeardownOverlayRecommended(index)) {
        actionIcon = QIcon::fromTheme(QStringLiteral("media-eject"));
    }

    const bool capacityRow = placesModel->data(index, KFilePlacesModel::CapacityBarRecommendedRole).toBool();
    const int capExtra = capacityRow ? luminosCapacityExtra(opt) : 0;
    // the name/disc line is the top part of the row; drives add the bar + free text below it
    QRect line = body;
    line.setHeight(body.height() - capExtra);

    const int iconBox = discPx > 0 ? discPx : glyphPx;
    const int actionAreaWidth = !actionIcon.isNull() ? s_lateralMargin + actionIconSize() : s_lateralMargin;
    const QRect iconRect(isLTR ? body.left() + padL : body.right() - padL - iconBox + 1,
                         line.top() + (line.height() - iconBox) / 2, iconBox, iconBox);
    const int textLeft = isLTR ? iconRect.right() + 1 + lx.px("filesPlaceTextGapPx", 12, 0, 40) : body.left() + actionAreaWidth + s_lateralMargin;
    const int textRight = isLTR ? body.right() - actionAreaWidth - s_lateralMargin : iconRect.left() - lx.px("filesPlaceTextGapPx", 12, 0, 40);
    QRect rectText(textLeft, line.top(), qMax(0, textRight - textLeft), line.height());

    const QPalette activePalette = KIconLoader::global()->customPalette();
    const bool changePalette = activePalette != opt.palette;
    if (changePalette) {
        KIconLoader::global()->setCustomPalette(opt.palette);
    }

    const QIcon icon = index.model()->data(index, Qt::DecorationRole).value<QIcon>();
    const qreal dpr = painter->device() ? painter->device()->devicePixelRatioF() : qApp->devicePixelRatio();
    if (discPx > 0) {
        // Active colours even when the window is in the background, so the discs never turn grey
        // accent = the colour scheme's focus colour (lavender in Luminos), glyph = dark ink on it
        const QColor accent = KColorScheme(QPalette::Active, KColorScheme::Window).decoration(KColorScheme::FocusColor).color();
        const QColor discC = KColorUtils::mix(accent, winC, lx.num("filesPlaceDiscDim", 0, 0, 100) / 100.0);
        const QColor glyphC = KColorUtils::mix(winC, accent, lx.num("filesPlaceGlyphInk", 12, 0, 100) / 100.0);
        painter->save();
        painter->setRenderHint(QPainter::Antialiasing, true);
        painter->setPen(Qt::NoPen);
        painter->setBrush(discC);
        painter->drawEllipse(QRectF(iconRect));
        // glyph = the icon's shape, filled with one colour (so every icon reads as a symbol)
        // fetched at <= 20 px so file-type icon packs give their small glyph, not a big tile; then drawn at glyphPx
        const int fetchPx = qMin(glyphPx, lx.px("filesPlaceGlyphFetchMaxPx", 20, 8, 64));
        QImage img = icon.pixmap(QSize(fetchPx, fetchPx), dpr, QIcon::Normal).toImage().convertToFormat(QImage::Format_ARGB32_Premultiplied);
        {
            QPainter ip(&img);
            ip.setCompositionMode(QPainter::CompositionMode_SourceIn);
            ip.fillRect(img.rect(), glyphC);
        }
        const QSizeF gs = (QSizeF(img.size()) / img.devicePixelRatio()) * (qreal(glyphPx) / fetchPx);
        painter->setRenderHint(QPainter::SmoothPixmapTransform, true);
        painter->drawImage(QRectF(QPointF(iconRect.center().x() + 0.5 - gs.width() / 2.0, iconRect.center().y() + 0.5 - gs.height() / 2.0), gs), img);
        painter->restore();
    } else {
        const QPixmap pm = icon.pixmap(QSize(glyphPx, glyphPx), dpr, selected ? QIcon::Selected : QIcon::Normal);
        painter->drawPixmap(iconRect.topLeft(), pm);
    }

    if (!actionIcon.isNull()) {
        const int iconSize = actionIconSize();
        QIcon::Mode mode = QIcon::Normal;
        if (m_hoveredAction == index) {
            mode = QIcon::Active;
        }

        const QPixmap pixmap = actionIcon.pixmap(iconSize, iconSize, mode);

        // same spot as stock KIO, so clicking it still ejects (pointIsTeardownAction)
        const QRectF rect(isLTR ? opt.rect.right() - actionAreaWidth : opt.rect.left() + s_lateralMargin,
                          line.top() + (line.height() - iconSize) / 2,
                          iconSize,
                          iconSize);

        if (isBusy) {
            painter->save();
            painter->setRenderHint(QPainter::SmoothPixmapTransform);
            painter->translate(rect.center());
            painter->rotate(m_busyAnimationRotation);
            painter->translate(QPointF(-rect.width() / 2.0, -rect.height() / 2.0));
            painter->drawPixmap(0, 0, pixmap);
            painter->restore();
        } else {
            painter->drawPixmap(rect.topLeft(), pixmap);
        }
    }

    if (changePalette) {
        if (activePalette == QPalette()) {
            KIconLoader::global()->resetPalette();
        } else {
            KIconLoader::global()->setCustomPalette(activePalette);
        }
    }

    painter->setPen(textC);

    if (capacityRow) {
        const auto info = m_freeSpaceInfo.value(persistentIndex);

        checkFreeSpace(index); // async

        const int barH = lx.px("filesPlaceBarPx", 4, 1, 12);
        const QRect barRect(rectText.left(), line.bottom() + 1, qMax(0, body.right() - lx.px("filesPlacePadPx", 9, 0, 40) - rectText.left()), barH);
        QColor capacityBgColor = textC;
        capacityBgColor.setAlphaF(0.14 * capacityBgColor.alphaF());
        painter->save();
        painter->setRenderHint(QPainter::Antialiasing, true);
        painter->setPen(Qt::NoPen);
        painter->setBrush(capacityBgColor);
        painter->drawRoundedRect(QRectF(barRect), barH / 2.0, barH / 2.0);
        if (info.size > 0) {
            const qreal usedSpace = info.used / qreal(info.size);
            QColor capacityFgColor = KColorScheme(QPalette::Active, KColorScheme::Window).decoration(KColorScheme::FocusColor).color();
            if (usedSpace > 0.95) {
                if (!m_warningCapacityBarColor.isValid()) {
                    m_warningCapacityBarColor = KColorScheme(cgp, KColorScheme::View).foreground(KColorScheme::NegativeText).color();
                }
                capacityFgColor = m_warningCapacityBarColor;
            }
            QRectF fill(barRect);
            fill.setWidth(qMax<qreal>(barH, barRect.width() * usedSpace));
            painter->setBrush(capacityFgColor);
            painter->drawRoundedRect(fill, barH / 2.0, barH / 2.0);

            QFont small = opt.font;
            small.setPointSizeF(small.pointSizeF() * lx.num("filesPlaceSmallScale", 0.82, 0.5, 1.2));
            painter->setFont(small);
            QColor dim = textC;
            dim.setAlphaF(0.55);
            painter->setPen(dim);
            const QString freeText = i18nc("@info free disk space", "%1 free of %2", KIO::convertSize(info.size - info.used), KIO::convertSize(info.size));
            const QRect smallRect(barRect.left(), barRect.bottom() + 3, barRect.width(), QFontMetrics(small).height());
            painter->drawText(smallRect, Qt::AlignLeft | Qt::AlignTop, QFontMetrics(small).elidedText(freeText, Qt::ElideRight, smallRect.width()));
        }
        painter->restore();
        painter->setPen(textC);
    }

    QFont nameFont = opt.font;
    nameFont.setPointSizeF(nameFont.pointSizeF() * lx.num("filesPlaceTextScale", 1.0, 0.6, 1.6));
    painter->setFont(nameFont);
    const QFontMetrics nfm(nameFont);
    const QString text = index.model()->data(index).toString();
    const QString elidedText = nfm.elidedText(text, Qt::ElideRight, rectText.width());

    const bool isElided = (text != elidedText);

    if (isElided) {
        m_elidedTexts.insert(persistentIndex);
    } else if (auto it = m_elidedTexts.find(persistentIndex); it != m_elidedTexts.end()) {
        m_elidedTexts.erase(it);
    }

    painter->drawText(rectText, Qt::AlignLeft | Qt::AlignVCenter, elidedText);

    painter->restore();
}

// [CHANGE: claude-code | 2026-11-09] DECISION 182: room under a drive's name for its bar + "x free of y"
int KFilePlacesViewDelegate::luminosCapacityExtra(const QStyleOptionViewItem &option) const
{
    const auto &lx = LuminosFiles::Style::self();
    QFont small = option.font;
    small.setPointSizeF(small.pointSizeF() * lx.num("filesPlaceSmallScale", 0.82, 0.5, 1.2));
    return lx.px("filesPlaceBarPx", 4, 1, 12) + 3 + QFontMetrics(small).height() + 6;
}
'''
s = s[:start] + new_paint + s[end_full:]

# the stock code above the replaced part still computes isLTR etc? it doesn't — check nothing references removed names later
# ---- section header: small grey capitals
R('''    QRect textRect(option.rect);
    textRect.setLeft(textRect.left() + 6);''', '''    // [CHANGE: claude-code | 2026-11-09] DECISION 182: small grey capitals, lined up with the discs
    const auto &lx = LuminosFiles::Style::self();
    QFont headerFont = option.font;
    headerFont.setPointSizeF(headerFont.pointSizeF() * lx.num("filesPlaceHeaderScale", 0.8, 0.5, 1.4));
    headerFont.setWeight(QFont::Medium);
    if (lx.flag("filesPlaceHeaderCaps", true)) {
        headerFont.setCapitalization(QFont::AllUppercase);
        headerFont.setLetterSpacing(QFont::PercentageSpacing, 106);
    }
    QRect textRect(option.rect);
    textRect.setLeft(textRect.left() + 2 + lx.px("filesPlacePadPx", 9, 0, 40) + 3);''')
R('''    painter->setPen(penColor);
    painter->drawText(textRect, Qt::AlignLeft | Qt::AlignBottom, option.fontMetrics.elidedText(category, Qt::ElideRight, textRect.width()));''',
'''    penColor = mixedColor(c1, c2, lx.px("filesPlaceHeaderMix", 50, 10, 100));
    painter->setPen(penColor);
    painter->setFont(headerFont);
    painter->drawText(textRect, Qt::AlignLeft | Qt::AlignBottom, QFontMetrics(headerFont).elidedText(category, Qt::ElideRight, textRect.width()));''')
R('''    Q_UNUSED(index);
    // Account for the spacing between header and item
    const int spacing = (s_lateralMargin + m_view->spacing());
    int height = m_view->fontMetrics().height() + spacing;
    height += 2 * spacing;
    return height;''', '''    Q_UNUSED(index);
    // [CHANGE: claude-code | 2026-11-09] DECISION 182: height of the small capitals + room above
    const auto &lx = LuminosFiles::Style::self();
    QFont headerFont = m_view->font();
    headerFont.setPointSizeF(headerFont.pointSizeF() * lx.num("filesPlaceHeaderScale", 0.8, 0.5, 1.4));
    const int spacing = (s_lateralMargin + m_view->spacing());
    return QFontMetrics(headerFont).height() + lx.px("filesPlaceHeaderTopPx", 14, 0, 60) + spacing;''')
open(p, 'w').write(s)

h = f'{root}/src/filewidgets/kfileplacesview_p.h'
t = open(h).read()
a = '    int sectionHeaderHeight(const QModelIndex &index) const;\n'
assert t.count(a) == 1, 'hdr anchor'
t = t.replace(a, a + '    int luminosCapacityExtra(const QStyleOptionViewItem &option) const; // [CHANGE: claude-code | 2026-11-09] DECISION 182\n')
open(h, 'w').write(t)
print('ok')
