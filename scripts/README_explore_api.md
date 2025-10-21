# BragerOne API Structure Explorer

Skrypt do eksploracji struktury odpowiedzi z API BragerOne w celu stworzenia precyzyjnych modeli Pydantic.

## Użycie

### Metoda 1: Zmienne środowiskowe (zalecane)

Utwórz plik `.env` w głównym katalogu projektu:
```bash
# .env
BRAGERONE_USERNAME=your_email@example.com
BRAGERONE_PASSWORD=your_password
```

Uruchom skrypt:
```bash
cd /workspace
python scripts/explore_api_structure.py
```

### Metoda 2: Argumenty z linii poleceń

```bash
cd /workspace
python scripts/explore_api_structure.py --username YOUR_USERNAME --password YOUR_PASSWORD
```

### Opcje

- `--username` - Nazwa użytkownika BragerOne (domyślnie: `BRAGERONE_USERNAME` z .env)
- `--password` - Hasło do BragerOne (domyślnie: `BRAGERONE_PASSWORD` z .env)  
- `--output FILE` - Zapisz wyniki do pliku zamiast wyświetlać na stdout

## Przykłady

```bash
# Używając .env (najwygodniej)
python scripts/explore_api_structure.py

# Z argumentami linii poleceń
python scripts/explore_api_structure.py --username user@example.com --password secret123

# Zapisz do pliku
python scripts/explore_api_structure.py --output api_structure.txt

# Override .env z linii poleceń
python scripts/explore_api_structure.py --username other@example.com --output results.txt
```

## Co robi skrypt

1. **Loguje się** do API BragerOne
2. **Eksploruje endpointy:**
   - Authentication (`/auth/user`)
   - User info (`/user`)
   - User permissions (`/user/permissions`)
   - Objects list (`/objects`)
   - Object details i permissions
   - Modules list dla pierwszego obiektu
   - Module card dla pierwszego modułu
   - Modules parameters prime
   - Modules activity quantity prime

3. **Analizuje strukturę** każdej odpowiedzi JSON
4. **Generuje sugestie** dla modeli Pydantic na podstawie typów danych

## Wyjście

Dla każdego endpointa skrypt wyświetla:
- **Pretty JSON** - sformatowaną odpowiedź z API
- **Pydantic hints** - sugerowaną strukturę klasy BaseModel

Przykład wyjścia:
```
=== Authentication Response ===
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "expires_in": 3600,
  "user": {
    "id": 123,
    "email": "user@example.com"
  }
}

class AuthResponse(BaseModel):
    access_token: str
    expires_in: int
    user: UserModel
```

## Użycie wyników

Wyniki można wykorzystać do stworzenia modeli w `src/pybragerone/models/api/`:
- `auth.py` - AuthResponse, User
- `user.py` - UserInfo, UserPermissions  
- `object.py` - ObjectInfo, ObjectPermissions
- `module.py` - ModuleInfo, ModuleCard
- `system.py` - SystemVersion, ModulesParameters, etc.