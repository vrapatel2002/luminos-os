' dumbtv home for Roku. [CHANGE: claude-code | 2026-10-27]
' Apps and icons come from the TV's own ECP (/query/apps, /query/icon/<id>);
' opening an app or input is ECP /launch/<id>. No account, no analytics, no other network.

sub init()
    m.COLS = 3
    m.TW = 520
    m.TH = 180
    m.GAP = 40
    m.accents = [
        { n: "Blue", c: "0x4FA3FFFF" }, { n: "White", c: "0xFFFFFFFF" }, { n: "Cyan", c: "0x3FD0E0FF" },
        { n: "Green", c: "0x3CCF8EFF" }, { n: "Amber", c: "0xF2A33AFF" }, { n: "Red", c: "0xF05454FF" },
        { n: "Pink", c: "0xF07AB8FF" }, { n: "Violet", c: "0xC58CFFFF" }
    ]
    ' Afterglow colours for known apps, by Roku channel id (values from dumbtv's BrandColors where they exist).
    m.brands = {
        "12": "0x85050CFF", "837": "0x94001EFF", "13": "0x006182FF",
        "819325": "0x4B2A7AFF", "592369": "0x3A2E6EFF", "151908": "0x4A1F7AFF",
        "tvinput.dtv": "0x24302AFF"
    }

    m.clock = m.top.findNode("clock")
    m.date = m.top.findNode("date")
    m.grid = m.top.findNode("grid")
    m.inputs = m.top.findNode("inputs")
    m.inputsHeader = m.top.findNode("inputsHeader")
    m.status = m.top.findNode("status")
    m.toastBox = m.top.findNode("toastBox")
    m.toastBg = m.top.findNode("toastBg")
    m.toast = m.top.findNode("toast")
    m.menu = m.top.findNode("menu")
    m.menuTitle = m.top.findNode("menuTitle")
    m.menuItems = m.top.findNode("menuItems")

    m.cfg = loadCfg()
    m.base = ""
    m.allApps = []
    m.allInputs = []
    m.tiles = []
    m.pills = []
    m.row = 0
    m.idx = 0
    m.menuOpen = false
    m.showHidden = false

    m.clockTimer = m.top.findNode("clockTimer")
    m.clockTimer.observeField("fire", "updateClock")
    m.clockTimer.control = "start"
    m.toastTimer = m.top.findNode("toastTimer")
    m.toastTimer.observeField("fire", "hideToast")
    updateClock()

    m.top.setFocus(true)
    m.status.text = "Loading your apps…"
    loadApps()
end sub

' ---------- settings (kept on the TV in the registry) ----------
function loadCfg() as Object
    cfg = { order: [], hidden: ["151908"], accent: 0, style: "original", showInputs: true }
    sec = CreateObject("roRegistrySection", "dumbtv")
    if sec.Exists("cfg")
        saved = ParseJson(sec.Read("cfg"))
        if saved <> invalid
            for each k in saved
                cfg[k] = saved[k]
            end for
        end if
    end if
    return cfg
end function

sub saveCfg()
    sec = CreateObject("roRegistrySection", "dumbtv")
    sec.Write("cfg", FormatJson(m.cfg))
    sec.Flush()
end sub

function accentColor() as String
    i = m.cfg.accent
    if i < 0 or i >= m.accents.Count() then i = 0
    return m.accents[i].c
end function

function isHidden(id as String) as Boolean
    for each h in m.cfg.hidden
        if h = id then return true
    end for
    return false
end function

' ---------- clock ----------
sub updateClock()
    dt = CreateObject("roDateTime")
    dt.ToLocalTime()
    hh = dt.GetHours()
    mm = dt.GetMinutes()
    ap = "AM"
    if hh >= 12 then ap = "PM"
    h12 = hh mod 12
    if h12 = 0 then h12 = 12
    mins = mm.ToStr()
    if mm < 10 then mins = "0" + mins
    m.clock.text = h12.ToStr() + ":" + mins + " " + ap
    m.date.text = dt.AsDateString("long-date")
end sub

' ---------- apps ----------
sub loadApps()
    m.appsTask = CreateObject("roSGNode", "EcpTask")
    m.appsTask.command = "apps"
    m.appsTask.observeField("result", "onApps")
    m.appsTask.control = "RUN"
end sub

