#!/usr/bin/env python3
# [CHANGE: cowork | 2026-11-13] DECISION 188 end-to-end proof. Run as root. Creates a 1-use invite,
# signs up "lumtest" through the PUBLIC Caddy URL, checks the account, then deletes everything.
import json, secrets, sqlite3, ssl, string, subprocess, time, urllib.error, urllib.request

ctx = ssl._create_unverified_context()             # tls internal on the LAN address
PUB = "https://192.168.2.61:8452"
J = "http://127.0.0.1:8056"
tok = open("/root/.jfa-token").read().strip()
JK = sqlite3.connect("file:/var/lib/jellyfin/data/jellyfin.db?mode=ro", uri=True).execute(
    "select AccessToken from ApiKeys where Name='luminos-admin'").fetchone()[0]
SK = json.load(open("/var/lib/jellyseerr/settings.json"))["main"]["apiKey"]
NAME = "lumtest"
PW = "Lt" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14)) + "9"


def req(url, body=None, method=None, headers=None, form=False):
    h = dict(headers or {})
    data = None
    if body is not None:
        if form:
            data = body.encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, method=method or ("POST" if body is not None else "GET"), headers=h)
    try:
        with urllib.request.urlopen(r, timeout=30, context=ctx) as f:
            raw = f.read()
            return f.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode()[:200]), f.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:4000], e.headers


A = {"Authorization": "Bearer " + tok}
ok = True
def check(label, cond):
    global ok
    ok = ok and cond
    print(("PASS " if cond else "FAIL ") + label)

# 1. invite
st, r, _ = req(J + "/invites", {"days": 1, "hours": 0, "minutes": 0, "multiple-uses": False,
                                "remaining-uses": 1, "no-limit": False, "profile": "viewer", "label": "e2e-test"}, headers=A)
st, inv, _ = req(J + "/invites", headers=A)
code = next(i["code"] for i in inv["invites"] if i.get("label") == "e2e-test")
check("invite created (1 use, profile viewer)", bool(code))
st, page, _ = req(PUB + "/invite/" + code)
check("invite page opens through Caddy (%s)" % st, st == 200)

# 2. sign up through the public URL, like a guest would
st, r, _ = req(PUB + "/user/invite", {"code": code, "username": NAME, "password": PW, "email": ""})
check("sign-up accepted (%s %s)" % (st, str(r)[:80]), st == 200)

# 3. the new account
users = req("http://127.0.0.1:8096/Users", headers={"X-Emby-Token": JK})[1]
u = next((x for x in users if x["Name"] == NAME), None)
check("account exists in Jellyfin", u is not None)
pol = u["Policy"] if u else {}
check("not admin", pol.get("IsAdministrator") is False)
check("cannot delete media", pol.get("EnableContentDeletion") is False)
check("cannot download", pol.get("EnableContentDownloading") is False)
check("cannot remote-control others", pol.get("EnableRemoteControlOfOtherUsers") is False)
check("can play + works over tailnet", pol.get("EnableMediaPlayback") and pol.get("EnableRemoteAccess"))
check("hidden from login screen list", pol.get("IsHidden") is True)
check("max 3 streams, lockout after 5 bad passwords",
      pol.get("MaxActiveSessions") == 3 and pol.get("LoginAttemptsBeforeLockout") == 5)

# 4. the guest can sign in to Jellyfin...
auth = 'MediaBrowser Client="e2e", Device="e2e", DeviceId="e2e-lumtest", Version="1"'
st, r, _ = req("http://127.0.0.1:8096/Users/AuthenticateByName", {"Username": NAME, "Pw": PW},
               headers={"Authorization": auth})
check("guest signs in to Jellyfin", st == 200)
gtok = r.get("AccessToken") if isinstance(r, dict) else None
if gtok:
    st, _, _ = req("http://127.0.0.1:8096/Library/VirtualFolders", headers={"Authorization": auth + ', Token="%s"' % gtok})
    check("guest cannot read server library settings (%s)" % st, st in (401, 403))
    req("http://127.0.0.1:8096/Sessions/Logout", {}, method="POST",
        headers={"Authorization": auth + ', Token="%s"' % gtok})

# 5. ...but NOT past the admin gate
st, body, h = req("https://192.168.2.61:8446/luminos-auth/login",
                  "username=%s&password=%s&next=/" % (NAME, PW), form=True,
                  headers={"Origin": "https://192.168.2.61:8446"})
check("admin gate refuses the guest (%s)" % st, st == 403 and "only for the server owner" in str(body))

# 6. Jellyseerr: guest signs in, gets request-only
st, r, _ = req("http://127.0.0.1:5055/api/v1/auth/jellyfin", {"username": NAME, "password": PW})
check("guest signs in to Jellyseerr (%s)" % st, st == 200)
seer = req("http://127.0.0.1:5055/api/v1/user?take=50", headers={"X-Api-Key": SK})[1]
su = next((x for x in seer.get("results", []) if (x.get("jellyfinUsername") or "").lower() == NAME), None)
check("Jellyseerr user is request-only (permissions=%s)" % (su or {}).get("permissions"),
      su is not None and su.get("permissions") == 32)

# 7. clean up
if su:
    print("cleanup seerr user:", req("http://127.0.0.1:5055/api/v1/user/%d" % su["id"], method="DELETE",
                                     headers={"X-Api-Key": SK})[0])
if u:
    print("cleanup jellyfin user:", req("http://127.0.0.1:8096/Users/%s" % u["Id"], method="DELETE",
                                        headers={"X-Emby-Token": JK})[0])
inv = req(J + "/invites", headers=A)[1]
left = [i["code"] for i in (inv.get("invites") or []) if i.get("label") == "e2e-test"]
if left:
    print("cleanup invite:", req(J + "/invites", {"code": left[0]}, method="DELETE", headers=A)[0])
users = req("http://127.0.0.1:8096/Users", headers={"X-Emby-Token": JK})[1]
print("jellyfin users now:", sorted(x["Name"] for x in users))
print("ALL PASS" if ok else "SOME FAILED")
