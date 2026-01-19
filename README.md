# mkg-core

Gemeinsame Python-Kernbibliothek für die MKG Platform.

## Übersicht

`mkg-core` stellt wiederverwendbare Komponenten für alle Python-basierten MKG-Repositories bereit:

| Modul | Beschreibung |
|-------|--------------|
| `base` | BaseHandler, BaseRepository, BaseService |
| `models` | Pydantic-Basismodelle mit Standard-Feldern |
| `exceptions` | Einheitliche Exception-Hierarchie |
| `utils` | Logging, Tenant-Context, Validation, Pagination |
| `clients` | AWS Client Wrapper (DynamoDB, S3, Secrets Manager) |

## Installation

```bash
# Als Dependency in pyproject.toml
mkg-core = { git = "https://github.com/mkg-machines/mkg-lib-core.git", tag = "v1.0.0" }

# Für Entwicklung
pip install -e ".[dev]"
```

## Quick Start

```python
from mkg_core import __version__

print(f"mkg-core version: {__version__}")
```

## Entwicklung

### Voraussetzungen

- Python 3.13+
- pip

### Setup

```bash
# Repository klonen
git clone git@github.com:mkg-machines/mkg-lib-core.git
cd mkg-lib-core

# Virtual Environment erstellen
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# oder: .venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -e ".[dev]"
```

### Tests ausführen

```bash
# Alle Tests
pytest

# Nur Unit Tests
pytest tests/unit -m unit

# Mit Coverage
pytest --cov
```

### Code-Qualität

```bash
# Linting
ruff check .

# Formatting prüfen
ruff format --check .

# Formatting anwenden
ruff format .

# Security Check
bandit -r src/

# Type Checking
mypy src/
```

## Projektstruktur

```
mkg-lib-core/
├── src/
│   └── mkg_core/
│       ├── __init__.py
│       ├── base/           # Base Classes
│       ├── models/         # Pydantic Models
│       ├── exceptions/     # Exception Hierarchy
│       ├── utils/          # Utilities
│       └── clients/        # AWS Clients
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
└── README.md
```

## Konventionen

- **Python Version:** 3.13
- **Formatter/Linter:** Ruff
- **Type Hints:** Pflicht für alle öffentlichen APIs
- **Docstrings:** Google-Style
- **Tests:** pytest mit moto für AWS Mocking

## Lizenz

Proprietary - MKG Machines GmbH
