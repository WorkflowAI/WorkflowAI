import logging
from collections.abc import Callable
from datetime import datetime
from typing import override

from core.domain.analytics_events.analytics_events import EventProperties, OrganizationProperties, TaskProperties

from ._analytics_service import AnalyticsService


class NoopAnalyticsService(AnalyticsService):
    """An analytics service that does nothing. Used when skipping users"""

    @override
    def send_event(
        self,
        builder: Callable[[], EventProperties],
        time: datetime | None = None,
        task_properties: Callable[[], TaskProperties] | None = None,
        organization_properties: Callable[[], OrganizationProperties] | None = None,
    ):
        logging.getLogger(self.__class__.__name__).debug("Skipping analytics event")
