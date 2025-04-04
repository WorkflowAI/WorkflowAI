import os
from contextlib import contextmanager
from typing import Any

from sentry_sdk import new_scope

from core.domain.errors import ScopeConfigurableError
from core.domain.tenant_data import TenantData
from core.domain.version_reference import VersionReference as DomainVersionReference
from core.storage import ObjectNotFoundException


@contextmanager
def configure_scope_for_error(
    error: BaseException,
    tags: dict[str, str | bool | int | float] | None = None,
    extras: dict[str, Any] | None = None,
):
    with new_scope() as scope:
        if tags:
            for k, v in tags.items():
                scope.set_tag(k, v)

        if extras:
            for k, v in extras.items():
                scope.set_extra(k, v)

        if isinstance(error, ScopeConfigurableError):
            error.configure_scope(scope)

        yield


@contextmanager
def prettify_errors(
    user_org: TenantData | None,
    task_id: str,
    task_schema_id: int,
    reference: DomainVersionReference,
):
    try:
        yield
    except ObjectNotFoundException:
        if isinstance(reference.version, int):
            message = f"Version {reference.version} not found for task '{task_id}' and schema '{task_schema_id}'"
        else:
            workflowai_url = os.getenv("WORKFLOWAI_APP_URL", "https://workflowai.com")
            url = (
                f"{workflowai_url}/{user_org.slug}/agents/{task_id}/{task_schema_id}/deployments"
                if user_org
                else workflowai_url
            )
            message = f"No version deployed to {reference.version} for agent '{task_id}' and schema '{task_schema_id}'. Go to {url} to deploy a version."
        raise ObjectNotFoundException(
            message,
            code="version_not_found",
        )
