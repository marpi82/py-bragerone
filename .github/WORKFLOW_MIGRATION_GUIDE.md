# Workflow Migration Guide - Branch Protection Compatibility

## 🔍 Issue: Job Name Changes

### Current jobs in `ci.yml`

```text
- secrets
- lint
- typecheck
- tests
- docs-verify
- build
```

### New jobs in optimized workflow

```text
- secrets
- quality      ← CHANGE: merges lint + typecheck
- tests
- docs-verify
- build
```

## ⚠️ Impact on Branch Protection Rules

If you have branch protection rules requiring statuses:

- ❌ `lint` - **WILL NOT EXIST**
- ❌ `typecheck` - **WILL NOT EXIST**
- ✅ `quality` - **NEW STATUS**

## 🎯 Solutions (choose one)

### Option 1: Backward Compatible (RECOMMENDED) ⭐

Keep old job names for branch protection compatibility:

```yaml
jobs:
  secrets:
    name: secrets (gitleaks)
    # ...

  # Keep "lint" name for branch protection compatibility
  lint:
    name: quality (lint + typecheck)
    runs-on: ubuntu-latest
    steps:
      # ... all steps from quality

  # Alias job - redirects to lint
  typecheck:
    name: typecheck (→ lint)
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - run: echo "Typecheck executed in 'lint' job"

  tests:
    # ...

  docs-verify:
    # ...

  build:
    needs: [secrets, lint, typecheck, tests, docs-verify]
    # ...
```

**Benefits:**

- ✅ Zero changes to branch protection rules
- ✅ All existing statuses continue to work
- ✅ Optimization achieved (lint executes once, typecheck is just an alias)

**Drawbacks:**

- Less elegant (dummy job)
- Imprecise "lint" name (also does typecheck)

---

### Option 2: Clean Migration (requires rules update)

Introduce new names and update branch protection:

**Step 1: Add transition period**

```yaml
jobs:
  quality:
    name: quality (lint + typecheck)
    # ... new job

  # Aliases for backward compatibility - remove after migration
  lint:
    name: lint (deprecated → quality)
    needs: quality
    runs-on: ubuntu-latest
    steps:
      - run: echo "Moved to 'quality' job"

  typecheck:
    name: typecheck (deprecated → quality)
    needs: quality
    runs-on: ubuntu-latest
    steps:
      - run: echo "Moved to 'quality' job"
```

**Step 2: Update Branch Protection Rules**

- Settings → Branches → Branch protection rules
- Replace `lint` and `typecheck` with `quality`

**Step 3: Remove aliases after 1-2 weeks**

**Benefits:**

- ✅ Clean, modern workflow
- ✅ Better naming
- ✅ Full optimization

**Drawbacks:**

- Requires manual settings change
- Transition period with dummy jobs

---

### Option 3: Gradual Migration (best for production)

**Phase 1: Add new workflow in parallel**

```bash
# Keep ci.yml
# Add ci-v2.yml with new names
```

**Phase 2: Test new workflow**

- Create test branch
- Verify everything works

**Phase 3: Update branch protection**

- Add `quality` to required checks
- Remove `lint` and `typecheck` from required checks

**Phase 4: Replace ci.yml → ci-v2.yml**

**Benefits:**

- ✅ Zero downtime
- ✅ Safe migration
- ✅ Rollback possible

---

## 📋 Checklist: What to check before migration

```bash
# 1. Check current branch protection rules
gh api repos/:owner/:repo/branches/main/protection \
  --jq '.required_status_checks.contexts[]'

# 2. Check which statuses are currently required
# Look for: "lint", "typecheck"

# 3. After migration, check statuses
gh pr checks <PR_NUMBER>
```

## 🔧 Recommendations

Considering you're in alpha phase (release/2025a4):

### Variant A: If NO branch protection on main

→ **Use Option 2 (Clean Migration)** without transition aliases

### Variant B: If branch protection EXISTS

→ **Use Option 1 (Backward Compatible)** and change later

### Variant C: For maximum safety

→ **Use Option 3 (Gradual Migration)**

## 💡 Implementation Suggestion

Since you're on `release/2025a4` branch, I propose:

1. **Now**: Implement Option 1 (backward compatible)
2. **After merge to main**: Check branch protection rules
3. **After verification**: Decide if you want to switch to clean variant

Agreed?
