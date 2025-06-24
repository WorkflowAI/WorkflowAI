from api.routers.mcp.mcp_server import description_for_search_documentation


def test_description_includes_index_page():
    """Ensure the dynamically generated description lists the `index` page."""
    description = description_for_search_documentation()

    assert "'index'" in description, "The index page should be present in the generated available pages list."
