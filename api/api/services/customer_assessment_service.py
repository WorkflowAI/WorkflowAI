import logging
from typing import List, NamedTuple, Optional, Set

from api.services.scraping_service import ScrapingService
from core.agents.company_domain_from_email_agent import (
    ClassifyEmailDomainAgentInput,
    ClassifyEmailDomainAgentOutput,
    run_classify_email_domain_agent,
)
from core.agents.customer_assessment_agent import (
    CustomerAssessementAgentInput,
    CustomerAssessementAgentOutput,
    customer_assessement_agent,
)
from core.domain.url_content import URLContent
from core.tools.browser_text.browser_text_tool import get_sitemap
from core.utils.email_utils import safe_domain_from_email
from core.utils.enrich_so import (
    EnrichSoEnrichedCompanyData,
    EnrichSoEnrichedEmailData,
    get_enriched_company_profile_data,
    get_enriched_email_data,
)

_logger = logging.getLogger(__name__)


class ExtendedCustomerAssessementAgentOutput(CustomerAssessementAgentOutput):
    base_user_email: str
    base_user_name: str | None
    base_user_title: str | None
    base_user_linkedin_url: str | None

    def __str__(self) -> str:  # noqa: C901
        """A cool presentation of the company with emojis and all"""
        parts: list[str] = []

        parts.append("*Day 0 Customer Assessment:*\n\n")  # bold

        if self.base_user_name:
            parts.append(self.base_user_name)
        if self.base_user_title:
            parts.append(self.base_user_title)
        parts.append(self.base_user_email)

        if self.base_user_linkedin_url:
            parts.append(self.base_user_linkedin_url)

        if self.company_name:
            parts.append(f"🏢 Company Name: {self.company_name}")
        if self.company_industry:
            parts.append(f"🏭 Industry: {self.company_industry}")

        if self.founded_year:
            parts.append(f"📅 Founded in {self.founded_year}")

        if self.company_employees_count:
            parts.append(f"👥 {self.company_employees_count:,} employees")

        if self.company_funding_million_usd:
            parts.append(f"💰 Funding: ${self.company_funding_million_usd:.1f}M")
        if self.company_annual_revenue_millions_usd:
            parts.append(f"💵 Annual Revenue: ${self.company_annual_revenue_millions_usd:.1f}M")

        if self.company_website_url:
            parts.append(f"🌐 Website: {self.company_website_url}")
        if self.company_linkedin_url:
            parts.append(f"🌐 LinkedIn: {self.company_linkedin_url}")

        if self.locations:
            parts.append(f"🌍 Locations: {', '.join(self.locations)}")

        if self.summary:
            parts.append(f"✍️ Summary: {self.summary}")

        return "\n".join(parts)


class EnrichmentData(NamedTuple):
    """Container for enrichment data from enrich.so"""

    email_data: Optional[EnrichSoEnrichedEmailData]
    company_data: Optional[EnrichSoEnrichedCompanyData]
    enriched_contents: List[URLContent]


async def _get_company_domain(client_email: str) -> Optional[str]:
    """Determine the company domain from an email address."""
    email_classification = await run_classify_email_domain_agent(
        ClassifyEmailDomainAgentInput(email_domain=client_email),
    )

    if email_classification.result == ClassifyEmailDomainAgentOutput.Result.COMPANY_EMAIL_DOMAIN:
        return safe_domain_from_email(client_email)

    return None


async def _get_enrichment_data(client_email: str) -> EnrichmentData:
    """Get enriched data for email and company from enrich.so."""
    enrich_so_data: Optional[EnrichSoEnrichedEmailData] = None
    enrich_so_company_data: Optional[EnrichSoEnrichedCompanyData] = None
    enriched_contents: List[URLContent] = []

    try:
        enrich_so_data = await get_enriched_email_data(client_email)
    except Exception as e:
        _logger.exception("Error getting enriched user data from enrich.so", exc_info=e)

    if (
        enrich_so_data
        and enrich_so_data.positions
        and enrich_so_data.positions.positionHistory
        and len(enrich_so_data.positions.positionHistory) > 0
    ):
        enriched_contents.append(
            URLContent(
                url=f"enrich.so people API response for {client_email}",
                content=enrich_so_data.model_dump_json(),
            ),
        )

        latest_position = enrich_so_data.positions.positionHistory[0]
        if linked_url := latest_position.linkedInUrl:
            try:
                enrich_so_company_data = await get_enriched_company_profile_data(linked_url)

                enriched_contents.append(
                    URLContent(
                        url=f"enrich.so company API response for {linked_url}",
                        content=enrich_so_company_data.model_dump_json(),
                    ),
                )
            except Exception as e:
                _logger.exception("Error getting enriched company data from enrich.so", exc_info=e)

    return EnrichmentData(
        email_data=enrich_so_data,
        company_data=enrich_so_company_data,
        enriched_contents=enriched_contents,
    )


