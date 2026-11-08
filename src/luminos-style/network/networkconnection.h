// [CHANGE: claude-code | 2026-11-08] DECISION 178 — Luminos Wi-Fi page helper (org.luminos.network).
// One saved NetworkManager connection, exposed to QML as plain properties: live status (signal, speed, band, IP...)
// and the settings the new Wi-Fi details page edits. Nothing is written until save(); save() merges the stored
// secrets back in first, because NetworkManager replaces the whole profile on update and would otherwise drop a
// system-stored Wi-Fi password. Separate plugin from org.luminos.style so ordinary apps never load NetworkManagerQt.
#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QString>
#include <QStringList>

class NetworkConnection : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString path READ path WRITE setPath NOTIFY pathChanged)
    // read-only: identity + live status
    Q_PROPERTY(bool valid READ valid NOTIFY loaded)
    Q_PROPERTY(QString name READ name NOTIFY loaded)
    Q_PROPERTY(QString kind READ kind NOTIFY loaded) // "wifi" | "ethernet" | "vpn" | "other"
    Q_PROPERTY(QString securityText READ securityText NOTIFY loaded)
    Q_PROPERTY(bool securityEditable READ securityEditable NOTIFY loaded) // WPA2/WPA3 Personal only
    Q_PROPERTY(bool active READ active NOTIFY statusChanged)
    Q_PROPERTY(QString stateText READ stateText NOTIFY statusChanged)
    Q_PROPERTY(int signal READ signal NOTIFY statusChanged)
    Q_PROPERTY(QString speedText READ speedText NOTIFY statusChanged)
    Q_PROPERTY(QString bandText READ bandText NOTIFY statusChanged)
    Q_PROPERTY(QString bandShort READ bandShort NOTIFY statusChanged)
    Q_PROPERTY(QString ipv4Now READ ipv4Now NOTIFY statusChanged)
    Q_PROPERTY(QString gatewayNow READ gatewayNow NOTIFY statusChanged)
    Q_PROPERTY(QString ipv6Now READ ipv6Now NOTIFY statusChanged)
    Q_PROPERTY(QString dnsNow READ dnsNow NOTIFY statusChanged)
    Q_PROPERTY(QString bssid READ bssid NOTIFY statusChanged)
    Q_PROPERTY(QString macNow READ macNow NOTIFY statusChanged)
    Q_PROPERTY(QString interfaceName READ interfaceName NOTIFY statusChanged)
    // editable
    Q_PROPERTY(bool autoconnect MEMBER m_autoconnect NOTIFY edited)
    Q_PROPERTY(bool allUsers MEMBER m_allUsers NOTIFY edited)
    Q_PROPERTY(int metered MEMBER m_metered NOTIFY edited)        // 0 automatic, 1 yes, 2 no
    Q_PROPERTY(int securityKind MEMBER m_securityKind NOTIFY edited) // 0 WPA2 Personal, 1 WPA3 Personal
    Q_PROPERTY(QString password MEMBER m_password NOTIFY edited)
    Q_PROPERTY(bool passwordEdited MEMBER m_passwordEdited NOTIFY edited)
    Q_PROPERTY(bool ipv4Manual MEMBER m_ipv4Manual NOTIFY edited)
    Q_PROPERTY(QStringList ipv4Addresses MEMBER m_ipv4Addresses NOTIFY edited) // R12: several, "192.168.2.50/24"
    Q_PROPERTY(QString ipv4Gateway MEMBER m_ipv4Gateway NOTIFY edited)
    Q_PROPERTY(bool dnsAuto MEMBER m_dnsAuto NOTIFY edited)
    Q_PROPERTY(QString dnsServers MEMBER m_dnsServers NOTIFY edited) // "1.1.1.1, 9.9.9.9"
    Q_PROPERTY(int ipv6Mode MEMBER m_ipv6Mode NOTIFY edited)      // 0 automatic, 1 manual, 2 off
    Q_PROPERTY(QStringList ipv6Addresses MEMBER m_ipv6Addresses NOTIFY edited) // R12: several, "fd00::5/64"
    Q_PROPERTY(QString ipv6Gateway MEMBER m_ipv6Gateway NOTIFY edited)
    Q_PROPERTY(int band MEMBER m_band NOTIFY edited)              // 0 automatic, 1 2.4 GHz, 2 5 GHz
    Q_PROPERTY(int macMode MEMBER m_macMode NOTIFY edited)        // 0 default, 1 laptop's own, 2 random, 3 stable random
    Q_PROPERTY(bool hidden MEMBER m_hidden NOTIFY edited)
    Q_PROPERTY(int mtu MEMBER m_mtu NOTIFY edited)                // 0 = automatic
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)

