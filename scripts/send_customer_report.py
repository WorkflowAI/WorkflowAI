import asyncio
from datetime import date
from typing import Annotated

import typer

from _common import PROD_ARG, STAGING_ARG, get_mongo_storage
from core.services.customers.customer_service import CustomerService
from core.services.users.shared_user_service import shared_user_service
from core.services.users.user_service import UserService
from core.storage.mongo.mongo_storage import MongoStorage


async def daily_report(
    storage: MongoStorage,
    user_service: UserService,
    today: date,
    commit: bool,
):
    if commit:
        await CustomerService.send_daily_report(user_service, today, storage.active_tasks)
        return

    report = await CustomerService.build_daily_report(user_service, today, storage.active_tasks)
    print(report)


def _run(
    prod: PROD_ARG,
    staging: STAGING_ARG,
    commit: Annotated[bool, typer.Option()] = False,
):
    mongo_storage = get_mongo_storage(prod=prod, staging=staging, tenant="__system__")

    asyncio.run(daily_report(mongo_storage, shared_user_service, date.today(), commit))


if __name__ == "__main__":
    typer.run(_run)
