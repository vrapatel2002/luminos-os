' dumbtv home for Roku — a home screen with your apps and inputs, nothing else.
' Roku port of the dumbtv home design (github.com/humblemuzzu/dumbtv, MIT).
' [CHANGE: claude-code | 2026-10-27]

sub Main()
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.setMessagePort(port)
    screen.CreateScene("Home")
    screen.show()
    while true
        msg = wait(0, port)
        if type(msg) = "roSGScreenEvent"
            if msg.isScreenClosed() then return
        end if
    end while
end sub
