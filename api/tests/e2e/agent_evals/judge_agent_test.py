from tests.e2e.agent_evals.judge_agent import fuzzy_contains, judge_answer, normalize_text


async def test_judge_answer_basic():
    response = await judge_answer(
        answer_to_judge="Hello ! How can I help you ?",
        assertions=[
            "is in English.",
            "is at least three sentences long",
            "contains a Python code block",
        ],
    )
    assert len(response.judgements) == 3
    assert response.judgements[0].is_assertion_enforced is True
    assert response.judgements[1].is_assertion_enforced is False
    assert response.judgements[2].is_assertion_enforced is False


class TestNormalizeText:
    """Test cases for the normalize_text function."""

    def test_basic_normalization(self):
        """Test basic text normalization."""
        assert normalize_text("Hello World") == "hello world"
        assert normalize_text("HELLO WORLD") == "hello world"

    def test_whitespace_normalization(self):
        """Test whitespace removal and normalization."""
        assert normalize_text("  hello   world  ") == "hello world"
        assert normalize_text("hello\n\tworld\r\n") == "hello world"
        assert normalize_text("hello\t\t\tworld") == "hello world"

    def test_punctuation_removal(self):
        """Test punctuation removal."""
        assert normalize_text("hello, world!") == "hello world"
        assert normalize_text("hello; world?") == "hello world"
        assert normalize_text("hello-world") == "hello world"
        assert normalize_text("'hello' \"world\"") == "hello world"
        assert normalize_text("hello:world.") == "hello world"

    def test_empty_and_edge_cases(self):
        """Test edge cases."""
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""
        assert normalize_text("!!!") == ""
        assert normalize_text(".,;:") == ""


class TestFuzzyContains:
    """Test cases for the fuzzy_contains function."""

    def test_exact_matches(self):
        """Test exact string matches."""
        assert fuzzy_contains("hello world", "This is a hello world example") is True
        assert fuzzy_contains("test", "This is a test case") is True

    def test_case_insensitive_matches(self):
        """Test case insensitive matching."""
        assert fuzzy_contains("Hello World", "this is a hello world example") is True
        assert fuzzy_contains("TEST", "this is a test case") is True
        assert fuzzy_contains("hello WORLD", "This Is A Hello World Example") is True

    def test_whitespace_variations(self):
        """Test matching with different whitespace."""
        assert fuzzy_contains("hello world", "hello    world is here") is True
        assert fuzzy_contains("hello  world", "hello world is here") is True
        assert fuzzy_contains("hello\nworld", "hello world is here") is True
        assert fuzzy_contains("hello\tworld", "hello world is here") is True

    def test_punctuation_variations(self):
        """Test matching with different punctuation."""
        assert fuzzy_contains("hello, world!", "hello world is here") is True
        assert fuzzy_contains("hello world", "hello, world! is here") is True
        assert fuzzy_contains("hello-world", "hello world is here") is True
        assert fuzzy_contains("'hello world'", "hello world is here") is True

    def test_fuzzy_matching_with_typos(self):
        """Test fuzzy matching with minor typos."""
        # Minor character differences should still match with default threshold
        assert fuzzy_contains("hello world", "helo world is here") is True
        assert fuzzy_contains("test case", "test cse is here") is True
        assert fuzzy_contains("example text", "exampl text is here") is True

    def test_threshold_behavior(self):
        """Test different threshold values."""
        # With high threshold, require more similarity
        assert fuzzy_contains("hello world", "helo worl", threshold=0.9) is False
        assert fuzzy_contains("hello world", "hello world", threshold=0.9) is True

        # With low threshold, allow more differences
        assert fuzzy_contains("hello world", "helo worl", threshold=0.6) is True
        assert fuzzy_contains("test", "pest", threshold=0.6) is True

    def test_not_found_cases(self):
        """Test cases where verbatim should not be found."""
        assert fuzzy_contains("completely different", "hello world example") is False
        assert fuzzy_contains("not here", "this is a test case") is False
        assert fuzzy_contains("xyz", "hello world") is False

    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        # Empty strings
        assert fuzzy_contains("", "hello world") is False
        assert fuzzy_contains("hello", "") is False
        assert fuzzy_contains("", "") is False

        # None values should return False
        assert fuzzy_contains(None, "hello world") is False
        assert fuzzy_contains("hello", None) is False
        assert fuzzy_contains(None, None) is False

    def test_substring_matching(self):
        """Test that substrings are properly matched."""
        text = "The quick brown fox jumps over the lazy dog"
        assert fuzzy_contains("quick brown", text) is True
        assert fuzzy_contains("fox jumps", text) is True
        assert fuzzy_contains("lazy dog", text) is True

    def test_partial_word_matching(self):
        """Test matching with partial words."""
        text = "implementation details for the project"
        assert fuzzy_contains("implementation detail", text) is True
        assert fuzzy_contains("details for project", text) is True

    def test_long_text_matching(self):
        """Test matching in longer texts."""
        long_text = """
        This is a very long piece of text that contains multiple sentences.
        It includes various words and phrases that we might want to match.
        The fuzzy matching should work even in longer documents.
        """
        assert fuzzy_contains("very long piece", long_text) is True
        assert fuzzy_contains("multiple sentences", long_text) is True
        assert fuzzy_contains("fuzzy matching should work", long_text) is True

    def test_special_characters(self):
        """Test matching with special characters."""
        text = "The API returns JSON with @mentions and #hashtags"
        assert fuzzy_contains("API returns JSON", text) is True
        assert fuzzy_contains("mentions and hashtags", text) is True
        # Special characters should be normalized away
        assert fuzzy_contains("@mentions", text) is True
        assert fuzzy_contains("#hashtags", text) is True


class TestIntegrationScenarios:
    """Integration test scenarios that simulate real usage."""

    def test_llm_response_variations(self):
        """Test scenarios that might occur with LLM responses."""
        llm_response = """
        The system should implement user authentication using JWT tokens.
        Users can sign up with email and password, and then log in to access protected routes.
        The authentication flow includes token validation and refresh mechanisms.
        """

        # These verbatims should be found even with minor variations
        assert fuzzy_contains("user authentication using JWT", llm_response) is True
        assert fuzzy_contains("sign up with email and password", llm_response) is True
        assert fuzzy_contains("token validation and refresh", llm_response) is True

        # With minor typos or variations
        assert fuzzy_contains("user authentication using JWT tokens", llm_response) is True
        assert fuzzy_contains("email and password", llm_response) is True

    def test_code_snippet_matching(self):
        """Test matching code snippets that might have formatting differences."""
        code_response = "The function should return json.dumps(data) for serialization"

        assert fuzzy_contains("json.dumps(data)", code_response) is True
        assert fuzzy_contains("return json dumps data", code_response) is True
        assert fuzzy_contains("function should return", code_response) is True

    def test_technical_documentation_matching(self):
        """Test matching technical documentation content."""
        tech_doc = """
        Configure the database connection using the following parameters:
        - host: localhost
        - port: 5432
        - database: myapp_production
        - ssl_mode: require
        """

        assert fuzzy_contains("database connection using", tech_doc) is True
        assert fuzzy_contains("host localhost", tech_doc) is True
        assert fuzzy_contains("port 5432", tech_doc) is True
        assert fuzzy_contains("ssl mode require", tech_doc) is True
