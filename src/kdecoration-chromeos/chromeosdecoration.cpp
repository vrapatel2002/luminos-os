// [CHANGE: claude-code | 2026-10-10] Luminos ChromeOS-style frame: decoration geometry, config, painting.
// Design constants derived from Chromium (ChromeOS ash/chromeos/ui frame code), (c) The Chromium
// Authors, BSD-3-Clause -- see chromeosdecoration.h for the source file of each constant.
#include "chromeosdecoration.h"
#include <KConfigGroup>
#include <KDecoration3/DecoratedWindow>
#include <KDecoration3/DecorationSettings>
#include <KPluginFactory>
#include <KSharedConfig>
#include <QLinearGradient>
#include <QPainter>
#include <algorithm>

K_PLUGIN_FACTORY_WITH_JSON(LuminosChromeOSFactory, "metadata.json", registerPlugin<Luminos::Decoration>(); registerPlugin<Luminos::Button>();)

namespace Luminos
{
namespace
{
// Garbage (non-integer) -> default; out of range -> clamped.
int readInt(const KConfigGroup &group, const char *key, int fallback, int lo, int hi)
{
    bool ok = false;
    const int value = group.readEntry(key, QString()).trimmed().toInt(&ok);
    return ok ? std::clamp(value, lo, hi) : fallback;
}

bool readBool(const KConfigGroup &group, const char *key, bool fallback)
{
    const QString s = group.readEntry(key, QString()).trimmed().toLower();
    const bool yes = s == QLatin1String("true") || s == QLatin1String("1");
    const bool no = s == QLatin1String("false") || s == QLatin1String("0");
    return yes ? true : (no ? false : fallback);
}

Config loadConfig(bool reparse)
{
    auto file = KSharedConfig::openConfig(QStringLiteral("luminos-chromeosrc"), KConfig::NoGlobals);
    if (reparse) {
        file->reparseConfiguration();
    }
    const KConfigGroup group(file, QStringLiteral("Frame"));
    const Config d;
    return Config{readInt(group, "CornerRadius", d.cornerRadius, 0, 32),
                  readInt(group, "HeaderHeight", d.headerHeight, 28, 64),
                  readBool(group, "ShowTitle", d.showTitle)};
}
}

Decoration::Decoration(QObject *parent, const QVariantList &args)
    : KDecoration3::Decoration(parent, args)
{
}

bool Decoration::init()
{
    using W = KDecoration3::DecoratedWindow;
    m_cfg = loadConfig(false);
    m_buttons = new KDecoration3::DecorationButtonGroup(this);
    m_buttons->setSpacing(0);
    for (auto type : {KDecoration3::DecorationButtonType::Minimize, KDecoration3::DecorationButtonType::Maximize,
                      KDecoration3::DecorationButtonType::Close}) {
        m_buttons->addButton(new Button(type, this, m_buttons));
    }
    auto *w = window();
    for (auto signal : {&W::activeChanged, &W::maximizedChanged, &W::maximizedHorizontallyChanged, &W::maximizedVerticallyChanged}) {
        connect(w, signal, this, &Decoration::updateLayout);
    }
    connect(w, &W::adjacentScreenEdgesChanged, this, &Decoration::updateLayout);
    connect(w, &W::widthChanged, this, &Decoration::updateButtons);
    const auto repaint = [this] { update(); };
    connect(w, &W::paletteChanged, this, repaint);
    connect(w, &W::captionChanged, this, repaint);
    connect(settings().get(), &KDecoration3::DecorationSettings::fontChanged, this, repaint);
    connect(m_buttons, &KDecoration3::DecorationButtonGroup::geometryChanged, this, &Decoration::updateButtons);
    connect(settings().get(), &KDecoration3::DecorationSettings::reconfigured, this, &Decoration::reconfigure);
    updateLayout();
    return true;
}

void Decoration::reconfigure()
{
    m_cfg = loadConfig(true);
    const auto buttons = m_buttons->buttons();
    for (auto *button : buttons) {
        button->setGeometry(QRectF(0, 0, Frame::ButtonW, m_cfg.headerHeight));
    }
    updateLayout();
}

// Square corners when maximized or tiled against a screen edge (ChromeOS does the same when snapped).
qreal Decoration::effectiveRadius() const
{
    const auto *w = window();
    const bool flush = w->isMaximized() || w->isMaximizedHorizontally() || w->isMaximizedVertically()
        || w->adjacentScreenEdges() != Qt::Edges();
    return flush ? 0 : m_cfg.cornerRadius;
}

void Decoration::updateLayout()
{
    const qreal r = effectiveRadius();
    const qreal e = Frame::ResizeOutside;
    setBorders(QMarginsF(0, m_cfg.headerHeight, 0, 0));
    setResizeOnlyBorders(QMarginsF(e, e, e, e));
    setBorderRadius(KDecoration3::BorderRadius(r));
    // Outer highlight ring: drawn by KWin around the whole window (client included), following the radius.
    const QColor outer(0, 0, 0, Frame::RingOuterAlpha);
    setBorderOutline(window()->isMaximized() ? KDecoration3::BorderOutline()
                                             : KDecoration3::BorderOutline(1, outer, KDecoration3::BorderRadius(r)));
    setShadow(cachedShadow(window()->isActive(), int(r)));
    updateButtons();
    update();
}

void Decoration::updateButtons()
{
    const qreal width = window()->width();
    m_buttons->setPos(QPointF(width - m_buttons->geometry().width() - Frame::CloseTrailingPad, 0));
    setTitleBar(QRectF(0, 0, width, m_cfg.headerHeight));
}

void Decoration::paint(QPainter *painter, const QRectF &repaintArea)
{
    const qreal r = effectiveRadius();
    const QRectF header(0, 0, window()->width(), m_cfg.headerHeight);
    painter->save();
    painter->setRenderHint(QPainter::Antialiasing);
    painter->setPen(Qt::NoPen);
    painter->setBrush(window()->palette().color(QPalette::Window));
    painter->setClipRect(header, Qt::IntersectClip);
    painter->drawRoundedRect(header.adjusted(0, 0, 0, r), r, r); // rounded top corners only
    painter->restore();
    if (m_cfg.showTitle) {
        paintTitle(painter);
    }
    m_buttons->paint(painter, repaintArea);
    paintInnerRing(painter, r);
}

void Decoration::paintTitle(QPainter *painter) const
{
    const qreal right = m_buttons->geometry().left() - Frame::TitleInset;
    const QRectF rect(Frame::TitleInset, 0, std::max<qreal>(0, right - Frame::TitleInset), m_cfg.headerHeight);
    QColor ink = window()->palette().color(QPalette::WindowText);
    if (!window()->isActive()) {
        ink.setAlphaF(Frame::InactiveIconAlpha);
    }
    painter->save();
    painter->setFont(settings()->font());
    painter->setPen(ink);
    const QString text = settings()->fontMetrics().elidedText(window()->caption(), Qt::ElideRight, rect.width());
    painter->drawText(rect, Qt::AlignLeft | Qt::AlignVCenter | Qt::TextSingleLine, text);
    painter->restore();
}

// Inner highlight ring. The decoration texture only covers the header (borders are 0 elsewhere), so the
// ring is drawn along the header and fades out down its height; the outer ring is KWin's border outline.
void Decoration::paintInnerRing(QPainter *painter, qreal radius) const
{
    const QRectF header(0, 0, window()->width(), m_cfg.headerHeight);
    painter->save();
    painter->setRenderHint(QPainter::Antialiasing);
    painter->setClipRect(header, Qt::IntersectClip);
    QLinearGradient fade(header.topLeft(), header.bottomLeft());
    fade.setColorAt(0, QColor(255, 255, 255, Frame::RingInnerAlpha));
    fade.setColorAt(1, QColor(255, 255, 255, 0));
    painter->setPen(QPen(QBrush(fade), 1));
    painter->setBrush(Qt::NoBrush);
    const QRectF ring = header.adjusted(0.5, 0.5, -0.5, radius + 1);
    painter->drawRoundedRect(ring, std::max<qreal>(0, radius - 0.5), std::max<qreal>(0, radius - 0.5));
    painter->restore();
}
}

#include "chromeosdecoration.moc"
