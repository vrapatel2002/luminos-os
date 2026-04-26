// Luminos OS — Keyboard Backlight KCM
// [CHANGE: claude-code | 2026-04-26]

#include <KQuickManagedConfigModule>
#include <KPluginFactory>
#include <QDir>
#include <QFile>
#include <QProcess>
#include <QRegularExpression>
#include <QTextStream>
#include <QTimer>

// Effects that take -c <color>
static const QStringList COLOR1_EFFECTS  = {QStringLiteral("static"),QStringLiteral("pulse"),QStringLiteral("comet"),QStringLiteral("flash"),QStringLiteral("highlight"),QStringLiteral("laser"),QStringLiteral("ripple")};
// Effects that take --colour <c1> --colour2 <c2> --speed
static const QStringList COLOR2_EFFECTS  = {QStringLiteral("breathe"),QStringLiteral("stars")};
// Effects that take only --speed (no color)
static const QStringList SPEEDONLY_EFFECTS = {QStringLiteral("rainbow-cycle"),QStringLiteral("rainbow-wave"),QStringLiteral("rain")};
// Effects that take -c <color> AND --speed
static const QStringList COLOR1SPEED_EFFECTS = {QStringLiteral("highlight"),QStringLiteral("laser"),QStringLiteral("ripple")};

class LuminosKeyboardKcm : public KQuickManagedConfigModule
{
    Q_OBJECT
    Q_PROPERTY(QString color    READ color    WRITE setColor    NOTIFY colorChanged)
    Q_PROPERTY(QString color2   READ color2   WRITE setColor2   NOTIFY color2Changed)
    Q_PROPERTY(int     brightness READ brightness WRITE setBrightness NOTIFY brightnessChanged)
    Q_PROPERTY(QString mode     READ mode     WRITE setMode     NOTIFY modeChanged)
    Q_PROPERTY(int     speed    READ speed    WRITE setSpeed    NOTIFY speedChanged)
    Q_PROPERTY(bool    autoColorEnabled  READ autoColorEnabled  WRITE setAutoColorEnabled  NOTIFY autoColorEnabledChanged)
    Q_PROPERTY(int     autoColorInterval READ autoColorInterval WRITE setAutoColorInterval NOTIFY autoColorIntervalChanged)
    Q_PROPERTY(QStringList autoColors   READ autoColors   WRITE setAutoColors   NOTIFY autoColorsChanged)

    // Read-only helpers for QML show/hide logic
    Q_PROPERTY(bool hasColor  READ hasColor  NOTIFY modeChanged)
    Q_PROPERTY(bool hasColor2 READ hasColor2 NOTIFY modeChanged)
    Q_PROPERTY(bool hasSpeed  READ hasSpeed  NOTIFY modeChanged)

public:
    LuminosKeyboardKcm(QObject *parent, const KPluginMetaData &data)
        : KQuickManagedConfigModule(parent, data)
        , m_configPath(QDir::homePath() + QStringLiteral("/.config/luminos-keyboard.conf"))
        , m_autoTimer(new QTimer(this))
    {
        connect(m_autoTimer, &QTimer::timeout, this, &LuminosKeyboardKcm::cycleAutoColor);
    }

    // --- property getters ---
    QString color()    const { return m_color; }
    QString color2()   const { return m_color2; }
    int brightness()   const { return m_brightness; }
    QString mode()     const { return m_mode; }
    int speed()        const { return m_speed; }
    bool autoColorEnabled()  const { return m_autoEnabled; }
    int autoColorInterval()  const { return m_autoInterval; }
    QStringList autoColors() const { return m_autoColors; }

    bool hasColor()  const { return COLOR1_EFFECTS.contains(m_mode) || COLOR2_EFFECTS.contains(m_mode); }
    bool hasColor2() const { return COLOR2_EFFECTS.contains(m_mode); }
    bool hasSpeed()  const { return COLOR2_EFFECTS.contains(m_mode) || SPEEDONLY_EFFECTS.contains(m_mode) || COLOR1SPEED_EFFECTS.contains(m_mode); }

