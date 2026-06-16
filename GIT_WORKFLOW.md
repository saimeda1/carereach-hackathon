# Git Workflow for CareReach Project

## Quick Reference: Keeping Your GitHub Repo in Sync

You'll be making changes in Databricks and want to keep GitHub updated. Here's the simple workflow:

---

## 🔄 Daily Workflow (After Initial Setup)

### When You Make Changes:

1. **Edit your files** in Databricks (notebooks, app files, docs)
2. **Check what changed**:
   ```
   In Repos UI: Click on your repo → See "Modified" badge
   OR use Git Status button
   ```

3. **Commit & Push** (2 ways):

   **Option A: UI (Easiest)**
   - Click the Git icon (branch icon) in the repo toolbar
   - Review changed files
   - Enter commit message: e.g., "Updated trust scoring algorithm"
   - Click "Commit & Push"
   
   **Option B: Notebook Cell**
   ```python
   # In any notebook in your Git folder
   %sh
   cd /Repos/ganeshazure21@gmail.com/carereach-hackathon
   git add .
   git commit -m "Updated trust scoring algorithm"
   git push
   ```

4. **Verify on GitHub**:
   - Visit: https://github.com/saimeda1/carereach-hackathon
   - Refresh page → Your changes should appear!

---

## 📥 Pull Changes (If you edit on GitHub directly)

If you make changes on GitHub.com (edit README, etc.):

1. **In Databricks Repos UI**:
   - Click the Git icon → "Pull" button
   
2. **Or in a notebook**:
   ```python
   %sh
   cd /Repos/ganeshazure21@gmail.com/carereach-hackathon
   git pull
   ```

---

## 🎯 Common Scenarios

### Scenario 1: Updated your notebook

```bash
# Modified: Healthcare_Facility_Analysis.ipynb

Commit message: "Improved AI enrichment prompts for better trust scoring"
```

### Scenario 2: Updated the app

```bash
# Modified: app/app.py

Commit message: "Added new demand-supply visualization to dashboard"
```

### Scenario 3: Updated documentation

```bash
# Modified: README.md, ARCHITECTURE.md

Commit message: "Updated architecture docs with performance metrics"
```

### Scenario 4: Multiple files changed

```bash
# Modified: 
#   - notebooks/analysis.ipynb
#   - app/app.py
#   - README.md

Commit message: "Major update: new trust algorithm + app UI improvements + docs"
```

---

## 🚨 Handling Conflicts

If you get a merge conflict (rare):

1. **Pull first**:
   ```bash
   git pull
   ```

2. **Databricks will show conflicts**:
   - Open the conflicted file
   - Look for `<<<<<<<` markers
   - Choose which version to keep
   - Remove the conflict markers

3. **Commit the resolution**:
   ```bash
   git add .
   git commit -m "Resolved merge conflict in README"
   git push
   ```

---

## 💡 Best Practices

### ✅ DO:
- **Commit often** (after each logical change)
- **Write clear messages** ("What" and "Why")
- **Pull before starting work** (if others are collaborating)
- **Test before pushing** (run notebook cells, test app)

### ❌ DON'T:
- **Don't commit secrets** (.env files, API keys) - use .gitignore
- **Don't commit large data files** (CSVs, Parquet) - use .gitignore
- **Don't force push** (unless you really know what you're doing)
- **Don't commit broken code** (test first!)

---

## 📝 Commit Message Examples

### Good Messages:
```
✅ "Add deduplication logic to silver layer"
✅ "Fix trust score calculation for missing fields"
✅ "Update README with demo video link"
✅ "Improve agent prompt for better gap characterization"
```

### Bad Messages:
```
❌ "update"
❌ "fixed stuff"
❌ "changes"
❌ "asdfasdf"
```

---

## 🔧 Quick Commands Cheat Sheet

```bash
# Check status (what changed?)
git status

# See your changes
git diff

# Add all changes
git add .

# Commit with message
git commit -m "Your message here"

# Push to GitHub
git push

# Pull from GitHub
git pull

# See commit history
git log --oneline

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Discard all local changes (CAREFUL!)
git reset --hard HEAD
```

---

## 🎬 Example Full Workflow

```bash
# 1. Start your day - pull latest
cd /Repos/ganeshazure21@gmail.com/carereach-hackathon
git pull

# 2. Make changes in Databricks
#    (edit notebooks, app files, docs)

# 3. Check what you changed
git status
git diff

# 4. Stage and commit
git add .
git commit -m "Enhanced trust scoring with AI calibration factor"

# 5. Push to GitHub
git push

# 6. Verify on GitHub
#    Visit: https://github.com/saimeda1/carereach-hackathon
```

---

## 🆘 Troubleshooting

### Problem: "Permission denied" when pushing

**Solution**: Check your GitHub authentication
```bash
# Verify you're authenticated
git config --list | grep user

# If issues, re-link GitHub in Databricks:
# Settings → Linked Accounts → GitHub → Reconnect
```

### Problem: "Your branch is behind"

**Solution**: Pull first, then push
```bash
git pull
git push
```

### Problem: "Uncommitted changes" blocking pull

**Solution**: Commit or stash first
```bash
# Option 1: Commit them
git add .
git commit -m "Work in progress"
git pull

# Option 2: Stash them temporarily
git stash
git pull
git stash pop
```

---

## 🎓 Learning Resources

- **GitHub Basics**: https://guides.github.com/introduction/git-handbook/
- **Git Cheat Sheet**: https://education.github.com/git-cheat-sheet-education.pdf
- **Databricks Repos**: https://docs.databricks.com/repos/index.html

---

## 📞 Need Help?

If you run into Git issues:

1. Check the error message carefully
2. Search the error on Stack Overflow
3. Ask in Databricks Community
4. DM me (if working with a team)

---

**Remember**: Git is your safety net. Commit often, push regularly, and you'll never lose work! 🛡️