#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-11-09] DECISION 182 — Luminos Files icon pack generator.
# Makes the "luminos-files" icon theme: every file-type (mimetype) and folder icon becomes a soft
# coloured rounded tile with a simple glyph and, where known, a small extension tag (MD, SH, LOG...).
# It inherits yet-another-monochrome-icon-set, so every other icon stays exactly as it is now.
# Small sizes (<= 20 px, e.g. the sidebar and menus) keep the monochrome glyphs for folders.
#
#   usage: make-files-icons.py OUTDIR
import os, re, shutil, sys

MONO = '/usr/share/icons/yet-another-monochrome-icon-set'
PAPIRUS = '/usr/share/icons/Papirus/64x64/mimetypes'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'luminos-files'

# colour per kind (same palette as the approved prototype docs/windowstyle/mock/files-page.html)
COL = {'folder': '#c6c3f5', 'doc': '#f2c99a', 'code': '#9fd8c5', 'web': '#9fd8c5', 'data': '#a9c7f7', 'log': '#b7c2d0',
       'img': '#f2a7c3', 'vid': '#d7b6f5', 'audio': '#b6e3a8', 'arc': '#e8d58f', 'bin': '#c9c4cf', 'other': '#c9c4cf', 'font': '#c9c4cf'}
MIX = {'folder': .34}  # tile = colour mixed into #26262b by this much (others .22)
BASE = (0x26, 0x26, 0x2b)

