# 🚀 Live Testing - Quick Start

## Setup (30 sekund)

```bash
# 1. Konfiguruj credentials
cp .env.example .env
# Edytuj .env: ustaw PYBO_EMAIL i PYBO_PASSWORD

# 2. Uruchom test
poetry run python scripts/test_live_menu.py

# 3. Analizuj wyniki
poetry run python scripts/analyze_results.py
```

## Co sprawdzamy?

- 🔐 **Bezpieczeństwo**: Czy filtry uprawnień działają?
- 📊 **Dokładność**: Czy parser odpowiada rzeczywistej aplikacji?
- 🎯 **Kompletność**: Czy wszystkie parametry są wykryte?

## Kluczowe pliki

- `.env` - Twoje credentials (PYBO_EMAIL, PYBO_PASSWORD)
- `scripts/live_test_results/*.json` - Wyniki testów
- `scripts/README_live_testing.md` - Pełna dokumentacja

## Weryfikacja

1. Sprawdź wyniki w `scripts/analyze_results.py`
2. Zaloguj się do BragerOne app
3. Porównaj `visible_tokens` z tym co widzisz
4. Upewnij się że `hidden_tokens` są ukryte

## Red flags ❌

- `filter_efficiency_percent: 0` - brak bezpieczeństwa!
- `hidden_tokens` widoczne w aplikacji - problem!
- Różnice w strukturze menu