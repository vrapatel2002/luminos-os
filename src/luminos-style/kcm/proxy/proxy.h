// [CHANGE: claude-code | 2026-11-08] DECISION 179 — Luminos Proxy page (replaces kio-extras kcm_proxy in System Settings).
// Reads and writes exactly the keys kio-extras uses (kioslaverc [Proxy Settings]), so every KDE app and Chrome keep
// obeying it; after Apply it sends the same "reparse" signal to running KIO workers.
#pragma once
#include <KQuickConfigModule>

class Proxy : public KQuickConfigModule
{
    Q_OBJECT
    // 0 off, 1 find automatically (WPAD), 2 setup script (PAC), 3 manual, 4 environment variables
    Q_PROPERTY(int mode READ mode WRITE setMode NOTIFY changed)
    Q_PROPERTY(QString pacUrl READ pacUrl WRITE setPacUrl NOTIFY changed)
    Q_PROPERTY(bool sameForAll READ sameForAll WRITE setSameForAll NOTIFY changed)
    Q_PROPERTY(QString httpHost READ httpHost WRITE setHttpHost NOTIFY changed)
    Q_PROPERTY(int httpPort READ httpPort WRITE setHttpPort NOTIFY changed)
    Q_PROPERTY(QString httpsHost READ httpsHost WRITE setHttpsHost NOTIFY changed)
    Q_PROPERTY(int httpsPort READ httpsPort WRITE setHttpsPort NOTIFY changed)
    Q_PROPERTY(QString ftpHost READ ftpHost WRITE setFtpHost NOTIFY changed)
    Q_PROPERTY(int ftpPort READ ftpPort WRITE setFtpPort NOTIFY changed)
    Q_PROPERTY(QString socksHost READ socksHost WRITE setSocksHost NOTIFY changed)
    Q_PROPERTY(int socksPort READ socksPort WRITE setSocksPort NOTIFY changed)
    Q_PROPERTY(QString noProxyFor READ noProxyFor WRITE setNoProxyFor NOTIFY changed)
    Q_PROPERTY(bool onlyForList READ onlyForList WRITE setOnlyForList NOTIFY changed)
    Q_PROPERTY(QString envSummary READ envSummary NOTIFY changed)

public:
    Proxy(QObject *parent, const KPluginMetaData &data);

    void load() override;
    void save() override;
    void defaults() override;

#define LX_RW(type, name, setter) \
    type name() const { return m_##name; } \
    void setter(const type &v) { if (m_##name == v) return; m_##name = v; Q_EMIT changed(); setNeedsSave(true); }
    LX_RW(int, mode, setMode)
    LX_RW(QString, pacUrl, setPacUrl)
    LX_RW(bool, sameForAll, setSameForAll)
    LX_RW(QString, httpHost, setHttpHost)
    LX_RW(int, httpPort, setHttpPort)
    LX_RW(QString, httpsHost, setHttpsHost)
    LX_RW(int, httpsPort, setHttpsPort)
    LX_RW(QString, ftpHost, setFtpHost)
    LX_RW(int, ftpPort, setFtpPort)
    LX_RW(QString, socksHost, setSocksHost)
    LX_RW(int, socksPort, setSocksPort)
    LX_RW(QString, noProxyFor, setNoProxyFor)
    LX_RW(bool, onlyForList, setOnlyForList)
#undef LX_RW
    QString envSummary() const;

Q_SIGNALS:
    void changed();

private:
    int m_mode = 0;
    QString m_pacUrl;
    bool m_sameForAll = true;
    QString m_httpHost, m_httpsHost, m_ftpHost, m_socksHost;
    int m_httpPort = 0, m_httpsPort = 0, m_ftpPort = 0, m_socksPort = 0;
    QString m_noProxyFor;
    bool m_onlyForList = false;
    // environment-variable mode keeps the variable NAMES kio-extras stored; we never rewrite them
    QString m_envHttp, m_envHttps, m_envFtp, m_envSocks, m_envNoProxy;
};
