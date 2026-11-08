// [CHANGE: claude-code | 2026-11-08] DECISION 179 — see proxy.h.
#include "proxy.h"

#include <KConfigGroup>
#include <KPluginFactory>
#include <KSharedConfig>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QUrl>

K_PLUGIN_CLASS_WITH_JSON(Proxy, "kcm_luminos_proxy.json")

namespace
{
// kio-extras stores a proxy as "<url> <port>", e.g. "http://proxy.example.com 8080"
void splitProxy(const QString &value, QString *host, int *port)
{
    host->clear();
    *port = 0;
    if (value.trimmed().isEmpty())
        return;
    const int sp = value.lastIndexOf(QLatin1Char(' '));
    QString url = sp > 0 ? value.left(sp) : value;
    if (sp > 0)
        *port = value.mid(sp + 1).toInt();
    const QUrl u(url);
    if (u.isValid() && !u.host().isEmpty()) {
        // show "proxy.example.com" for the plain web schemes, keep anything unusual exactly as stored
        if (u.scheme() == QLatin1String("http") || u.scheme() == QLatin1String("ftp") || u.scheme() == QLatin1String("socks"))
            url = u.host();
        if (*port == 0 && u.port() > 0)
            *port = u.port();
    }
    *host = url;
}
QString joinProxy(const QString &host, int port, const QString &scheme)
{
    const QString h = host.trimmed();
    if (h.isEmpty())
        return QString();
    QString url = h.contains(QLatin1String("://")) ? h : scheme + QLatin1String("://") + h;
    return port > 0 ? url + QLatin1Char(' ') + QString::number(port) : url;
}
KConfigGroup group()
{
    return KSharedConfig::openConfig(QStringLiteral("kioslaverc"), KConfig::NoGlobals)->group(QStringLiteral("Proxy Settings"));
}
// kio's ProxyType: 0 none, 1 manual, 2 PAC, 3 WPAD, 4 env  <->  ours: 0 off, 1 WPAD, 2 PAC, 3 manual, 4 env
int fromKio(int t) { return t == 1 ? 3 : t == 3 ? 1 : (t >= 0 && t <= 4 ? t : 0); }
int toKio(int m) { return m == 3 ? 1 : m == 1 ? 3 : m; }
}

Proxy::Proxy(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    setButtons(Apply | Default);
}

void Proxy::load()
{
    KSharedConfig::openConfig(QStringLiteral("kioslaverc"), KConfig::NoGlobals)->reparseConfiguration();
    const KConfigGroup g = group();
    m_mode = fromKio(g.readEntry("ProxyType", 0));
    m_pacUrl = g.readEntry("Proxy Config Script", QString());
    m_noProxyFor = g.readEntry("NoProxyFor", QString());
    m_onlyForList = g.readEntry("ReversedException", false);
    const QString http = g.readEntry("httpProxy", QString()), https = g.readEntry("httpsProxy", QString());
    const QString ftp = g.readEntry("ftpProxy", QString()), socks = g.readEntry("socksProxy", QString());
    if (m_mode == 4) {
        m_envHttp = http; m_envHttps = https; m_envFtp = ftp; m_envSocks = socks; m_envNoProxy = m_noProxyFor;
        m_httpHost.clear(); m_httpsHost.clear(); m_ftpHost.clear(); m_socksHost.clear();
        m_httpPort = m_httpsPort = m_ftpPort = m_socksPort = 0;
        m_noProxyFor.clear();
        m_sameForAll = true;
    } else {
        splitProxy(http, &m_httpHost, &m_httpPort);
        splitProxy(https, &m_httpsHost, &m_httpsPort);
        splitProxy(ftp, &m_ftpHost, &m_ftpPort);
        splitProxy(socks, &m_socksHost, &m_socksPort);
        m_sameForAll = m_socksHost.isEmpty()
            && (m_httpsHost.isEmpty() || (m_httpsHost == m_httpHost && m_httpsPort == m_httpPort))
            && (m_ftpHost.isEmpty() || (m_ftpHost == m_httpHost && m_ftpPort == m_httpPort));
    }
    Q_EMIT changed();
    setNeedsSave(false);
    // test aid: LUMINOS_PROXY_TEST="mode=3;httpHost=proxy.test;httpPort=3128;..." sets these once and saves
    static bool testDone = false;
    const QString t = qEnvironmentVariable("LUMINOS_PROXY_TEST");
    if (!testDone && !t.isEmpty()) {
        testDone = true;
        for (const QString &kv : t.split(QLatin1Char(';'), Qt::SkipEmptyParts)) {
            const QString k = kv.section(QLatin1Char('='), 0, 0), v = kv.section(QLatin1Char('='), 1);
            setProperty(k.toLatin1().constData(), v);
        }
        QMetaObject::invokeMethod(this, &Proxy::save, Qt::QueuedConnection);
    }
}

