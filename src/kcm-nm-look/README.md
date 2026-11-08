# Wi-Fi page look (DECISION 177)
<!-- [CHANGE: claude-code | 2026-11-08] -->
The Wi-Fi & Networking page loads its QML from disk by searching the data folders, and `/usr/local/share` is searched
before `/usr/share`. `luminos-style` installs these four files to `/usr/local/share/kcm_networkmanagement/qml/`, so they
win over plasma-nm's own copies without forking plasma-nm. `main.qml` (the whole page, DECISION 178) and `Rows.qml` (card building blocks) are ours; the two dialogs are
unchanged copies (they must sit next to main.qml). Settings are read/written by the C++ helper `org.luminos.network`
(`src/luminos-style/network/`).
Base: plasma-nm 6.7.5 (`/usr/share/kcm_networkmanagement/qml`). A pacman hook warns when plasma-nm changes version.
Stock page back: `sudo rm -r /usr/local/share/kcm_networkmanagement` (or remove the lines from the luminos-style PKGBUILD).
The Status tab left alignment is not here: it is C++ in the systemsettings fork (`luminosLeftAlign`).
