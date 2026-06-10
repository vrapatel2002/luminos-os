// Luminos OS — Lid Light (Slash Ledbar) KCM
// [CHANGE: claude-code | 2026-06-09]

#include <KQuickManagedConfigModule>
#include <KPluginFactory>
#include <QDir>
#include <QFile>
#include <QProcess>
#include <QRegularExpression>
#include <QTextStream>

class LuminosLidLightKcm : public KQuickManagedConfigModule
{
    Q_OBJECT
    Q_PROPERTY(bool    enabled    READ enabled    WRITE setEnabled    NOTIFY enabledChanged)
    Q_PROPERTY(int     brightness READ brightness WRITE setBrightness NOTIFY brightnessChanged)
    Q_PROPERTY(QString mode       READ mode       WRITE setMode       NOTIFY modeChanged)
    Q_PROPERTY(int     interval   READ interval   WRITE setInterval   NOTIFY intervalChanged)
    Q_PROPERTY(bool    showOnBoot     READ showOnBoot     WRITE setShowOnBoot     NOTIFY showOnBootChanged)
    Q_PROPERTY(bool    showOnShutdown READ showOnShutdown WRITE setShowOnShutdown NOTIFY showOnShutdownChanged)
    Q_PROPERTY(bool    showOnSleep    READ showOnSleep    WRITE setShowOnSleep    NOTIFY showOnSleepChanged)
    Q_PROPERTY(bool    showOnBattery  READ showOnBattery  WRITE setShowOnBattery  NOTIFY showOnBatteryChanged)
    Q_PROPERTY(bool    showBatteryWarning READ showBatteryWarning WRITE setShowBatteryWarning NOTIFY showBatteryWarningChanged)

    Q_PROPERTY(QStringList availableModes READ availableModes CONSTANT)

public:
    LuminosLidLightKcm(QObject *parent, const KPluginMetaData &data)
        : KQuickManagedConfigModule(parent, data)
        , m_configPath(QDir::homePath() + QStringLiteral("/.config/luminos-lid-light.conf"))
    {}

    // --- property getters ---
    bool    enabled()    const { return m_enabled; }
    int     brightness() const { return m_brightness; }
    QString mode()       const { return m_mode; }
    int     interval()   const { return m_interval; }
    bool    showOnBoot()     const { return m_showOnBoot; }
    bool    showOnShutdown() const { return m_showOnShutdown; }
    bool    showOnSleep()    const { return m_showOnSleep; }
    bool    showOnBattery()  const { return m_showOnBattery; }
    bool    showBatteryWarning() const { return m_showBatteryWarning; }

    QStringList availableModes() const {
        return {
            QStringLiteral("Static"), QStringLiteral("Bounce"), QStringLiteral("Slash"),
            QStringLiteral("Loading"), QStringLiteral("BitStream"), QStringLiteral("Transmission"),
            QStringLiteral("Flow"), QStringLiteral("Flux"), QStringLiteral("Phantom"),
            QStringLiteral("Spectrum"), QStringLiteral("Hazard"), QStringLiteral("Interfacing"),
            QStringLiteral("Ramp"), QStringLiteral("GameOver"), QStringLiteral("Start"),
            QStringLiteral("Buzzer")
        };
    }

    // --- property setters ---
    void setEnabled(bool v)    { if (m_enabled != v)    { m_enabled = v;    Q_EMIT enabledChanged();    setNeedsSave(true); } }
    void setBrightness(int v)  { if (m_brightness != v) { m_brightness = v; Q_EMIT brightnessChanged(); setNeedsSave(true); } }
    void setMode(const QString &v) { if (m_mode != v)   { m_mode = v;       Q_EMIT modeChanged();       setNeedsSave(true); } }
    void setInterval(int v)    { if (m_interval != v)   { m_interval = v;   Q_EMIT intervalChanged();   setNeedsSave(true); } }
    void setShowOnBoot(bool v)     { if (m_showOnBoot != v)     { m_showOnBoot = v;     Q_EMIT showOnBootChanged();     setNeedsSave(true); } }
    void setShowOnShutdown(bool v) { if (m_showOnShutdown != v) { m_showOnShutdown = v; Q_EMIT showOnShutdownChanged(); setNeedsSave(true); } }
    void setShowOnSleep(bool v)    { if (m_showOnSleep != v)    { m_showOnSleep = v;    Q_EMIT showOnSleepChanged();    setNeedsSave(true); } }
    void setShowOnBattery(bool v)  { if (m_showOnBattery != v)  { m_showOnBattery = v;  Q_EMIT showOnBatteryChanged();  setNeedsSave(true); } }
    void setShowBatteryWarning(bool v) { if (m_showBatteryWarning != v) { m_showBatteryWarning = v; Q_EMIT showBatteryWarningChanged(); setNeedsSave(true); } }

    // --- invokable actions ---
    Q_INVOKABLE void preview() { applyToHardware(); }

