# Stack4Things v2.0 - Repository Setup Guide

## Repository Git

### GitLab Setup

1. **Creare nuovo repository su GitLab**
   ```bash
   # Nome repository: Stack4Things_v2.0
   # Visibility: Private (o Public a seconda delle esigenze)
   # Initialize repository: NO (avremo già il codice)
   ```

2. **Configurare remote**
   ```bash
   git remote add origin git@gitlab.com:<group>/Stack4Things_v2.0.git
   # oppure
   git remote add origin https://gitlab.com/<group>/Stack4Things_v2.0.git
   ```

3. **Push iniziale**
   ```bash
   git add .
   git commit -m "Initial commit: Stack4Things v2.0 foundation"
   git push -u origin main
   ```

### GitHub Setup

1. **Creare nuovo repository su GitHub**
   ```bash
   # Nome repository: Stack4Things_v2.0
   # Visibility: Private (o Public a seconda delle esigenze)
   # Initialize repository: NO (avremo già il codice)
   ```

2. **Configurare remote**
   ```bash
   git remote add origin git@github.com:<org>/Stack4Things_v2.0.git
   # oppure
   git remote add origin https://github.com/<org>/Stack4Things_v2.0.git
   ```

3. **Push iniziale**
   ```bash
   git add .
   git commit -m "Initial commit: Stack4Things v2.0 foundation"
   git push -u origin main
   ```

## Branch Strategy

### Branch Principali

- `main`: Branch principale per produzione
- `develop`: Branch di sviluppo integrato
- `release/*`: Branch per release
- `hotfix/*`: Branch per hotfix urgenti

### Branch Features

- `feature/*`: Nuove funzionalità
- `bugfix/*`: Fix di bug
- `refactor/*`: Refactoring
- `docs/*`: Documentazione

### Esempio Workflow

```bash
# Creare feature branch
git checkout -b feature/device-service-api

# Fare commit
git add .
git commit -m "feat: implement device service REST API"

# Push branch
git push origin feature/device-service-api

# Creare Merge Request su GitLab/GitHub
```

## Git Configuration

### Setup iniziale (se non già fatto)

```bash
# Configurare nome utente
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Configurare editor preferito
git config --global core.editor "vim"  # o "nano", "code", etc.

# Configurare line endings (cross-platform)
git config --global core.autocrlf input  # Linux/Mac
# git config --global core.autocrlf true  # Windows

# Abilitare colori
git config --global color.ui auto
```

### Git Hooks (opzionale ma consigliato)

Sono disponibili hook pre-commit in `scripts/git-hooks/`:

```bash
# Installare hook
cp scripts/git-hooks/pre-commit .git/hooks/
chmod +x .git/hooks/pre-commit
```

## Repository Structure

La struttura del repository è organizzata come segue:

```
Stack4Things_v2.0/
├── .git/                    # Git repository data
├── .gitignore               # Git ignore rules
├── .gitattributes           # Git attributes (line endings, etc.)
├── README.md                # Documentazione principale
├── CONTRIBUTING.md          # Guide per contribuire
├── TODO_LIST.md             # TODO list completa
├── QUICKSTART.md            # Quick start guide
├── services/                # Microservizi
├── libraries/               # Librerie condivise
├── infrastructure/           # Infrastructure as Code
├── docs/                    # Documentazione
├── scripts/                 # Utility scripts
└── docker-compose.dev.yml   # Development environment
```

## CI/CD Integration

### GitLab CI

Il repository include configurazione `.gitlab-ci.yml` per pipeline CI/CD automatiche.

### GitHub Actions

Il repository include configurazione `.github/workflows/` per GitHub Actions.

## Tags e Versioning

### Semantic Versioning

Usiamo Semantic Versioning (MAJOR.MINOR.PATCH):

```bash
# Creare tag per release
git tag -a v2.0.0 -m "Release version 2.0.0"
git push origin v2.0.0
```

### Changelog

Manteniamo un CHANGELOG.md per tracciare le modifiche tra versioni.

## Contributing

Vedi [CONTRIBUTING.md](../CONTRIBUTING.md) per linee guida dettagliate su come contribuire al progetto.

## Security

- **Secrets**: Non committare mai secrets, chiavi API, password, etc.
- **Secrets Management**: Usare variabili d'ambiente o secret management tools
- **Dependencies**: Mantenere aggiornate le dipendenze e verificare vulnerabilità
- **Branch Protection**: Configurare branch protection rules su main/develop

## Best Practices

1. **Commit Messages**: Usare conventional commits
   ```
   feat: add device service API
   fix: resolve database connection issue
   docs: update README with setup instructions
   ```

2. **Small Commits**: Fare commit frequenti e piccoli
3. **Review Code**: Creare sempre Merge/Pull Request per review
4. **Test**: Assicurarsi che i test passino prima di fare merge
5. **Documentation**: Aggiornare documentazione quando necessario

