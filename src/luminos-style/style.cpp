// [CHANGE: claude-code | 2026-11-08] Luminos style tuner (DECISION 176). See style.h.
#include "style.h"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <QRegularExpression>
#include <QTimer>

namespace
{
struct Knob { qreal def, lo, hi; };
// key -> default (= the literal the forks used before), allowed range
const QHash<QString, Knob> &knobs()
{
    static const QHash<QString, Knob> k = {
        {QStringLiteral("textSizePt"),     {10, 6, 20}},
        {QStringLiteral("pageTitlePx"),    {30, 14, 60}},
        {QStringLiteral("groupLabelPx"),   {12, 8, 24}},
        {QStringLiteral("cornerOuterPx"),  {28, 0, 48}},
        {QStringLiteral("cornerInnerPx"),  {4, 0, 24}},
        {QStringLiteral("cornerButtonPx"), {16, 0, 32}},
        {QStringLiteral("rowHeightPx"),    {60, 36, 100}},
        {QStringLiteral("rowGapPx"),       {4, 0, 16}},
        {QStringLiteral("cardPaddingPx"),  {20, 4, 48}},
        {QStringLiteral("sidebarWidthPx"), {330, 200, 520}},
        {QStringLiteral("pageWidthPx"),    {756, 480, 1600}},
        {QStringLiteral("iconCirclePx"),   {40, 20, 64}},
        {QStringLiteral("animationMs"),    {180, 0, 1000}},
        {QStringLiteral("searchHeightPx"), {48, 24, 96}},
        {QStringLiteral("searchLeftPx"),   {16, 0, 64}},
        {QStringLiteral("searchRightPx"),  {16, 0, 64}},
        {QStringLiteral("searchTopPx"),    {16, 0, 64}},
        {QStringLiteral("searchBottomPx"), {8, 0, 64}},
        {QStringLiteral("iconGlyphPx"),    {22, 10, 48}},
        {QStringLiteral("iconOffsetXPx"),  {0, -24, 24}},
        {QStringLiteral("iconOffsetYPx"),  {0, -24, 24}},
        {QStringLiteral("sidebarBottomPx"),{16, 0, 96}},
    };
    return k;
}
}

// One per process: every QML engine's Style singleton shares this watcher and these values.
class StyleBackend : public QObject
{
    Q_OBJECT
public:
    static StyleBackend *instance()
    {
        static StyleBackend *b = new StyleBackend;
        return b;
    }
    QString text(const QString &key) const { return m_texts.value(key); }
    qreal value(const QString &key) const
    {
        const auto it = m_values.constFind(key);
        return it != m_values.constEnd() ? *it : knobs().value(key).def;
    }
Q_SIGNALS:
    void changed();

private:
    StyleBackend()
    {
        const QString cfg = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation);
        m_dir = cfg + QStringLiteral("/luminos");
        m_path = m_dir + QStringLiteral("/style.json");
        m_debounce.setSingleShot(true);
        m_debounce.setInterval(30); // editors write in several steps; read once they are done
        connect(&m_debounce, &QTimer::timeout, this, &StyleBackend::reload);
        connect(&m_watch, &QFileSystemWatcher::fileChanged, &m_debounce, qOverload<>(&QTimer::start));
        connect(&m_watch, &QFileSystemWatcher::directoryChanged, &m_debounce, qOverload<>(&QTimer::start));
        reload();
    }
    void rewatch()
    {
        // watch the directory too: an atomic save replaces the file and drops the file watch
        if (!m_watch.directories().contains(m_dir) && QFileInfo(m_dir).isDir())
            m_watch.addPath(m_dir);
        else if (!QFileInfo(m_dir).isDir() && !m_watch.directories().contains(QFileInfo(m_dir).path()))
            m_watch.addPath(QFileInfo(m_dir).path()); // ~/.config: notices luminos/ being created
        if (!m_watch.files().contains(m_path) && QFileInfo::exists(m_path))
            m_watch.addPath(m_path);
    }
    void reload()
    {
        rewatch();
        QHash<QString, qreal> next;
        QHash<QString, QString> nextTexts;
        QFile f(m_path);
        if (f.open(QIODevice::ReadOnly)) {
            QJsonParseError err;
            const QJsonDocument doc = QJsonDocument::fromJson(f.readAll(), &err);
            if (err.error != QJsonParseError::NoError || !doc.isObject())
                return; // half-written or broken: keep the last good values
            const QJsonObject o = doc.object();
            for (auto it = knobs().constBegin(); it != knobs().constEnd(); ++it) {
                const QJsonValue v = o.value(it.key());
                if (v.isDouble())
                    next.insert(it.key(), qBound(it->lo, v.toDouble(), it->hi));
            }
            static const QRegularExpression hex(QStringLiteral("^#[0-9a-fA-F]{6}$"));
            for (const char *k : {"iconDiscColor", "iconGlyphColor"}) {
                const QString s = o.value(QLatin1String(k)).toString();
                if (hex.match(s).hasMatch())
                    nextTexts.insert(QLatin1String(k), s);
            }
        }
        if (next != m_values || nextTexts != m_texts) {
            m_values = next;
            m_texts = nextTexts;
            Q_EMIT changed();
        }
    }
    QString m_dir, m_path;
    QHash<QString, qreal> m_values;
    QHash<QString, QString> m_texts;
    QFileSystemWatcher m_watch;
    QTimer m_debounce;
};

Style::Style(QObject *parent)
    : QObject(parent)
    , m_backend(StyleBackend::instance())
{
    connect(m_backend, &StyleBackend::changed, this, &Style::changed);
}

#define LX_GET(type, name) type Style::name() const { return type(m_backend->value(QStringLiteral(#name))); }
LX_GET(qreal, textSizePt)
LX_GET(qreal, pageTitlePx)
LX_GET(qreal, groupLabelPx)
LX_GET(qreal, cornerOuterPx)
LX_GET(qreal, cornerInnerPx)
LX_GET(qreal, cornerButtonPx)
LX_GET(qreal, rowHeightPx)
LX_GET(qreal, rowGapPx)
LX_GET(qreal, cardPaddingPx)
LX_GET(qreal, sidebarWidthPx)
LX_GET(qreal, pageWidthPx)
LX_GET(qreal, iconCirclePx)
LX_GET(qreal, searchHeightPx)
LX_GET(qreal, searchLeftPx)
LX_GET(qreal, searchRightPx)
LX_GET(qreal, searchTopPx)
LX_GET(qreal, searchBottomPx)
LX_GET(qreal, iconGlyphPx)
LX_GET(qreal, iconOffsetXPx)
LX_GET(qreal, iconOffsetYPx)
LX_GET(qreal, sidebarBottomPx)
QString Style::iconDiscColor() const { return m_backend->text(QStringLiteral("iconDiscColor")); }
QString Style::iconGlyphColor() const { return m_backend->text(QStringLiteral("iconGlyphColor")); }
int Style::animationMs() const { return qRound(m_backend->value(QStringLiteral("animationMs"))); }

#include "style.moc"
