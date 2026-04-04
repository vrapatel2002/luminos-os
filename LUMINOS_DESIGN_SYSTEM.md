# LUMINOS OS — DESIGN SYSTEM
# Version: 1.0
# This file is the visual source of truth for all agents.
# Every UI decision lives here. No hardcoded values anywhere in code.
# For feature decisions read LUMINOS_PROJECT_SCOPE.md
# For why decisions were made read LUMINOS_DECISIONS.md

---

## THE VIBE
Classy, minimal, futuristic. Think macOS discipline meets high-end gaming.
Not flashy. Not busy. Everything has a reason to exist.
If a UI element does not need to be there — remove it.

---

## COLOR PALETTE

### Base
```
Background base:       #0A0A0F   (near black, slight blue tint — desktop bg)
Surface:               #13131A   (panels, windows, cards)
Surface elevated:      #1C1C26   (dock, tooltips, dropdowns)
Surface overlay:       rgba(255, 255, 255, 0.06)  (blur overlay on glass)
```

### Accent — Electric Blue (Default)
```
Accent primary:        #0080FF
Accent hover:          #0066CC
Accent pressed:        #0052A3
Accent glow:           rgba(0, 128, 255, 0.4)
Accent subtle:         rgba(0, 128, 255, 0.12)   (backgrounds, badges)
```

### Text
```
Text primary:          #FFFFFF
Text secondary:        #8888AA
Text disabled:         #444466
Text on accent:        #FFFFFF
```

### Borders
```
Border default:        rgba(255, 255, 255, 0.08)
Border focus:          rgba(0, 128, 255, 0.6)
Border subtle:         rgba(255, 255, 255, 0.04)
```

### Status Colors
```
Success:               #00C896
Warning:               #FFB020
Error:                 #FF4455
Info:                  #0080FF   (same as accent)
```

### Future Accent Options (not active yet — add to Appearance settings later)
```
Deep Purple:           #7B2FFF
Teal/Cyan:             #00C8C8
Amber/Gold:            #FFB020
Soft White:            #E8E8F0
```

---

## TYPOGRAPHY

### Font
```
Primary font:          Inter
Fallback:              system-ui, -apple-system, sans-serif
Install command:       sudo pacman -S ttf-inter
```

### Scale
```
Display (clock):       80px   weight 300   letter-spacing -2px
Heading 1:             32px   weight 600   letter-spacing -0.5px
Heading 2:             24px   weight 600   letter-spacing -0.3px
Heading 3:             18px   weight 500
Body large:            16px   weight 400
Body:                  14px   weight 400
Body small:            13px   weight 400
Caption:               12px   weight 400   text secondary color
Label:                 11px   weight 500   uppercase letter-spacing 0.5px
```

---

## SPACING

### Base Grid: 8px
```
4px   — micro (icon padding, tight gaps)
8px   — small (between related items)
12px  — base (standard component padding)
16px  — medium (section gaps, card padding)
24px  — large (between sections)
32px  — xl (major layout gaps)
48px  — 2xl (page margins)
```

---

## SHAPE & RADIUS

```
Sharp (maximized windows):     0px
Small (badges, tags):          4px
Medium (buttons, inputs):      8px
Default (panels, cards):       12px
Large (dock, modals):          16px
Full (pills, toggles):         999px
```

### Rule
Floating windows = 12px radius
Maximized windows = 0px radius (no radius when full screen)
Dock = 16px radius pill shape
Buttons = 8px radius
Inputs = 8px radius
Modals/dialogs = 12px radius

---

## BLUR & GLASS EFFECT

```
Blur strength:         blur(20px)
Glass overlay:         rgba(255, 255, 255, 0.06)
Glass border:          rgba(255, 255, 255, 0.08)
```

### How to apply glass effect
```css
background: rgba(28, 28, 38, 0.8);
backdrop-filter: blur(20px);
border: 1px solid rgba(255, 255, 255, 0.08);
```

### Where glass is used
- Dock
- Top bar
- Settings panels
- Login screen input field
- Notification toasts
- Right-click menus
- Dropdowns

### Where glass is NOT used
- Maximized windows (solid surface color instead)
- Full screen apps
- Anything that needs to perform at 60fps under heavy GPU load

---

## ANIMATIONS

### Timing
```
Instant:               0ms    (state changes that feel snappy)
Fast:                  100ms  (hover effects, small transitions)
Default:               200ms  (most UI transitions)
Slow:                  350ms  (page/panel transitions, modals)
```

### Easing
```
Default:               cubic-bezier(0.4, 0, 0.2, 1)   (material standard)
Enter:                 cubic-bezier(0.0, 0, 0.2, 1)   (decelerate)
Exit:                  cubic-bezier(0.4, 0, 1, 1)     (accelerate)
Spring:                cubic-bezier(0.34, 1.56, 0.64, 1) (bouncy, use sparingly)
```

### Rules
- Every interactive element must have a hover state
- Every click must have a pressed state
- No janky instant jumps — everything transitions
- Animations must not block interaction
- If performance drops — reduce blur first, then animations

---

## COMPONENTS

### Dock
```
Style:           Frosted glass pill
Height:          64px
Icon size:       48px
Icon padding:    12px between icons
Corner radius:   16px
Position:        Centered, bottom, 20px from screen edge
Hover:           Icon scales 1.1x + subtle blue glow beneath
Active app:      Small blue dot 4px below icon
Separator:       1px rgba(255,255,255,0.08) between pinned and running
Labels:          Hidden by default, show on hover
```

