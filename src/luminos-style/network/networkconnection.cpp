// [CHANGE: claude-code | 2026-11-08] DECISION 178 — see networkconnection.h.
#include "networkconnection.h"

#include <NetworkManagerQt/AccessPoint>
#include <NetworkManagerQt/ActiveConnection>
#include <NetworkManagerQt/Connection>
#include <NetworkManagerQt/ConnectionSettings>
#include <NetworkManagerQt/Device>
#include <NetworkManagerQt/Ipv4Setting>
#include <NetworkManagerQt/Ipv6Setting>
#include <NetworkManagerQt/Manager>
#include <NetworkManagerQt/Settings>
#include <NetworkManagerQt/WirelessDevice>
#include <NetworkManagerQt/WirelessSecuritySetting>
#include <NetworkManagerQt/WirelessSetting>

#include <QDBusPendingCallWatcher>
#include <QHostAddress>
#include <QRegularExpression>

using namespace NetworkManager;

namespace
{
template<typename T>
QSharedPointer<T> settingOf(const ConnectionSettings::Ptr &s, Setting::SettingType t)
{
    auto p = s->setting(t).dynamicCast<T>();
    return (p && !p->isNull()) ? p : QSharedPointer<T>();
}
int channelOf(uint mhz)
{
    if (mhz >= 2412 && mhz <= 2484)
        return mhz == 2484 ? 14 : int(mhz - 2407) / 5;
    if (mhz >= 5955)
        return int(mhz - 5950) / 5; // 6 GHz
    if (mhz >= 5000)
        return int(mhz - 5000) / 5;
    return 0;
}
QString joinHosts(const QList<QHostAddress> &l)
{
    QStringList out;
    for (const auto &a : l)
        out << a.toString();
    return out.join(QStringLiteral(", "));
}
const QString kWsec = QStringLiteral("802-11-wireless-security");
const QString k8021x = QStringLiteral("802-1x");
}

NetworkConnection::NetworkConnection(QObject *parent)
    : QObject(parent)
{
}

void NetworkConnection::setPath(const QString &p)
{
    if (p == m_path)
        return;
    m_path = p;
    Q_EMIT pathChanged();
    reload();
    refreshStatus();
}

void NetworkConnection::setBusy(bool b)
{
    if (m_busy != b) {
        m_busy = b;
        Q_EMIT busyChanged();
    }
}

