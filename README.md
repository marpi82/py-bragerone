# BragerOne

Asynchroniczny klient dla one.brager.pl / io.brager.pl:

- logowanie (JWT),
- wykrywanie modułów (DEV-ID),
- dynamiczne etykiety/jednostki z assetów frontendu,
- snapshot parametrów (REST) + live update (Socket.IO),
- API do budowy listy encji (dla Home Assistant w przyszłości).

## Instalacja dev

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```