sub onApps()
    r = m.appsTask.result
    m.base = r.base
    m.iconsOk = true
    rawApps = r.apps
    if rawApps = invalid or rawApps.Count() = 0
        ' Roku OS 15 answers 403 to ECP queries from apps on the TV itself.
        ' Fall back to a built-in list, checked natively with roAppManager.IsAppInstalled.
        if r.tried <> invalid
            for each t in r.tried
                print "dumbtv apps fallback, ecp said: "; t
            end for
        end if
        rawApps = builtinApps()
        m.iconsOk = false
    end if
    m.status.text = ""
    apps = []
    inputs = []
    for each a in rawApps
        if a.type = "appl" and a.id <> "dev"
            apps.Push(a)
        else if a.type = "tvin"
            if a.id = "tvinput.dtv" then apps.Push(a) else inputs.Push(a)
        end if
    end for
    m.allApps = orderApps(apps)
    m.allInputs = inputs
    build()
end sub

function builtinApps() as Object
    am = CreateObject("roAppManager")
    known = [
        { id: "819325", name: "JellyRock" }, { id: "837", name: "YouTube" }, { id: "12", name: "Netflix" },
        { id: "13", name: "Prime Video" }, { id: "592369", name: "Jellyfin" }, { id: "151908", name: "The Roku Channel" },
        { id: "2285", name: "Hulu" }, { id: "291097", name: "Disney+" }, { id: "61322", name: "Max" },
        { id: "74519", name: "Plex" }, { id: "2213", name: "Roku Media Player" }
    ]
    out = []
    for each k in known
        if am.IsAppInstalled(k.id, "")
            out.Push({ id: k.id, type: "appl", name: k.name })
        end if
    end for
    out.Push({ id: "tvinput.dtv", type: "tvin", name: "Live TV" })
    out.Push({ id: "tvinput.hdmi1", type: "tvin", name: "HDMI 1" })
    out.Push({ id: "tvinput.hdmi2", type: "tvin", name: "HDMI 2" })
    out.Push({ id: "tvinput.hdmi3", type: "tvin", name: "HDMI 3" })
    out.Push({ id: "tvinput.hdmi4", type: "tvin", name: "HDMI 4" })
    out.Push({ id: "tvinput.cvbs", type: "tvin", name: "AV" })
    return out
end function

function orderApps(apps as Object) as Object
    order = m.cfg.order
    if order = invalid or order.Count() = 0
        order = ["819325", "837", "12", "13", "592369", "tvinput.dtv"]
    end if
    byId = {}
    for each a in apps
        byId[a.id] = a
    end for
    out = []
    used = {}
    for each id in order
        if byId.DoesExist(id) and not used.DoesExist(id)
            out.Push(byId[id])
            used[id] = true
        end if
    end for
    for each a in apps
        if not used.DoesExist(a.id)
            out.Push(a)
            used[a.id] = true
        end if
    end for
    ids = []
    for each a in out
        ids.Push(a.id)
    end for
    m.cfg.order = ids
    return out
end function

function visibleApps() as Object
    out = []
    for each a in m.allApps
        if m.showHidden or not isHidden(a.id) then out.Push(a)
    end for
    return out
end function

sub clearGroup(g as Object)
    n = g.getChildCount()
    if n > 0 then g.removeChildrenIndex(n, 0)
end sub

sub build()
    clearGroup(m.grid)
    clearGroup(m.inputs)
    m.tiles = []
    m.pills = []
    accent = accentColor()
    apps = visibleApps()
    i = 0
    for each a in apps
        t = m.grid.createChild("Tile")
        t.kind = "app"
        t.appId = a.id
        if m.iconsOk then t.styleName = m.cfg.style else t.styleName = "afterglow"
        t.accent = accent
        if m.brands.DoesExist(a.id) then t.brand = m.brands[a.id]
        if m.iconsOk then t.iconUri = m.base + "/query/icon/" + a.id
        t.isHidden = isHidden(a.id)
        t.w = m.TW
        t.h = m.TH
        t.name = a.name
        t.translation = [(i mod m.COLS) * (m.TW + m.GAP), (i \ m.COLS) * (m.TH + m.GAP + 30)]
        m.tiles.Push(t)
        i = i + 1
    end for
    rows = (apps.Count() + m.COLS - 1) \ m.COLS
    if rows < 1 then rows = 1
    bottom = 316 + rows * (m.TH + m.GAP + 30)
    m.inputsHeader.translation = [140, bottom + 20]
    m.inputs.translation = [140, bottom + 74]
    m.inputsHeader.visible = m.cfg.showInputs
    m.inputs.visible = m.cfg.showInputs
    x = 0
    if m.cfg.showInputs
        for each a in m.allInputs
            p = m.inputs.createChild("Tile")
            p.kind = "pill"
            p.appId = a.id
            p.accent = accent
            p.w = 250
            p.h = 84
            p.name = a.name
            p.translation = [x, 0]
            m.pills.Push(p)
            x = x + 250 + 28
        end for
    end if
    clampFocus()
    applyFocus()
