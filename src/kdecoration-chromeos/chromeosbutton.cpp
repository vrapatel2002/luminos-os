// [CHANGE: claude-code | 2026-10-10] Luminos ChromeOS-style caption buttons (minimize, maximize/restore, close).
// Design constants derived from Chromium (ChromeOS ash/chromeos/ui frame code), (c) The Chromium
// Authors, BSD-3-Clause -- see chromeosdecoration.h for the source file of each constant.
#include "chromeosdecoration.h"
#include <KDecoration3/DecoratedWindow>
#include <QPainter>
#include <QPainterPath>

namespace Luminos
{
using Type = KDecoration3::DecorationButtonType;
using W = KDecoration3::DecoratedWindow;

Button::Button(Type type, KDecoration3::Decoration *decoration, QObject *parent)
    : KDecoration3::DecorationButton(type, decoration, parent)
{
    auto *d = qobject_cast<Decoration *>(decoration);
    if (!d) {
        return; // not our decoration (or missing factory args): stay inert
    }
    setGeometry(QRectF(0, 0, Frame::ButtonW, d->headerHeight()));
    auto *w = d->window();
    // Hide buttons the window cannot use (the group re-lays out on visibility change).
    if (type == Type::Minimize) {
        setVisible(w->isMinimizeable());
        connect(w, &W::minimizeableChanged, this, &DecorationButton::setVisible);
    } else if (type == Type::Maximize) {
        setVisible(w->isMaximizeable());
        connect(w, &W::maximizeableChanged, this, &DecorationButton::setVisible);
    } else if (type == Type::Close) {
        setVisible(w->isCloseable());
        connect(w, &W::closeableChanged, this, &DecorationButton::setVisible);
    }
}

// Constructor used by KDecoration3's plugin factory (e.g. the System Settings preview).
Button::Button(QObject *parent, const QVariantList &args)
    : Button(args.value(0).value<Type>(), args.value(1).value<KDecoration3::Decoration *>(), parent)
{
}

void Button::paint(QPainter *painter, const QRectF &)
{
    if (!isVisible()) {
        return;
    }
    const QPointF c = geometry().center();
    painter->save();
    painter->setRenderHint(QPainter::Antialiasing);
    if (isHovered() || isPressed()) {
        painter->setPen(Qt::NoPen);
        painter->setBrush(QColor(255, 255, 255, isPressed() ? Frame::PressedAlpha : Frame::HoverAlpha));
        painter->drawEllipse(c, Frame::HoverCircleR, Frame::HoverCircleR);
    }
    const auto *w = decoration()->window();
    QColor ink = w->palette().color(QPalette::WindowText);
    if (!w->isActive() || !isEnabled()) {
        ink.setAlphaF(ink.alphaF() * Frame::InactiveIconAlpha);
    }
    QPen pen(ink, Frame::GlyphStroke);
    pen.setCapStyle(Qt::FlatCap);
    pen.setJoinStyle(Qt::MiterJoin);
    painter->setPen(pen);
    painter->setBrush(Qt::NoBrush);
    const qreal half = Frame::IconSize / 2 - Frame::GlyphInset;
    paintGlyph(painter, QRectF(c.x() - half, c.y() - half, 2 * half, 2 * half));
    painter->restore();
}

// 16 px Material-style line glyphs: minimize line, maximize square, restore two squares, close X.
void Button::paintGlyph(QPainter *painter, const QRectF &r) const
{
    const qreal o = 3; // restore: offset of the back square
    if (type() == Type::Minimize) {
        painter->drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()));
    } else if (type() == Type::Close) {
        painter->drawLine(r.topLeft(), r.bottomRight());
        painter->drawLine(r.topRight(), r.bottomLeft());
    } else if (type() == Type::Maximize && !isChecked()) {
        painter->drawRect(r);
    } else if (type() == Type::Maximize) {
        painter->drawRect(QRectF(r.left(), r.top() + o, r.width() - o, r.height() - o));
        QPainterPath back;
        back.moveTo(r.left() + o, r.top() + o);
        back.lineTo(r.left() + o, r.top());
        back.lineTo(r.right(), r.top());
        back.lineTo(r.right(), r.bottom() - o);
        back.lineTo(r.right() - o, r.bottom() - o);
        painter->drawPath(back);
    }
}
}
