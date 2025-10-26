# Workflow Migration Guide - Branch Protection Compatibility

## 🔍 Problem: Zmiana nazw jobów

### Obecne joby w `ci.yml`:
```
- secrets
- lint
- typecheck
- tests
- docs-verify
- build
```

### Nowe joby w `ci-optimized.yml`:
```
- secrets
- quality      ← ZMIANA: łączy lint + typecheck
- tests
- docs-verify
- build
```

## ⚠️ Impact na Branch Protection Rules

Jeśli masz branch protection rules wymagające statusów:
- ❌ `lint` - **NIE BĘDZIE ISTNIEĆ**
- ❌ `typecheck` - **NIE BĘDZIE ISTNIEĆ**
- ✅ `quality` - **NOWY STATUS**

## 🎯 Rozwiązania (wybierz jedno)

### Opcja 1: Backward Compatible (ZALECANE) ⭐

Zachowaj stare nazwy jobów dla kompatybilności z branch protection:

```yaml
jobs:
  secrets:
    name: secrets (gitleaks)
    # ...

  # Zachowaj nazwę "lint" dla branch protection compatibility
  lint:
    name: quality (lint + typecheck)
    runs-on: ubuntu-latest
    steps:
      # ... wszystkie kroki z quality

  # Alias job - przekierowuje do lint
  typecheck:
    name: typecheck (→ lint)
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - run: echo "Typecheck wykonany w jobie 'lint'"

  tests:
    # ...

  docs-verify:
    # ...

  build:
    needs: [secrets, lint, typecheck, tests, docs-verify]
    # ...
```

**Korzyści:**
- ✅ Zero zmian w branch protection rules
- ✅ Wszystkie istniejące statusy dalej działają
- ✅ Optymalizacja (lint wykonuje się raz, typecheck to tylko alias)

**Wady:**
- Mało eleganckie (dummy job)
- Nieprecyzyjna nazwa "lint" (robi też typecheck)

---

### Opcja 2: Clean Migration (wymaga aktualizacji rules)

Wprowadź nowe nazwy i zaktualizuj branch protection:

**Krok 1: Dodaj przejściowy okres**
```yaml
jobs:
  quality:
    name: quality (lint + typecheck)
    # ... nowy job

  # Aliasy dla backward compatibility - usuń po migracji
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

**Krok 2: Zaktualizuj Branch Protection Rules**
- Settings → Branches → Branch protection rules
- Zamień `lint` i `typecheck` na `quality`

**Krok 3: Usuń aliasy po 1-2 tygodniach**

**Korzyści:**
- ✅ Czysty, nowoczesny workflow
- ✅ Lepsze nazewnictwo
- ✅ Pełna optymalizacja

**Wady:**
- Wymaga ręcznej zmiany settings
- Przejściowy okres z dummy jobami

---

### Opcja 3: Stopniowa Migracja (najlepsza dla produkcji)

**Faza 1: Dodaj nowy workflow równolegle**
```bash
# Zachowaj ci.yml
# Dodaj ci-v2.yml z nowymi nazwami
```

**Faza 2: Przetestuj nowy workflow**
- Stwórz test branch
- Sprawdź, czy wszystko działa

**Faza 3: Zaktualizuj branch protection**
- Dodaj `quality` do required checks
- Usuń `lint` i `typecheck` z required checks

**Faza 4: Zastąp ci.yml → ci-v2.yml**

**Korzyści:**
- ✅ Zero downtime
- ✅ Bezpieczna migracja
- ✅ Rollback możliwy

---

## 📋 Checklist: Co sprawdzić przed migracją

```bash
# 1. Sprawdź obecne branch protection rules
gh api repos/:owner/:repo/branches/main/protection \
  --jq '.required_status_checks.contexts[]'

# 2. Sprawdź jakie statusy są obecnie required
# Szukaj: "lint", "typecheck"

# 3. Po migracji sprawdź statusy
gh pr checks <PR_NUMBER>
```

## 🔧 Moje rekomendacje dla Ciebie

Biorąc pod uwagę, że jesteś w fazie alpha (release/2025a4):

### Wariant A: Jeśli NIE masz branch protection na main
→ **Użyj Opcji 2 (Clean Migration)** bez przejściowych aliasów

### Wariant B: Jeśli MASZ branch protection
→ **Użyj Opcji 1 (Backward Compatible)** i zmień później

### Wariant C: Dla maksymalnego bezpieczeństwa
→ **Użyj Opcji 3 (Stopniowa Migracja)**

## 💡 Moja sugestia implementacji

Ponieważ jesteś na branchu `release/2025a4`, proponuję:

1. **Teraz**: Wprowadzam Opcję 1 (backward compatible)
2. **Po merge do main**: Sprawdzisz branch protection rules
3. **Po weryfikacji**: Zdecydujesz, czy chcesz przejść na clean variant

Tak?
