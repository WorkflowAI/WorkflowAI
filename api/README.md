# Workflow AI

## Usage

### Requirements

- python 3.12.\* (< 3.13)
- docker to start the dependencies
- [poetry](https://python-poetry.org/) 1.8.\* (< 2.0)
- [ffmpeg](https://ffmpeg.org/ffmpeg.html) to handle audio files
- [poppler](https://poppler.freedesktop.org/) to handle pdf files

Example Mac setup:

```sh
# Install python 3.12 if needed
brew install python@3.12
# Install pipx https://pipx.pypa.io/stable/installation/
brew install pipx
pipx ensurepath
# Install poetry with pipx
pipx install poetry==2.1.3
# [Recommended] Configure poetry to create virtual envs in project
# It makes it easier to be picked up by vscode
poetry config virtualenvs.in-project true

# Install poppler for pdf parsing and ffmpeg for image detection
brew install poppler ffmpeg
```

### Installation

The install makefile rule installs all dependencies and the pre-commit hook.

```sh
# Install all **dependencies**
make install
# Create the .env. The sample provides basic values but you
# might need to add some secrets
cp .env.sample .env
# Start the mongo and redis dependencies as daemons
docker-compose up -d mongo redis azurite clickhouse
# Start the api
make api
# Or start the worker (only needed if you need to handle background tasks)
make worker
```

Also:

- Debug configurations are provided for vscode for both the worker and the api so it is possible to
  run both via cursor/vscode instead of with the makefile
- a docker-compose file is also provided for the api to test the app in
  deployed/isolated conditions. `docker-compose build && docker-compose up worker api` will start the backend entire stack
- a script to make the local blob storage public is provided in [scripts/make_blob_public.py](./scripts/make_blob_public.py). Making the blob storage public is required to view uploaded images
  in the app.

> Note that in docker, the host for dependencies (redis & mongo) will be different
> since it would use the internal docker network routing (see values in the
> docker-compose). The values are properly overriden in the docker-compose.yml file
> to use the internal hosts, so there should not be anything to change.

#### Single command startup

The provided docker-compose.yml provides a way to start the entire stack (backend and frontend) in a
single command.
It requires:

- that both the workflowai-api and workflowai.com projects are checked out in the same directory
- that both have project have a correctly setup .env file

```sh
docker-compose build && docker-compose up
```

Open http://localhost:8000 to access the app !

### Components

There are 2 components to this project:

- the api, based on [fastapi](https://fastapi.tiangolo.com/) that serves traffic
- the worker, based on [taskiq](https://taskiq-python.github.io/) that handles background tasks

Both can work as a standalone. The easiest way to work with both of them is to
run there associated commands `make api` or `make worker` in separate terminals or
using vscode to debug both at the same time.

### Setting up providers

This project supports a variety of LLM providers.

Each provider has a different set of credentials and configuration. Providers that have the required environment
variables are loaded by default.

### Tests

The project contains two kinds of tests:

- unit tests that test each layer in an isolated fashion. These tests are placed next to
  their related file with the `_test` suffix.
- integrations tests are in [tests/integration](./api/tests/integration) and test flows
  accross multiple layers, only mocking the LLM calls.

#### Setup

Running tests requires creating a clickhouse database.
Follow instructions to install the client https://clickhouse.com/docs/en/interfaces/cli

```sh
./clickhouse client --user default --password admin
CREATE DATABASE db_test;
```

### Importing tasks locally

> Careful, the behavior is undefined if the task already exists in the target db

```sh
export PYTHONPATH=.
python scripts/import_task.py --from prod:workflowai.com --to local:workflowai.com describe-images-with-context
```