async def _get_company_urls_content(company_domain: str, enriched_contents: List[URLContent]) -> List[URLContent]:
    """Get relevant URL content for the company domain."""
    company_sitemap: Set[str] = await get_sitemap(company_domain, limit=100)
    # Make sure we include the initial company domain in the sitemap
    company_sitemap.add(company_domain)

    scraping_service = ScrapingService()
    relevant_urls = await scraping_service.pick_relevant_links(
        list(company_sitemap),
        20,
        f"You are a market research analyst that assesses the priorities of leads for a SaaS B2B start up. Your goal is to pick the URLs that will allow to fill the following JSON structure: {CustomerAssessementAgentOutput.model_json_schema()}",
    )

    relevant_url_content = await scraping_service.fetch_url_contents_concurrently(
        relevant_urls,
        request_timeout=60.0,
        use_cache=True,
    )

    limited_url_content = await scraping_service.limit_url_content_size(
        relevant_url_content,
        1_500_000,  # TODO: Make this dynamic based on the model used
    )

    limited_url_content.extend(enriched_contents)
    return limited_url_content


async def _create_minimal_output(
    client_email: str,
    enrichment_data: EnrichmentData,
) -> ExtendedCustomerAssessementAgentOutput:
    """Create a minimal output when no company information is available."""
    email_data = enrichment_data.email_data
    return ExtendedCustomerAssessementAgentOutput(
        base_user_email=client_email,
        base_user_name=email_data.full_name if email_data else None,
        base_user_title=email_data.headline if email_data else None,
        base_user_linkedin_url=email_data.linkedInUrl if email_data else None,
    )


class CustomerAssessmentService:
    @staticmethod
    async def run_customer_assessment(client_email: str) -> ExtendedCustomerAssessementAgentOutput:
        try:
            # Get company domain from email
            company_domain = await _get_company_domain(client_email)

            # Get enrichment data
            enrichment_data = await _get_enrichment_data(client_email)

            # Update company domain if found in enrichment data
            if enrichment_data.company_data and enrichment_data.company_data.urls:
                company_domain = company_domain or enrichment_data.company_data.urls.company_page

            # Recheck email classification if company domain wasn't found initially
            if not company_domain:
                # Just perform the classification without storing result
                await run_classify_email_domain_agent(
                    ClassifyEmailDomainAgentInput(email_domain=client_email),
                )

            # Return minimal output if no company domain is found
            if not company_domain:
                _logger.warning("No company domain found for email", extra={"email": client_email})
                return await _create_minimal_output(client_email, enrichment_data)

            # Get company URL content
            url_contents = await _get_company_urls_content(company_domain, enrichment_data.enriched_contents)

            # Run customer assessment agent
            customer_assessment_agent_output = await customer_assessement_agent(
                CustomerAssessementAgentInput(
                    main_company_domain=company_domain,
                    url_contents=url_contents,
                ),
            )

            # Create and return final output
            email_data = enrichment_data.email_data
            return ExtendedCustomerAssessementAgentOutput(
                base_user_email=client_email,
                base_user_name=email_data.full_name if email_data else None,
                base_user_title=email_data.headline if email_data else None,
                base_user_linkedin_url=email_data.linkedInUrl if email_data else None,
                **customer_assessment_agent_output.model_dump(),
            )
        except Exception as e:
            _logger.exception("Error running customer assessment", exc_info=e)
            return ExtendedCustomerAssessementAgentOutput(
                base_user_email=client_email,
                base_user_name=None,
                base_user_title=None,
                base_user_linkedin_url=None,
            )
