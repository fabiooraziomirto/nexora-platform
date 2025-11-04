# Conventional Commits per Stack4Things v2.0

## Formato Commit Message

```
<type>(<scope>): <subject>

<body>

<footer>
```

## Types

- **feat**: Nuova funzionalità
- **fix**: Bug fix
- **docs**: Modifiche alla documentazione
- **style**: Formattazione, semicolons, etc. (non cambia il codice)
- **refactor**: Refactoring del codice
- **perf**: Miglioramenti delle performance
- **test**: Aggiunta o modifica di test
- **build**: Modifiche al build system o dipendenze
- **ci**: Modifiche a CI/CD
- **chore**: Task di manutenzione
- **revert**: Revert di un commit precedente

## Scope (opzionale)

- `device-service`: Device Service
- `plugin-service`: Plugin Service
- `execution-service`: Execution Service
- `network-service`: Network Service
- `dns-service`: DNS Service
- `webservice-service`: Webservice Service
- `fleet-service`: Fleet Service
- `common`: Common library
- `sdk`: SDK library
- `infrastructure`: Infrastructure as Code
- `docs`: Documentazione
- `ci`: CI/CD

## Esempi

```
feat(device-service): add device CRUD API endpoints

Implementa gli endpoint REST per la gestione dei dispositivi:
- GET /api/v2/devices (list)
- GET /api/v2/devices/{id} (get)
- POST /api/v2/devices (create)
- PATCH /api/v2/devices/{id} (update)
- DELETE /api/v2/devices/{id} (delete)

Closes #123
```

```
fix(common): resolve database connection pool issue

Corregge il problema di esaurimento del connection pool MySQL
quando ci sono molte richieste concorrenti.

Fixes #456
```

```
docs(readme): update setup instructions

Aggiorna le istruzioni di setup con i nuovi requisiti
per MySQL 10.11+ e OpenStack 2024.1+.
```

```
chore(deps): update FastAPI to 0.104.1

Aggiorna la dipendenza FastAPI alla versione 0.104.1
per migliorare le performance e correggere bug.
```

## Breaking Changes

Per breaking changes, aggiungere `BREAKING CHANGE:` nel footer:

```
feat(api): change device status enum values

BREAKING CHANGE: I valori dell'enum device status sono cambiati:
- 'online' -> 'connected'
- 'offline' -> 'disconnected'

Migration: aggiornare tutti i riferimenti nel codice.
```

## Best Practices

1. **Usa l'imperativo**: "add" non "added" o "adds"
2. **Sii specifico**: Evita messaggi generici come "fix bug"
3. **Limita la prima riga a 50 caratteri**
4. **Usa il body per spiegare il "cosa" e "perché"**
5. **Riferisci issue/PR**: Usa "Closes #123" o "Fixes #456"

