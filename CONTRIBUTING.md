# Stack4Things v2.0 - Contributing Guidelines

Grazie per il tuo interesse a contribuire a Stack4Things v2.0! Questo documento fornisce linee guida per contribuire al progetto.

## 📋 Indice

- [Code of Conduct](#code-of-conduct)
- [Come Contribuire](#come-contribuire)
- [Setup Sviluppo](#setup-sviluppo)
- [Standard del Codice](#standard-del-codice)
- [Conventional Commits](#conventional-commits)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentazione](#documentazione)

## 🤝 Code of Conduct

Questo progetto adotta un Code of Conduct che tutti i contributori devono rispettare. Essere rispettosi e inclusivi.

## 🚀 Come Contribuire

### Reporting Bugs

1. Verifica che il bug non sia già stato segnalato nelle [Issues](link-to-issues)
2. Crea una nuova issue con:
   - Titolo descrittivo
   - Descrizione dettagliata del problema
   - Steps per riprodurre
   - Comportamento atteso vs comportamento attuale
   - Ambiente (OS, Python version, etc.)

### Proporre Features

1. Verifica che la feature non sia già stata proposta
2. Crea una nuova issue con label "enhancement"
3. Descrivi:
   - Use case della feature
   - Benefici
   - Possibile implementazione (se hai idee)

### Contribuire al Codice

1. Fork del repository
2. Crea un branch dalla `develop` (o `main` se non esiste `develop`)
3. Implementa le modifiche
4. Aggiungi test
5. Assicurati che tutti i test passino
6. Aggiorna documentazione se necessario
7. Crea Pull Request

## 💻 Setup Sviluppo

Vedi [QUICKSTART.md](./QUICKSTART.md) per istruzioni dettagliate.

### Prerequisiti

- Python 3.11+
- Poetry
- Docker & Docker Compose
- Git

### Setup Iniziale

```bash
# Clone repository
git clone <repository-url>
cd Stack4Things_v2.0

# Setup development environment
./scripts/setup-dev.sh

# Install dependencies
cd services/device-service
poetry install
```

## 📝 Standard del Codice

### Python

- Seguire [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Usare type hints dove possibile
- Formattazione con Black (line length: 100)
- Linting con Ruff
- Type checking con mypy

### Formattazione

```bash
# Formattare codice
black .

# Linting
ruff check .

# Type checking
mypy .
```

### Struttura Codice

- **Services**: Un microservizio per cartella in `services/`
- **Libraries**: Codice condiviso in `libraries/`
- **Tests**: Test nella cartella `tests/` di ogni servizio
- **Documentation**: Documentazione in `docs/`

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`

## 📦 Conventional Commits

Usiamo [Conventional Commits](https://www.conventionalcommits.org/). Vedi [CONVENTIONAL_COMMITS.md](./docs/CONVENTIONAL_COMMITS.md) per dettagli.

Esempi:
- `feat(device-service): add device CRUD API`
- `fix(common): resolve database connection issue`
- `docs(readme): update setup instructions`

## 🔍 Pull Request Process

1. **Crea Branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Fai Commit**
   ```bash
   git commit -m "feat(service): add new feature"
   ```

3. **Push Branch**
   ```bash
   git push origin feature/my-feature
   ```

4. **Crea Pull Request**
   - Titolo descrittivo
   - Descrizione dettagliata
   - Link a issue correlata (se presente)
   - Checklist:
     - [ ] Test aggiunti/aggiornati
     - [ ] Documentazione aggiornata
     - [ ] Codice formattato (Black)
     - [ ] Linting passato (Ruff)
     - [ ] Type checking passato (mypy)

5. **Review**
   - Aspetta review da maintainer
   - Rispondi ai feedback
   - Risolvi eventuali conflitti

6. **Merge**
   - Merge dopo approvazione
   - Branch sarà cancellato dopo merge

## 🧪 Testing

### Scrivere Test

- Test unitari per ogni funzione/logica
- Test di integrazione per API
- Test di performance per operazioni critiche

### Eseguire Test

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=device_service --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::test_create_device
```

### Coverage

Mantenere coverage >80% per nuovo codice.

## 📚 Documentazione

### Codice

- Docstrings per tutte le funzioni/classi
- Usare Google style docstrings

```python
def create_device(device_data: DeviceCreate) -> DeviceResponse:
    """
    Create a new device.
    
    Args:
        device_data: Device creation data
        
    Returns:
        Created device response
        
    Raises:
        ValueError: If device data is invalid
    """
```

### API Documentation

- Documentare tutti gli endpoint REST
- Usare OpenAPI/Swagger
- Includere esempi di richiesta/risposta

### Documentazione Utente

- Aggiornare README quando necessario
- Aggiungere esempi d'uso
- Documentare breaking changes

## 🏗️ Architecture Changes

Per modifiche architetturali significative:

1. Creare ADR (Architecture Decision Record) in `docs/adr/`
2. Discutere con il team
3. Ottenere approvazione prima di implementare

## 📞 Supporto

- **Issues**: Usa GitHub/GitLab Issues
- **Discussions**: Usa GitHub/GitLab Discussions
- **Email**: [team email]

## 📄 Licenza

Contribuendo, accetti che le tue modifiche siano rilasciate sotto la stessa licenza del progetto (Apache License 2.0).

---

Grazie per contribuire a Stack4Things v2.0! 🎉
