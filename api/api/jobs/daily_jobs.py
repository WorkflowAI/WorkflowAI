from contextlib import asynccontextmanager
from datetime import datetime

from broker import broker

from api.jobs.common import SystemStorageDep, UserServiceDep
from core.services.customers.customer_service import CustomerService
from core.utils.redis_cache import should_run_today


@asynccontextmanager
async def _once_a_day(key: str):
    if await should_run_today(key, datetime.now().date()):
        yield


@broker.task()
async def send_daily_active_customers(user_service: UserServiceDep, storage: SystemStorageDep):
    async with _once_a_day("daily_active_customers"):
        await CustomerService.send_daily_report(user_service, datetime.now().date(), storage.active_tasks)
