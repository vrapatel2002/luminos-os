// [CHANGE: claude-code | 2026-11-09] DECISION 182 — Luminos Files look values.
// Reads ~/.config/luminos/style.json (the same file the Style Tuner writes) and calls back when it
// changes, so QtWidgets code (Dolphin, the KIO places panel) can follow the tuner live.
// Every value has a built-in default equal to the approved prototype, so a missing file or key
// changes nothing. Header-only: each library that includes it keeps its own copy.
#pragma once

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileSystemWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QStandardPaths>
#include <QTimer>

#include <functional>
#include <vector>

namespace LuminosFiles
{
class Style
{
public:
    static Style &self()
    {
        static Style s;
        return s;
    }

    // number from style.json, clamped; default when missing / not a number
    double num(const char *key, double def, double lo, double hi) const
    {
        const QJsonValue v = m_obj.value(QLatin1String(key));
        if (v.isDouble()) {
            return qBound(lo, v.toDouble(), hi);
        }
        if (v.isBool()) {
            return v.toBool() ? qMin(hi, 1.0) : qMax(lo, 0.0);
        }
        return def;
    }
    int px(const char *key, int def, int lo, int hi) const
    {
        return qRound(num(key, def, lo, hi));
    }
    bool flag(const char *key, bool def) const
    {
        const QJsonValue v = m_obj.value(QLatin1String(key));
        if (v.isBool()) {
            return v.toBool();
        }
        if (v.isDouble()) {
            return v.toDouble() != 0;
        }
        return def;
    }

    // run f whenever style.json changes, for as long as ctx lives
    void onChange(QObject *ctx, std::function<void()> f)
    {
        m_callbacks.push_back({QPointer<QObject>(ctx), std::move(f)});
    }

private:
    Style()
    {
        load();
        if (!QCoreApplication::instance()) {
            return;
        }
        m_watcher = new QFileSystemWatcher(QCoreApplication::instance());
        m_debounce = new QTimer(m_watcher);
        m_debounce->setSingleShot(true);
        m_debounce->setInterval(60);
        QObject::connect(m_debounce, &QTimer::timeout, m_watcher, [this] {
            load();
            rewatch();
            for (auto &c : m_callbacks) {
                if (c.ctx) {
                    c.f();
                }
            }
        });
        QObject::connect(m_watcher, &QFileSystemWatcher::fileChanged, m_debounce, qOverload<>(&QTimer::start));
        QObject::connect(m_watcher, &QFileSystemWatcher::directoryChanged, m_debounce, qOverload<>(&QTimer::start));
        rewatch();
    }
    static QString dir()
    {
        return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/luminos");
    }
    static QString path()
    {
        return dir() + QStringLiteral("/style.json");
    }
    void load()
    {
        QFile f(path());
        if (!f.open(QIODevice::ReadOnly)) {
            m_obj = QJsonObject(); // no file = all defaults
            return;
        }
        QJsonParseError err;
        const QJsonDocument doc = QJsonDocument::fromJson(f.readAll(), &err);
        if (err.error == QJsonParseError::NoError && doc.isObject()) {
            m_obj = doc.object(); // [R24] half-written / broken file: keep the last good values
        }
    }
    void rewatch()
    {
        if (!m_watcher) {
            return;
        }
        if (QFile::exists(path()) && !m_watcher->files().contains(path())) {
            m_watcher->addPath(path()); // editors replace the file, so re-add every time
        }
        if (QDir(dir()).exists() && !m_watcher->directories().contains(dir())) {
            m_watcher->addPath(dir());
        }
    }

    struct Callback {
        QPointer<QObject> ctx;
        std::function<void()> f;
    };
    QJsonObject m_obj;
    QFileSystemWatcher *m_watcher = nullptr;
    QTimer *m_debounce = nullptr;
    std::vector<Callback> m_callbacks;
};
}
