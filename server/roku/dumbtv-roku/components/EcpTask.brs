' [CHANGE: claude-code | 2026-10-27] v1.0.2: try every local address, log code + reason to the
' debug console (telnet <tv> 8085) so a failure says why instead of just "empty".
sub init()
    m.top.functionName = "doWork"
end sub

' Candidate ECP bases: the TV's LAN address(es) first, then loopback names.
function ecpBases() as Object
    out = []
    di = CreateObject("roDeviceInfo")
    ips = di.GetIPAddrs()
    for each k in ips
        out.Push("http://" + ips[k] + ":8060")
    end for
    out.Push("http://127.0.0.1:8060")
    out.Push("http://localhost:8060")
    return out
end function

' One request. Returns { code, body, reason }.
function fetch(url as String, method as String) as Object
    port = CreateObject("roMessagePort")
    x = CreateObject("roUrlTransfer")
    x.SetMessagePort(port)
    x.SetUrl(url)
    x.RetainBodyOnError(true)
    started = false
    if method = "POST"
        x.SetRequest("POST")
        started = x.AsyncPostFromString("")
    else
        started = x.AsyncGetToString()
    end if
    if not started then return { code: -999, body: "", reason: "request did not start" }
    msg = wait(5000, port)
    if type(msg) = "roUrlEvent"
        return { code: msg.GetResponseCode(), body: msg.GetString(), reason: msg.GetFailureReason() }
    end if
    x.AsyncCancel()
    return { code: -998, body: "", reason: "timeout after 5 s" }
end function

sub doWork()
    cmd = m.top.command
    tried = []
    for each base in ecpBases()
        if cmd = "apps"
            r = fetch(base + "/query/apps", "GET")
        else
            r = fetch(base + "/launch/" + m.top.arg, "POST")
        end if
        print "dumbtv ecp "; cmd; " "; base; " -> "; r.code; " "; r.reason
        tried.Push(base + " -> " + r.code.ToStr() + " " + r.reason)
        if r.code = 200
            if cmd = "apps"
                apps = []
                xml = CreateObject("roXMLElement")
                if xml.Parse(r.body)
                    for each a in xml.GetChildElements()
                        apps.Push({ id: a@id, type: a@type, name: a.GetText() })
                    end for
                end if
                m.top.result = { apps: apps, base: base, tried: tried }
            else
                m.top.result = { code: 200, tried: tried }
            end if
            return
        end if
    end for
    m.top.result = { apps: [], base: "", code: -1, tried: tried }
end sub
