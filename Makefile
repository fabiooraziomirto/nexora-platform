COMPOSE ?= docker compose
COMPOSE_FILE ?= docker-compose.dev.yml
PROFILE ?= dev

.PHONY: dev smoke ps logs down clean config local-smoke test-unit

dev:
	$(COMPOSE) -f $(COMPOSE_FILE) --profile $(PROFILE) up -d --build

smoke:
	$(COMPOSE) -f $(COMPOSE_FILE) --profile smoke up -d --build

ps:
	$(COMPOSE) -f $(COMPOSE_FILE) --profile $(PROFILE) ps

logs:
	$(COMPOSE) -f $(COMPOSE_FILE) --profile $(PROFILE) logs -f --tail=200

down:
	$(COMPOSE) -f $(COMPOSE_FILE) --profile $(PROFILE) down

clean:
	$(COMPOSE) -f $(COMPOSE_FILE) --profile $(PROFILE) down -v

config:
	$(COMPOSE) -f $(COMPOSE_FILE) --profile $(PROFILE) config --quiet

local-smoke:
	PROFILE=$(PROFILE) bash scripts/local-smoke.sh

test-unit:
	PYTHONPATH=libraries/common/src python3 -m pytest -c libraries/common/pyproject.toml libraries/common/tests/test_auth_context.py
	PYTHONPATH=packages/nexora-agent/src python3 -m pytest packages/nexora-agent/tests/test_executor.py packages/nexora-agent/tests/test_offline_queue.py
