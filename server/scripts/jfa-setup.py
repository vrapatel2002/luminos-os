#!/usr/bin/env python3
# [CHANGE: cowork | 2026-11-13] DECISION 188 one-off setup: Jellyfin service admin for jfa-go +
# the viewer template, then jfa-go's config. Run as root on the server. Idempotent-ish: refuses
# to overwrite an existing config. Prints NO passwords.
import json, os, secrets, sqlite3, string, sys, urllib.request

JF = "http://127.0.0.1:8096"
db = sqlite3.connect("file:/var/lib/jellyfin/data/jellyfin.db?mode=ro", uri=True)
KEY = db.execute("select AccessToken from ApiKeys where Name='luminos-admin'").fetchone()[0]
CFG = "/var/lib/jfa-go/config.ini"


def jf(path, body=None, method=None):
    req = urllib.request.Request(JF + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ("POST" if body is not None else "GET"),
                                 headers={"X-Emby-Token": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as f:
        raw = f.read()
    return json.loads(raw) if raw else None


def pw(n=40):
    a = string.ascii_letters + string.digits
    return "".join(secrets.choice(a) for _ in range(n))


def user(name):
    return next((u for u in jf("/Users") if u["Name"].lower() == name.lower()), None)


VIEWER = {  # what every invited person gets. DECISION 188.
    "IsAdministrator": False, "IsHidden": True, "IsDisabled": False,
    "EnableCollectionManagement": False, "EnableSubtitleManagement": False, "EnableLyricManagement": False,
    "EnableUserPreferenceAccess": True, "EnableRemoteControlOfOtherUsers": False,
    "EnableSharedDeviceControl": False, "EnableRemoteAccess": True,   # tailnet = "remote" to Jellyfin
    "EnableLiveTvManagement": False, "EnableLiveTvAccess": False,
    "EnableMediaPlayback": True, "EnableAudioPlaybackTranscoding": True,
    "EnableVideoPlaybackTranscoding": True, "EnablePlaybackRemuxing": True,
    "ForceRemoteSourceTranscoding": False,
    "EnableContentDeletion": False, "EnableContentDeletionFromFolders": [],
    "EnableContentDownloading": False, "EnableSyncTranscoding": False, "EnableMediaConversion": False,
    "EnableAllDevices": True, "EnableAllChannels": True, "EnableAllFolders": True,
    "LoginAttemptsBeforeLockout": 5, "MaxActiveSessions": 3, "EnablePublicSharing": False,
    "RemoteClientBitrateLimit": 0, "SyncPlayAccess": "JoinGroups",
    "AuthenticationProviderId": "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider",
    "PasswordResetProviderId": "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider",
}
SERVICE = dict(VIEWER, IsAdministrator=True, EnableRemoteAccess=False, EnableMediaPlayback=False,
               EnableContentDeletion=False, MaxActiveSessions=0, LoginAttemptsBeforeLockout=-1)

if os.path.exists(CFG):
    sys.exit("refusing: %s already exists" % CFG)

svc_pw = pw()
svc = user("luminos-invites") or jf("/Users/New", {"Name": "luminos-invites", "Password": svc_pw})
if user("luminos-invites") and "Id" in svc and svc.get("Name") == "luminos-invites" and not svc.get("_new"):
    # existed before: reset its password to the new random one so the config matches
    jf("/Users/%s/Password" % svc["Id"], {"CurrentPw": "", "NewPw": svc_pw, "ResetPassword": False})
jf("/Users/%s/Policy" % svc["Id"], SERVICE)

tpl = user("luminos-viewer-template") or jf("/Users/New", {"Name": "luminos-viewer-template", "Password": pw()})
jf("/Users/%s/Policy" % tpl["Id"], VIEWER)

os.makedirs("/var/lib/jfa-go", exist_ok=True)
conf = f"""; [CHANGE: cowork | 2026-11-13] DECISION 188 -- written by jfa-setup.py. 0600 jfago.
[updates]
enabled = false

[jellyfin]
username = luminos-invites
password = {svc_pw}
server = http://127.0.0.1:8096
public_server = https://192.168.2.61:8443
client = jfa-go
type = jellyfin

[ui]
language-form = en-us
language-admin = en-us
theme = Jellyfin (Dark)
host = 127.0.0.1
port = 8056
jellyfin_login = true
admin_only = true
allow_all = false
contact_message = Need help? Ask Shawn.
help_message = Pick a username and password. You'll use them for Jellyfin (watching) and Jellyseerr (asking for new shows).
success_message = Your account is ready. Sign in to Jellyfin with it, and to Jellyseerr (https://192.168.2.61:8444) to request shows.
jfa_url = https://192.168.2.61:8452
use_proxy_host = false
url_base =

[advanced]
log_ips = false
auth_retry_count = 6
auth_retry_gap = 10

[user_page]
enabled = true
show_link = true
referrals = false

[password_validation]
enabled = true
min_length = 8
upper = 1
lower = 0
number = 1
special = 0

[messages]
enabled = true
message = Need help? Ask Shawn.

[email]
collect = false
required = false
method =

[password_resets]
enabled = false

[jellyseerr]
enabled = false

[discord]
enabled = false

[telegram]
enabled = false

[matrix]
enabled = false
"""
fd = os.open(CFG, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(conf)
print("service admin:", svc["Id"], "| template:", tpl["Id"], "| config written (password not shown)")
