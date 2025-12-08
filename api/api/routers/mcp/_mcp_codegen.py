import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from core.domain.consts import WORKFLOWAI_RUN_URL
from core.domain.task_deployment import TaskDeployment
from core.domain.task_variant import SerializableTaskVariant
from core.domain.version_environment import VersionEnvironment
from core.utils.strings import to_pascal_case
from core.utils.templates import TemplateManager

SDK = Literal["python/openai-sdk", "javascript/openai-sdk", "golang/openai-sdk", "curl"]


class CodegenService:
    template_manager = TemplateManager()

    @classmethod
    def _read_template(cls, file_name: str) -> str:
        with open(Path(__file__).parent / "_templates" / f"{file_name}.jinja2", "r") as file:
            return file.read()

    @classmethod
    async def _render_template(cls, sdk: SDK, variables: dict[str, Any]) -> str:
        # Remove / and - and replace with _
        template_name = f"{sdk.replace('/', '_').replace('-', '_')}"
        template = await cls.template_manager.get_template(template_name)
        if not template:
            content = await asyncio.to_thread(cls._read_template, template_name)
            template = await cls.template_manager.add_template(content, key=template_name)

        return await TemplateManager.render_compiled(template[0], variables)

    async def _generate_code_inner(
        self,
        agent_id: str,
        model: str,
        sdk: SDK,
        schema_id: int | None = None,
        environment: VersionEnvironment | None = None,
        existing_response_format_object: str | None = None,
        response_json_schema: dict[str, Any] | None = None,
        input_schema: dict[str, Any] | None = None,
    ) -> str:
        variables: dict[str, Any] = {
            "agent_id": agent_id,
            "run_url": WORKFLOWAI_RUN_URL,
            "input_doc": not environment and not schema_id and not input_schema,
        }
        if existing_response_format_object:
            variables["has_existing_response_format_object"] = True
            variables["response_format_object_name"] = existing_response_format_object
        else:
            variables["has_existing_response_format_object"] = False
            variables["response_format_object_name"] = f"{to_pascal_case(agent_id)}Output"

        if response_json_schema:
            variables["json_schema"] = json.dumps(response_json_schema)
        if input_schema:
            variables["input_schema"] = json.dumps(input_schema)

        if environment:
            if not schema_id:
                raise ValueError("Schema ID is required when environment is provided")
            variables["model"] = f"#{schema_id}/{environment}"
            variables["deployment"] = True

        if "model" not in variables:
            variables["model"] = model

        return await self._render_template(sdk, variables)

    async def generate_code(
        self,
        sdk: SDK,
        model: str,
        variant: SerializableTaskVariant,
        deployment: TaskDeployment | None,
        existing_response_format_object: str | None,
    ):
        agent_id = variant.task_id
        schema_id = variant.task_schema_id
        environment = deployment.environment if deployment else None

        return await self._generate_code_inner(
            agent_id=agent_id,
            model=model,
            sdk=sdk,
            schema_id=schema_id,
            environment=environment,
            existing_response_format_object=existing_response_format_object,
            response_json_schema=variant.output_schema.json_schema,
            input_schema=variant.input_schema.json_schema,
        )
