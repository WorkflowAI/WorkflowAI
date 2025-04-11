## Reliability
[![Better Stack Badge](https://uptime.betterstack.com/status-badges/v2/monitor/1cuxx.svg)](https://status.workflowai.com)

Our goal with WorkflowAI Cloud is to provide a 100% uptime on our API endpoint that is used for running an AI agent.

We've designed our architecture to be resilient in a few ways:
- at the AI provider level, we implemented a fallback mechanism that brings redundacy. For example, if OpenAI API is down, WorkflowAI will automatically switch to Azure OpenAI API.
- at the API level, we run our inference API `run.workflowai.com` in a separate container, isolated from the rest of our other API endpoints.
- at the database level, we use a multi-region database to ensure that your data is always available.
- at the datacenter level, we bring redundacy by running our API in multiple independant regions.

## 1. AI provider fallback

WorkflowAI continuously monitors the health and performance of all integrated AI providers. When a provider experiences downtime or degraded performance, our system automatically switches to a healthy alternative provider without any manual intervention.

For example, all OpenAI models are also available through Azure OpenAI Service. If the OpenAI API becomes unavailable, WorkflowAI will automatically failover to Azure OpenAI within one second. This seamless transition ensures your agent runs continue without interruption, and you don't need to make any changes to your code.

This intelligent routing between providers happens behind the scenes, maintaining consistent response times and reliability for your applications even during provider outages.

## 2. Database redundacy

We use MongoDB Atlas for our primary database infrastructure, which ensures high availability through a distributed architecture with a [99.995% SLA](https://www.mongodb.com/cloud/atlas/reliability). Our database deployment includes 7 replicas across 3 Azure regions:
- 3 replicas in East US2
- 2 replicas in Iowa
- 2 replicas in California

These replicas automatically synchronize data between them, ensuring that if one database instance or even an entire region fails, the others can immediately take over without data loss. MongoDB Atlas also offers automatic failover capabilities, where if the primary node becomes unavailable, a secondary replica is automatically promoted to primary, typically within seconds. This multi-region architecture ensures continuous database operations even during regional outages, maintenance windows, or unexpected infrastructure issues.

{% hint style="info" %}
For storing run history and analytics data, we use Clickhouse, which excels at handling large volumes of data efficiently. It's important to note that while Clickhouse powers our analytics and observability features, it's not required for the core agent execution functionality. The process that stores run history is completely isolated from the critical run path, ensuring that your agents will continue to run normally even if the Clickhouse database experiences temporary unavailability.
{% endhint %}

## 3. Datacenter redundancy

We use [Azure Front Door](https://azure.microsoft.com/en-us/products/frontdoor) as our global load balancer to ensure high availability across multiple regions. Our infrastructure is deployed in both East US and Central US datacenters, providing geographic redundancy.

Azure Front Door continuously monitors the health of our backend services in each region. If one of our datacenters experiences an outage or performance degradation, Azure Front Door automatically redirects traffic to the healthy region within approximately 30 seconds. This intelligent routing happens without any manual intervention, ensuring minimal disruption to your API calls.

This multi-region architecture allows us to maintain high availability even during regional cloud provider outages, helping us achieve our goal of 100% uptime for the WorkflowAI API.

{% hint style="info" %}
If you have any question about our architecture, please [contact us](mailto:team@workflowai.support).
{% endhint %}
