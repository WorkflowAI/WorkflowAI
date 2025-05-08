from api.broker import broker
from api.jobs.common import CustomerServiceDep
from core.domain.events import ProxyAgentCreatedEvent


@broker.task(retry_on_error=True, max_retries=1)
async def handle_proxy_agent_created(event: ProxyAgentCreatedEvent, customer_service: CustomerServiceDep):
    await customer_service.send_proxy_agent_created(event)


JOBS = [handle_proxy_agent_created]