G = {  # 24x24 stroke glyphs
 'folder': 'M3 7.5A2.5 2.5 0 0 1 5.5 5h4l2 2h7A2.5 2.5 0 0 1 21 9.5v8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z',
 'doc': 'M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v5h5M9 13h6M9 17h4',
 'code': 'M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16',
 'web': 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
 'data': 'M12 4c4 0 7 1.2 7 2.8v10.4c0 1.6-3 2.8-7 2.8s-7-1.2-7-2.8V6.8C5 5.2 8 4 12 4zM5 7c0 1.5 3 2.8 7 2.8S19 8.5 19 7M5 12c0 1.5 3 2.8 7 2.8s7-1.3 7-2.8',
 'log': 'M6 4h12v16H6zM9 8h6M9 12h6M9 16h3',
 'img': 'M4 5h16v14H4zM4 16l5-5 4 4 2-2 5 5M15 9h.01',
 'vid': 'M4 6h16v12H4zM10 9.5v5l4-2.5z',
 'audio': 'M9 18V6l10-2v12M9 18a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0zM19 16a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z',
 'arc': 'M7 3h10v18H7zM12 3v2M12 7v2M12 11v2M11 15h2v3h-2z',
 'bin': 'M6 4h12v16H6zM9 8h2v3H9zM13 8h2M13 11h2M9 14h2M13 14h2v3h-2z',
 'font': 'M5 20L11 4h2l6 16M8 14h8',
 'other': 'M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v5h5',
}
FOLDER_INNER = {  # small symbol inside special folders
 'videos': 'M10.5 11v5l4-2.5z', 'video': 'M10.5 11v5l4-2.5z',
 'download': 'M12 10.5v5m0 0l-2-2m2 2l2-2', 'downloads': 'M12 10.5v5m0 0l-2-2m2 2l2-2',
 'pictures': 'M8.5 16l2.5-2.5 2 2 1-1 1.5 1.5M14 11.5h.01', 'image': 'M8.5 16l2.5-2.5 2 2 1-1 1.5 1.5M14 11.5h.01',
 'music': 'M11 16v-4.5l3-.8V15M11 16a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM14 15a1 1 0 1 1-2 0 1 1 0 0 1 2 0z', 'sound': 'M11 16v-4.5l3-.8V15M11 16a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM14 15a1 1 0 1 1-2 0 1 1 0 0 1 2 0z',
 'documents': 'M10 11.5h4M10 14h4M10 16.5h2.5', 'text': 'M10 11.5h4M10 14h4M10 16.5h2.5',
 'templates': 'M9.5 11h5v5h-5z', 'publicshare': 'M12 11a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM9.5 17c.5-1.4 1.4-2 2.5-2s2 .6 2.5 2', 'public': 'M12 11a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM9.5 17c.5-1.4 1.4-2 2.5-2s2 .6 2.5 2',
 'user-desktop': 'M9 11h6v3.5H9zM11 16.5h2', 'desktop': 'M9 11h6v3.5H9zM11 16.5h2', 'user-home': 'M9.5 13.5l2.5-2 2.5 2v3h-5z', 'home': 'M9.5 13.5l2.5-2 2.5 2v3h-5z',
 'network': 'M9 16h6M12 11v5M10 11h4', 'remote': 'M9 16h6M12 11v5M10 11h4', 'development': 'M10.5 11.5L9 13.5l1.5 2M13.5 11.5l1.5 2-1.5 2', 'script': 'M10.5 11.5L9 13.5l1.5 2M13.5 11.5l1.5 2-1.5 2', 'scripts': 'M10.5 11.5L9 13.5l1.5 2M13.5 11.5l1.5 2-1.5 2',
}
TAGS = {
 'text-markdown': 'MD', 'text-x-markdown': 'MD', 'application-x-shellscript': 'SH', 'text-x-script': 'SH', 'text-x-sh': 'SH',
 'application-json': 'JSON', 'text-json': 'JSON', 'text-x-json': 'JSON', 'text-x-log': 'LOG', 'text-html': 'HTML', 'application-xhtml+xml': 'HTML',
 'text-plain': 'TXT', 'application-pdf': 'PDF', 'application-zip': 'ZIP', 'application-x-iso9660-image': 'ISO', 'application-x-cd-image': 'ISO',
 'text-x-python': 'PY', 'text-x-python3': 'PY', 'text-x-c++src': 'CPP', 'text-x-csrc': 'C', 'text-x-chdr': 'H', 'text-x-c++hdr': 'HPP',
 'application-x-yaml': 'YAML', 'application-yaml': 'YAML', 'text-x-yaml': 'YAML', 'text-csv': 'CSV', 'application-toml': 'TOML', 'text-x-toml': 'TOML',
 'application-octet-stream': 'BIN', 'text-x-qml': 'QML', 'application-javascript': 'JS', 'text-javascript': 'JS', 'application-x-javascript': 'JS',
 'text-css': 'CSS', 'application-xml': 'XML', 'text-xml': 'XML', 'application-x-sharedlib': 'SO', 'application-x-compressed-tar': 'TGZ',
 'application-x-xz': 'XZ', 'application-x-xz-compressed-tar': 'TXZ', 'application-x-tar': 'TAR', 'application-gzip': 'GZ', 'application-x-gzip': 'GZ',
 'application-x-7z-compressed': '7Z', 'application-vnd.rar': 'RAR', 'application-x-rar': 'RAR', 'application-zstd': 'ZST', 'application-x-zstd-compressed-tar': 'TZST',
 'text-x-go': 'GO', 'text-rust': 'RS', 'text-x-rust': 'RS', 'text-x-java': 'JAVA', 'text-x-lua': 'LUA', 'application-x-desktop': 'DESK',
 'application-x-executable': 'EXE', 'application-x-ms-dos-executable': 'EXE', 'application-sql': 'SQL', 'text-x-sql': 'SQL', 'text-x-cmake': 'CMAKE',
 'text-x-makefile': 'MAKE', 'text-x-patch': 'DIFF', 'text-x-diff': 'DIFF', 'application-x-ipynb+json': 'IPYNB', 'text-x-typescript': 'TS',
 'application-vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX', 'application-vnd.oasis.opendocument.text': 'ODT',
 'application-vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX', 'application-vnd.oasis.opendocument.spreadsheet': 'ODS',
 'application-vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX', 'application-x-bittorrent': 'TOR', 'application-x-subrip': 'SRT',
 'text-x-changelog': 'LOG', 'video-x-matroska': 'MKV', 'video-matroska': 'MKV', 'text-x-shellscript': 'SH', 'application-x-perl': 'PL', 'audio-matroska': 'MKA', 'application-x-ndjson': 'JSON', 'application-geo+json': 'JSON', 'video-mp4': 'MP4', 'video-webm': 'WEBM', 'video-x-msvideo': 'AVI', 'video-quicktime': 'MOV', 'audio-x-flac': 'FLAC', 'audio-mpeg': 'MP3', 'application-x-trash': '', 'text-x-ini': 'INI', 'text-x-dbus-service': 'INI',
}

def kind(n):
    if n.startswith(('folder', 'inode-directory', 'gnome-fs-directory', 'inode-dir')): return 'folder'
    if n.startswith('image-'): return 'img'
    if n.startswith('video-'): return 'vid'
    if n.startswith('audio-'): return 'audio'
    if n.startswith(('font-', 'application-x-font')) or 'font' in n: return 'font'
    if 'log' in n.split('-')[-1] or 'changelog' in n: return 'log'
    if n in ('text-html', 'application-xhtml+xml') or 'html' in n: return 'web'
    if re.search(r'json|xml|yaml|toml|csv|spreadsheet|sheet|database|sql|sqlite|calc|x-ini', n): return 'data'
    if re.search(r'zip|tar|xz|gzip|bzip|7z|rar|zstd|compress|archive|iso9660|cd-image|disk-image|x-deb|x-rpm|package|lzma|lz4|cpio|squashfs|appimage|flatpak', n): return 'arc'
    if re.search(r'executable|sharedlib|octet-stream|x-object|x-core|firmware|x-elf', n): return 'bin'
    if re.search(r'script|text-x-(?!log)|javascript|java|python|perl|ruby|php|source|src|hdr|makefile|cmake|patch|diff|qml|typescript|x-desktop|lua|rust|go$', n): return 'code'
    if n.startswith(('text-', 'x-office-document')) or re.search(r'pdf|document|word|opendocument-text|rtf|epub|ebook|presentation|slide|postscript|x-office', n): return 'doc'
    return 'other'

