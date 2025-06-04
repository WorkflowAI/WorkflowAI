from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from core.domain.analytics_events.analytics_events import EventProperties, OrganizationProperties, TaskProperties


class AnalyticsService(Protocol):
    def send_event(
        self,
        builder: Callable[[], EventProperties],
        time: datetime | None = None,
        task_properties: Callable[[], TaskProperties] | None = None,
        organization_properties: Callable[[], OrganizationProperties] | None = None,
    ) -> None: ...
