' [CHANGE: claude-code | 2026-10-27]
sub init()
    m.ring = m.top.findNode("ring")
    m.bg = m.top.findNode("bg")
    m.icon = m.top.findNode("icon")
    m.fadeA = m.top.findNode("fadeA")
    m.fadeB = m.top.findNode("fadeB")
    m.fadeC = m.top.findNode("fadeC")
    m.corner = m.top.findNode("corner")
    m.inside = m.top.findNode("inside")
    m.below = m.top.findNode("below")
    redraw()
end sub

sub place(node as Object, x as Integer, y as Integer, w as Integer, h as Integer)
    node.translation = [x, y]
    node.width = w
    node.height = h
end sub

sub redraw()
    if m.bg = invalid then return
    w = m.top.w
    h = m.top.h
    f = m.top.isFocused
    accent = m.top.accent

    place(m.ring, -6, -6, w + 12, h + 12)
    m.ring.color = accent
    m.ring.visible = f
    place(m.bg, 0, 0, w, h)

    m.icon.visible = false
    m.fadeA.visible = false
    m.fadeB.visible = false
    m.fadeC.visible = false
    m.corner.visible = false
    m.inside.visible = false
    m.below.visible = false

    if m.top.kind = "pill"
        m.bg.color = "0x1A1F28FF"
        place(m.inside, 0, 0, w, h)
        m.inside.text = m.top.name
        m.inside.visible = true
    else if m.top.styleName = "afterglow"
        brand = m.top.brand
        if brand = "" then brand = accent
        m.bg.color = brand
        q = h \ 4
        place(m.fadeA, 0, 0, w, q)
        place(m.fadeB, 0, q, w, q)
        place(m.fadeC, 0, q * 2, w, q)
        m.fadeA.visible = true
        m.fadeB.visible = true
        m.fadeC.visible = true
        place(m.inside, 24, 0, w - 48, h)
        m.inside.text = UCase(m.top.name)
        m.inside.visible = true
        if m.top.iconUri <> ""
            place(m.corner, w - 104, h - 74, 88, 62)
            m.corner.uri = m.top.iconUri
            m.corner.visible = true
        end if
    else
        m.bg.color = "0x1A1F28FF"
        place(m.icon, 0, 0, w, h)
        if m.icon.uri <> m.top.iconUri then m.icon.uri = m.top.iconUri
        m.icon.visible = true
        place(m.below, 4, h + 14, w, 40)
        m.below.text = m.top.name
        m.below.visible = f
    end if

    m.top.scaleRotateCenter = [w / 2, h / 2]
    if f
        m.top.scale = [1.04, 1.04]
    else
        m.top.scale = [1.0, 1.0]
    end if
    if m.top.isHidden
        m.top.opacity = 0.35
    else
        m.top.opacity = 1.0
    end if
end sub
