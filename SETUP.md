# Day 0 — Setup guide (first time with CLAUDE.md, skills and output styles)

~35 minutes. You already know the Claude Code chat in VS Code. This adds three things on top:

| Piece | What it is | Where | Effect |
|---|---|---|---|
| **CLAUDE.md** | Project memory: a file Claude Code reads automatically at the start of every session | repo root | Claude knows the project, the rules, and which code is yours to write, without you re-explaining each time |
| **Output style "Learning"** | A built-in mode where Claude explains its choices and leaves `TODO(human)` gaps for you | `.claude/settings.json` | You write the parts that matter; Claude does the plumbing |
| **Skills** (= custom slash commands) | Reusable instructions in `.claude/skills/<name>/SKILL.md` | `.claude/skills/` | `/next`, `/log-day`, `/new-scenario`, `/review-scenario` |

---

## 1. Create the repo (5 min)
1. Unzip this folder where you keep projects, and open it in VS Code.
2. In the terminal:
   ```bash
   git init && git add . && git commit -m "Project setup: roadmap, CLAUDE.md, skills"
   ```
   `.claude/settings.json` and `.claude/skills/` are meant to be committed. `.claude/settings.local.json` (your personal overrides) is git-ignored.

## 2. Check Claude Code picks everything up (10 min)
Open the Claude Code panel in VS Code (start a **new** conversation so it loads the files), then:

1. **CLAUDE.md:** ask *"What are the rules for this project, and which parts am I supposed to write myself?"*
   It should mention the ownership split and `TODO(human)`. If it doesn't, check that the file is at the repo root and that you opened the repo folder itself (not its parent).
2. **Output style:** type `/` → **Output styles**. **Learning** should be selected (it comes from `.claude/settings.json`).
   - If it isn't: select it there, or run `/output-style Learning`.
   - The value in `settings.json` is case-sensitive (`"Learning"`, not `"learning"`).
   - This needs a recent Claude Code version. If the menu isn't there, update the extension.
3. **Skills:** type `/` and look for `next`, `log-day`, `new-scenario`, `review-scenario`.
   - Run `/next`. It should answer with **Where you are: Day 0** and the next setup step, then ask "Shall I scaffold it?".
   - You don't need the slash. Asking *"what's next?"* in plain words should trigger the same skill, because its description tells Claude when to use it. `/log-day`, `/new-scenario` and `/review-scenario` only run when you call them explicitly, so they never fire by surprise.

## 3. Pick the dev model (10 min)
Check current free-tier limits and tool-calling support for one Gemini Flash-class model and one Groq-hosted model. Choose one, write it in `.env` (copy from `.env.example`), and record it in `PROGRESS.md` ("Dev model").

## 4. Close Day 0 (5 min)
Run `/log-day`, tick **CP0**, and set "Current day" to Day 1.

---

## How a normal day works

```
Start     New Claude Code conversation → "what's next?"
          → day briefing: concepts (the why) + interview questions + plan
          → first step

Working   "what's next?" → one step → "Shall I scaffold it?" → yes
          → Claude scaffolds and stops at a  ● Learn by Doing  request
          → you fill the TODO(human) in the file → tell Claude "done"
          → it runs the check, gives one Insight on your code, continues
          Stuck → "give me a hint for the TODO in loop.py"
          Want a deeper look → "review my agent/tools/logs.py"

Evening   /log-day → review the PROGRESS diff → write 1–2 paragraphs in docs/concepts.md
```

## Tips
- **Questions that aren't about the next step are fine:** "explain why we cap tool output", "is this a workflow or still an agent?". The mentor role lives in CLAUDE.md.
- **Start a fresh Claude Code conversation each day.** CLAUDE.md, PROGRESS.md and `/next` restore the context, and long sessions get slower and drift.
- **If Claude Code writes one of your parts:** say *"revert that to a TODO(human) with a hint"*. CLAUDE.md tells it to.
- **Learning mode feels slow for generated work** (target app, scenarios, UI)? Switch temporarily with `/output-style default`, then back with `/output-style Learning`.
- **Want it to explain less, or more?** Say so. Output style and CLAUDE.md are instructions, not hard rules, so they adapt to what you ask.

Docs: [Output styles](https://code.claude.com/docs/en/output-styles) · [Skills / slash commands](https://code.claude.com/docs/en/slash-commands) · [CLAUDE.md / memory](https://code.claude.com/docs/en/memory)
