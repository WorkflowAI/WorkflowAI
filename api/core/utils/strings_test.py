import pytest

from .strings import (
    b64_urldecode,
    clean_unicode_chars,
    is_url_safe,
    is_valid_unicode,
    normalize,
    obfuscate,
    remove_accents,
    remove_empty_lines,
    slugify,
    split_words,
    to_pascal_case,
    to_snake_case,
)


@pytest.mark.parametrize(
    "string, exp",
    [
        ("café", "cafe"),
        ("hello", "hello"),
    ],
)
def test_remove_accents(string: str, exp: str) -> None:
    assert remove_accents(string) == exp


@pytest.mark.parametrize(
    "string, exp",
    [
        ("hello", ["hello"]),
        ("helloBla", ["hello", "Bla"]),
        ("hello bla", ["hello", "bla"]),
        ("hello-bla", ["hello", "bla"]),
        ("hello_bla", ["hello", "bla"]),
        ("ExtractPhysicalLocationFromEmail", ["Extract", "Physical", "Location", "From", "Email"]),
    ],
)
def test_split_words(string: str, exp: list[str]) -> None:
    assert split_words(string) == exp


@pytest.mark.parametrize(
    "string, exp",
    [
        ("hello", "Hello"),
        ("helloBla", "HelloBla"),
        ("hello bla", "HelloBla"),
        ("hello-bla", "HelloBla"),
        ("hello_bla", "HelloBla"),
        ("ExtractPhysicalLocationFromEmail", "ExtractPhysicalLocationFromEmail"),
    ],
)
def test_to_pascal_case(string: str, exp: str) -> None:
    assert to_pascal_case(string) == exp


@pytest.mark.parametrize(
    "string, exp",
    [
        ("hello", "hello"),
        ("helloBla", "hello_bla"),
        ("hello bla", "hello_bla"),
        ("hello-bla", "hello_bla"),
        ("hello_bla", "hello_bla"),
    ],
)
def test_to_snake_case(string: str, exp: str) -> None:
    assert to_snake_case(string) == exp


@pytest.mark.parametrize(
    "b64,hex",
    [
        (
            "ZXlKaGJHY2lPaUpJVXpJMU5pSjkuU1hUaWdKbHpJR0VnWkdGdVoyVnliM1Z6SUdKMWMybHVaWE56TENCR2NtOWtieXdnWjI5cGJtY2diM1YwSUhsdmRYSWdaRzl2Y2k0",
            "65794a68624763694f694a49557a49314e694a392e53585469674a6c7a494745675a4746755a3256796233567a49474a3163326c755a584e7a4c434247636d396b627977675a323970626d63676233563049486c76645849675a473976636934",
        ),
    ],
)
def test_b64_urldecode(b64: str, hex: str) -> None:
    decoded = b64_urldecode(b64)
    assert decoded.hex() == hex


@pytest.mark.parametrize(
    "string, exp",
    [
        ("café", "cafe"),
        ("hello", "hello"),
        ("Hello", "hello"),
        ("Hello, World!", "hello world"),
        ("Hello,  World!", "hello world"),
        ("Hello\n \nWorld  ", "hello world"),
    ],
)
def test_normalize(string: str, exp: str) -> None:
    assert normalize(string) == exp


@pytest.mark.parametrize(
    "string, exp",
    [
        ("hello", True),
        ("hello-world", True),
        ("hello_world", True),
        ("hello world", False),
        ("hello-world-123", True),
        ("hello-world-123!", False),
    ],
)
def test_is_url_safe(string: str, exp: bool) -> None:
    assert is_url_safe(string) == exp


@pytest.mark.parametrize(
    ("string", "exp"),
    [
        ("hello", "hello"),
        ("Hello World", "hello-world"),
        ("Café au lait", "cafe-au-lait"),
        ("émojí 😀 test", "emoji-test"),
        ("Special@#$%^&*()Characters", "specialcharacters"),
        ("Multiple   spaces", "multiple-spaces"),
        ("mixed-CASE_string", "mixed-case_string"),
        ("números_123", "numeros_123"),
        ("Über straße", "uber-strae"),
        ("  leading-trailing-spaces  ", "leading-trailing-spaces"),
        ("a/b/c/path-like", "abcpath-like"),
        ("dots.in.string", "dotsinstring"),
        ("under_score_case", "under_score_case"),
        ("camelCaseText", "camel-case-text"),
        ("PascalCaseText", "pascal-case-text"),
        ("text_summarizer_agent", "text_summarizer_agent"),
        ("Text_Summarizer_Agent", "text_summarizer_agent"),
    ],
)
def test_slugify(string: str, exp: str) -> None:
    assert slugify(string) == exp
    assert is_url_safe(exp), "sanity"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello\n\nworld", "hello\nworld"),  # Basic case with one empty line
        ("hello\nworld", "hello\nworld"),  # No empty lines
        ("hello\n\n\nworld", "hello\nworld"),  # Multiple empty lines compressed to one
        ("hello\n\n\n\nworld", "hello\nworld"),  # More empty lines compressed to one
        ("", ""),  # Empty string
        ("\n\n", "\n"),  # Just empty lines become one newline
        ("\n\n\n", "\n"),  # Multiple empty lines become one newline
        ("hello\n\nworld\n\n", "hello\nworld\n"),  # Empty lines at the end
        ("\n\nhello\n\nworld", "\nhello\nworld"),  # Empty lines at the beginning
        ("hello\nworld\n", "hello\nworld\n"),  # Trailing newline preserved
        ("hello\r\n\r\nworld", "hello\r\n\r\nworld"),  # Windows line endings remain unchanged
    ],
)
def test_remove_empty_lines(text: str, expected: str) -> None:
    """Test that remove_empty_lines correctly replaces any consecutive newline characters with a single newline."""
    assert remove_empty_lines(text) == expected


@pytest.mark.parametrize(
    "input_str, expected_output",
    [
        pytest.param("hello \u0000e9 world", "hello é world", id="null byte"),
        pytest.param("hello\ud83d\udc00world", "helloworld", id="invalid surrogate"),
        # For now we split surrogates char
        pytest.param("hello\ud83d\ude00world", "helloworld", id="valid surrogate"),
        pytest.param("hello😁world", "hello😁world", id="emoji"),
        pytest.param("hello\u0000ci29", "helloci29", id="actual null byte"),
    ],
)
def test_clean_unicode_chars(input_str: str, expected_output: str):
    assert clean_unicode_chars(input_str) == expected_output


class TestObfuscate:
    @pytest.mark.parametrize(
        "input_str, max_chars, expected_output",
        [
            pytest.param("hello world", 5, "hello***", id="basic"),
            pytest.param("hello world", 11, "***", id="max chars reached"),
        ],
    )
    def test_obfuscate(self, input_str: str, max_chars: int, expected_output: str):
        assert obfuscate(input_str, max_chars) == expected_output


class TestIsValidUnicode:
    def test_not_raised_on_single_byte(self):
        assert is_valid_unicode(b"a") is None
