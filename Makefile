export PYTHONPATH := $(PWD)/api

.PHONY: api.lock
api.lock:
	poetry lock

.PHONY: api.start
api.start:
	poetry run uvicorn api.main:app --reload

.PHONY: api.install.deps
api.install.deps:
	poetry install

.PHONY: api.test
api.test.unit:
	poetry run pytest --ignore=api/tests/LLM_tests --ignore=api/tests/e2e --ignore=api/tests/component .

.PHONY: api.test.component
api.test.component:
	poetry run pytest api/tests/component

.PHONY: api.test.integration
api.test.integration:
	poetry run pytest api/tests/integration -n=5

.PHONY: api.lint
api.lint:
	poetry run ruff check .
	poetry run pyright .

.PHONY: api.format
api.format:
	poetry run ruff format .

.PHONY: client.lint
client.lint:
	yarn prettier-check
	yarn lint

.PHONY: client.format
client.format:
	yarn format

.PHONY: format
format: api.format client.format

.PHONY: lint
lint: api.lint client.lint

.PHONY: mongo.migrate
mongo.migrate:
	PYTHONPATH=./api:./scripts poetry run python scripts/mongo_migrate.py ${ARGS}


