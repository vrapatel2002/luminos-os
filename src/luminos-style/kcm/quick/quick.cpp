// [CHANGE: claude-code | 2026-11-10] R25 — see quick.h.
#include "quick.h"

#include <KConfigGroup>
#include <KLocalizedString>
#include <KPluginFactory>
#include <KSharedConfig>
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <QFileInfo>
#include <QGuiApplication>
#include <QPalette>
#include <QDir>
#include <QProcess>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QTimer>

K_PLUGIN_CLASS_WITH_JSON(Quick, "kcm_luminos_quick.json")

namespace
{
// Slow .. Instant, as AnimationDurationFactor (1 = normal, 0 = no animation)
const double kFactors[] = {4.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25, 0.0};
constexpr int kSteps = sizeof(kFactors) / sizeof(kFactors[0]);

KConfigGroup kde() { return KSharedConfig::openConfig(QStringLiteral("kdeglobals"))->group(QStringLiteral("KDE")); }
KConfigGroup memory() // which dark / light scheme to go back to
{
    return KSharedConfig::openConfig(QStringLiteral("luminos/quick.conf"), KConfig::NoGlobals)->group(QStringLiteral("Theme"));
}
bool schemeIsDark()
{
    // the window colour this app is really drawn with (kdeglobals may not carry the scheme's colours)
    const QStringList c = KSharedConfig::openConfig(QStringLiteral("kdeglobals"))->group(QStringLiteral("Colors:Window")).readEntry("BackgroundNormal", QString()).split(QLatin1Char(','));
    const QColor bg = c.size() >= 3 ? QColor(c[0].toInt(), c[1].toInt(), c[2].toInt()) : QGuiApplication::palette().color(QPalette::Window);
    return bg.lightnessF() < 0.5;
}
}

Quick::Quick(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    setButtons(NoAdditionalButton); // everything saves on the spot
}

int Quick::animSteps() const { return kSteps; }

void Quick::load()
{
    auto g = KSharedConfig::openConfig(QStringLiteral("kdeglobals"));
    g->reparseConfiguration();
    m_scheme = g->group(QStringLiteral("General")).readEntry("ColorScheme", QStringLiteral("BreezeLight"));
    m_dark = schemeIsDark();
    const double f = kde().readEntry("AnimationDurationFactor", 1.0);
    int best = 3;
    for (int i = 0; i < kSteps; ++i)
        if (qAbs(kFactors[i] - f) < qAbs(kFactors[best] - f))
            best = i;
    m_animStep = best;
    m_singleClick = kde().readEntry("SingleClick", true);
    readWallpaper();
    Q_EMIT changed();
}

