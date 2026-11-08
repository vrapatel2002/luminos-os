// [CHANGE: claude-code | 2026-11-08] DECISION 179 — see netpref.h.
#include "netpref.h"

#include <KConfigGroup>
#include <KPluginFactory>
#include <KSharedConfig>
#include <QDBusConnection>
#include <QDBusMessage>

K_PLUGIN_CLASS_WITH_JSON(NetPref, "kcm_luminos_netpref.json")

namespace
{
KConfigGroup rootOf(const QString &file)
{
    auto cfg = KSharedConfig::openConfig(file, KConfig::NoGlobals);
    cfg->reparseConfiguration();
    return cfg->group(QStringLiteral("<default>")); // the file's top-level group, as KConfigSkeleton writes it
}
}

NetPref::NetPref(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    setButtons(Apply | Default);
}

void NetPref::load()
{
    m_markPartial = rootOf(QStringLiteral("kioslaverc")).readEntry("MarkPartial", true);
    const KConfigGroup ftp = rootOf(QStringLiteral("kio_ftprc"));
    m_ftpPassive = !ftp.readEntry("DisablePassiveMode", false);
    m_ftpMarkPartial = ftp.readEntry("MarkPartial", true);
    Q_EMIT changed();
    setNeedsSave(false);
    static bool testDone = false; // test aid: LUMINOS_NETPREF_TEST="markPartial=false;ftpPassive=false"
    const QString t = qEnvironmentVariable("LUMINOS_NETPREF_TEST");
    if (!testDone && !t.isEmpty()) {
        testDone = true;
        for (const QString &kv : t.split(QLatin1Char(';'), Qt::SkipEmptyParts))
            setProperty(kv.section(QLatin1Char('='), 0, 0).toLatin1().constData(), kv.section(QLatin1Char('='), 1) == QLatin1String("true"));
        QMetaObject::invokeMethod(this, &NetPref::save, Qt::QueuedConnection);
    }
}

void NetPref::save()
{
    KConfigGroup k = rootOf(QStringLiteral("kioslaverc"));
    k.writeEntry("MarkPartial", m_markPartial);
    k.sync();
    KConfigGroup f = rootOf(QStringLiteral("kio_ftprc"));
    f.writeEntry("DisablePassiveMode", !m_ftpPassive);
    f.writeEntry("MarkPartial", m_ftpMarkPartial);
    f.sync();
    QDBusMessage m = QDBusMessage::createSignal(QStringLiteral("/KIO/Scheduler"), QStringLiteral("org.kde.KIO.Scheduler"),
                                                QStringLiteral("reparseSlaveConfiguration"));
    m << QString();
    QDBusConnection::sessionBus().send(m);
    setNeedsSave(false);
}

void NetPref::defaults()
{
    setMarkPartial(true);
    setFtpPassive(true);
    setFtpMarkPartial(true);
}

#include "netpref.moc"
