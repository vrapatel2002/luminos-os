# HIVE Popup — Visual Tuning Guide
<!-- [CHANGE: gemini-cli | 2026-04-27] Updated line numbers for native window changes -->

## Quick Reference
All tunable values are in: `src/hive/HiveChat.qml`

## Window
| What | Property | Line(s) | Default | Effect |
|------|----------|---------|---------|--------|
| Window width | `width:` | Line 14 | `820` | Wider/narrower popup |
| Window height | `height:` | Line 15 | `620` | Taller/shorter popup |
| Corner radius | `radius:` | Line 39 | `16` | Roundness of corners |
| Background color | `color:` | Line 38 | `"#FAF9F6"` | Base tone of entire window |
| Shadow blur/spread | `shadowBlur:` | Line 46 | `1.0` | Softness/spread of the drop shadow (0.0 to 1.0) |
| Shadow offset Y | `shadowVerticalOffset:` | Line 48 | `4` | How far the shadow drops down |

## Greeting
| What | Property | Line(s) | Default | Effect |
|------|----------|---------|---------|--------|
| Greeting font size | `font.pixelSize:` | Line 82 | `36` | Bigger/smaller greeting text |
| Accent color | `color:` | Line 74 | `"#D4784A"` | Color of the ✳ sparkle icon |
| Greeting text color | `color:` | Line 80 | `"#2D2B28"` | Color of "Morning, Sam" text |
| Greeting spacing | `spacing:` | Line 70 | `12` | Distance between sparkle and greeting |

## Input Bar
| What | Property | Line(s) | Default | Effect |
|------|----------|---------|---------|--------|
| Input background | `color:` | Line 233 | `"#FFFFFF"` | Background color of the text field |
| Corner radius | `radius:` | Line 234 | `26` | Roundness (pill shape) |
| Border width | `border.width:` | Line 235 | `1.5` | Thickness of the input box border |
| Border focus color | `border.color:` | Line 236 | `"#D4784A"` | Border color when actively typing |
| Placeholder color | `placeholderTextColor:` | Line 258 | `"#A39E96"` | Color of "How can I help you today?" |
| Bottom right label | `color:` | Line 292 | `"#B5B0A8"` | Color of "Nexus · HIVE" |

## Chat Messages
| What | Property | Line(s) | Default | Effect |
|------|----------|---------|---------|--------|
| User bubble bg | `color:` | Line 131 | `"#F0EDE8"` | Background color for user text bubbles |
| Message text color | `color:` | Line 152 | `"#2D2B28"` | Font color for both user and AI |
| Message font size | `font.pixelSize:` | Line 154 | `14` | Size of the chat messages |
| AI line height | `lineHeight:` | Line 157 | `1.6` | Spacing between lines of text in AI responses |
| Typing dot color | `color:` | Line 200 | `"#A39E96"` | Color of the bouncing loading dots |
| Chat view padding | `padding:` | Line 103 | `20` | Inner padding around message bubbles |

## Category Chips
| What | Property | Line(s) | Default | Effect |
|------|----------|---------|---------|--------|
| Chip hover background| `color:` | Line 328 | `"#F5F3EF"` | Color of the chip when mouse hovers over it |
| Chip hover border | `border.color:` | Line 330 | `"#D1CEC8"` | Border color on hover |
| Chip text color | `color:` | Line 342 | `"#5A5650"` | Font color of the chip labels |
| Gap between chips | `spacing:` | Line 310 | `8` | Distance between each chip |

## Animations
| What | Property | Line(s) | Default | Effect |
|------|----------|---------|---------|--------|
| Window open fade-in | `duration:` | Line 40 | `200` | MS to fade in the window |
| Window close fade-out| `duration:` | Line 377 | `150` | MS to fade out when closed |
| Greeting fade-out | `duration:` | Line 61 | `300` | MS for landing page to vanish on send |
| Chat view fade-in | `duration:` | Line 106 | `300` | MS for messages to appear |

## Color Palette Reference
| Name | Hex | Used For |
|------|-----|----------|
| Cream Background | `#FAF9F6` | Main window background |
| Warm Orange | `#D4784A` | Accents, active focus, send button active |
| Near Black | `#2D2B28` | Primary reading text |
| Warm Tan | `#F0EDE8` | User message bubbles |
| Light Border | `#E5E2DC` | Inactive borders, chips |
| Hover State | `#F5F3EF` | Chip hover, inactive send icon |

## How to Apply Changes
1. Edit `~/luminos-os/src/hive/HiveChat.qml`
2. Save the file
3. Press `SUPER+SPACE` twice (close + reopen) to see changes
   *(OR manually run: `qml6 ~/luminos-os/src/hive/HiveChat.qml`)*
