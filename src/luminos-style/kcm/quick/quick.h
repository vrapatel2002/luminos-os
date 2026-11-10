// [CHANGE: claude-code | 2026-11-10] R25 — Luminos Quick Settings page (docs/windowstyle/mock/system-settings-nexus.html).
// Every control saves the moment it changes (no Apply), into the same KDE keys the stock landing page uses:
// kdeglobals [KDE] AnimationDurationFactor / SingleClick, and the colour scheme via plasma-apply-colorscheme.
#pragma once
#include <KQuickConfigModule>
#include <QUrl>

class Quick : public KQuickConfigModule
{
    Q_OBJECT
    Q_PROPERTY(bool dark READ dark NOTIFY changed)
    Q_PROPERTY(int animStep READ animStep WRITE setAnimStep NOTIFY changed)
    Q_PROPERTY(int animSteps READ animSteps CONSTANT)
    Q_PROPERTY(bool singleClick READ singleClick WRITE setSingleClick NOTIFY changed)
    Q_PROPERTY(QUrl wallpaper READ wallpaper NOTIFY changed)
    Q_PROPERTY(QString wallpaperName READ wallpaperName NOTIFY changed)
    Q_PROPERTY(QString schemeName READ schemeName NOTIFY changed)

public:
    Quick(QObject *parent, const KPluginMetaData &data);
    void load() override;

    bool dark() const { return m_dark; }
    int animStep() const { return m_animStep; }
    int animSteps() const;
    void setAnimStep(int step);
    bool singleClick() const { return m_singleClick; }
    void setSingleClick(bool on);
    QUrl wallpaper() const { return m_wallpaper; }
    QString wallpaperName() const { return m_wallpaperName; }
    QString schemeName() const { return m_scheme; }

    Q_INVOKABLE void setDark(bool dark);
    Q_INVOKABLE void openWallpaper();
    Q_INVOKABLE void openModule(const QString &id);
    Q_INVOKABLE void openTuner();

Q_SIGNALS:
    void changed();

private:
    void readWallpaper();
    bool m_dark = true;
    int m_animStep = 3;
    bool m_singleClick = true;
    QUrl m_wallpaper;
    QString m_wallpaperName, m_scheme;
    bool m_makingStill = false;
};
