// Luminos OS — Lid Light (Slash Ledbar) KCM
// [CHANGE: claude-code | 2026-06-10]

#include <KQuickManagedConfigModule>
#include <KPluginFactory>
#include <QDir>
#include <QFile>
#include <QProcess>
#include <QRegularExpression>
#include <QTextStream>
#include <QTimer>

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
    Q_PROPERTY(bool    batteryIndicator READ batteryIndicator WRITE setBatteryIndicator NOTIFY batteryIndicatorChanged)
    Q_PROPERTY(int     batteryPollSecs  READ batteryPollSecs  WRITE setBatteryPollSecs  NOTIFY batteryPollSecsChanged)
    Q_PROPERTY(int     currentBatteryPct READ currentBatteryPct NOTIFY currentBatteryPctChanged)
    Q_PROPERTY(QString currentBatteryStatus READ currentBatteryStatus NOTIFY currentBatteryPctChanged)

    Q_PROPERTY(QStringList availableModes READ availableModes CONSTANT)
    Q_PROPERTY(QStringList modeDescriptions READ modeDescriptions CONSTANT)

public:
    LuminosLidLightKcm(QObject *parent, const KPluginMetaData &data)
        : KQuickManagedConfigModule(parent, data)
        , m_configPath(QDir::homePath() + QStringLiteral("/.config/luminos-lid-light.conf"))
        , m_batteryTimer(new QTimer(this))
    {
        connect(m_batteryTimer, &QTimer::timeout, this, &LuminosLidLightKcm::updateBatteryIndicator);
    }

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
    bool    batteryIndicator() const { return m_batteryIndicator; }
    int     batteryPollSecs()  const { return m_batteryPollSecs; }
    int     currentBatteryPct() const { return m_currentBatteryPct; }
    QString currentBatteryStatus() const { return m_currentBatteryStatus; }

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

    QStringList modeDescriptions() const {
        return {
            QStringLiteral("Solid light, no animation"),
            QStringLiteral("Light bounces back and forth"),
            QStringLiteral("Quick diagonal slash effect"),
            QStringLiteral("Loading/progress bar animation"),
            QStringLiteral("Digital data stream effect"),
            QStringLiteral("Signal transmission pulse"),
            QStringLiteral("Smooth flowing light"),
            QStringLiteral("Fluctuating intensity"),
            QStringLiteral("Ghostly fade in/out"),
            QStringLiteral("Color spectrum sweep"),
            QStringLiteral("Warning flash pattern"),
            QStringLiteral("Tech interface animation"),
            QStringLiteral("Gradual ramp up/down"),
            QStringLiteral("Game over sequence"),
            QStringLiteral("Startup sequence"),
            QStringLiteral("Quick buzz flash")
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
    void setBatteryIndicator(bool v) {
        if (m_batteryIndicator != v) {
            m_batteryIndicator = v;
            Q_EMIT batteryIndicatorChanged();
            setNeedsSave(true);
            updateBatteryTimer();
        }
    }
    void setBatteryPollSecs(int v) {
        if (m_batteryPollSecs != v) {
            m_batteryPollSecs = v;
            Q_EMIT batteryPollSecsChanged();
            setNeedsSave(true);
            updateBatteryTimer();
        }
    }

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
                if (key == QLatin1String("LID_BAT_INDICATOR")) m_batteryIndicator = (val == QLatin1String("true"));
                if (key == QLatin1String("LID_BAT_POLL"))    m_batteryPollSecs = val.toInt();
            }
        }
        // Guard defaults
        if (m_brightness < 0 || m_brightness > 255) m_brightness = 128;
        if (m_mode.isEmpty()) m_mode = QStringLiteral("Static");
        if (m_interval < 0 || m_interval > 5) m_interval = 0;
        if (m_batteryPollSecs < 5 || m_batteryPollSecs > 300) m_batteryPollSecs = 30;

        readBattery();

        Q_EMIT enabledChanged(); Q_EMIT brightnessChanged(); Q_EMIT modeChanged();
        Q_EMIT intervalChanged(); Q_EMIT showOnBootChanged(); Q_EMIT showOnShutdownChanged();
        Q_EMIT showOnSleepChanged(); Q_EMIT showOnBatteryChanged(); Q_EMIT showBatteryWarningChanged();
        Q_EMIT batteryIndicatorChanged(); Q_EMIT batteryPollSecsChanged(); Q_EMIT currentBatteryPctChanged();
        setNeedsSave(false);
        updateBatteryTimer();
    }

    void save() override {
        applyToHardware();
        QFile f(m_configPath);
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            QTextStream out(&f);
            out << "LID_ENABLED=\""       << (m_enabled ? "true" : "false")           << "\"\n";
            out << "LID_BRIGHTNESS=\""    << QString::number(m_brightness)             << "\"\n";
            out << "LID_MODE=\""          << m_mode                                   << "\"\n";
            out << "LID_INTERVAL=\""      << QString::number(m_interval)              << "\"\n";
            out << "LID_BOOT=\""          << (m_showOnBoot ? "true" : "false")        << "\"\n";
            out << "LID_SHUTDOWN=\""      << (m_showOnShutdown ? "true" : "false")    << "\"\n";
            out << "LID_SLEEP=\""         << (m_showOnSleep ? "true" : "false")       << "\"\n";
            out << "LID_BATTERY=\""       << (m_showOnBattery ? "true" : "false")     << "\"\n";
            out << "LID_BAT_WARNING=\""   << (m_showBatteryWarning ? "true" : "false") << "\"\n";
            out << "LID_BAT_INDICATOR=\"" << (m_batteryIndicator ? "true" : "false")  << "\"\n";
            out << "LID_BAT_POLL=\""      << QString::number(m_batteryPollSecs)       << "\"\n";
        }
        setNeedsSave(false);
        updateBatteryTimer();
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
        setBatteryIndicator(false);
        setBatteryPollSecs(30);
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
    void batteryIndicatorChanged();
    void batteryPollSecsChanged();
    void currentBatteryPctChanged();

