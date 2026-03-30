# Project Guidelines

## Naming Convention
- PascalCase for theme names: `MacTahoeLiquidKde-Dark`, `MacTahoeLiquidKde-Light`
- kebab-case for IDs: `org.kde.mac-tahoe-liquid-kde.<component>`
- Plasmoid suffixes are simple nouns: `.menu`, `.launcher`, `.trashcan` — not compound words like `.kpplemenu`

## Plasmoids
- All plasmoids live in `src/offline/plasmoids/`
- They must be fully self-contained — no dependency on third-party compiled C++ plugins
- Exception: `org.kde.plasma.private.kicker` is OK (ships with plasma-workspace, always present)
- Launcher is forked from TahoeLauncher (EliverLara) — GPL-2.0 license kept as `LICENSE-TahoeLauncher`
- Menu plasmoid is 100% original

## Branding
- No external author references in metadata, configs, or QML headers — the user maintains attribution separately
- Mirror files keep source URLs (functional, not attribution)
- README Credits section is managed manually by the user
- Do NOT add "fork of X" or "based on Y" to README descriptions
- Do NOT reference Pear OS

## macOS Terminology
- "Recent Applications" → "Suggestions" (matches macOS naming)
- "Applications" → "Apps"
- "Show more" → "Show All"
- Menu items: About This Computer, System Settings, App Store, Force Quit, Sleep, Restart, Shut Down, Lock Screen, Log Out

## UI/UX Preferences
- No icons in the Menu plasmoid dropdown — text only, like macOS Apple menu
- Hover tiles: glass effect (semi-transparent fill, micro border 0.5px, 22px radius) — not outlined borders
- System font always — never hardcode font names or sizes
- Popup plasmoids: fixed size, not resizable
- Top panel: applets-only floating (not full floating)
- Category switcher: must support mouse drag AND wheel scroll

## Installer
- `install.sh` / `uninstall.sh` are the entry points
- `theme-switch.sh` handles light/dark switching including aurorae decorations
- Window decorations go through kwinrc `org.kde.kdecoration2` group
- Use `qdbus6` with fallback to `qdbus`
- Use `kwriteconfig6` for config changes
- Aurorae assembly: `decoration.svg` + `rc` + button icon SVGs + metadata per theme dir

## What NOT to Do
- Don't add scaled variants (1.25x, 1.5x) — keep only the base theme
- Don't use fullscreen Window overlays for launchers — use popup representations
- Don't add session/shutdown buttons inside the launcher — that's the Menu plasmoid's job
- Don't make commits referencing "Kmenu" or "Kpple" — use "Menu" and "Launcher"