void Proxy::save()
{
    KConfigGroup g = group();
    g.writeEntry("ProxyType", toKio(m_mode));
    g.writeEntry("ReversedException", m_onlyForList);
    if (m_mode == 2)
        g.writeEntry("Proxy Config Script", m_pacUrl.trimmed());
    if (m_mode == 3) {
        const QString http = joinProxy(m_httpHost, m_httpPort, QStringLiteral("http"));
        g.writeEntry("httpProxy", http);
        g.writeEntry("httpsProxy", m_sameForAll ? http : joinProxy(m_httpsHost, m_httpsPort, QStringLiteral("http")));
        g.writeEntry("ftpProxy", m_sameForAll ? joinProxy(m_httpHost, m_httpPort, QStringLiteral("ftp")) : joinProxy(m_ftpHost, m_ftpPort, QStringLiteral("ftp")));
        g.writeEntry("socksProxy", m_sameForAll ? QString() : joinProxy(m_socksHost, m_socksPort, QStringLiteral("socks")));
        g.writeEntry("NoProxyFor", m_noProxyFor.trimmed());
    } else if (m_mode == 4) {
        // first switch to env mode: use the usual variable names, like kio-extras' "auto detect" button does
        g.writeEntry("httpProxy", m_envHttp.isEmpty() ? QStringLiteral("http_proxy") : m_envHttp);
        g.writeEntry("httpsProxy", m_envHttps.isEmpty() ? QStringLiteral("https_proxy") : m_envHttps);
        g.writeEntry("ftpProxy", m_envFtp.isEmpty() ? QStringLiteral("ftp_proxy") : m_envFtp);
        g.writeEntry("socksProxy", m_envSocks.isEmpty() ? QStringLiteral("socks_proxy") : m_envSocks);
        g.writeEntry("NoProxyFor", m_envNoProxy.isEmpty() ? QStringLiteral("no_proxy") : m_envNoProxy);
    }
    g.sync();
    // tell running KIO workers to re-read it (same signal kio-extras sends)
    QDBusMessage m = QDBusMessage::createSignal(QStringLiteral("/KIO/Scheduler"), QStringLiteral("org.kde.KIO.Scheduler"),
                                                QStringLiteral("reparseSlaveConfiguration"));
    m << QString();
    QDBusConnection::sessionBus().send(m);
    load();
}

void Proxy::defaults()
{
    m_mode = 0;
    m_pacUrl.clear();
    m_sameForAll = true;
    m_httpHost.clear(); m_httpsHost.clear(); m_ftpHost.clear(); m_socksHost.clear();
    m_httpPort = m_httpsPort = m_ftpPort = m_socksPort = 0;
    m_noProxyFor.clear();
    m_onlyForList = false;
    Q_EMIT changed();
    setNeedsSave(true);
}

QString Proxy::envSummary() const
{
    QStringList out;
    const auto add = [&out](const QString &label, const QString &var) {
        const QString name = var.isEmpty() ? QString() : var;
        if (name.isEmpty())
            return;
        const QString val = qEnvironmentVariable(name.toLocal8Bit().constData());
        out << QStringLiteral("%1: $%2 = %3").arg(label, name, val.isEmpty() ? QStringLiteral("(not set)") : val);
    };
    add(QStringLiteral("Web"), m_envHttp.isEmpty() ? QStringLiteral("http_proxy") : m_envHttp);
    add(QStringLiteral("Secure web"), m_envHttps.isEmpty() ? QStringLiteral("https_proxy") : m_envHttps);
    return out.join(QLatin1Char('\n'));
}

#include "proxy.moc"
