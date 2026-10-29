# GIT SECRET CLEANUP RUNBOOK — SUPERVISED MAINTENANCE PROCEDURE

**Target Repository:** `rajeshri-shahu-mandi-erp`  
**Remote URL:** `https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp.git`  
**Document Classification:** Confidential Release-Engineering Runbook  
**Execution Status:** **DOCUMENTED ONLY — DO NOT EXECUTE AUTOMATICALLY**  

---

## 1. Safety & Authorization Boundary

> [!WARNING]
> **Strict Authorization Policy:**  
> This runbook is a documented operational procedure for the human repository administrator.  
> **Do not execute these commands within automated AI agent sessions.**  
> Git history rewriting changes commit hashes across the repository and requires coordinated team notification, force-push permissions, and collaborator branch re-basing.

---

## 2. Forensic Audit & Affected Commits

### 2.1 Scope of Exposure
- **Compromised Secret:** Vendor Ed25519 private signing key.
- **Introduction Commit:** `7390ac0f2f36f2705eb5b9ae170465019b2a3cf0` (2026-10-29 11:32:59 +0530)
- **Subject:** `feat(security): implement commercial ed25519 licensing, role isolation, and session hardening`
- **Remediation Commit (Working Tree):** `c684b0fc74dd4ecb4858115ccedf1b624de69f6b` (2026-10-29 12:30:48 +0530)
- **Subject:** `fix(security): resolve vendor key exposure, blacklist retired key, and harden session & route authorization`

### 2.2 Files Containing the Historical Secret in Commit `7390ac0`
1. `vendor_license_issuer.py` (added in `7390ac0` with hardcoded private key; sanitized in `c684b0f`).
2. `LICENSING_SECURITY_IMPLEMENTATION_REPORT.md` (added in `7390ac0` with key in Section 2.1; redacted in `c684b0f`).

### 2.3 Branch and Tag Topology
- **Branches:** `main` (tracking `origin/main`).
- **Tags:** None currently exist.
- **Upstream Remotes:** `origin` (`https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp.git`).

---

## 3. Pre-Requisites & Safe Backup Procedure

Before executing any history rewriting, create an immutable, full backup outside the working directory.

### Step 3.1: Create Timestamped Mirror Backup
Run in an isolated operator shell (PowerShell or Bash):
```bash
# 1. Navigate to a secure backup directory outside project root
cd C:\projects\backups\

# 2. Create a bare mirror backup of the entire repository
git clone --mirror https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp.git rajeshri-shahu-mandi-erp-mirror-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').git

# 3. Create a secondary working tree backup
git clone https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp.git rajeshri-shahu-mandi-erp-pre-clean-backup
```

### Step 3.2: Verify Tooling Availability
Ensure `git-filter-repo` is installed:
```bash
python -m pip install --user git-filter-repo
git filter-repo --version
```

---

## 4. Git-Filter-Repo Execution Procedure

### Step 4.1: Fresh Dedicated Clean Clone
Always execute history rewriting on a fresh, isolated clone to avoid pushing uncommitted local files or corrupting active workspaces:
```bash
cd C:\projects\temp_cleanup\
git clone https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp.git repo-cleanup
cd repo-cleanup
```

### Step 4.2: Scrub the Target File from Entire History
Because `vendor_license_issuer.py` is an internal vendor tool and was added to `.gitignore`, completely purge it from all historical commits:
```bash
# Completely remove vendor_license_issuer.py from historical tree
git filter-repo --path vendor_license_issuer.py --invert-paths --force
```

### Step 4.3: Redact Secret Occurrences from Historical Reports
To scrub the secret string from `LICENSING_SECURITY_IMPLEMENTATION_REPORT.md` across commits without deleting the documentation file:
Create a replacement expressions file `replace_secrets.txt`:
```
# Format: regex:pattern==>replacement
regex:[0-9a-fA-F]{64}==>[REDACTED_VENDOR_PRIVATE_KEY]
```
Execute replacement filter:
```bash
git filter-repo --replace-text replace_secrets.txt --force
```

---

## 5. Non-Disclosing Verification Commands

Verify that the compromised secret no longer exists in any commit object, tree, or blob **without ever printing the secret string**:

```bash
# 1. Verify vendor_license_issuer.py does not exist in any historical commit
git log --all --full-history -- "vendor_license_issuer.py"
# Output MUST be completely blank

# 2. Verify no references to vendor_license_issuer remain in git tree objects
git rev-list --all | git diff-tree --stdin --name-only -r | findstr "vendor_license_issuer"
# Output MUST be completely empty

# 3. Search for known vendor key hashes/patterns safely using count check
python -c "
import subprocess
out = subprocess.check_output(['git', 'log', '-p', '--all'], encoding='utf-8', errors='ignore')
# Count occurrences of retired key substring prefix
found = '569a71904257' in out
print('Secret Present in Git History:', found)
assert not found, 'CRITICAL: Secret still present in history!'
print('Verification PASSED: History is 100% clean.')
"
```

---

## 6. Coordinated Remote Update & Collaborator Procedure

### Step 6.1: Force Push Cleaned History to GitHub
```bash
# Add origin remote back (git-filter-repo removes remotes for safety)
git remote add origin https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp.git

# Force-push updated main branch
git push origin --force --all
```

### Step 6.2: Purge GitHub Server-Side Cached Refs
GitHub retains unreachable commits in internal cache for up to 90 days. To permanently purge them from GitHub storage:
1. Contact GitHub Support or use GitHub Repository Settings:
   - Temporarily disable repository pull requests/issues caching if available.
2. In GitHub Organization settings, check **Secret Scanning Alerts** and close any associated alert with resolution *"Revoked / Rotated"*.

### Step 6.3: Collaborator Re-Cloning Instructions
Inform all team members to discard their local working copies and re-clone:
```bash
# Collaborators must NOT pull (pulling merges the old dirty history back in)
# Discard local clone and re-clone fresh:
cd C:\projects\tests\
rmdir /s /q "commoditi software"
git clone https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp.git "commoditi software"
```

---

## 7. Handling Forks, Residual References & Pull Requests

- **Forks:** If any collaborator or contractor previously forked the repository on GitHub, those forks will retain the old commit until the fork owners either delete their fork or force-push the cleaned history. Check with all authorized collaborators.
- **GitHub Pull Requests:** If pull requests were opened against commit `7390ac0`, close those PRs without merging and open fresh ones from the cleaned `main` branch.