end sub

' ---------- focus ----------
function currentList() as Object
    if m.row = 1 then return m.pills
    return m.tiles
end function

sub clampFocus()
    if m.row = 1 and m.pills.Count() = 0 then m.row = 0
    if m.row = 0 and m.tiles.Count() = 0 and m.pills.Count() > 0 then m.row = 1
    lst = currentList()
    if m.idx >= lst.Count() then m.idx = lst.Count() - 1
    if m.idx < 0 then m.idx = 0
end sub

sub applyFocus()
    for i = 0 to m.tiles.Count() - 1
        m.tiles[i].isFocused = (m.row = 0 and i = m.idx)
    end for
    for i = 0 to m.pills.Count() - 1
        m.pills[i].isFocused = (m.row = 1 and i = m.idx)
    end for
end sub

function focusedItem() as Object
    lst = currentList()
    if m.idx >= 0 and m.idx < lst.Count() then return lst[m.idx]
    return invalid
end function

sub moveFocus(key as String)
    n = m.tiles.Count()
    if m.row = 0
        col = m.idx mod m.COLS
        if key = "left" and col > 0 then m.idx = m.idx - 1
        if key = "right" and col < m.COLS - 1 and m.idx + 1 < n then m.idx = m.idx + 1
        if key = "up" and m.idx - m.COLS >= 0 then m.idx = m.idx - m.COLS
        if key = "down"
            if m.idx + m.COLS < n
                m.idx = m.idx + m.COLS
            else if m.idx \ m.COLS < (n - 1) \ m.COLS
                m.idx = n - 1
            else if m.pills.Count() > 0
                m.row = 1
                m.idx = col
            end if
        end if
    else
        if key = "left" and m.idx > 0 then m.idx = m.idx - 1
        if key = "right" and m.idx + 1 < m.pills.Count() then m.idx = m.idx + 1
        if key = "up" and n > 0
            m.row = 0
            lastRow = (n - 1) \ m.COLS
            m.idx = lastRow * m.COLS
            if m.idx >= n then m.idx = n - 1
        end if
    end if
    clampFocus()
    applyFocus()
end sub

' ---------- open ----------
sub activate()
    t = focusedItem()
    if t = invalid then return
    if m.row = 1
        showToast("Switching to " + t.name + "…")
    else
        showToast("Opening " + t.name + "…")
    end if
    m.launchTask = CreateObject("roSGNode", "EcpTask")
    m.launchTask.command = "launch"
    m.launchTask.arg = t.appId
    m.launchTask.observeField("result", "onLaunched")
    m.launchTask.control = "RUN"
end sub

sub onLaunched()
    r = m.launchTask.result
    if r <> invalid and r.code <> invalid and r.code <> 200
        detail = ""
        if r.tried <> invalid and r.tried.Count() > 0 then detail = r.tried[0]
        showToast("The TV refused to open it: " + detail)
    end if
end sub

sub showToast(text as String)
    m.toast.text = text
    w = Len(text) * 17 + 80
    if w > 1600 then w = 1600
    m.toastBg.width = w
    m.toastBg.height = 80
    m.toast.width = w
    m.toast.height = 80
    m.toastBox.translation = [(1920 - w) / 2, 940]
    m.toastBox.visible = true
    m.toastTimer.control = "stop"
    m.toastTimer.duration = 2.5
    m.toastTimer.control = "start"
end sub

sub hideToast()
    m.toastBox.visible = false
end sub

' ---------- options menu (★) ----------
sub openMenu()
    m.menuOpen = true
    m.menuSel = 0
    renderMenu()
    m.menu.visible = true
end sub

sub closeMenu()
    m.menuOpen = false
    m.menu.visible = false
end sub

function menuEntries() as Object
    e = []
    t = focusedItem()
    if m.row = 0 and t <> invalid
        e.Push({ id: "left", label: "Move left" })
        e.Push({ id: "right", label: "Move right" })
        if isHidden(t.appId)
            e.Push({ id: "hide", label: "Show this app" })
        else
            e.Push({ id: "hide", label: "Hide this app" })
        end if
    end if
    e.Push({ id: "accent", label: "Accent: " + m.accents[m.cfg.accent].n })
    styleName = "Original"
    if m.cfg.style = "afterglow" then styleName = "Afterglow"
    e.Push({ id: "style", label: "Tile style: " + styleName })
    inputsLabel = "hidden"
    if m.cfg.showInputs then inputsLabel = "shown"
    e.Push({ id: "inputs", label: "Inputs row: " + inputsLabel })
    hiddenLabel = "off"
    if m.showHidden then hiddenLabel = "on"
    e.Push({ id: "showHidden", label: "Show hidden apps: " + hiddenLabel })
    e.Push({ id: "reset", label: "Reset order and hidden apps" })
    e.Push({ id: "close", label: "Close" })
    return e