    // --- property setters ---
    void setColor(const QString &v)  { if (m_color  != v) { m_color  = v; Q_EMIT colorChanged();  setNeedsSave(true); } }
    void setColor2(const QString &v) { if (m_color2 != v) { m_color2 = v; Q_EMIT color2Changed(); setNeedsSave(true); } }
    void setBrightness(int v)        { if (m_brightness != v) { m_brightness = v; Q_EMIT brightnessChanged(); setNeedsSave(true); } }
    void setMode(const QString &v)   { if (m_mode   != v) { m_mode   = v; Q_EMIT modeChanged();   setNeedsSave(true); } }
    void setSpeed(int v)             { if (m_speed  != v) { m_speed  = v; Q_EMIT speedChanged();  setNeedsSave(true); } }
    void setAutoColorEnabled(bool v) { if (m_autoEnabled  != v) { m_autoEnabled  = v; Q_EMIT autoColorEnabledChanged(); setNeedsSave(true); updateAutoTimer(); } }
    void setAutoColorInterval(int v) { if (m_autoInterval != v) { m_autoInterval = v; Q_EMIT autoColorIntervalChanged(); setNeedsSave(true); updateAutoTimer(); } }
    void setAutoColors(const QStringList &v) { if (m_autoColors != v) { m_autoColors = v; Q_EMIT autoColorsChanged(); setNeedsSave(true); } }

    // --- invokable actions ---
    Q_INVOKABLE void preview() { applyToHardware(); }

    Q_INVOKABLE void addAutoColor(const QString &c) {
        if (!m_autoColors.contains(c)) {
            m_autoColors.append(c);
            Q_EMIT autoColorsChanged();
            setNeedsSave(true);
        }
    }
    Q_INVOKABLE void removeAutoColor(int index) {
        if (index >= 0 && index < m_autoColors.size()) {
            m_autoColors.removeAt(index);
            Q_EMIT autoColorsChanged();
            setNeedsSave(true);
        }
    }

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
                if (key == QLatin1String("KB_COLOR"))         m_color      = val;
                if (key == QLatin1String("KB_COLOR2"))        m_color2     = val;
                if (key == QLatin1String("KB_BRIGHTNESS"))    m_brightness = val.toInt();
                if (key == QLatin1String("KB_MODE"))          m_mode       = val;
                if (key == QLatin1String("KB_SPEED"))         m_speed      = val.toInt();
                if (key == QLatin1String("KB_AUTO_ENABLED"))  m_autoEnabled  = (val == QLatin1String("true"));
                if (key == QLatin1String("KB_AUTO_INTERVAL")) m_autoInterval = val.toInt();
                if (key == QLatin1String("KB_AUTO_COLORS") && !val.isEmpty())
                    m_autoColors = val.split(QLatin1Char(','), Qt::SkipEmptyParts);
            }
        }
        // Guard defaults
        if (m_color.isEmpty())  m_color = QStringLiteral("ffffff");
        if (m_color2.isEmpty()) m_color2 = QStringLiteral("0000ff");
        if (m_brightness < 1 || m_brightness > 3) m_brightness = 3;
        if (m_mode.isEmpty())  m_mode = QStringLiteral("static");
        if (m_autoInterval < 1) m_autoInterval = 5;
        if (m_autoColors.isEmpty()) m_autoColors = {QStringLiteral("ff0000"),QStringLiteral("00ff00"),QStringLiteral("0000ff"),QStringLiteral("ffff00"),QStringLiteral("ff00ff"),QStringLiteral("00ffff")};

        Q_EMIT colorChanged(); Q_EMIT color2Changed(); Q_EMIT brightnessChanged();
        Q_EMIT modeChanged(); Q_EMIT speedChanged();
        Q_EMIT autoColorEnabledChanged(); Q_EMIT autoColorIntervalChanged(); Q_EMIT autoColorsChanged();
        setNeedsSave(false);
        updateAutoTimer();
    }

    void save() override {
        m_autoTimer->stop(); // stop so we apply the chosen/saved config, then restart
        applyToHardware();
        QFile f(m_configPath);
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            QTextStream out(&f);
            out << "KB_COLOR=\""         << m_color                       << "\"\n";
            out << "KB_COLOR2=\""        << m_color2                      << "\"\n";
            out << "KB_BRIGHTNESS=\""    << QString::number(m_brightness)  << "\"\n";
            out << "KB_MODE=\""          << m_mode                        << "\"\n";
            out << "KB_SPEED=\""         << QString::number(m_speed)       << "\"\n";
            out << "KB_AUTO_ENABLED=\""  << (m_autoEnabled ? "true" : "false") << "\"\n";
            out << "KB_AUTO_INTERVAL=\"" << QString::number(m_autoInterval) << "\"\n";
            out << "KB_AUTO_COLORS=\""   << m_autoColors.join(QLatin1Char(',')) << "\"\n";
        }
        QProcess::startDetached(QStringLiteral("systemctl"),
            {QStringLiteral("--user"), QStringLiteral("restart"),
             QStringLiteral("luminos-keyboard.service")});
        setNeedsSave(false);
        updateAutoTimer();
    }

    void defaults() override {
        setColor(QStringLiteral("ffffff"));
        setColor2(QStringLiteral("0000ff"));
        setBrightness(3);
        setMode(QStringLiteral("static"));
        setSpeed(1);
        setAutoColorEnabled(false);
        setAutoColorInterval(5);
        setAutoColors({QStringLiteral("ff0000"),QStringLiteral("00ff00"),QStringLiteral("0000ff"),QStringLiteral("ffff00"),QStringLiteral("ff00ff"),QStringLiteral("00ffff")});
    }

