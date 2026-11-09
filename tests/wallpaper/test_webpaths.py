"""BUG-235 — a Lively web page's root-absolute paths must still find their files under file://.

[CHANGE: claude-code | 2026-11-08]
SPDX-License-Identifier: GPL-3.0-or-later

The rule under test is the browser's own: a reference written in a file resolves
against that file's folder. So every assertion is "after the rewrite, resolving the
reference from where it is written lands on the same file Lively's "/" = package
folder would have served" — not a restatement of the regexes.
"""
import os
import posixpath

from hypothesis import assume, given, settings, strategies as st

import luminos_wallpaper_webpaths as W

LIVING_ROOM_HEAD = """<script async src="/js/es-module-shims.js"></script>
<script type="importmap">
  {"imports": {"three": "/js/threejs/three.module.js", "three/addons/": "/js/threejs/jsm/"}}
</script>
<link rel="stylesheet" href="/styles/style.css?v=2">
<img src="//cdn.example.com/a.png"><a href="https://x.org/js/a.js">x</a>
<script>fetch("/api/missing"); s.split("/");</script>"""


def make(tmp, files):
    for rel, text in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return str(tmp)


def pkg(tmp):
    return make(tmp, {"index.html": LIVING_ROOM_HEAD, "js/es-module-shims.js": "",
                      "js/threejs/three.module.js": "", "js/threejs/jsm/x.js": "",
                      "styles/style.css": "body{background:url(/img/bg.png)}", "img/bg.png": "",
                      "sub/page.html": '<script src="/js/es-module-shims.js"></script>'})


def test_living_room_head_becomes_relative(tmp_path):
    root = pkg(tmp_path)
    changed = W.fix_package(root)
    html = (tmp_path / "index.html").read_text()
    assert '"./js/threejs/three.module.js"' in html and '"./js/threejs/jsm/"' in html
    assert 'src="./js/es-module-shims.js"' in html and 'href="./styles/style.css?v=2"' in html
    assert "url(../img/bg.png)" in (tmp_path / "styles/style.css").read_text()
    assert 'src="../js/es-module-shims.js"' in (tmp_path / "sub/page.html").read_text()
    assert sorted(changed) == ["index.html", "styles/style.css", "sub/page.html"]


def test_leaves_external_missing_and_bare_root_alone(tmp_path):
    W.fix_package(pkg(tmp_path))
    html = (tmp_path / "index.html").read_text()
    for kept in ('"//cdn.example.com/a.png"', '"https://x.org/js/a.js"', '"/api/missing"', 'split("/")'):
        assert kept in html


def test_never_escapes_the_package(tmp_path):
    root = make(tmp_path / "p", {"index.html": '<script src="/../outside.js"></script>'})
    (tmp_path / "outside.js").write_text("")
    assert W.fix_package(root) == []


def test_second_run_changes_nothing(tmp_path):
    root = pkg(tmp_path)
    W.fix_package(root)
    assert W.fix_package(root) == []


SEG = st.text(alphabet="abcdefghij-_.", min_size=1, max_size=6).filter(lambda s: s not in (".", ".."))


@settings(max_examples=150, deadline=None)
@given(target=st.lists(SEG, min_size=1, max_size=4), here=st.lists(SEG, max_size=3),
       tail=st.sampled_from(["", "?v=1", "#top", "?a=b#c"]))
def test_rewrite_resolves_to_the_same_file(tmp_path_factory, target, here, tail):
    root = str(tmp_path_factory.mktemp("pkg"))
    full = os.path.join(root, *target)
    # one name cannot be both the target file and a folder on the way to `here`
    assume(all(os.path.join(root, *here[:i + 1]) != full for i in range(len(here))))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if not os.path.isdir(full):
        open(full, "a").close()
    folder = os.path.join(root, *here)
    os.makedirs(folder, exist_ok=True)
    out = W.relative(root, folder, "/" + "/".join(target) + tail)
    bare, kept = W.split_tail(out)
    assert kept == tail and bare.startswith(("./", "../"))
    assert os.path.normpath(posixpath.join(folder, bare)) == os.path.normpath(full)
    quoted = '"%s"' % out
    assert W.rewrite_text(root, folder, quoted) == quoted   # a second pass leaves it alone


@settings(max_examples=150, deadline=None)
@given(st.text(alphabet=st.characters(blacklist_characters="/"), max_size=200))
def test_text_without_root_paths_is_untouched(tmp_path_factory, text):
    root = str(tmp_path_factory.mktemp("pkg"))
    assert W.rewrite_text(root, root, text) == text
