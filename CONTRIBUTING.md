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
