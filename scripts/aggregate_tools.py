import asyncio
import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from _common import PROD_ARG, STAGING_ARG, get_clickhouse_client, get_mongo_storage
from core.storage.organization_storage import OrganizationSystemStorage

_COST_TABLE = {
    "@search-google": 0.001,
}


class ToolAggregator:
    def __init__(self, system_storage: OrganizationSystemStorage, prod: bool, staging: bool):
        self._system_storage = system_storage
        self._prod = prod
        self._staging = staging

    async def aggregate_tools(self, tenant: str, from_date: datetime.date, to_date: datetime.date):
        tenant_data = await self._system_storage.get_public_organization(tenant)
        tenant_uid = tenant_data.uid

        clickhouse_client = get_clickhouse_client(prod=self._prod, staging=self._staging, tenant_uid=tenant_uid)

        query = """
          SELECT
            runs.created_at_date AS day,
            simpleJSONExtractString(tool_call, 'name') AS tool_name,
            count(*) AS call_count
          FROM
            runs
          ARRAY JOIN
            tool_calls AS tool_call
          WHERE
            tool_calls != '[]' AND
            runs.created_at_date >= {from_date: Date} AND
            runs.created_at_date <= {to_date: Date} AND
            runs.tenant_uid = {tenant_uid: UInt32}
          GROUP BY
            day, tool_name
        """

        result = await clickhouse_client.query(
            query,
            None,
            {"from_date": from_date, "to_date": to_date, "tenant_uid": tenant_uid},
        )

        table = Table(title="Tool Cost per day")
        table.add_column("Day", justify="right")
        table.add_column("Tool", justify="right")
        table.add_column("Call count", justify="right")
        table.add_column("Cost", justify="right")

        cost = 0
        for row in result.result_rows:
            day: datetime.date = row[0]
            tool_name = row[1]
            call_count = row[2]

            daily_cost = _COST_TABLE.get(tool_name, 0) * call_count
            daily_cost_str = f"${daily_cost:.2f}"
            table.add_row(day.isoformat(), tool_name, str(call_count), daily_cost_str)
            cost += daily_cost

        console = Console()
        console.print(table)

        console.print(f"Total cost: ${cost:.2f}", style="bold green")


def main(
    prod: PROD_ARG,
    staging: STAGING_ARG,
    tenant: Annotated[str, typer.Option()],
    from_date: Annotated[str, typer.Option()],
    to_date: Annotated[str, typer.Option()],
):
    storage = get_mongo_storage(prod=prod, staging=staging, tenant="__system__")
    aggregator = ToolAggregator(storage.organizations, prod=prod, staging=staging)
    try:
        from_date_date = datetime.date.fromisoformat(from_date)
        to_date_date = datetime.date.fromisoformat(to_date)
    except ValueError:
        typer.echo("Invalid date format. Please use YYYY-MM-DD format.", err=True)
        raise typer.Exit(1)
    asyncio.run(aggregator.aggregate_tools(tenant, from_date_date, to_date_date))


if __name__ == "__main__":
    typer.run(main)
