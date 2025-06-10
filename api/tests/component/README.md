# Component Tests

Component tests:

- test the API from the outside (i-e by calling endpoints) by avoiding to Mock internal components as much as possible
- use containerized dependencies when possible, like MongoDB, Redis, etc.
- mock any external http calls, like calls to LLM providers

Component tests are ran on every PR. See the [API Quality workflow](/.github/workflows/.api-quality.yml) for more details.

## Requirements

For safety reasons, environment variables are hardcoded on test setup (see [conftest.py](./conftest.py)).
Since the database is scrubbed before tests are ran, hardcoding environment variables ensure the tests
will have no impact on existing data.

Component tests require local instances of the following services:

- a mongodb instance running on `localhost:27017`
- a redis instance running on `localhost:6379`
- a clickhouse instance running on `localhost:8123`
- an azure storage emulator running on `localhost:10000`

All dependencies can be started using the `docker-compose.yml` file.

```bash
docker-compose up -d mongo redis azurite clickhouse
```

## Running tests

```bash
# Run all component tests
poetry run pytest api/tests/component
# Run all component tests in a specific file
poetry run pytest api/tests/component/test_file.py
# Run a specific test
poetry run pytest api/tests/component/test_file.py::test_name
```
