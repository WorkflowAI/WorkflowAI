import workflowai
from pydantic import BaseModel, Field


class CompanyContextAgentInput(BaseModel):
    company_name: str | None = Field(
        default=None,
        description="The name of the company",
    )
    company_website_content: str | None = Field(
        default=None,
        description="Some content extracted from the company's website, that must be the sole source of information to generate the company context",
    )


class CompanyContextAgentOutput(BaseModel):
    company_context: str | None = Field(
        default=None,
        description="A brief overview of what the company does",
    )


INSTRUCTIONS = """
What does this company do? Provide a detailled description of the company and its products. Do not add any markdown or formatting (ex: bold, italic, underline, etc.) in the response, except line breaks, punctation and eventual bullet points.
"""


@workflowai.agent(
    version=workflowai.VersionProperties(
        model=workflowai.Model.GEMINI_2_0_FLASH_001,
        instructions=INSTRUCTIONS,
    ),
)
async def company_context_agent(
    input: CompanyContextAgentInput,
) -> CompanyContextAgentOutput: ...
