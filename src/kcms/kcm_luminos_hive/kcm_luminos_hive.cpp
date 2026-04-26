// Luminos OS — HIVE AI Settings KCM
// [CHANGE: antigravity | 2026-04-26]
//
// Provides a native KDE System Settings module for HIVE AI configuration.
// Reads/writes ~/.config/luminos-hive.conf and exposes properties to QML.

#include <KQuickManagedConfigModule>
#include <KPluginFactory>

#include <QFile>
#include <QProcess>
#include <QRegularExpression>
#include <QStringList>
#include <QTextStream>
#include <QDir>

class LuminosHiveKcm : public KQuickManagedConfigModule {
    Q_OBJECT
    // ── Properties exposed to QML ──────────────────────────────────
    Q_PROPERTY(QString mode READ mode WRITE setMode NOTIFY modeChanged)
    Q_PROPERTY(QString shortcutKey READ shortcutKey WRITE setShortcutKey NOTIFY shortcutKeyChanged)
    Q_PROPERTY(bool orchestratorRunning READ orchestratorRunning NOTIFY orchestratorRunningChanged)
    Q_PROPERTY(QString nexusStatus READ nexusStatus NOTIFY statusChanged)
    Q_PROPERTY(QString boltStatus READ boltStatus NOTIFY statusChanged)
    Q_PROPERTY(QString novaStatus READ novaStatus NOTIFY statusChanged)
    Q_PROPERTY(QString eyeStatus READ eyeStatus NOTIFY statusChanged)
    Q_PROPERTY(QString sentinelStatus READ sentinelStatus NOTIFY statusChanged)
    Q_PROPERTY(QString vramUsage READ vramUsage NOTIFY statusChanged)
    Q_PROPERTY(QString vramFree READ vramFree NOTIFY statusChanged)

public:
    explicit LuminosHiveKcm(QObject *parent, const KPluginMetaData &data)
        : KQuickManagedConfigModule(parent, data)
        , m_configPath(QDir::homePath() + QStringLiteral("/.config/luminos-hive.conf"))
    {
        setButtons(Apply | Default);
        load();
    }

    // ── Getters ────────────────────────────────────────────────────
    QString mode()           const { return m_mode; }
    QString shortcutKey()    const { return m_shortcutKey; }
    bool orchestratorRunning() const { return m_orchestratorRunning; }
    QString nexusStatus()    const { return m_nexusStatus; }
    QString boltStatus()     const { return m_boltStatus; }
    QString novaStatus()     const { return m_novaStatus; }
    QString eyeStatus()      const { return m_eyeStatus; }
    QString sentinelStatus() const { return m_sentinelStatus; }
    QString vramUsage()      const { return m_vramUsage; }
    QString vramFree()       const { return m_vramFree; }

    // ── Setters ────────────────────────────────────────────────────
    void setMode(const QString &v) {
        if (m_mode != v) { m_mode = v; Q_EMIT modeChanged(); setNeedsSave(true); }
    }
    void setShortcutKey(const QString &v) {
        if (m_shortcutKey != v) { m_shortcutKey = v; Q_EMIT shortcutKeyChanged(); setNeedsSave(true); }
    }

    // ── Refresh model/GPU status ───────────────────────────────────
    Q_INVOKABLE void refreshStatus() {
        // Check orchestrator
        QProcess procCheck;
        procCheck.start(QStringLiteral("pgrep"), {QStringLiteral("-f"), QStringLiteral("hive/orchestrator")});
        procCheck.waitForFinished(3000);
        m_orchestratorRunning = (procCheck.exitCode() == 0);

        // Check GPU VRAM
        QProcess nvidiaSmi;
        nvidiaSmi.start(QStringLiteral("nvidia-smi"),
            {QStringLiteral("--query-gpu=memory.used,memory.free"),
             QStringLiteral("--format=csv,noheader,nounits")});
        nvidiaSmi.waitForFinished(3000);
        if (nvidiaSmi.exitCode() == 0) {
            const auto parts = QString::fromUtf8(nvidiaSmi.readAllStandardOutput()).trimmed().split(QStringLiteral(","));
            if (parts.size() >= 2) {
                m_vramUsage = parts[0].trimmed() + QStringLiteral(" MiB");
                m_vramFree  = parts[1].trimmed() + QStringLiteral(" MiB");
            }
        }

        // Check llama-server processes for model status
        auto checkModel = [](const QString &pattern) -> QString {
            QProcess p;
            p.start(QStringLiteral("pgrep"), {QStringLiteral("-af"), pattern});
            p.waitForFinished(2000);
            return (p.exitCode() == 0) ? QStringLiteral("Running") : QStringLiteral("Idle");
        };

        m_nexusStatus   = checkModel(QStringLiteral("dolphin"));
        m_boltStatus    = checkModel(QStringLiteral("qwen.*coder"));
        m_novaStatus    = checkModel(QStringLiteral("deepseek"));
        m_eyeStatus     = checkModel(QStringLiteral("qwen.*vl"));
        m_sentinelStatus = checkModel(QStringLiteral("mobilellm"));

        Q_EMIT orchestratorRunningChanged();
        Q_EMIT statusChanged();
    }

    // ── Toggle mode shortcut ───────────────────────────────────────
    Q_INVOKABLE void toggleMode() {
        setMode(m_mode == QStringLiteral("ai") ? QStringLiteral("normal") : QStringLiteral("ai"));
    }

    // ── KCM lifecycle ──────────────────────────────────────────────
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
                if (key == QLatin1String("HIVE_MODE"))     m_mode = val;
                if (key == QLatin1String("HIVE_SHORTCUT")) m_shortcutKey = val;
            }
        }
        // Defaults
        if (m_mode.isEmpty())        m_mode = QStringLiteral("normal");
        if (m_shortcutKey.isEmpty()) m_shortcutKey = QStringLiteral("Meta+Space");

        Q_EMIT modeChanged();
        Q_EMIT shortcutKeyChanged();
        setNeedsSave(false);
        refreshStatus();
    }

    void save() override {
        QFile f(m_configPath);
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            QTextStream out(&f);
            out << "HIVE_MODE=\""     << m_mode        << "\"\n";
            out << "HIVE_SHORTCUT=\"" << m_shortcutKey  << "\"\n";
        }
        // Signal running orchestrator to reload config
        QProcess::startDetached(QStringLiteral("pkill"),
            {QStringLiteral("-USR1"), QStringLiteral("-f"), QStringLiteral("hive/orchestrator")});
        setNeedsSave(false);
    }

    void defaults() override {
        setMode(QStringLiteral("normal"));
        setShortcutKey(QStringLiteral("Meta+Space"));
    }

Q_SIGNALS:
    void modeChanged();
    void shortcutKeyChanged();
    void orchestratorRunningChanged();
    void statusChanged();

private:
    QString m_configPath;
    QString m_mode          = QStringLiteral("normal");
    QString m_shortcutKey   = QStringLiteral("Meta+Space");
    bool    m_orchestratorRunning = false;
    QString m_nexusStatus   = QStringLiteral("Unknown");
    QString m_boltStatus    = QStringLiteral("Unknown");
    QString m_novaStatus    = QStringLiteral("Unknown");
    QString m_eyeStatus     = QStringLiteral("Unknown");
    QString m_sentinelStatus = QStringLiteral("Unknown");
    QString m_vramUsage     = QStringLiteral("N/A");
    QString m_vramFree      = QStringLiteral("N/A");
};

K_PLUGIN_CLASS_WITH_JSON(LuminosHiveKcm, "kcm_luminos_hive.json")
#include "kcm_luminos_hive.moc"