end function

sub renderMenu()
    t = focusedItem()
    if m.row = 0 and t <> invalid
        m.menuTitle.text = t.name
    else
        m.menuTitle.text = "Options"
    end if
    clearGroup(m.menuItems)
    m.entries = menuEntries()
    if m.menuSel >= m.entries.Count() then m.menuSel = m.entries.Count() - 1
    accent = accentColor()
    y = 0
    for i = 0 to m.entries.Count() - 1
        l = m.menuItems.createChild("Label")
        f = CreateObject("roSGNode", "Font")
        f.uri = "font:SystemFontFile"
        f.size = 32
        l.font = f
        l.translation = [0, y]
        if i = m.menuSel
            l.text = "›  " + m.entries[i].label
            l.color = accent
        else
            l.text = "    " + m.entries[i].label
            l.color = "0xEEF1F5FF"
        end if
        y = y + 64
    end for
end sub

sub moveApp(delta as Integer)
    t = focusedItem()
    if t = invalid then return
    fromIdx = -1
    for i = 0 to m.allApps.Count() - 1
        if m.allApps[i].id = t.appId then fromIdx = i
    end for
    target = fromIdx + delta
    ' skip over apps that are hidden from view
    while target >= 0 and target < m.allApps.Count() and not m.showHidden and isHidden(m.allApps[target].id)
        target = target + delta
    end while
    if fromIdx < 0 or target < 0 or target >= m.allApps.Count() then return
    tmp = m.allApps[fromIdx]
    m.allApps[fromIdx] = m.allApps[target]
    m.allApps[target] = tmp
    ids = []
    for each a in m.allApps
        ids.Push(a.id)
    end for
    m.cfg.order = ids
    saveCfg()
    build()
    ' keep focus on the moved tile
    for i = 0 to m.tiles.Count() - 1
        if m.tiles[i].appId = tmp.id then m.idx = i
    end for
    applyFocus()
end sub

sub menuAct(id as String, dir as Integer)
    if id = "left"
        moveApp(-1)
    else if id = "right"
        moveApp(1)
    else if id = "hide"
        t = focusedItem()
        if t = invalid then return
        if isHidden(t.appId)
            keep = []
            for each h in m.cfg.hidden
                if h <> t.appId then keep.Push(h)
            end for
            m.cfg.hidden = keep
        else
            m.cfg.hidden.Push(t.appId)
        end if
        saveCfg()
        build()
        closeMenu()
        return
    else if id = "accent"
        n = m.accents.Count()
        m.cfg.accent = (m.cfg.accent + dir + n) mod n
        saveCfg()
        build()
    else if id = "style"
        if m.cfg.style = "afterglow" then m.cfg.style = "original" else m.cfg.style = "afterglow"
        saveCfg()
        build()
    else if id = "inputs"
        m.cfg.showInputs = not m.cfg.showInputs
        saveCfg()
        build()
    else if id = "showHidden"
        m.showHidden = not m.showHidden
        build()
    else if id = "reset"
        m.cfg.order = []
        m.cfg.hidden = ["151908"]
        saveCfg()
        m.allApps = orderApps(m.allApps)
        saveCfg()
        build()
    else if id = "close"
        closeMenu()
        return
    end if
    renderMenu()
end sub

function menuKey(key as String) as Boolean
    if key = "back" or key = "options"
        closeMenu()
    else if key = "up"
        if m.menuSel > 0 then m.menuSel = m.menuSel - 1
        renderMenu()
    else if key = "down"
        if m.menuSel < m.entries.Count() - 1 then m.menuSel = m.menuSel + 1
        renderMenu()
    else if key = "OK" or key = "right"
        menuAct(m.entries[m.menuSel].id, 1)
    else if key = "left"
        id = m.entries[m.menuSel].id
        if id = "accent" then menuAct(id, -1)
        if id = "style" or id = "inputs" or id = "showHidden" then menuAct(id, -1)
    end if
    return true
end function

' ---------- remote ----------
function onKeyEvent(key as String, press as Boolean) as Boolean
    if not press then return false
    if m.menuOpen then return menuKey(key)
    if key = "left" or key = "right" or key = "up" or key = "down"
        moveFocus(key)
        return true
    else if key = "OK"
        activate()
        return true
    else if key = "options"
        openMenu()
        return true
    else if key = "back"
        ' like dumbtv: Back jumps to the first tile instead of leaving
        m.row = 0
        m.idx = 0
        clampFocus()
        applyFocus()
        return true
    end if
    return false
end function
