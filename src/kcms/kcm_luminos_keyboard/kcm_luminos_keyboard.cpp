// Luminos OS — Keyboard Backlight KCM
// [CHANGE: claude-code | 2026-04-26]

#include <KQuickManagedConfigModule>
#include <KPluginFactory>
#include <QDir>
#include <QFile>
#include <QProcess>
#include <QRegularExpression>
#include <QTextStream>

class LuminosKeyboardKcm : public KQuickManagedConfigModule
{
    Q_OBJECT
    Q_PROPERTY(QString color READ color WRITE setColor NOTIFY colorChanged)
    Q_PROPERTY(int brightness READ brightness WRITE setBrightness NOTIFY brightnessChanged)
    Q_PROPERTY(QString mode READ mode WRITE setMode NOTIFY modeChanged)

public:
    LuminosKeyboardKcm(QObject *parent, const KPluginMetaData &data)
        : KQuickManagedConfigModule(parent, data)
        , m_configPath(QDir::homePath() + QStringLiteral("/.config/luminos-keyboard.conf"))
    {
    }

    QString color()    const { return m_color;      }
    int     brightness() const { return m_brightness; }
    QString mode()     const { return m_mode;       }

    void setColor(const QString &c) {
        if (m_color != c) { m_color = c; Q_EMIT colorChanged(); setNeedsSave(true); }
    }
    void setBrightness(int b) {
        if (m_brightness != b) { m_brightness = b; Q_EMIT brightnessChanged(); setNeedsSave(true); }
    }
    void setMode(const QString &m) {
        if (m_mode != m) { m_mode = m; Q_EMIT modeChanged(); setNeedsSave(true); }
    }

    Q_INVOKABLE void preview() { applyToHardware(); }

    void load() override {
        QFile f(m_configPath);
        if (f.open(QIODevice::ReadOnly)) {
            QTextStream in(&f);
            static const QRegularExpression re(QStringLiteral("^(\\w+)=\"?([^\"]*)\"?$"));
            while (!in.atEnd()) {
                const auto match = re.match(in.readLine());
                if (!match.hasMatch()) continue;
                const auto key = match.captured(1);
                const auto val = match.captured(2);
                if (key == QLatin1String("KB_COLOR"))      m_color      = val;
                if (key == QLatin1String("KB_BRIGHTNESS")) m_brightness = val.toInt();
                if (key == QLatin1String("KB_MODE"))       m_mode       = val;
            }
        }
        Q_EMIT colorChanged();
        Q_EMIT brightnessChanged();
        Q_EMIT modeChanged();
        setNeedsSave(false);
    }

    void save() override {
        applyToHardware();
        QFile f(m_configPath);
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            QTextStream out(&f);
            out << "KB_COLOR=\""      << m_color                      << "\"\n";
            out << "KB_BRIGHTNESS=\"" << QString::number(m_brightness) << "\"\n";
            out << "KB_MODE=\""       << m_mode                       << "\"\n";
        }
        QProcess::startDetached(QStringLiteral("systemctl"),
            {QStringLiteral("--user"), QStringLiteral("restart"),
             QStringLiteral("luminos-keyboard.service")});
        setNeedsSave(false);
    }

    void defaults() override {
        setColor(QStringLiteral("ffffff"));
        setBrightness(3);
        setMode(QStringLiteral("static"));
    }

Q_SIGNALS:
    void colorChanged();
    void brightnessChanged();
    void modeChanged();

private:
    void applyToHardware() {
        QProcess::startDetached(QStringLiteral("asusctl"),
            {QStringLiteral("aura"), QStringLiteral("effect"),
             m_mode, QStringLiteral("-c"), m_color});

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

    QString m_configPath;
    QString m_color      = QStringLiteral("ffffff");
    int     m_brightness = 3;
    QString m_mode       = QStringLiteral("static");
};

K_PLUGIN_CLASS_WITH_JSON(LuminosKeyboardKcm, "kcm_luminos_keyboard.json")
#include "kcm_luminos_keyboard.moc"
