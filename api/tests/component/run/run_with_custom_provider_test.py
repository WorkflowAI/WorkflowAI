from core.domain.models import Model
from tests.component.common import (
    IntegrationTestClient,
    task_url_v1,
)


async def test_run_with_custom_provider_v1(test_client: IntegrationTestClient):
    # Check that we do not decrement credits for runs with custom providers
    task = await test_client.create_task()

    # Fetch the organization settings before running the task
    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10.0

    test_client.mock_openai_call(
        provider="azure_openai",
        usage={"prompt_tokens": 10000, "completion_tokens": 10000, "total_tokens": 200000},
    )

    # Create a custom azure provider
    await test_client.post(
        "/_/organization/settings/providers",
        json={
            "provider": "azure_openai",
            "deployments": {
                "eastus": {
                    "api_key": "custom_api_key",
                    "url": "https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/",
                    "models": ["gpt-4o-2024-11-20"],
                },
            },
            "preserve_credits": False,
        },
    )

    org = await test_client.get_org()
    assert org["providers"] and len(org["providers"]) == 1

    # Now run the task
    run = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, autowait=True)

    # Customer key is used first,
    completions = await test_client.get(task_url_v1(task, f"/runs/{run['id']}/completions"))
    assert len(completions["completions"]) == 1
    assert completions["completions"][0]["provider"] == "azure_openai"
    assert completions["completions"][0]["provider_config_id"] == org["providers"][0]["id"]

    # Check that credits were removed
    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10.0 - 0.000_002_5 * 10000 - 0.000_010 * 10000


async def test_run_with_custom_provider_fallback(test_client: IntegrationTestClient):
    # Check that we do not decrement credits for runs with custom providers
    task = await test_client.create_task()

    # Fetch the organization settings before running the task
    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10.0

    # Create a custom azure provider, we will test the config when it is created
    test_client.mock_openai_call(provider="azure_openai")
    await test_client.post(
        "/_/organization/settings/providers",
        json={
            "provider": "azure_openai",
            "deployments": {
                "eastus": {
                    "api_key": "custom_api_key",
                    "url": "https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/",
                    "models": ["gpt-4o-2024-11-20"],
                },
            },
        },
    )

    org = await test_client.get_org()
    assert org["providers"] and len(org["providers"]) == 1

    test_client.mock_openai_call(provider="azure_openai", status_code=429)
    test_client.mock_openai_call(
        usage={"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000},
    )

    run = await test_client.run_task_v1(task, model=Model.GPT_4O_2024_11_20, autowait=True)
    completions = await test_client.get(task_url_v1(task, f"/runs/{run['id']}/completions"))
    assert len(completions["completions"]) == 2
    # We first tried the custom provider, then the default one
    assert completions["completions"][0]["provider"] == "azure_openai"
    assert completions["completions"][0]["provider_config_id"] == org["providers"][0]["id"]
    assert completions["completions"][1]["provider"] == "openai"
    assert not completions["completions"][1].get("provider_config_id")

    # Check that credits were removed
    org = await test_client.get_org()
    assert org["current_credits_usd"] == 10.0 - 0.000_002_5 * 1000 - 0.000_010 * 1000
