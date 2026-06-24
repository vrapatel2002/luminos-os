# Luminos Theme — token pipeline
<!-- [CHANGE: claude-code | 2026-06-14] -->

**Single source of truth:** [`design/luminos-tokens.json`](../../design/luminos-tokens.json)
mirrored by the canonical QML component [`Theme.qml`](./Theme.qml). Edit these two
together — they are the only place visual values may live (per
`LUMINOS_DESIGN_SYSTEM.md` Rule 1, which previously pointed at the now-archived
`luminos_theme.py`).

## How it fans out

`scripts/luminos-theme-gen` reads the JSON (+ copies `Theme.qml`) and writes:

| Output | Consumer |
|---|---|
| each package's `contents/ui/Theme.qml` (verbatim copy) | Plasma plasmoids + HIVE QML |
| `config/kde/colors/Luminos.colors` | Qt / KDE apps |
| `config/gtk-3.0/gtk.css`, `config/gtk-4.0/gtk.css` | GTK + **libadwaita** (only lever that reaches it) |

Regenerate: `cd scripts/luminos-theme-gen && go run . -repo ~/luminos-os`
Verify in CI / pre-commit: `go run . -repo ~/luminos-os -check` (exit 1 if stale).

## QML usage (self-contained, no cross-module import)

`Theme.qml` is an **instantiable** `QtObject` (not a `pragma Singleton`), copied
into each package so there is no QML import-path runtime dependency:

```qml
Theme { id: theme }
...
color: theme.accent
radius: theme.radiusDefault
Behavior on x { NumberAnimation { duration: theme.durDefault
    easing.type: Easing.BezierSpline; easing.bezierCurve: theme.easeStandard } }
```

## Deploy / apply order (do AFTER the live training run — never mid-run)

1. `go run . -repo ~/luminos-os` (regenerate; repo-only).
2. Install plasmoids/KCMs as usual — each carries its own `Theme.qml`.
3. `cp config/kde/colors/Luminos.colors ~/.local/share/color-schemes/` then set
   `ColorScheme=Luminos` and reload (`plasma-apply-colorscheme Luminos`).
4. `cp config/gtk-{3,4}.0/gtk.css ~/.config/gtk-{3,4}.0/`.

Nothing here applies itself. No `kwriteconfig6`, no compositor reload.

## Open decision for Sam

HIVE ships a deliberate **warm** sub-palette (`hive*` tokens, accent `#D4784A`).
The system palette is electric blue `#0080FF`. Decide whether HIVE keeps its warm
identity or unifies to the system accent — both are expressible from the tokens;
nothing is lost. See `hive.$comment` in the JSON.