void NetworkConnection::reload()
{
    m_valid = false;
    m_password.clear();
    m_passwordEdited = false;
    Connection::Ptr c = m_path.isEmpty() ? Connection::Ptr() : findConnection(m_path);
    if (!c) {
        Q_EMIT loaded();
        Q_EMIT edited();
        return;
    }
    const ConnectionSettings::Ptr s = c->settings();
    m_valid = true;
    m_name = s->id();
    switch (s->connectionType()) {
    case ConnectionSettings::Wireless: m_kind = QStringLiteral("wifi"); break;
    case ConnectionSettings::Wired: m_kind = QStringLiteral("ethernet"); break;
    case ConnectionSettings::Vpn:
    case ConnectionSettings::WireGuard: m_kind = QStringLiteral("vpn"); break;
    default: m_kind = QStringLiteral("other"); break;
    }
    m_autoconnect = s->autoconnect();
    m_allUsers = s->permissions().isEmpty();
    switch (s->metered()) {
    case ConnectionSettings::MeteredYes: m_metered = 1; break;
    case ConnectionSettings::MeteredNo: m_metered = 2; break;
    default: m_metered = 0; break;
    }

    m_securityText = QStringLiteral("Open");
    m_securityEditable = false;
    m_securityKind = 0;
    if (auto ws = settingOf<WirelessSecuritySetting>(s, Setting::WirelessSecurity)) {
        switch (ws->keyMgmt()) {
        case WirelessSecuritySetting::WpaPsk:
            m_securityText = QStringLiteral("WPA2 Personal"); m_securityEditable = true; m_securityKind = 0; break;
        case WirelessSecuritySetting::SAE:
            m_securityText = QStringLiteral("WPA3 Personal"); m_securityEditable = true; m_securityKind = 1; break;
        case WirelessSecuritySetting::WpaEap:
        case WirelessSecuritySetting::WpaEapSuiteB192:
            m_securityText = QStringLiteral("WPA Enterprise"); break;
        case WirelessSecuritySetting::Wep: m_securityText = QStringLiteral("WEP"); break;
        case WirelessSecuritySetting::OWE: m_securityText = QStringLiteral("Enhanced Open"); break;
        default: m_securityText = QStringLiteral("Other"); break;
        }
    }

    m_band = 0; m_macMode = 0; m_hidden = false; m_mtu = 0;
    if (auto w = settingOf<WirelessSetting>(s, Setting::Wireless)) {
        m_band = w->band() == WirelessSetting::Bg ? 1 : w->band() == WirelessSetting::A ? 2 : 0;
        const QString mac = w->assignedMacAddress();
        m_macMode = mac.isEmpty() ? 0 : mac == QLatin1String("permanent") ? 1 : mac == QLatin1String("random") ? 2
                  : mac == QLatin1String("stable") ? 3 : -1; // -1 = a typed-in address: shown as "Custom", kept on save
        m_hidden = w->hidden();
        m_mtu = int(w->mtu());
    }

    m_ipv4Manual = false; m_ipv4Address.clear(); m_ipv4Gateway.clear(); m_ipv4Prefix = 24; m_dnsAuto = true; m_dnsServers.clear();
    if (auto v4 = settingOf<Ipv4Setting>(s, Setting::Ipv4)) {
        m_ipv4Manual = v4->method() == Ipv4Setting::Manual;
        if (!v4->addresses().isEmpty()) {
            m_ipv4Address = v4->addresses().first().ip().toString();
            m_ipv4Prefix = v4->addresses().first().prefixLength();
            if (!v4->addresses().first().gateway().isNull())
                m_ipv4Gateway = v4->addresses().first().gateway().toString();
        }
        if (!v4->gateway().isEmpty())
            m_ipv4Gateway = v4->gateway();
        m_dnsAuto = !v4->ignoreAutoDns();
        m_dnsServers = joinHosts(v4->dns());
    }
    m_ipv6Mode = 0; m_ipv6Address.clear(); m_ipv6Gateway.clear(); m_ipv6Prefix = 64;
    if (auto v6 = settingOf<Ipv6Setting>(s, Setting::Ipv6)) {
        const auto m = v6->method();
        m_ipv6Mode = m == Ipv6Setting::Manual ? 1 : (m == Ipv6Setting::Ignored || m == Ipv6Setting::ConfigDisabled) ? 2 : 0;
        if (!v6->addresses().isEmpty()) {
            m_ipv6Address = v6->addresses().first().ip().toString();
            m_ipv6Prefix = v6->addresses().first().prefixLength();
            if (!v6->addresses().first().gateway().isNull())
                m_ipv6Gateway = v6->addresses().first().gateway().toString();
        }
    }
    Q_EMIT loaded();
    Q_EMIT edited();
}

QString NetworkConnection::activePath() const
{
    for (const ActiveConnection::Ptr &ac : activeConnections()) {
        if (ac && ac->connection() && ac->connection()->path() == m_path)
            return ac->path();
    }
    return QString();
}

void NetworkConnection::refreshStatus()
{
    m_active = false;
    m_stateText = QStringLiteral("Not connected");
    m_signal = 0;
    m_speedText.clear(); m_bandText.clear(); m_bandShort.clear(); m_ipv4Now.clear(); m_gatewayNow.clear();
    m_ipv6Now.clear(); m_dnsNow.clear(); m_bssid.clear(); m_macNow.clear(); m_interfaceName.clear();
    ActiveConnection::Ptr ac;
    for (const ActiveConnection::Ptr &a : activeConnections()) {
        if (a && a->connection() && a->connection()->path() == m_path) {
            ac = a;
            break;
        }
    }
    if (ac) {
        m_active = ac->state() == ActiveConnection::Activated;
        m_stateText = m_active ? QStringLiteral("Connected")
                    : ac->state() == ActiveConnection::Activating ? QStringLiteral("Connecting") : QStringLiteral("Disconnecting");
        if (!ac->devices().isEmpty()) {
            if (Device::Ptr dev = findNetworkInterface(ac->devices().first())) {
                m_interfaceName = dev->ipInterfaceName();
                const IpConfig v4 = dev->ipV4Config();
                if (!v4.addresses().isEmpty())
                    m_ipv4Now = v4.addresses().first().ip().toString();
                m_gatewayNow = v4.gateway();
                m_dnsNow = joinHosts(v4.nameservers());
                const IpConfig v6 = dev->ipV6Config();
                for (const auto &a : v6.addresses()) {
                    if (!a.ip().isLinkLocal()) {
                        m_ipv6Now = a.ip().toString();
                        break;
                    }
                }
                if (auto wd = dev.dynamicCast<WirelessDevice>()) {
                    m_macNow = wd->hardwareAddress();
                    const int kbit = wd->bitRate();
                    m_speedText = kbit >= 1000000 ? QStringLiteral("%1 Gbit/s").arg(kbit / 1000000.0, 0, 'f', 1)
                                                  : QStringLiteral("%1 Mbit/s").arg(kbit / 1000);
                    if (AccessPoint::Ptr ap = wd->activeAccessPoint()) {
                        m_signal = ap->signalStrength();
                        m_bssid = ap->hardwareAddress();
                        const uint f = ap->frequency();
                        m_bandShort = f >= 5925 ? QStringLiteral("6 GHz") : f >= 4900 ? QStringLiteral("5 GHz") : QStringLiteral("2.4 GHz");
                        m_bandText = QStringLiteral("%1 GHz · channel %2").arg(f / 1000.0, 0, 'f', 3).arg(channelOf(f));
                    }
                }
            }
        }
    }
    Q_EMIT statusChanged();
}