public:
    explicit NetworkConnection(QObject *parent = nullptr);

    QString path() const { return m_path; }
    void setPath(const QString &p);
    bool valid() const { return m_valid; }
    QString name() const { return m_name; }
    QString kind() const { return m_kind; }
    QString securityText() const { return m_securityText; }
    bool securityEditable() const { return m_securityEditable; }
    bool active() const { return m_active; }
    QString stateText() const { return m_stateText; }
    int signal() const { return m_signal; }
    QString speedText() const { return m_speedText; }
    QString bandText() const { return m_bandText; }
    QString bandShort() const { return m_bandShort; }
    QString ipv4Now() const { return m_ipv4Now; }
    QString gatewayNow() const { return m_gatewayNow; }
    QString ipv6Now() const { return m_ipv6Now; }
    QString dnsNow() const { return m_dnsNow; }
    QString bssid() const { return m_bssid; }
    QString macNow() const { return m_macNow; }
    QString interfaceName() const { return m_interfaceName; }
    bool busy() const { return m_busy; }

    Q_INVOKABLE void reload();          // re-read the profile, dropping unsaved edits
    Q_INVOKABLE void refreshStatus();   // live numbers; QML calls it on a timer while the page is visible
    Q_INVOKABLE void save();
    Q_INVOKABLE void requestPassword(); // fills `password` from the stored secrets (may ask the wallet)
    Q_INVOKABLE void connectNow(const QString &devicePath);
    Q_INVOKABLE void disconnectNow();
    Q_INVOKABLE void forget();
    // R12: create + join a hidden network (security 0 none, 1 WPA2 Personal, 2 WPA3 Personal); result in joinFinished
    Q_INVOKABLE void joinHidden(const QString &ssid, int security, const QString &password, const QString &devicePath);
    // test aid (like LUMINOS_SS_OPEN_DRAWER): LUMINOS_NM_OPEN=<connection path> opens that details page at start-up
    Q_INVOKABLE QString testOpenPath() const { return qEnvironmentVariable("LUMINOS_NM_OPEN"); }

Q_SIGNALS:
    void pathChanged();
    void loaded();
    void statusChanged();
    void edited();
    void busyChanged();
    void saveFinished(bool ok, const QString &message);
    void passwordLoaded(bool ok);
    void forgotten();
    void joinFinished(bool ok, const QString &message);

private:
    void setBusy(bool b);
    QString activePath() const;
    void doUpdate(const QVariantMap &secretsWs, const QVariantMap &secrets8021x);

    QString m_path;
    bool m_valid = false;
    QString m_name, m_kind, m_securityText;
    bool m_securityEditable = false;
    bool m_active = false;
    QString m_stateText;
    int m_signal = 0;
    QString m_speedText, m_bandText, m_bandShort, m_ipv4Now, m_gatewayNow, m_ipv6Now, m_dnsNow, m_bssid, m_macNow, m_interfaceName;
    bool m_busy = false;

    bool m_autoconnect = true, m_allUsers = true;
    int m_metered = 0, m_securityKind = 0;
    QString m_password;
    bool m_passwordEdited = false;
    bool m_ipv4Manual = false;
    QStringList m_ipv4Addresses;
    QString m_ipv4Gateway;
    bool m_dnsAuto = true;
    QString m_dnsServers;
    int m_ipv6Mode = 0;
    QStringList m_ipv6Addresses;
    QString m_ipv6Gateway;
    int m_band = 0, m_macMode = 0;
    bool m_hidden = false;
    int m_mtu = 0;
};
