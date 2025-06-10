from openai.types.chat import ChatCompletion

from tests.component.common import IntegrationTestClient


async def fetch_run_from_completion(test_client: IntegrationTestClient, completion: ChatCompletion):
    task_id, run_id = completion.id.split("/")
    return await test_client.fetch_run({"id": task_id}, run_id=run_id, v1=True)


async def save_version_from_completion(
    test_client: IntegrationTestClient,
    completion: ChatCompletion,
    deploy_to: str | None = None,
):
    task_id, run_id = completion.id.split("/")
    created = await test_client.post(f"/v1/_/agents/{task_id}/runs/{run_id}/version/save")

    if deploy_to:
        await test_client.post(
            f"/v1/_/agents/{task_id}/versions/{created['id']}/deploy",
            json={"environment": deploy_to},
        )

    return await test_client.fetch_version({"id": task_id}, created["id"])