void NetworkConnection::requestPassword()
{
    Connection::Ptr c = findConnection(m_path);
    if (!c) {
        Q_EMIT passwordLoaded(false);
        return;
    }
    auto *w = new QDBusPendingCallWatcher(c->secrets(kWsec), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, w] {
        QDBusPendingReply<NMVariantMapMap> r = *w;
        w->deleteLater();
        if (r.isError()) {
            Q_EMIT passwordLoaded(false);
            return;
        }
        const QVariantMap m = r.value().value(kWsec);
        m_password = m.value(QStringLiteral("psk")).toString();
        m_passwordEdited = false;
        Q_EMIT edited();
        Q_EMIT passwordLoaded(true);
    });
}

void NetworkConnection::save()
{
    Connection::Ptr c = findConnection(m_path);
    if (!c || m_busy) {
        Q_EMIT saveFinished(false, QStringLiteral("This connection no longer exists."));
        return;
    }
    setBusy(true);
    const ConnectionSettings::Ptr s = c->settings();
    const bool hasWsec = !settingOf<WirelessSecuritySetting>(s, Setting::WirelessSecurity).isNull();
    const bool has8021x = !settingOf<Setting>(s, Setting::Security8021x).isNull();
    if (!hasWsec && !has8021x) {
        doUpdate({}, {});
        return;
    }
    // Fetch what is stored first: an update without them would erase a password kept by NetworkManager itself.
    auto *w = new QDBusPendingCallWatcher(c->secrets(hasWsec ? kWsec : k8021x), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, w, hasWsec, has8021x, c] {
        QDBusPendingReply<NMVariantMapMap> r = *w;
        w->deleteLater();
        const QVariantMap first = r.isError() ? QVariantMap() : r.value().value(hasWsec ? kWsec : k8021x);
        if (hasWsec && has8021x) {
            auto *w2 = new QDBusPendingCallWatcher(c->secrets(k8021x), this);
            connect(w2, &QDBusPendingCallWatcher::finished, this, [this, w2, first] {
                QDBusPendingReply<NMVariantMapMap> r2 = *w2;
                w2->deleteLater();
                doUpdate(first, r2.isError() ? QVariantMap() : r2.value().value(k8021x));
            });
            return;
        }
        if (hasWsec)
            doUpdate(first, {});
        else
            doUpdate({}, first);
    });
}

