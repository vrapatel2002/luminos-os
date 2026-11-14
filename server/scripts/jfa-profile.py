#!/usr/bin/env python3
# [CHANGE: cowork | 2026-11-13] DECISION 188: make jfa-go's default profile "viewer" from the
# template user, then delete the template user. Run as root. Prints no secrets.
import base64, configparser, json, sqlite3, sys, urllib.request

c = configparser.ConfigParser(strict=False, interpolation=None)
c.read("/var/lib/jfa-go/config.ini")
U, P = c["jellyfin"]["username"], c["jellyfin"]["password"]
J = "http://127.0.0.1:8056"


def call(path, body=None, method=None, token=None, basic=False):
    h = {"Content-Type": "application/json"}
    if basic:
        h["Authorization"] = "Basic " + base64.b64encode(("%s:%s" % (U, P)).encode()).decode()
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(J + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ("POST" if body is not None else "GET"), headers=h)
    with urllib.request.urlopen(req, timeout=30) as f:
        raw = f.read()
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw.decode()


tok = call("/token/login", basic=True)["token"]
open("/root/.jfa-token", "w").write(tok)          # for the follow-up test script; deleted after
JK = sqlite3.connect("file:/var/lib/jellyfin/data/jellyfin.db?mode=ro", uri=True).execute(
    "select AccessToken from ApiKeys where Name='luminos-admin'").fetchone()[0]
users = json.load(urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:8096/Users", headers={"X-Emby-Token": JK}), timeout=30))
tpl = next(u for u in users if u["Name"] == "luminos-viewer-template")

print("create profile:", call("/profiles", {"name": "viewer", "id": tpl["Id"], "homescreen": True}, token=tok))
print("set default:", call("/profiles/default", {"name": "viewer"}, token=tok))
profs = call("/profiles", token=tok)
print("profiles:", json.dumps(profs)[:400])
if "viewer" not in json.dumps(profs):
    sys.exit("profile missing -- template user NOT deleted")
req = urllib.request.Request("http://127.0.0.1:8096/Users/%s" % tpl["Id"], method="DELETE",
                             headers={"X-Emby-Token": JK})
print("delete template user:", urllib.request.urlopen(req, timeout=30).status)
