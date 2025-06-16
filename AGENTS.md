# WorkflowAI Monorepo

This monorepo has two major components:

- The API, which is a Python FastAPI application that provides a REST API for the WorkflowAI platform.
- The Client, which is a Next.js application written in Typescript.

As a base rule, always check the README.md of the directory you are working in.

## API

Dependency management is done with `poetry`. `poetry install` installs dependencies.

When modifying the API, ensure that:

- ruff check still passes. The command to run is `poetry run ruff check .` to check the entire codebase or `poetry run ruff check path-to-file.py` to check a specific file.
- pyright check still passes. The command to run is `poetry run pyright .` to check the entire codebase or `poetry run pyright path-to-file.py` to check a specific file.
- the affected tests pass or new tests are added. See [testing infrastructure](#testing-infrastructure).

### Testing infrastructure

Pytest is used for testing. It is possible to run tests using `poetry run pytest <test-file.py>` for all tests within a file or `poetry run pytest <test-file.py::test_name>` for a specific test.

There are 4 layers of tests:

- Unit tests are added next to the code they test. For example, unit tests for `api/core/models.py` are in `api/core/models_test.py`. A unit test should be added or modified every time there is a change to the API.
- Component tests hit the API "from the outside" but mock external http calls and use containerized, isolated dependencies. See [the component test README.md](./api/tests/component/README.md) for more details. You should execute at least one component tests after having made changes to the API.
- Integration tests hit the API "from the outside" but do not mock crucial http calls. Integration tests only run post merge on main. Only add integration tests when explicitely asked and always provide a report on how they were executed since they will not be ran by the PR's CI.

### Adding integrations for the Completion endpoint

One of the features of WorkflowAI is an openai compatible endpoint.

The [integrations directory](./integrations) contains integrations with external library. It is used both as an example of how external libraries should be used with WorkflowAI and to
make sure our completion endpoint is compatible.

It includes scripts in different languages. Always check the individual README.md files to check how to run the integrations and view the language specific requirements.

Integration scripts require that a server is running to be tested. The integration test layer providers
way to run a local instance of the server and execute the script via the `api_server` fixture defined in the integration conftest [conftest.py](./api/tests/integration/conftest.py). For example, when
adding a new JS integration script, you could test it by adding a test:

```python
def test_my_new_script(api_server: str):
    result = subprocess.run(
        ["yarn", "tsx", f"openai_examples/{example.name}"],
        capture_output=True,  # Capture both stdout and stderr
        text=True,  # Return strings instead of bytes
        cwd=_js_dir(),  # Set the working directory to whevever the root command should be executed from
        env={
            **os.environ,
            # Make sure to correctly set the environment variables
            # WORKFLOWAI_API_KEY is set within the conftest so you do not
            # need to set it anywhere
            "OPENAI_API_KEY": os.environ["WORKFLOWAI_API_KEY"],
            "OPENAI_BASE_URL": f"{api_server}/v1",
        },
    )

    assert result.returncode == 0, f"Command failed with stderr: {result.stderr}\nstdout: {result.stdout}"
```

and executing the test with `poetry run pytest api/tests/integration/my_test_file.py::test_my_new_script`

## Client

### Checks

- `eslint` is used to check for linting errors.
- `prettier` is used to check for formatting errors.
- `typescript` is used for type checking.

Useful commands:

- `yarn prettier-check` check for formatting errors.
- `yarn format` to format the code.
- `yarn workspace workflowai lint` run eslint on the client code
- `yarn workspace workflowai build` to build the client, including checking for type errors.

## Docs

The [documentation](./docsv2) is written in [MDX](https://mdxjs.com/) and uses [FumaDocs](https://fumadocs.com/) as a framework.

Useful commands:

- `yarn workspace docs dev` to start the development server.
- `yarn workspace docs build` to build the documentation. Make sure to run this before pushing the PR to make sure it builds
- `yarn workspace docs lint` to lint the documentation.