void NetworkConnection::doUpdate(const QVariantMap &secretsWs, const QVariantMap &secrets8021x)
{
    Connection::Ptr c = findConnection(m_path);
    if (!c) {
        setBusy(false);
        Q_EMIT saveFinished(false, QStringLiteral("This connection no longer exists."));
        return;
    }
    ConnectionSettings::Ptr s = c->settings();
    s->setAutoconnect(m_autoconnect);
    if (m_allUsers) {
        s->setPermissions({});
    } else if (s->permissions().isEmpty()) {
        s->addToPermissions(QString::fromLocal8Bit(qgetenv("USER")), QString());
    }
    s->setMetered(m_metered == 1 ? ConnectionSettings::MeteredYes : m_metered == 2 ? ConnectionSettings::MeteredNo : ConnectionSettings::MeteredUnknown);

    if (auto w = settingOf<WirelessSetting>(s, Setting::Wireless)) {
        w->setBand(m_band == 1 ? WirelessSetting::Bg : m_band == 2 ? WirelessSetting::A : WirelessSetting::Automatic);
        if (m_macMode >= 0) {
            static const char *modes[] = {"", "permanent", "random", "stable"};
            w->setAssignedMacAddress(QString::fromLatin1(modes[qBound(0, m_macMode, 3)]));
        }
        w->setHidden(m_hidden);
        w->setMtu(quint32(qMax(0, m_mtu)));
    }
    if (auto ws = settingOf<WirelessSecuritySetting>(s, Setting::WirelessSecurity)) {
        if (m_securityEditable)
            ws->setKeyMgmt(m_securityKind == 1 ? WirelessSecuritySetting::SAE : WirelessSecuritySetting::WpaPsk);
    }
    if (auto v4 = settingOf<Ipv4Setting>(s, Setting::Ipv4)) {
        if (m_ipv4Manual) {
            IpAddress a;
            a.setIp(QHostAddress(m_ipv4Address.trimmed()));
            a.setPrefixLength(m_ipv4Prefix);
            if (!m_ipv4Gateway.trimmed().isEmpty())
                a.setGateway(QHostAddress(m_ipv4Gateway.trimmed()));
            v4->setMethod(Ipv4Setting::Manual);
            v4->setAddresses({a});
            v4->setGateway(m_ipv4Gateway.trimmed());
        } else if (v4->method() == Ipv4Setting::Manual) {
            v4->setMethod(Ipv4Setting::Automatic);
            v4->setAddresses({});
            v4->setGateway(QString());
        }
        v4->setIgnoreAutoDns(!m_dnsAuto);
        QList<QHostAddress> dns;
        for (const QString &part : m_dnsServers.split(QRegularExpression(QStringLiteral("[,\\s]+")), Qt::SkipEmptyParts)) {
            QHostAddress h(part);
            if (!h.isNull() && h.protocol() == QAbstractSocket::IPv4Protocol)
                dns << h;
        }
        v4->setDns(dns);
    }
    if (auto v6 = settingOf<Ipv6Setting>(s, Setting::Ipv6)) {
        const auto was = v6->method();
        if (m_ipv6Mode == 1) {
            IpAddress a;
            a.setIp(QHostAddress(m_ipv6Address.trimmed()));
            a.setPrefixLength(m_ipv6Prefix);
            if (!m_ipv6Gateway.trimmed().isEmpty())
                a.setGateway(QHostAddress(m_ipv6Gateway.trimmed()));
            v6->setMethod(Ipv6Setting::Manual);
            v6->setAddresses({a});
        } else if (m_ipv6Mode == 2) {
            if (was != Ipv6Setting::Ignored && was != Ipv6Setting::ConfigDisabled)
                v6->setMethod(Ipv6Setting::ConfigDisabled);
        } else if (was == Ipv6Setting::Manual || was == Ipv6Setting::Ignored || was == Ipv6Setting::ConfigDisabled) {
            v6->setMethod(Ipv6Setting::Automatic);
            v6->setAddresses({});
        }
    }

    NMVariantMapMap map = s->toMap();
    QVariantMap ws = map.value(kWsec);
    if (map.contains(kWsec)) {
        for (auto it = secretsWs.constBegin(); it != secretsWs.constEnd(); ++it)
            if (!ws.contains(it.key()))
                ws.insert(it.key(), it.value());
        if (m_passwordEdited)
            ws.insert(QStringLiteral("psk"), m_password);
        map.insert(kWsec, ws);
    }
    if (map.contains(k8021x)) {
        QVariantMap e = map.value(k8021x);
        for (auto it = secrets8021x.constBegin(); it != secrets8021x.constEnd(); ++it)
            if (!e.contains(it.key()))
                e.insert(it.key(), it.value());
        map.insert(k8021x, e);
    }

    auto *w = new QDBusPendingCallWatcher(c->update(map), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, w] {
        QDBusPendingReply<> r = *w;
        w->deleteLater();
        setBusy(false);
        if (r.isError()) {
            Q_EMIT saveFinished(false, r.error().message());
            return;
        }
        reload();
        Q_EMIT saveFinished(true, QString());
    });
}

void NetworkConnection::connectNow(const QString &devicePath)
{
    activateConnection(m_path, devicePath, QString());
}

void NetworkConnection::disconnectNow()
{
    const QString ap = activePath();
    if (!ap.isEmpty())
        deactivateConnection(ap);
}

void NetworkConnection::forget()
{
    Connection::Ptr c = findConnection(m_path);
    if (!c)
        return;
    auto *w = new QDBusPendingCallWatcher(c->remove(), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, w] {
        QDBusPendingReply<> r = *w;
        w->deleteLater();
        if (!r.isError())
            Q_EMIT forgotten();
    });
}
