import os

from core.domain.analytics_events.analytics_events import (
    OrganizationProperties,
    TaskProperties,
    UserProperties,
)

from ._amplitude_analytics_service import AmplitudeAnalyticsService
from ._analytics_service import AnalyticsService

_BLACKLISTED_ORG_IDS = {
    *os.getenv("ANALYTICS_BLACKLISTED_ORGS", "").split(","),
}


async def start_analytics():
    await AmplitudeAnalyticsService.batched_amplitude.start()


async def close_analytics():
    await AmplitudeAnalyticsService.batched_amplitude.close()


def analytics_service(
    user_properties: UserProperties | None,
    organization_properties: OrganizationProperties | None,
    task_properties: TaskProperties | None,
) -> AnalyticsService:
    if organization_properties and organization_properties.organization_id in _BLACKLISTED_ORG_IDS:
        from ._noop_analytics_service import NoopAnalyticsService

        return NoopAnalyticsService()

    return AmplitudeAnalyticsService(user_properties, organization_properties, task_properties)
