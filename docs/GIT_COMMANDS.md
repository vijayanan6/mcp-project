# Git Commands Used in This Project

A reference of every Git command used while building the MCP Learning Project,
with explanations of when and why each was used.

---

## One-Time Setup

These commands were run once at the start of the project.

```powershell
# Tell Git who you are (shown on every commit)
git config --global user.name "Your Name"
git config --global user.email "your@email.com"

# Turn the project folder into a Git repository
git init

# Connect local repo to GitHub
git remote add origin https://github.com/vijayanan6/mcp-project.git

# Rename the default branch to "main" and push for the first time
git branch -M main
git push -u origin main
```

---

## Daily Workflow

These three commands were used every time a change was made.

```powershell
# 1. See what files changed (run this first every time)
git status

# 2. Stage all changes for the next commit
git add .

# 3. Save a snapshot with a description
git commit -m "feat: describe what you built"

# 4. Upload to GitHub
git push origin main
```

### Commit message format used in this project

```
feat: add SQLite database for persistence
feat: add RAG with ChromaDB for semantic search
docs: update README with final architecture
docs: add LEARNING_JOURNEY.md
fix: resolve SSL certificate error on Windows
```

`feat:` = new feature
`docs:` = documentation only
`fix:` = bug fix

---

## Branching

Feature branches were used to keep `main` always working while
building new features.

```powershell
# Create a new branch and switch to it immediately
git checkout -b feature/sqlite-database

# Switch to an existing branch
git checkout feature/sqlite-database

# Switch back to main
git checkout main

# See all branches (* shows current branch)
git branch

# Merge a finished feature branch into main
git merge feature/sqlite-database

# Push a branch to GitHub (first time)
git push -u origin feature/sqlite-database
```

### Branches created in this project

```powershell
git checkout -b feature/sqlite-database    # Phase 5 — SQLite persistence
git checkout -b feature/rag-chromadb       # Phase 6 — RAG + ChromaDB
```

---

## Checking and Inspecting

```powershell
# See where the remote (GitHub) is pointing
git remote -v

# See commit history (one line per commit)
git log --oneline

# See last 5 commits only
git log --oneline -5

# See exactly what changed in files (before staging)
git diff

# See what's staged and ready to commit
git diff --staged
```

---

## The Full Workflow Used in This Project

Every feature followed this exact pattern:

```powershell
# Step 1 — Create a branch
git checkout -b feature/name

# Step 2 — Write the code
# ... edit files ...

# Step 3 — Check what changed
git status

# Step 4 — Stage everything
git add .

# Step 5 — Commit with a clear message
git commit -m "feat: describe the change"

# Step 6 — Push the branch to GitHub
git push -u origin feature/name

# Step 7 — Merge into main
git checkout main
git merge feature/name

# Step 8 — Push main to GitHub
git push origin main
```

---

## Commit History of This Project

```
ae049f1  docs: add TUTORIAL.md beginner teaching guide with exercises
b341bda  docs: add INSIGHTS.md with final project learnings
fa13166  docs: rewrite ARCHITECTURE.md as plain readable format
8785335  docs: add ARCHITECTURE.md with Mermaid diagrams for copilot tools
fc886e0  docs: update CLAUDE.md and README.md with full current state
677d7ac  docs: update project notes with all phases and final architecture
620a642  docs: add full learning journey documentation across all phases
28b7a69  feat: add RAG with ChromaDB for semantic document search
f45961b  feat: prioritise docs before general knowledge in system prompt
798a14c  feat: replace in-memory storage with SQLite database
d9346db  Initial commit - MCP learning project
```

---

## Quick Reference Card

| Command | What it does |
|---|---|
| `git init` | Start tracking a folder |
| `git status` | See what changed |
| `git add .` | Stage all changes |
| `git commit -m "msg"` | Save a snapshot |
| `git push origin main` | Upload to GitHub |
| `git log --oneline` | See commit history |
| `git remote -v` | See GitHub connection |
| `git checkout -b name` | Create + switch to new branch |
| `git checkout main` | Switch back to main |
| `git branch` | List all branches |
| `git merge branch-name` | Merge a branch into current |
| `git diff` | See unstaged changes |
| `git pull` | Download latest from GitHub |

---

## Commit Signing (Security)

Every commit made on this machine is now signed with a dedicated SSH key, so
GitHub shows a "Verified" badge next to each commit — proof it actually came
from this machine and wasn't pushed by someone with a stolen token.

```powershell
# One-time setup (already done)
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/git_signing_key.pub
git config --global commit.gpgsign true
```

The public key was added to GitHub under Settings > SSH and GPG keys > New
SSH key, with Key type set to **Signing Key** (not Deploy key, and not
Authentication Key — those are different things). No extra steps needed for
day-to-day commits; signing happens automatically.

---

## Rules Learned

1. **Always run `git status` before committing** — know what you are saving
2. **Never commit directly to main for features** — use a branch
3. **Write meaningful commit messages** — future you will thank you
4. **`git push` after every merge** — keep GitHub in sync
5. **`.gitignore` protects sensitive files** — set it up before the first commit
