# Ongoing Development & Git Update Guide

This repository is configured for clean, frictionless ongoing updates. Because local runtime SQLite files (`*.db*`) and virtual environments are excluded via `.gitignore`, running the backend locally or triaging alerts in the workbench will **never dirty your git tree with binary conflicts**.

---

## 1. Quick Routine: Making & Pushing Changes

Whenever you modify frontend components, backend services, or documentation:

```bash
# 1. Check changed files
git status

# 2. If you modified frontend files in web/src/, re-build the production dist
npm --prefix web run build

# 3. Run the automated test suite to verify 0 regressions
python3 -m unittest discover -s tests -q

# 4. Stage your changes
git add .

# 5. Commit with a meaningful message
git commit -m "feat(ui): update liquid glass alert drawer styling"

# 6. Push to GitHub
git push origin main
```

---

## 2. Pulling Remote Changes on Another Machine

```bash
# Pull latest code
git pull origin main

# Launch server immediately (SQLite database will auto-bootstrap in ~0.6s if not present)
make serve
# or:
PYTHONPATH=src python3 -m yottaflex.cli serve --scale full --port 8080
```

---

## 3. Modifying Synthetic Datasets or Re-exporting

If you adjust rules or generator seeds:

```bash
# Re-generate full dataset & update SQL seeds
make run-all SCALE=full SEED=20261022

# Verify reproducibility
make verify-repro SCALE=full

# Commit updated seeds & reports
git add data/exports/
git commit -m "data: refresh synthetic full dataset seeds and lift reports"
git push origin main
```
