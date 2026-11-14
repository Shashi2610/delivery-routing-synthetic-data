# Project rules

## Code style
- Write clean, simple, readable Python. Prefer plain functions over clever abstractions.
- Use clear, descriptive names for variables and functions.
- Keep functions short and single-purpose.
- No inline comments or docstrings unless the logic is genuinely non-obvious. When needed, one short line explaining why, not what.
- No emojis, banners or decorative output in code or print statements.
- No unused imports, dead code or placeholder TODOs.
- Avoid heavy dependencies. Use only pandas, numpy and the standard library unless I ask.

## Project rules
- Local only. No hosting, no paid or external APIs.
- Seed 20261022 by default. All randomness goes through one seeded generator.
- Derived values are computed from source records, never generated independently.
- Never overwrite history. State changes are new event rows.
- Ground truth goes in ground_truth/ and must never leak into input tables.
- No secrets in the repo. Use .env (git-ignored) and keep .env.example updated.

## Git
- Do not run git commit or git push yourself. I will commit manually.
- If you ever write a commit message, do not add Co-Authored-By or any tool attribution lines.
- Suggest short, plain commit messages in imperative form (e.g. "Add router").

## Working style
- Do one step at a time and stop. Do not build ahead.
- Briefly explain key decisions and trade-offs after each step so I can document them.
- Ask me when requirements are unclear instead of guessing.
