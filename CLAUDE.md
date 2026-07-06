# Project Guidelines — Claude

> Canonical guidance lives in [`AGENTS.md`](AGENTS.md). Claude Code
> reads `CLAUDE.md` by convention; this file is a thin pointer so the
> content can't drift between tools. The OpenAI Codex CLI reads
> `AGENTS.md` (and / or `CODEX.md`), Google Gemini CLI reads
> `GEMINI.md` — all of them mirror back to `AGENTS.md`.
>
> **Read `AGENTS.md` in full before making changes.** It covers:
>
> - Naming conventions (PascalCase themes, kebab-case IDs)
> - Plasmoid + branding rules (no "fork-of-X" language, no Pear OS refs)
> - macOS terminology mapping (Suggestions / Apps / Show All)
> - Installer entry points (`install` / `uninstall` / `installer`,
>   sudo policy, auto-update on install)
> - Distro detection layer (`src/scripts/distro.py`) — the ONLY place
>   per-distro paths or package manager commands are allowed
> - Preflight contract (9 fail-fast checks, Qt6 setuid guard)
> - Live theme switching (Kvantum cycle, LAF retry 2s + 6s + 6s)
> - All assets fully bundled offline — the pipeline has no download
>   phase
> - Dependency guards (kw_write returns, fc-cache, GRUB)
> - Container CI matrix (`tests/containers/`)
> - The "what NOT to do" list — read it twice

Open `AGENTS.md` and follow it.