### Top Bar
```
Height:          36px
Style:           Frosted glass, full width
Left:            Workspace dots indicator
Center:          Clock — HH:MM, body large, text primary
Right:           Wifi + battery + volume icons — 16px each
Bottom border:   rgba(255, 255, 255, 0.06)
No window title in bar
```

### Windows
```
Floating:        12px radius, blur enabled, blue border on focus
Maximized:       0px radius, no blur, no border radius
Shadow:          0px 8px 32px rgba(0, 128, 255, 0.15)
Focused border:  1px rgba(0, 128, 255, 0.6)
Unfocused:       1px rgba(255, 255, 255, 0.06)
```

### Buttons
```
Primary:
  Background:    #0080FF
  Hover:         #0066CC
  Pressed:       #0052A3
  Text:          #FFFFFF
  Radius:        8px
  Height:        36px
  Padding:       0px 16px

Secondary:
  Background:    rgba(255, 255, 255, 0.06)
  Hover:         rgba(255, 255, 255, 0.1)
  Border:        rgba(255, 255, 255, 0.08)
  Text:          #FFFFFF
  Radius:        8px

Destructive:
  Background:    rgba(255, 68, 85, 0.15)
  Hover:         rgba(255, 68, 85, 0.25)
  Border:        rgba(255, 68, 85, 0.4)
  Text:          #FF4455
```

### Input Fields
```
Background:      rgba(255, 255, 255, 0.06)
Border:          rgba(255, 255, 255, 0.08)
Border focus:    rgba(0, 128, 255, 0.6)
Radius:          8px
Height:          40px
Padding:         0px 12px
Text:            #FFFFFF
Placeholder:     #8888AA
Font:            Inter 14px
```

### Settings Panels
```
Background:      #13131A
Sidebar width:   220px
Panel padding:   24px
Section gap:     24px
Item height:     44px
Item radius:     8px
Item hover:      rgba(255, 255, 255, 0.06)
Active item:     rgba(0, 128, 255, 0.12) + left border #0080FF 2px
Dividers:        rgba(255, 255, 255, 0.06)
```

### Toggles / Switches
```
Track off:       rgba(255, 255, 255, 0.12)
Track on:        #0080FF
Thumb:           #FFFFFF
Width:           40px
Height:          22px
Radius:          999px (full pill)
```

### Notification Toasts
```
Style:           Frosted glass pill
Max width:       360px
Padding:         12px 16px
Radius:          12px
Position:        Top right, 16px from edges
Stack gap:       8px
Auto dismiss:    5 seconds default
```

### Sliders
```
Track:           rgba(255, 255, 255, 0.12)
Fill:            #0080FF
Thumb:           #FFFFFF, 16px circle
Height:          4px track
```

### Dropdowns / Menus
```
Background:      #1C1C26
Border:          rgba(255, 255, 255, 0.08)
Radius:          12px
Padding:         4px
Item height:     36px
Item padding:    0px 12px
Item hover:      rgba(255, 255, 255, 0.06)
Item radius:     8px
Shadow:          0px 8px 24px rgba(0, 0, 0, 0.4)
```

---

## LOGIN SCREEN

```
Background:      Full screen blurred wallpaper
                 Fallback: #0A0A0F if no wallpaper
Blur:            blur(40px) + rgba(0,0,0,0.4) overlay

Clock:
  Font:          Inter 80px weight 300
  Color:         #FFFFFF
  Position:      Center screen, slightly above middle
  Letter-spacing: -2px

Date:
  Font:          Inter 16px weight 400
  Color:         #8888AA
  Position:      8px below clock
  Format:        Tuesday, April 04 2026

Password input (hidden until Enter pressed):
  Animation:     Slides up 200ms ease, fade in
  Width:         320px
  Height:        48px
  Background:    rgba(255, 255, 255, 0.08)
  Backdrop:      blur(20px)
  Border:        rgba(255, 255, 255, 0.12)
  Border focus:  rgba(0, 128, 255, 0.6)
  Radius:        12px
  Text:          centered, #FFFFFF, Inter 16px
  Placeholder:   "Enter password"
  Color:         #8888AA
```

---

## WALLPAPER SETTINGS (Simple — No Exceptions)

```
Layout:          Grid of thumbnails — 3 columns
Thumbnail size:  Fit the grid, maintain aspect ratio
Click:           Applies wallpaper immediately, no confirm needed
Add own:         Single "+" card at end of grid, opens file picker
Accepted types:  jpg, png, webp, mp4, webm, gif
Toggle:          "Static" / "Video" filter above grid — that is all
No:              Blur sliders, stretch modes, per-monitor settings,
                 fit/fill/stretch options, any other settings
```

---

## RULES FOR ALL AGENTS

```
1. Every color value must come from luminos_theme.py — never hardcode
2. Inter font everywhere — no exceptions
3. Every interactive element needs hover + pressed states
4. Glass effect only where listed — not everywhere
5. Rounded corners on floating, sharp on maximized — always
6. Animations must use the timing values above — no custom values
7. When in doubt about a visual decision — refer to this document
8. If this document does not cover it — ask Sam before deciding
9. Do not add visual complexity — if simpler works, use simpler
10. Every component must look intentional, not accidental
```
