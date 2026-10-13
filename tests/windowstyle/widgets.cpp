// [CHANGE: claude-code | 2026-10-12] Phase 6 QtWidgets probe (Darkly). Built on the fly by luminos-windowstyle-check into a
// temp dir: g++ -fPIC widgets.cpp $(pkg-config --cflags --libs Qt6Widgets). Prints PASS|FAIL lines. Run offscreen.
#include <QApplication>
#include <QMenu>
#include <QScrollBar>
#include <QStyleOptionSlider>
#include <QToolTip>
#include <QWidget>
#include <QImage>
#include <cstdio>
#include <algorithm>
#include <vector>
static double lum(QColor c) { return (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255.0; }
static void out(bool ok, const char *n, const QString &d) { printf("%s %s: %s\n", ok ? "PASS" : "FAIL", n, qPrintable(d)); }
int main(int argc, char **argv) {
    QApplication app(argc, argv); app.setStyle("Darkly");
    QString st = app.style()->name();
    QMenu menu; QAction *a = menu.addAction("Open"); menu.addSeparator(); menu.addAction("Quit");
    menu.popup(QPoint(0, 0)); app.processEvents();
    QImage m = menu.grab().toImage(); int ih = menu.actionGeometry(a).height(); int k = 4;   // (4.5,4.5) is outside a r16 arc, inside r <= 15
    int ca = qAlpha(m.pixel(k, k)), cb = qAlpha(m.pixel(m.width() - 1 - k, m.height() - 1 - k));
    out(st == "darkly" && ca < 128 && cb < 128 && ih >= 38 && ih <= 42, "widgets-menu", QString("style %1, corner alpha at 4px diagonal %2/%3 (want < 128: r16), "
        "item height %4 (want 38-42)").arg(st).arg(ca).arg(cb).arg(ih));
    QToolTip::showText(QPoint(300, 300), "Hello tooltip"); app.processEvents(); QWidget *tip = nullptr;
    for (QWidget *w : QApplication::topLevelWidgets()) if (w->inherits("QTipLabel") && w->isVisible()) tip = w;
    QImage ti = tip ? tip->grab().toImage() : QImage(); std::vector<double> ls;   // median: the surface may be inset in an opaque offscreen window
    for (int y = 0; y < ti.height(); y++) for (int x = 0; x < ti.width(); x++) ls.push_back(lum(ti.pixelColor(x, y)));
    std::sort(ls.begin(), ls.end()); double tb = ls.empty() ? 0 : ls[ls.size() / 2];
    double wb = lum(app.palette().color(QPalette::Window));
    out(tb > wb + 0.5, "widgets-tooltip", QString("QToolTip surface luminance %1 vs Window %2 (want > +0.5)").arg(tb, 0, 'f', 2).arg(wb, 0, 'f', 2));
    QScrollBar sb(Qt::Vertical); sb.setRange(0, 100); sb.setPageStep(30); sb.resize(sb.sizeHint().width(), 200); sb.show(); app.processEvents();
    QStyleOptionSlider o; o.initFrom(&sb); o.orientation = Qt::Vertical; o.minimum = 0; o.maximum = 100; o.pageStep = 30; o.sliderPosition = 0;
    o.subControls = QStyle::SC_All; QRect sub = sb.style()->subControlRect(QStyle::CC_ScrollBar, &o, QStyle::SC_ScrollBarSubLine, &sb);
    QRect add = sb.style()->subControlRect(QStyle::CC_ScrollBar, &o, QStyle::SC_ScrollBarAddLine, &sb);
    QImage g(sb.size(), QImage::Format_ARGB32); g.fill(Qt::transparent); sb.render(&g, QPoint(), QRegion(), QWidget::DrawChildren);
    int groove = qAlpha(g.pixel(g.width() / 2, g.height() - 10));   // handle sits at the top (value 0)
    out(sub.isEmpty() && add.isEmpty() && groove == 0, "widgets-scrollbar", QString("sub/add line rects %1x%2 / %3x%4 (want empty), groove alpha %5 (want 0)")
        .arg(sub.width()).arg(sub.height()).arg(add.width()).arg(add.height()).arg(groove));
    return 0;
}