private:
    void readBattery() {
        QFile capFile(QStringLiteral("/sys/class/power_supply/BAT1/capacity"));
        if (capFile.open(QIODevice::ReadOnly)) {
            m_currentBatteryPct = QString::fromUtf8(capFile.readAll().trimmed()).toInt();
        }
        QFile statusFile(QStringLiteral("/sys/class/power_supply/BAT1/status"));
        if (statusFile.open(QIODevice::ReadOnly)) {
            m_currentBatteryStatus = QString::fromUtf8(statusFile.readAll().trimmed());
        }
    }

    void applyToHardware() {
        if (m_enabled) {
            QProcess::startDetached(QStringLiteral("asusctl"),
                {QStringLiteral("slash"), QStringLiteral("--enable")});

            if (m_batteryIndicator) {
                applyBatteryBrightness();
            } else {
                QProcess::startDetached(QStringLiteral("asusctl"),
                    {QStringLiteral("slash"), QStringLiteral("-l"), QString::number(m_brightness)});
                QProcess::startDetached(QStringLiteral("asusctl"),
                    {QStringLiteral("slash"), QStringLiteral("--mode"), m_mode});
            }

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

    void applyBatteryBrightness() {
        readBattery();
        Q_EMIT currentBatteryPctChanged();

        int bright = m_currentBatteryPct * 255 / 100;
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("slash"), QStringLiteral("-l"), QString::number(bright)});

        // Charging → Flow, low battery → Hazard, otherwise → Static
        QString autoMode;
        if (m_currentBatteryStatus == QLatin1String("Charging")) {
            autoMode = QStringLiteral("Flow");
        } else if (m_currentBatteryPct <= 15) {
            autoMode = QStringLiteral("Hazard");
        } else {
            autoMode = QStringLiteral("Static");
        }
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("slash"), QStringLiteral("--mode"), autoMode});
    }

    void updateBatteryTimer() {
        if (m_batteryIndicator && m_enabled) {
            m_batteryTimer->setInterval(m_batteryPollSecs * 1000);
            if (!m_batteryTimer->isActive()) {
                applyBatteryBrightness();
                m_batteryTimer->start();
            }
        } else {
            m_batteryTimer->stop();
        }
    }

    void updateBatteryIndicator() {
        if (m_batteryIndicator && m_enabled)
            applyBatteryBrightness();
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
    bool    m_batteryIndicator = false;
    int     m_batteryPollSecs  = 30;
    int     m_currentBatteryPct = 0;
    QString m_currentBatteryStatus;
    QTimer *m_batteryTimer;
};

K_PLUGIN_CLASS_WITH_JSON(LuminosLidLightKcm, "kcm_luminos_lid_light.json")
#include "kcm_luminos_lid_light.moc"
