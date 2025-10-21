# Live Menu Testing Scripts

Skrypty do testowania parsera menu BragerOne z rzeczywistymi danymi z Twojego konta.

## 🚀 Szybki Start

### 1. Konfiguracja

```bash
# Skopiuj i edytuj plik środowiskowy
cp .env.example .env

# Edytuj .env i ustaw swoje credentials:
# PYBO_EMAIL=twoj@email.com
# PYBO_PASSWORD=twoje_haslo
# PYBO_OBJECT_ID=439  # opcjonalne - konkretny obiekt do testowania
```

### 2. Uruchomienie testów

```bash
# Test główny z prawdziwymi danymi
poetry run python scripts/test_live_menu.py

# Analiza wyników
poetry run python scripts/analyze_results.py
```

## 📁 Struktura plików

```
scripts/
├── test_live_menu.py          # Główny skrypt testowania live
├── analyze_results.py         # Analiza wyników testów
├── live_test_results/         # Katalog z wynikami (tworzony automatycznie)
│   ├── live_test_results_device_0.json
│   └── live_test_results_device_439.json
└── README_live_testing.md     # Ta dokumentacja
```

## 🔍 Co testujemy?

### Bezpieczeństwo 🔐
- Czy parser poprawnie filtruje parametry według uprawnień użytkownika?
- Czy parametry wrażliwe są ukryte przed nieupoważnionymi użytkownikami?
- Jaka jest efektywność filtrowania (% ukrytych tokenów)?

### Dokładność 📊
- Czy sparsowana struktura menu odpowiada rzeczywistej aplikacji?
- Czy wszystkie dostępne parametry są wykrywane?
- Czy hierarchia tras jest poprawna?

### Kompletność 🎯
- Testowanie różnych wartości `device_menu` (0 vs konkretny obiekt)
- Porównanie menu z filtrami uprawnień vs bez filtrów
- Analiza tokenów parametrów i tras nawigacyjnych

## 📊 Interpretacja wyników

### Pliki JSON
Każdy test generuje plik `live_test_results_device_{ID}.json` zawierający:

```json
{
  "test_info": {
    "timestamp": 1234567890.123,
    "user_email": "test@example.com",
    "log_level": "INFO"
  },
  "device_menu": 0,
  "object_info": {
    "id": 439,
    "name": "Nazwa obiektu"
  },
  "permissions": {
    "user_permissions": [...],
    "object_permissions": [...]
  },
  "menu_all": {
    "routes_count": 50,
    "tokens": ["token1", "token2", ...],
    "sample_route": {...}
  },
  "menu_filtered": {
    "routes_count": 30,
    "tokens": ["token1", "token3", ...],
    "sample_route": {...}
  },
  "security_analysis": {
    "total_tokens": 100,
    "visible_tokens": 75,
    "hidden_tokens": 25,
    "hidden_token_list": [...],
    "filter_efficiency_percent": 25.0
  }
}
```

### Kluczowe metryki

- **Total tokens**: Wszystkie parametry dostępne w systemie
- **Visible tokens**: Parametry dostępne dla Twojego konta
- **Hidden tokens**: Parametry ukryte przez filtry bezpieczeństwa
- **Filter efficiency**: % ukrytych tokenów (wyższe = lepsze bezpieczeństwo)

### Ocena bezpieczeństwa

- ✅ **Dobra** (>20% tokenów ukrytych): Silne filtrowanie bezpieczeństwa
- ⚠️ **Umiarkowana** (5-20% ukrytych): Moderate security filtering  
- ❌ **Wymaga uwagi** (<5% ukrytych): Słabe lub brak filtrowania

## ✅ Lista kontrolna weryfikacji

### Automatyczna weryfikacja (przez skrypty)
- [x] Połączenie z API i logowanie
- [x] Pobieranie uprawnień użytkownika i obiektów
- [x] Parsowanie struktury menu
- [x] Filtrowanie według uprawnień
- [x] Analiza efektywności bezpieczeństwa

### Manualna weryfikacja (przez Ciebie)
- [ ] Zaloguj się do aplikacji BragerOne
- [ ] Przejdź do sekcji parametrów/konfiguracji
- [ ] Porównaj widoczne parametry z `visible_tokens` w JSON
- [ ] Sprawdź czy `hidden_tokens` są rzeczywiście niedostępne
- [ ] Zweryfikuj hierarchię menu z aplikacją

## 🔧 Rozwiązywanie problemów

### Błędy logowania
```bash
# Sprawdź credentials w .env
grep PYBO_ .env

# Sprawdź czy zmienne są załadowane
poetry run python -c "import os; print(f'Email: {os.getenv(\"PYBO_EMAIL\")}')"
```

### Problemy z Index URL
Skrypt automatycznie próbuje alternatywne URL-e:
- `https://one.brager.pl/assets/index-{object_id}.js`
- `https://one.brager.pl/assets/index-main.js`
- `https://one.brager.pl/assets/index.js`

### Debug Mode
```bash
# Więcej szczegółów w logach
echo "LOG_LEVEL=DEBUG" >> .env
poetry run python scripts/test_live_menu.py
```

### Analiza konkretnego obiektu
```bash
# Ustaw konkretny obiekt w .env
echo "PYBO_OBJECT_ID=439" >> .env
poetry run python scripts/test_live_menu.py
```

## 🎯 Następne kroki

Po pomyślnym teście:

1. **Jeśli wszystko działa** ✅
   - Parser jest gotowy do integracji z aplikacją
   - Można przejść do implementacji cache'owania
   - Rozważyć optymalizacje wydajności

2. **Jeśli są rozbieżności** ❌
   - Porównaj szczegółowo JSON z aplikacją
   - Zidentyfikuj brakujące lub dodatkowe parametry
   - Sprawdź logikę filtrowania uprawnień
   - Dostosuj parser według potrzeb

3. **Bezpieczeństwo** 🔐
   - Sprawdź czy nie ma wycieków uprawnień
   - Zweryfikuj że wszystkie wrażliwe parametry są ukryte
   - Przetestuj z różnymi rolami użytkowników jeśli możliwe

## 📞 Wsparcie

Jeśli napotkasz problemy:
1. Sprawdź logi w terminalu
2. Przejrzyj wygenerowane pliki JSON
3. Uruchom `analyze_results.py` dla szczegółowej analizy
4. Porównaj wyniki z rzeczywistą aplikacją