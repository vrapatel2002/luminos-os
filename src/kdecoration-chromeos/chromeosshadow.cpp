// [CHANGE: claude-code | 2026-10-10] Luminos ChromeOS-style frame: elevation shadow texture.
// Design constants derived from Chromium (ChromeOS ash/chromeos/ui frame code), (c) The Chromium
// Authors, BSD-3-Clause -- see chromeosdecoration.h for the source file of each constant.
#include "chromeosdecoration.h"
#include <KDecoration3/DecorationShadow>
#include <QHash>
#include <QPainter>
#include <algorithm>
#include <cmath>
#include <vector>

namespace Luminos
{
namespace
{
using Shadow = std::shared_ptr<KDecoration3::DecorationShadow>;

// One pass of a running-sum box blur over a line copied into `src`.
void boxBlurLine(const uchar *src, uchar *dst, int n, int stride, int r)
{
    int sum = 0;
    for (int i = -r; i <= r; ++i) {
        sum += src[std::clamp(i, 0, n - 1)];
    }
    for (int i = 0; i < n; ++i) {
        dst[i * stride] = uchar(sum / (2 * r + 1));
        sum += src[std::min(i + r + 1, n - 1)] - src[std::max(i - r, 0)];
    }
}

// Three box passes approximate the Gaussian Skia uses for gfx::ShadowValue.
void blurAlpha8(QImage &img, qreal sigma)
{
    const int r = std::max(1, int(std::lround((std::sqrt(4 * sigma * sigma + 1) - 1) / 2)));
    const int w = img.width(), h = img.height(), bpl = img.bytesPerLine();
    std::vector<uchar> tmp(std::max(w, h));
    uchar *bits = img.bits();
    for (int pass = 0; pass < 3; ++pass) {
        for (int y = 0; y < h; ++y) {
            std::copy_n(bits + y * bpl, w, tmp.begin());
            boxBlurLine(tmp.data(), bits + y * bpl, w, 1, r);
        }
        for (int x = 0; x < w; ++x) {
            for (int y = 0; y < h; ++y) {
                tmp[y] = bits[y * bpl + x];
            }
            boxBlurLine(tmp.data(), bits + x, h, bpl, r);
        }
    }
}

QImage blurredShape(QSize size, const QRectF &box, qreal radius, qreal sigma)
{
    QImage img(size, QImage::Format_Alpha8);
    img.fill(0);
    QPainter p(&img);
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(Qt::NoPen);
    p.setBrush(Qt::black);
    p.drawRoundedRect(box, radius, radius);
    p.end();
    blurAlpha8(img, sigma);
    return img;
}

// Key shadow (0, e) blur e at 20 % over ambient (0, 0) blur e at 10 %, then the window area cut out.
Shadow createShadow(int e, qreal radius)
{
    const qreal sigma = 0.57735 * (e / 2.0) + 0.5; // Skia BlurRadiusToSigma(blur / 2)
    const int ext = int(std::ceil(3 * sigma));
    const int side = 2 * (int(std::ceil(radius)) + ext) + 1;
    const QMargins pad(ext, ext, ext, ext + e);
    const QSize size(side + pad.left() + pad.right(), side + pad.top() + pad.bottom());
    const QRectF box(pad.left(), pad.top(), side, side);
    const QImage ambient = blurredShape(size, box, radius, sigma);
    const QImage key = blurredShape(size, box.translated(0, e), radius, sigma);
    QImage out(size, QImage::Format_ARGB32_Premultiplied);
    for (int y = 0; y < size.height(); ++y) {
        auto *line = reinterpret_cast<QRgb *>(out.scanLine(y));
        for (int x = 0; x < size.width(); ++x) {
            const qreal a = ambient.constScanLine(y)[x] / 255.0 * Frame::AmbientAlpha;
            const qreal k = key.constScanLine(y)[x] / 255.0 * Frame::KeyAlpha;
            line[x] = qRgba(0, 0, 0, int(std::lround((a + k - a * k) * 255)));
        }
    }
    QPainter p(&out);
    p.setRenderHint(QPainter::Antialiasing);
    p.setCompositionMode(QPainter::CompositionMode_DestinationOut);
    p.setPen(Qt::NoPen);
    p.setBrush(Qt::black);
    p.drawRoundedRect(box.adjusted(2, 2, -2, -2), radius, radius);
    p.end();
    auto shadow = std::make_shared<KDecoration3::DecorationShadow>();
    shadow->setPadding(QMarginsF(pad));
    shadow->setInnerShadowRect(QRectF(box.center(), QSizeF(1, 1)));
    shadow->setShadow(out);
    return shadow;
}
}

// Shared by every window: one shadow per (active, radius) pair.
Shadow cachedShadow(bool active, int radius)
{
    static QHash<int, Shadow> cache;
    Shadow &shadow = cache[radius * 2 + (active ? 1 : 0)];
    if (!shadow) {
        shadow = createShadow(active ? Frame::ShadowActive : Frame::ShadowInactive, radius);
    }
    return shadow;
}
}
