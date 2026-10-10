// [CHANGE: claude-code | 2026-10-10] Luminos ChromeOS-style window frame (KDecoration3), DECISION 135.
//
// Design constants derived from Chromium (ChromeOS ash/chromeos/ui frame code),
// (c) The Chromium Authors, BSD-3-Clause. Source file per constant:
//   HeaderHeight, ButtonW, ButtonH ... ui/views/window/caption_button_layout_constants.cc
//   CloseTrailingPad, IconSize ....... chromeos/ui/frame/caption_buttons/frame_caption_button_container_view.cc
//   HoverCircleR (ink-drop circle) ... ui/views/window/frame_caption_button.cc
//   HoverAlpha, PressedAlpha ......... ash/style/ash_color_mixer.cc, ui/color/sys_color_mixer.cc
//   InactiveIconAlpha 0.38 ........... ash/style/color_util.cc
//   ResizeOutside, CornerRadius ...... chromeos/ui/base/chromeos_ui_constants.h (Luminos: 16, ChromeOS: 12)
//   Shadow elevations, key/ambient ... ui/wm/core/shadow_types.cc, ui/gfx/shadow_value.cc, ui/color/ui_color_mixer.cc
//   Highlight rings .................. ui/views/highlight_border.cc, chromeos/ui/frame/highlight_border_overlay.cc
#pragma once
#include <KDecoration3/Decoration>
#include <KDecoration3/DecorationButton>
#include <KDecoration3/DecorationButtonGroup>
#include <KDecoration3/DecorationShadow>
#include <QVariant>

namespace Luminos
{
namespace Frame
{
constexpr int ButtonW = 36;
constexpr int CloseTrailingPad = 8;
constexpr qreal IconSize = 16;
constexpr qreal GlyphInset = 3; // 16 px box, 10 px glyph, like the Material caption icons
constexpr qreal GlyphStroke = 1.5;
constexpr qreal HoverCircleR = 14;
constexpr int HoverAlpha = 0x14;
constexpr int PressedAlpha = 0x24;
constexpr qreal InactiveIconAlpha = 0.38;
constexpr qreal ResizeOutside = 6;
constexpr int ShadowActive = 24;
constexpr int ShadowInactive = 12;
constexpr qreal KeyAlpha = 0.20;
constexpr qreal AmbientAlpha = 0.10;
constexpr int RingOuterAlpha = 20; // 8 % black
constexpr int RingInnerAlpha = 15; // 6 % white
constexpr qreal TitleInset = 8;
}

// Shared shadow texture per (active, radius); see chromeosshadow.cpp.
std::shared_ptr<KDecoration3::DecorationShadow> cachedShadow(bool active, int radius);

struct Config {
    int cornerRadius = 16; // [Frame] CornerRadius, 0..32
    int headerHeight = 40; // [Frame] HeaderHeight, 28..64 (28 = hover circle)
    bool showTitle = false; // [Frame] ShowTitle
};

class Decoration : public KDecoration3::Decoration
{
    Q_OBJECT
public:
    explicit Decoration(QObject *parent = nullptr, const QVariantList &args = QVariantList());
    bool init() override;
    void paint(QPainter *painter, const QRectF &repaintArea) override;
    int headerHeight() const { return m_cfg.headerHeight; }

public Q_SLOTS:
    void reconfigure();

private:
    qreal effectiveRadius() const;
    void updateLayout();
    void updateButtons();
    void paintTitle(QPainter *painter) const;
    void paintInnerRing(QPainter *painter, qreal radius) const;

    Config m_cfg;
    KDecoration3::DecorationButtonGroup *m_buttons = nullptr;
};

class Button : public KDecoration3::DecorationButton
{
    Q_OBJECT
public:
    Button(KDecoration3::DecorationButtonType type, KDecoration3::Decoration *decoration, QObject *parent = nullptr);
    Button(QObject *parent, const QVariantList &args);
    void paint(QPainter *painter, const QRectF &repaintArea) override;

private:
    void paintGlyph(QPainter *painter, const QRectF &box) const;
};
}