    // --- KCModule overrides ---
    void load() override {
        QFile f(m_configPath);
        if (f.open(QIODevice::ReadOnly)) {
            QTextStream in(&f);
            static const QRegularExpression re(QStringLiteral("^([\\w]+)=\"?([^\"]*)\"?$"));
            while (!in.atEnd()) {
                const auto match = re.match(in.readLine().trimmed());
                if (!match.hasMatch()) continue;
                const auto key = match.captured(1);
                const auto val = match.captured(2);
                if (key == QLatin1String("LID_ENABLED"))     m_enabled    = (val == QLatin1String("true"));
                if (key == QLatin1String("LID_BRIGHTNESS"))  m_brightness = val.toInt();
                if (key == QLatin1String("LID_MODE"))        m_mode       = val;
                if (key == QLatin1String("LID_INTERVAL"))    m_interval   = val.toInt();
                if (key == QLatin1String("LID_BOOT"))        m_showOnBoot     = (val == QLatin1String("true"));
                if (key == QLatin1String("LID_SHUTDOWN"))    m_showOnShutdown = (val == QLatin1String("true"));
                if (key == QLatin1String("LID_SLEEP"))       m_showOnSleep    = (val == QLatin1String("true"));
                if (key == QLatin1String("LID_BATTERY"))     m_showOnBattery  = (val == QLatin1String("true"));
                if (key == QLatin1String("LID_BAT_WARNING")) m_showBatteryWarning = (val == QLatin1String("true"));
            }
        }
        // Guard defaults
        if (m_brightness < 0 || m_brightness > 255) m_brightness = 128;
        if (m_mode.isEmpty()) m_mode = QStringLiteral("Static");
        if (m_interval < 0 || m_interval > 5) m_interval = 0;

        Q_EMIT enabledChanged(); Q_EMIT brightnessChanged(); Q_EMIT modeChanged();
        Q_EMIT intervalChanged(); Q_EMIT showOnBootChanged(); Q_EMIT showOnShutdownChanged();
        Q_EMIT showOnSleepChanged(); Q_EMIT showOnBatteryChanged(); Q_EMIT showBatteryWarningChanged();
        setNeedsSave(false);
    }

    void save() override {
        applyToHardware();
        QFile f(m_configPath);
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            QTextStream out(&f);
            out << "LID_ENABLED=\""     << (m_enabled ? "true" : "false")         << "\"\n";
            out << "LID_BRIGHTNESS=\""  << QString::number(m_brightness)          << "\"\n";
            out << "LID_MODE=\""        << m_mode                                 << "\"\n";
            out << "LID_INTERVAL=\""    << QString::number(m_interval)            << "\"\n";
            out << "LID_BOOT=\""        << (m_showOnBoot ? "true" : "false")      << "\"\n";
            out << "LID_SHUTDOWN=\""    << (m_showOnShutdown ? "true" : "false")   << "\"\n";
            out << "LID_SLEEP=\""       << (m_showOnSleep ? "true" : "false")     << "\"\n";
            out << "LID_BATTERY=\""     << (m_showOnBattery ? "true" : "false")   << "\"\n";
            out << "LID_BAT_WARNING=\"" << (m_showBatteryWarning ? "true" : "false") << "\"\n";
        }
        setNeedsSave(false);
    }

    void defaults() override {
        setEnabled(true);
        setBrightness(128);
        setMode(QStringLiteral("Static"));
        setInterval(0);
        setShowOnBoot(true);
        setShowOnShutdown(true);
        setShowOnSleep(true);
        setShowOnBattery(false);
        setShowBatteryWarning(true);
    }

Q_SIGNALS:
    void enabledChanged();
    void brightnessChanged();
    void modeChanged();
    void intervalChanged();
    void showOnBootChanged();
    void showOnShutdownChanged();
    void showOnSleepChanged();
    void showOnBatteryChanged();
    void showBatteryWarningChanged();

private:
    void applyToHardware() {
        if (m_enabled) {
            QProcess::startDetached(QStringLiteral("asusctl"),
                {QStringLiteral("slash"), QStringLiteral("--enable")});
            QProcess::startDetached(QStringLiteral("asusctl"),
                {QStringLiteral("slash"), QStringLiteral("-l"), QString::number(m_brightness)});
            QProcess::startDetached(QStringLiteral("asusctl"),
                {QStringLiteral("slash"), QStringLiteral("--mode"), m_mode});
            QProcess::startDetached(QStringLiteral("asusctl"),
                {QStringLiteral("slash"), QStringLiteral("--interval"), QString::number(m_interval)});
        } else {
            QProcess::startDetached(QStringLiteral("asusctl"),
                {QStringLiteral("slash"), QStringLiteral("--disable")});
        }

        // Event triggers
        auto boolStr = [](bool v) { return v ? QStringLiteral("true") : QStringLiteral("false"); };
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("slash"), QStringLiteral("-B"), boolStr(m_showOnBoot)});
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("slash"), QStringLiteral("-S"), boolStr(m_showOnShutdown)});
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("slash"), QStringLiteral("-s"), boolStr(m_showOnSleep)});
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("slash"), QStringLiteral("-b"), boolStr(m_showOnBattery)});
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("slash"), QStringLiteral("-w"), boolStr(m_showBatteryWarning)});
    }

    QString m_configPath;
    bool    m_enabled          = true;
    int     m_brightness       = 128;
    QString m_mode             = QStringLiteral("Static");
    int     m_interval         = 0;
    bool    m_showOnBoot       = true;
    bool    m_showOnShutdown   = true;
    bool    m_showOnSleep      = true;
    bool    m_showOnBattery    = false;
    bool    m_showBatteryWarning = true;
};

K_PLUGIN_CLASS_WITH_JSON(LuminosLidLightKcm, "kcm_luminos_lid_light.json")
#include "kcm_luminos_lid_light.moc"
