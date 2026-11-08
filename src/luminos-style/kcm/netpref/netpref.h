// [CHANGE: claude-code | 2026-11-08] DECISION 179 — Luminos Connection Preferences page (replaces kio-extras kcm_netpref).
// Same three keys kio-extras writes: kioslaverc MarkPartial, kio_ftprc DisablePassiveMode + MarkPartial.
#pragma once
#include <KQuickConfigModule>

class NetPref : public KQuickConfigModule
{
    Q_OBJECT
    Q_PROPERTY(bool markPartial READ markPartial WRITE setMarkPartial NOTIFY changed)
    Q_PROPERTY(bool ftpPassive READ ftpPassive WRITE setFtpPassive NOTIFY changed)
    Q_PROPERTY(bool ftpMarkPartial READ ftpMarkPartial WRITE setFtpMarkPartial NOTIFY changed)
public:
    NetPref(QObject *parent, const KPluginMetaData &data);
    void load() override;
    void save() override;
    void defaults() override;
    bool markPartial() const { return m_markPartial; }
    bool ftpPassive() const { return m_ftpPassive; }
    bool ftpMarkPartial() const { return m_ftpMarkPartial; }
    void setMarkPartial(bool v) { if (v != m_markPartial) { m_markPartial = v; Q_EMIT changed(); setNeedsSave(true); } }
    void setFtpPassive(bool v) { if (v != m_ftpPassive) { m_ftpPassive = v; Q_EMIT changed(); setNeedsSave(true); } }
    void setFtpMarkPartial(bool v) { if (v != m_ftpMarkPartial) { m_ftpMarkPartial = v; Q_EMIT changed(); setNeedsSave(true); } }
Q_SIGNALS:
    void changed();
private:
    bool m_markPartial = true, m_ftpPassive = true, m_ftpMarkPartial = true;
};
