# Contributing

## Guidelines

### Deployments

This project uses GitHub Actions for CI / CD.

- the `main` branch is the central branch that contains the latest version of WorkflowAI. Any merge on main triggers
  a deployment to the staging environment
- any pull request that targets main triggers a quality check of the client and API portions based on
  the changes. The quality checks are required to pass before merging to main.
- Releases (`release/*`) and hotfix (`hotfix/*`) trigger deployments to the preview environment
- Deployments to the production environment are triggered by versioned tags.

### Branch flow

#### Feature or fix

A traditional feature or fix starts by creating a branch from `main` and results in a pull request on the `main` branch.
By convention, feature branch names should start with the name of the person creating the branch.

#### Release process

Releases are the process of deploying the code currently living in the staging env to production. The flow
starts with the creation of the `release/<release-date>` branch which triggers a deployment to the preview environment. A
PR from the release branch into main should be created as well.
This allows `main` to continue changing independently while the release is being QAed. Any fix for the release
should be a pull request into the release branch.

When the release is ready, the appropriate tags and GitHub releases should be created from the release branch to
trigger deployments to the production environment. Once everything is OK, the branch should be merged to `main`.

#### Hotfix process

A hotfix allows fixing bugs in production without having to push changes to the development environment first.
A hotfix branch should be created from the latest tag and a PR targeting `main` should be created. The flow is then the
same as the release process.

### Adding new models

#### Model enum

The [Model enum](./api/core/domain/models/models.py) contains the list of all models that were ever supported by WorkflowAI.

- never remove a model from the Model enum
- a model ID should always be versioned when possible, meaning that the model ID should include the version number when available e-g `gpt-4.1-2025-04-14`
- the model ID should match the provider's model ID when possible

#### Model data

The [ModelData](./api/core/domain/models/model_data.py) class contains metadata about a model, including the display name, icon URL, etc. It also allows deprecating a model by providing a replacement model.

The actual data is built by `_raw_model_data` in the [model_data_mapping.py](./api/core/domain/models/model_data_mapping.py) file. Every model in the Model enum should have an associated ModelData object.

When adding a new model, you must provide:

- `display_name`: Human-readable name for the model
- `icon_url`: URL to the model's icon (typically the provider's logo)
- `max_tokens_data`: Maximum token limits for input and output
- `release_date`: When the model was released
- `quality_data`: Performance metrics (MMLU, GPQA scores, etc.)
- `provider_name`: Name of the provider
- `supports_*` flags: What capabilities the model supports (JSON mode, images, etc.)
- `fallback`: Optional fallback configuration for error handling

When deprecating a model, make sure to replace every case where the model is used in the replacement model. We do not allow replacement models to be deprecated. Only deprecate models when either:

- the model will no longer be supported by the provider in the near future
- the model has a clear replacement model and using the original model is not recommended

#### Model provider data

The [ModelProviderData](./api/core/domain/models/model_provider_data.py) class contains pricing information per provider per model. If a model is supported by a provider, then it must have a ModelProviderData object.

The provider data is configured in [model_provider_data_mapping.py](./api/core/domain/models/model_provider_data_mapping.py). Each provider has its own dictionary mapping models to their provider data.

When adding a new model, you must add pricing data for each provider that supports it, including:

- `text_price`: Cost per token for input/output
- `image_price`: Cost per image (if applicable)
- `audio_price`: Cost per audio input (if applicable)
- `lifecycle_data`: Sunset dates and replacement models (if applicable)

When deprecating a model, remove its model provider data as well.

When explicitly asked to make a model a "default" model, meaning that it will be displayed by default by the frontend:

- set the `is_default` flag to `True` in the model provider data
- make sure the model places high in the Model enum since the Model enum gives the default order of models.
- add the model to its "usual" position in the enum but comment it out to enhance readability.
- it likely replaces another "default" model, so remove it from the top of the enum and uncomment the corresponding line in its "usual" position.

#### Checking tests

All the tests in the [domain models directory](./api/core/domain/models) should be executed and pass

```bash
pytest api/core/domain/models
```

### Documentation

#### Endpoints

Endpoints or fields that are exposed to the public should be properly documented:

- each endpoint function should be documented with a `docstring`. See the [FastAPI documentation](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#summary-and-description) for more details.
- a `docstring` should be added to each pydantic model used in a response. The docstring should describe the model and its fields.
- a `description` should be added to each field in the response

```python
class Item(BaseModel):
    """
    The docstring that describes the Object itself
    """
    id: int = Field(
        description="A description of the field",
    )

@router.get("/items")
async def get_items() -> list[Item]:
    """
    The description of the endpoint
    """
    ...
```

##### Excluding certain fields or endpoints for the documentation

Sometimes, certain fields or endpoints should be excluded from the public documentation, because they are internal or not meant to be used by the end user.

- excluding a field should be done with the `SkipJsonSchema` [annotation](https://docs.pydantic.dev/latest/api/json_schema/#pydantic.json_schema.SkipJsonSchema) imported from [`api.routers._common`](api/api/routers/_common.py). Our local implementation wraps the Pydantic annotation to only hide the fields in production.
- excluding an endpoint should be done with the `PRIVATE_KWARGS` variable imported from [`api.routers._common`](api/api/routers/_common.py).

> Do NOT use `Field(exclude=True)` as it excludes the field from being processed by Pydantic and not by the documentation generation.

> Documentation will only be hidden in production. We need full documentation in Dev to allow code generation.

```python
from api.routers._common import PRIVATE_KWARGS, SkipJsonSchema

class Item(BaseModel):
    id: SkipJsonSchema[int] = Field(
        description="A field that will not be displayed in the production documentation.",
    )

@router.get("/items", **PRIVATE_KWARGS)
async def get_items():
    """
    A route that will not be displayed in the production documentation.
    """
    ...
```
