# Skill organization

Keep repository-local skill collections under `skills/` so multiple collections can coexist.

- Store Lester skills in `skills/lester-skills/<skill-name>/SKILL.md`.
- Store other skill collections in `skills/<collection-name>/<skill-name>/SKILL.md`.
- Keep shared Lester conventions in `skills/lester-skills/`, including this file.
- Do not create a top-level `lester-skills/` directory or mix other collections into it.
- Update agent instructions and documentation links when adding or moving skills.
- Apply this structure consistently in every project that carries Lester skills; change source repositories rather than generated build or staging copies.

Example:

```text
skills/
├── lester-skills/
│   ├── other-skills.md
│   └── communication-autonomy/
│       └── SKILL.md
└── another-collection/
    └── skill-name/
        └── SKILL.md
```