def tag(n, k):
    if n in TAGS: return TAGS[n]
    if k in ('img', 'vid', 'audio'):
        t = n.split('-')[-1].replace('x-', '')
        if 2 <= len(t) <= 4 and t.isalnum(): return t.upper()
    return ''

def mix(hexc, a):
    c = tuple(int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return '#%02x%02x%02x' % tuple(round(BASE[i] + (c[i] - BASE[i]) * a) for i in range(3))

def svg(n, k):
    col = COL[k]; bg = mix(col, MIX.get(k, .22)); t = tag(n, k)
    inner = ''
    if k == 'folder':
        key = n.replace('folder-', '').replace('-symbolic', '')
        if key in FOLDER_INNER:
            inner = f'<path d="{FOLDER_INNER[key]}" fill="none" stroke="{col}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    glyph = (f'<g transform="translate(14.4 14.4) scale(1.4)"><path d="{G[k]}" fill="none" stroke="{col}" stroke-width="1.75" '
             f'stroke-linecap="round" stroke-linejoin="round"/>{inner}</g>')
    label = ''
    if t:
        fs = 8.2 if len(t) <= 3 else 7.2 if len(t) == 4 else 6.2
        w = max(18, len(t) * fs * 0.68 + 7)
        label = (f'<rect x="{62 - w:.1f}" y="47" width="{w:.1f}" height="13" rx="4" fill="#1b1b1f"/>'
                 f'<text x="{62 - w / 2:.1f}" y="56.6" font-family="Google Sans Flex,Inter,sans-serif" font-weight="700" '
                 f'font-size="{fs}" fill="#b0abb7" text-anchor="middle">{t}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
            f'<rect x="4" y="4" width="56" height="56" rx="13.5" fill="{bg}"/>{glyph}{label}</svg>\n')

def names(d):
    return {f[:-4] for f in os.listdir(d) if f.endswith('.svg')} if os.path.isdir(d) else set()

def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(f'{OUT}/mimetypes/scalable'); os.makedirs(f'{OUT}/places/scalable'); os.makedirs(f'{OUT}/places/16')
    mimes = names(f'{MONO}/mimetypes/scalable') | names(PAPIRUS) | set(TAGS)
    mimes = {m for m in mimes if not m.endswith('-symbolic') and not m.startswith(('folder', 'inode-directory'))}
    folders = {f for f in names(f'{MONO}/places/scalable') | names(f'{MONO}/places/16') if re.match(r'(folder|inode-directory|gnome-fs-directory|user-desktop$|user-home$)', f) and not f.endswith('-symbolic')}
    folders |= {'user-desktop', 'user-home'}  # ~/Desktop and ~ shown as folders in the file view
    folders |= {'inode-directory', 'folder', 'folder-videos', 'folder-download', 'folder-documents', 'folder-pictures', 'folder-music', 'folder-templates', 'folder-publicshare', 'folder-desktop'}
    counts = {}
    for m in sorted(mimes):
        k = kind(m); counts[k] = counts.get(k, 0) + 1
        open(f'{OUT}/mimetypes/scalable/{m}.svg', 'w').write(svg(m, k))
    for f in sorted(folders):
        open(f'{OUT}/places/scalable/{f}.svg', 'w').write(svg(f, 'folder'))
        small = f'{MONO}/places/16/{f}.svg'
        if not os.path.exists(small): small = f'{MONO}/places/scalable/{f}.svg'
        if not os.path.exists(small): small = f'{MONO}/places/16/folder.svg'
        shutil.copy(small, f'{OUT}/places/16/{f}.svg')
    open(f'{OUT}/index.theme', 'w').write('''[Icon Theme]
Name=Luminos Files
Comment=Luminos: coloured file-type tiles on top of the monochrome set (DECISION 182)
Inherits=yet-another-monochrome-icon-set,Papirus-Dark,breeze-dark,Adwaita,hicolor
FollowsColorScheme=true
Example=folder
KDE-Extensions=.svg
Directories=places/16,places/scalable,mimetypes/scalable

[places/16]
Context=Places
Size=16
MinSize=8
MaxSize=20
Type=Scalable

[places/scalable]
Context=Places
Size=64
MinSize=21
MaxSize=512
Type=Scalable

[mimetypes/scalable]
Context=MimeTypes
Size=64
MinSize=8
MaxSize=512
Type=Scalable
''')
    print(f'{len(mimes)} file types, {len(folders)} folders', counts)

main()
