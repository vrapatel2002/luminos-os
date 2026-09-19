"""Property tests for the runtime shader baker.  SPEC §3.4, DECISION 119.
[CHANGE: claude-code | 2026-09-19]

The baker builds GLSL from a file a person chose and a JSON file next to it, then
hands a path and a uniform list to QML that splices both into generated code. So
the things worth pinning are: nothing user-named can collide with a name the
wrapper owns, nothing unusable reaches the output, and no input raises.
"""
import json
import os

import pytest
from hypothesis import given, settings, strategies as st

import luminos_shader_bake as B

CONTROL_TYPES = ["slider", "color", "dropdown", "textbox", "checkbox", "file", "button", "label"]

control = st.fixed_dictionaries({"type": st.sampled_from(CONTROL_TYPES),
                                 "value": st.one_of(st.floats(allow_nan=False, allow_infinity=False),
                                                    st.text(max_size=8), st.booleans())})
schema = st.dictionaries(st.text(min_size=1, max_size=12), control, max_size=6)
junk = st.one_of(st.none(), st.text(), st.integers(), st.lists(st.text(), max_size=3),
                 st.dictionaries(st.text(max_size=6), st.text(max_size=6), max_size=3))

TOY = "void mainImage(out vec4 fragColor, in vec2 fragCoord) { fragColor = vec4(iTime); }"
QT_SHAPED = "#version 440\nvoid main() { }"


# ---- uniform_decls ----------------------------------------------------------
@given(junk)
def test_uniform_decls_never_raises(value):
    assert isinstance(B.uniform_decls(value), list)


@given(schema)
@settings(max_examples=120)
def test_every_declared_name_is_a_legal_identifier(s):
    for name, glsl in B.uniform_decls(s):
        assert B._NAME_RE.match(name)
        assert glsl in ("float", "vec4")


@given(schema)
@settings(max_examples=120)
def test_a_reserved_name_can_never_become_a_uniform(s):
    """A property called iTime would compile into a duplicate declaration and take
    the whole wallpaper down. This is the test that says it cannot happen."""
    names = {n for n, _ in B.uniform_decls(s)}
    assert names.isdisjoint(B._RESERVED)


@pytest.mark.parametrize("name", ["iTime", "iResolution", "qt_Opacity", "main", "texture2D"])
def test_named_reserved_words_are_dropped(name):
    assert B.uniform_decls({name: {"type": "slider", "value": 1}}) == []


@pytest.mark.parametrize("name", ["bad name", "2start", "has-dash", "", "x" * 40, "a;b"])
def test_names_that_are_not_identifiers_are_dropped(name):
    assert B.uniform_decls({name: {"type": "slider", "value": 1}}) == []


@pytest.mark.parametrize("ctype", ["textbox", "file", "button", "label"])
def test_control_types_with_no_glsl_meaning_are_dropped(ctype):
    assert B.uniform_decls({"thing": {"type": ctype, "value": "x"}}) == []


def test_vec4_is_declared_before_float():
    decls = B.uniform_decls({"f": {"type": "slider", "value": 1}, "c": {"type": "color", "value": "#fff"}})
    assert [t for _, t in decls] == ["vec4", "float"]


# ---- wrap -------------------------------------------------------------------
def test_a_qt_shaped_shader_is_passed_through_untouched():
    assert B.wrap(QT_SHAPED, []) == QT_SHAPED


def test_a_shadertoy_shader_gets_a_version_and_a_main():
    out = B.wrap(TOY, [])
    assert out.startswith("#version 440")
    assert "void main()" in out and TOY in out


def test_the_template_placeholder_never_survives_into_the_output():
    """It once appeared inside the template's own header comment, and the percent
    format spliced uniform declarations into a comment and broke the next line."""
    out = B.wrap(TOY, [("uGlow", "float")])
    assert "%(props)s" not in out
    assert "float uGlow;" in out


@given(schema)
@settings(max_examples=60)
def test_wrapping_never_raises_and_declares_each_uniform_once(s):
    out = B.wrap(TOY, B.uniform_decls(s))
    for name, glsl in B.uniform_decls(s):
        assert out.count(" %s;" % name) == 1


# ---- cache ------------------------------------------------------------------
def test_cache_key_is_stable_and_content_addressed():
    assert B.cache_key("a") == B.cache_key("a")
    assert B.cache_key("a") != B.cache_key("b")


def test_cache_dir_follows_xdg(monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg-test")
    assert B.cache_dir() == "/tmp/xdg-test/luminos/wallpaper-shaders"


# ---- bake: the failure paths are the ones a user actually meets --------------
def test_a_missing_shader_is_a_sentence_not_a_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    ok, msg = B.bake(str(tmp_path / "nope.frag"))
    assert not ok and "cannot read" in msg and "\n" not in msg


def test_malformed_properties_json_is_named(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    frag = tmp_path / "a.frag"; frag.write_text(TOY)
    bad = tmp_path / "a.properties.json"; bad.write_text("{ not json")
    ok, msg = B.bake(str(frag), str(bad))
    assert not ok and "not valid JSON" in msg


def test_a_missing_compiler_says_which_package(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    frag = tmp_path / "a.frag"; frag.write_text(TOY)
    ok, msg = B.bake(str(frag), None, qsb=str(tmp_path / "no-qsb"))
    assert not ok and "qt6-shadertools" in msg


def test_first_error_picks_the_compiler_line():
    assert "no matching" in B._first_error("warning: x\nERROR: 1:2: no matching overload\nmore")
    assert B._first_error("") == "shader failed to compile"


QSB = os.path.exists(B._QSB)


@pytest.mark.skipif(not QSB, reason="qsb not installed here")
def test_a_real_shadertoy_shader_compiles_and_caches(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    frag = tmp_path / "a.frag"; frag.write_text(TOY)
    props = tmp_path / "a.properties.json"
    props.write_text(json.dumps({"uGlow": {"type": "slider", "value": 1.0},
                                 "uTint": {"type": "color", "value": "#fff"},
                                 "iTime": {"type": "slider", "value": 1.0}}))
    ok, first = B.bake(str(frag), str(props))
    assert ok, first
    assert first.endswith(".qsb") and os.path.exists(first)
    ok, second = B.bake(str(frag), str(props))
    assert ok and second == first          # content-addressed: no recompile


@pytest.mark.skipif(not QSB, reason="qsb not installed here")
def test_a_broken_shader_fails_with_the_compilers_own_words(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    frag = tmp_path / "b.frag"
    frag.write_text("void mainImage(out vec4 c, in vec2 f) { c = no_such_fn(1.0); }")
    ok, msg = B.bake(str(frag))
    assert not ok and "no_such_fn" in msg and "\n" not in msg