void Quick::readWallpaper()
{
    // the desktop's wallpaper: a still for Luminos live wallpapers (the one its settings dialog caches), the image otherwise
    m_wallpaper.clear();
    m_wallpaperName.clear();
    auto cfg = KSharedConfig::openConfig(QStringLiteral("plasma-org.kde.plasma.desktop-appletsrc"), KConfig::NoGlobals);
    const KConfigGroup conts = cfg->group(QStringLiteral("Containments"));
    for (const QString &id : conts.groupList()) {
        const KConfigGroup c = conts.group(id);
        const QString plugin = c.readEntry("wallpaperplugin");
        if (plugin.isEmpty() || c.readEntry("activityId").isEmpty())
            continue;
        const KConfigGroup gen = c.group(QStringLiteral("Wallpaper")).group(plugin).group(QStringLiteral("General"));
        QString file;
        if (plugin == QLatin1String("org.luminos.livewallpaper")) {
            const QString mode = gen.readEntry("WallpaperMode", QStringLiteral("image"));
            if (mode == QLatin1String("video")) {
                const QString v = gen.readEntry("Video");
                m_wallpaperName = QFileInfo(v).completeBaseName();
                const QString still = QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation) + QStringLiteral("/luminos/wallpaper-thumbs/")
                    + QString::fromLatin1(QCryptographicHash::hash(v.toUtf8(), QCryptographicHash::Md5).toHex()) + QStringLiteral(".jpg");
                if (QFileInfo::exists(still)) {
                    file = still;
                } else if (QFileInfo(v).isFile() && !m_makingStill) { // make the still once (the wallpaper dialog uses the same file)
                    m_makingStill = true;
                    QDir().mkpath(QFileInfo(still).path());
                    auto *p = new QProcess(this);
                    connect(p, &QProcess::finished, this, [this, p] { p->deleteLater(); readWallpaper(); m_makingStill = false; Q_EMIT changed(); });
                    p->start(QStringLiteral("ffmpeg"), {QStringLiteral("-y"), QStringLiteral("-loglevel"), QStringLiteral("error"), QStringLiteral("-ss"), QStringLiteral("1"),
                                                        QStringLiteral("-i"), v, QStringLiteral("-frames:v"), QStringLiteral("1"),
                                                        QStringLiteral("-vf"), QStringLiteral("scale=960:-2"), still});
                }
            } else if (mode == QLatin1String("image")) {
                file = gen.readEntry("Image");
            } else {
                const QString src = mode == QLatin1String("web") ? gen.readEntry("WebUrl") : gen.readEntry("QmlScene");
                m_wallpaperName = QFileInfo(QFileInfo(src).path()).fileName();
            }
        } else {
            file = gen.readEntry("Image");
        }
        if (file.startsWith(QLatin1String("file://")))
            file = QUrl(file).toLocalFile();
        if (!file.isEmpty() && QFileInfo(file).isFile()) {
            m_wallpaper = QUrl::fromLocalFile(file);
            if (m_wallpaperName.isEmpty())
                m_wallpaperName = QFileInfo(file).completeBaseName();
        }
        if (!m_wallpaperName.isEmpty()) { // "arlecchino-girl.3840x2160" -> "arlecchino girl"
            m_wallpaperName.remove(QRegularExpression(QStringLiteral("[._ -]?\\d{3,5}x\\d{3,5}$")));
            m_wallpaperName.replace(QLatin1Char('-'), QLatin1Char(' ')).replace(QLatin1Char('_'), QLatin1Char(' '));
        }
        break;
    }
}

void Quick::setAnimStep(int step)
{
    step = qBound(0, step, kSteps - 1);
    if (step == m_animStep)
        return;
    m_animStep = step;
    KConfigGroup g = kde();
    g.writeEntry("AnimationDurationFactor", kFactors[step], KConfig::Notify);
    g.sync();
    Q_EMIT changed();
}

void Quick::setSingleClick(bool on)
{
    if (on == m_singleClick)
        return;
    m_singleClick = on;
    KConfigGroup g = kde();
    g.writeEntry("SingleClick", on, KConfig::Notify);
    g.sync();
    Q_EMIT changed();
}

void Quick::setDark(bool dark)
{
    if (dark == m_dark)
        return;
    KConfigGroup mem = memory();
    mem.writeEntry(m_dark ? "Dark" : "Light", m_scheme); // so the other button brings this one back
    mem.sync();
    const QString target = dark ? mem.readEntry("Dark", QStringLiteral("Caelestia")) : mem.readEntry("Light", QStringLiteral("BreezeLight"));
    m_dark = dark;
    m_scheme = target;
    Q_EMIT changed();
    QProcess::startDetached(QStringLiteral("plasma-apply-colorscheme"), {target});
    QTimer::singleShot(1500, this, [this] { load(); }); // pick up what really got applied
}

void Quick::openWallpaper()
{
    QDBusMessage m = QDBusMessage::createMethodCall(QStringLiteral("org.kde.plasmashell"), QStringLiteral("/PlasmaShell"),
                                                    QStringLiteral("org.kde.PlasmaShell"), QStringLiteral("evaluateScript"));
    m << QStringLiteral("desktops()[0].showConfigurationInterface()");
    QDBusConnection::sessionBus().asyncCall(m);
}

void Quick::openModule(const QString &id)
{
    QProcess::startDetached(QStringLiteral("systemsettings"), {id}); // the running window switches to that page
}

void Quick::openTuner()
{
    QProcess::startDetached(QStringLiteral("luminos-style-tuner"), {});
}

#include "quick.moc"