Q_SIGNALS:
    void colorChanged();
    void color2Changed();
    void brightnessChanged();
    void modeChanged();
    void speedChanged();
    void autoColorEnabledChanged();
    void autoColorIntervalChanged();
    void autoColorsChanged();

private:
    QString speedName() const {
        switch (m_speed) { case 0: return QStringLiteral("low"); case 2: return QStringLiteral("high"); default: return QStringLiteral("med"); }
    }

    void applyToHardware() {
        QStringList args{QStringLiteral("aura"), QStringLiteral("effect"), m_mode};

        if (COLOR2_EFFECTS.contains(m_mode)) {
            // breathe / stars: --colour c1 --colour2 c2 --speed spd
            args << QStringLiteral("--colour") << m_color
                 << QStringLiteral("--colour2") << m_color2
                 << QStringLiteral("--speed") << speedName();
        } else if (SPEEDONLY_EFFECTS.contains(m_mode)) {
            // rainbow-cycle / rainbow-wave / rain: --speed only
            args << QStringLiteral("--speed") << speedName();
        } else if (COLOR1SPEED_EFFECTS.contains(m_mode)) {
            // highlight / laser / ripple: -c color --speed
            args << QStringLiteral("-c") << m_color << QStringLiteral("--speed") << speedName();
        } else if (COLOR1_EFFECTS.contains(m_mode)) {
            // static / pulse / comet / flash: -c color
            args << QStringLiteral("-c") << m_color;
        }
        // "none" → no extra args

        QProcess::startDetached(QStringLiteral("asusctl"), args);

        // Apply brightness via sysfs
        QFile sysfs(QStringLiteral("/sys/class/leds/asus::kbd_backlight/brightness"));
        if (sysfs.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            sysfs.write(QString::number(m_brightness).toUtf8());
        } else {
            QProcess::startDetached(QStringLiteral("bash"),
                {QStringLiteral("-c"),
                 QStringLiteral("echo %1 | sudo tee /sys/class/leds/asus::kbd_backlight/brightness")
                     .arg(m_brightness)});
        }
    }

    void updateAutoTimer() {
        if (m_autoEnabled && !m_autoColors.isEmpty()) {
            m_autoTimer->setInterval(m_autoInterval * 1000);
            if (!m_autoTimer->isActive()) m_autoTimer->start();
        } else {
            m_autoTimer->stop();
        }
    }

    void cycleAutoColor() {
        if (m_autoColors.isEmpty()) return;
        m_autoColorIndex = (m_autoColorIndex + 1) % m_autoColors.size();
        m_color = m_autoColors[m_autoColorIndex];
        Q_EMIT colorChanged();
        applyToHardware();
    }

    QString     m_configPath;
    QString     m_color      = QStringLiteral("ffffff");
    QString     m_color2     = QStringLiteral("0000ff");
    int         m_brightness = 3;
    QString     m_mode       = QStringLiteral("static");
    int         m_speed      = 1;       // 0=low 1=med 2=high
    bool        m_autoEnabled  = false;
    int         m_autoInterval = 5;     // seconds
    QStringList m_autoColors   = {QStringLiteral("ff0000"),QStringLiteral("00ff00"),QStringLiteral("0000ff"),QStringLiteral("ffff00"),QStringLiteral("ff00ff"),QStringLiteral("00ffff")};
    int         m_autoColorIndex = 0;
    QTimer     *m_autoTimer;
};

K_PLUGIN_CLASS_WITH_JSON(LuminosKeyboardKcm, "kcm_luminos_keyboard.json")
#include "kcm_luminos_keyboard.moc"
