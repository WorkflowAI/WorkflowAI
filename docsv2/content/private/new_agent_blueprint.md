
This is an example of a fully-featured WorkflowAI agent that MUST serve as a blueprint when creating a new agent. This code example is written in Python, but the same concept applies for other SDKs, for example OpenAI TypeScript SDK and direct HTTP calls.

The code below demonstrates:
- How to use input variables in the agent's messages ({{example_variable}}), which should be always used for any new agent
- How to use structured output with Pydantic models, which should be always used for any new agent, except when the output is a simple string
- How to use the WorkflowAI hosted tools (@perplexity-sonar-pro, @google-search, @browser-text), that must be used when the agent needs real time data or web search capabilities
- How to name the agent by adding a 'agent_id' metadata, which is used to identify the agent in the WorkflowAI platform. 'agent_id'  MUST ALWAYS be added to the agent's metadata
- How to add metadata to the agent's runs (lead_id), which is used to easily search the agent's runs for this specific lead later
- Where to set custom tools that will be manually implemented by the user and run in the user's runtime.

This code contains a lot of comments that you must reuse for the user, the final user too, but make sure to adapt those comments so that they make sense in the user's context.

```python
import logging
import os
from typing import Any, Dict, List

import openai
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Define structured output schema
class CompanyInfo(BaseModel):
    locations: list[str] = Field(
        description="List of company locations including headquarters and major offices",  # description and examples help the agent understand the expected output
        examples=[["San Francisco, CA, USA", "New York, NY, USA", "London, UK"]],
    )
    founded_year: int = Field(
        description="Year the company was founded", examples=[2010]
    )
    websites: list[str] = Field(
        description="List of company websites including main website and relevant subdomains. Only include TLDs",
        examples=[
            [
                "https://company.com",
                "https://careers.company.com",
                "https://blog.company.com",
            ]
        ],
    )
    employees_count: int = Field(
        description="Number of employees in the company", examples=[1000]
    )
    summary: str = Field(
        description="Comprehensive summary of the company including business model, key products/services, and market position",
        examples=[
            "TechCorp is a leading software company specializing in cloud infrastructure solutions, serving over 10,000 enterprise customers globally with their flagship platform that enables scalable application deployment."
        ],
    )


def enrich_company_info(
    company_name: str, lead_id: str, additional_requirements: str | None = None
) -> CompanyInfo | None:
    """
    Enrich company information using WorkflowAI agent

    Args:
        company_name: Name of the company to research
        additional_requirements: Specific additional information to extract
        lead_id: ID of the lead that triggered the agent, only used for metadata in order to faciliate tracking down the road

    Returns:
        CompanyInfo: Structured company information or None if error
    """

    # Set up your WorkflowAI API key
    client = openai.OpenAI(
        api_key=os.getenv(
            "WORKFLOWAI_API_KEY"
        ),  # Get your API key from https://workflowai.com/keys
        base_url="http://run.workflowai.com/v1",  # Replace the OpenAI base URL with the WorkflowAI one
    )

    # Define the agent messages with input variables in double curly braces {{}}
    # Note that WorkflowAI messages are Jinja2 compatible and can handle if statements (see: {% if additional_requirements %})
    # Note that the WorkflowAI hosted tools (@perplexity-sonar-pro, @google-search, @browser-text) are directly added into the messages and DO NOT need to be also added to the 'tools' parameter of the client.beta.chat.completions.parse call
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": """You are a company information enrichment specialist. Your task is to gather comprehensive information about companies using web search and provide structured, accurate data.

    For the given company name, you must:
    1. Use @google-search & @browser-text to find the company's official information
    2. Search for company locations, headquarters, and major offices
    3. Find all relevant company websites (main site, careers, blog, etc.)
    4. Gather information for a comprehensive company summary

    Always verify information from multiple sources and prioritize official company sources. Be thorough but concise in your responses.

    Provide comprehensive information about this company including locations, websites, and a detailed summary. If additional requirements are specified, make sure to address those specifically.""",
        },
        {
            "role": "user",
            "content": """Please enrich the following company information:

    Company Name: {{company_name}}
    {% if additional_requirements %}
    Additional Requirements: {{additional_requirements}}
    {% endif %}""",
        },
    ]

    try:
        completion = client.beta.chat.completions.parse(  # Non-structured output is also supported with 'client.chat.completions.parse'
            model="gemini-2.5-pro",  # Pick a model from https://workflowai.com/models, more than 100 models are available
            messages=messages,
            response_format=CompanyInfo,  # Activate the structured output by passing the Pydantic model here
            extra_body={
                "input": {  # Variables corresponding to the input variables in the messages are passed as a dictionary here
                    "company_name": company_name,
                    "additional_requirements": additional_requirements
                    or "No additional requirements",
                }
            },
            metadata={
                # IMPORTANT: add the 'agent_id' as metadata in order to have all the agent's runs logged at:
                #  https://workflowai.com/workflowai/agents/company-info-enrichment/1/runs
                "agent_id": "company-info-enrichment",
                # Add the 'lead_id' in order to be able to easily search the agent's runs for this specific lead later
                "lead_id": lead_id,
                "some_other_metadata_key": "some_other_metadata_value",
            },
            # You can add any tool below that will be run in the user's runtime.
            # Hosted tools (@perplexity-sonar-pro, @google-search,@browser-text) are already included in the messages and DO NOT need to be added here
            tools=[],
        )

        return completion.choices[0].message.parsed

    except Exception as e:
        logger.exception("Error enriching company info", exc_info=e)
        return None


if __name__ == "__main__":
    print(enrich_company_info(company_name="WorkflowAI", lead_id="example_lead_id"))

```
