import logging
import os
from datetime import datetime
from typing import Callable, override

from api.services.analytics._batched_amplitude import BatchedAmplitude
from core.domain.analytics_events.analytics_events import (
    AnalyticsEvent,
    EventProperties,
    FullAnalyticsEvent,
    OrganizationProperties,
    TaskProperties,
    UserProperties,
)
from core.utils.background import add_background_task
from core.utils.fields import datetime_factory

from ._analytics_service import AnalyticsService


class AmplitudeAnalyticsService(AnalyticsService):
    batched_amplitude = BatchedAmplitude(
        api_key=os.getenv("AMPLITUDE_API_KEY", ""),
        url=os.getenv("AMPLITUDE_URL", "https://api2.amplitude.com/2/httpapi"),
    )

    def __init__(
        self,
        user_properties: UserProperties | None,
        organization_properties: OrganizationProperties | None,
        task_properties: TaskProperties | None,
    ):
        self.user_properties = user_properties
        self.organization_properties = organization_properties
        self.task_properties = task_properties
        self._logger = logging.getLogger(self.__class__.__name__)

    def _build_organization(self, builder: Callable[[], OrganizationProperties] | None = None):
        if builder:
            return builder()
        return self.organization_properties or OrganizationProperties(tenant="unknown")

    @override
    def send_event(
        self,
        builder: Callable[[], EventProperties],
        time: datetime | None = None,
        task_properties: Callable[[], TaskProperties] | None = None,
        organization_properties: Callable[[], OrganizationProperties] | None = None,
    ):
        try:
            full = FullAnalyticsEvent(
                user_properties=self.user_properties,
                organization_properties=self._build_organization(organization_properties),
                task_properties=task_properties() if task_properties else self.task_properties,
                event=AnalyticsEvent(event_properties=builder(), time=time or datetime_factory()),
            )
            add_background_task(self.batched_amplitude.send_event(full))
        except Exception:
            self._logger.exception("Failed to build analytics event")
            return
