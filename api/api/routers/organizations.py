import logging

from fastapi import APIRouter, HTTPException

from api.dependencies.provider_factory import ProviderFactoryDep
from api.dependencies.storage import OrganizationStorageDep
from api.tags import RouteTags
from core.domain.tenant_data import (
    ProviderConfig,
    ProviderSettings,
    TenantData,
)
from core.storage import ObjectNotFoundException

router = APIRouter(prefix="/organization", tags=[RouteTags.ORGANIZATIONS])

_logger = logging.getLogger(__name__)


@router.get("/settings", description="List settings for a tenant")
async def get_organization_settings(storage: OrganizationStorageDep) -> TenantData:
    try:
        return await storage.get_organization()
    except ObjectNotFoundException:
        _logger.warning("Organization not found", extra={"tenant": storage.tenant})
        return TenantData()


@router.post("/settings/providers", description="Add a provider config")
async def add_provider_settings(
    request: ProviderConfig,
    storage: OrganizationStorageDep,
    provider_factory: ProviderFactoryDep,
) -> ProviderSettings:
    provider_cls = provider_factory.provider_type(request)
    # Will raise InvalidProviderConfig if the config is invalid
    config = provider_cls.sanitize_config(request)

    provider = provider_cls(config, config_id="temp")

    is_valid = await provider.check_valid()
    if not is_valid:
        raise HTTPException(400, "Invalid provider config")

    return await storage.add_provider_config(config)


@router.delete("/settings/providers/{provider_id}", description="Delete a provider config")
async def delete_provider_settings(provider_id: str, storage: OrganizationStorageDep) -> None:
    await storage.delete_provider_config(provider_id)
