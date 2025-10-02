import base64
import contextlib
import hashlib
import re
import string
import unicodedata


def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def split_words(input_str: str) -> list[str]:
    name = re.sub("([a-z])([A-Z])", r"\1 \2", input_str)
    return re.split(r"\s|-|_", name)


def to_pascal_case(input_str: str, separator: str = "") -> str:
    components = split_words(input_str)
    return separator.join(x.title() for x in components)


def to_snake_case(input_str: str) -> str:
    components = split_words(input_str)
    return "_".join(x.lower() for x in components)


def to_kebab_case(input_str: str) -> str:
    components = split_words(input_str)
    return "-".join(x.lower() for x in components)


def b64_urldecode(input_str: str) -> bytes:
    """Decode a base64url encoded string and accepts no padding."""
    # Fix padding
    rem = len(input_str) % 4
    if rem > 0:
        input_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(input_str)


def normalize(s: str, case_sensitive: bool = False, remove_punctuation: bool = True):
    """Normalize a string for comparison by removing diacritics, making it case insensitive, and removing punctuation."""
    # Remove diacritics
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    if not case_sensitive:
        # Make case insensitive
        s = s.lower()
    # Remove punctuation
    if remove_punctuation:
        s = s.translate(str.maketrans("", "", string.punctuation))
    # Remove duplicate whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def slugify(s: str) -> str:
    n = normalize(s, case_sensitive=True, remove_punctuation=False)
    n = to_kebab_case(n)
    # Making sure by removing any non-url safe characters
    return re.sub(r"[^a-z0-9-]", "", n).replace("--", "-")


def is_url_safe(input_str: str) -> bool:
    return re.match(r"^[a-zA-Z0-9_-]+$", input_str) is not None


def remove_empty_lines(text: str) -> str:
    return re.sub(r"\n+", "\n", text)


def safe_b64decode(input_str: str | None) -> bytes | None:
    if not input_str:
        return None
    with contextlib.suppress(Exception):
        return base64.b64decode(input_str)
    return None


def is_valid_unicode(b: bytes):
    if len(b) != 2:
        return None
    # Convert bytes to an integer.
    try:
        code_point = int(b, 16)
    except ValueError:
        return None

    # Check that it's in the valid Unicode range and not a surrogate.
    if 0 <= code_point <= 0x10FFFF and not (0xD800 <= code_point <= 0xDFFF):
        return chr(code_point).encode()
    return None


def clean_unicode_chars(input_str: str) -> str:
    # Sometimes models return invalid unicode characters
    # For example \ud83d or \u0000e9
    # First we strip encode in utf8 by ingoring all errors
    encoded = input_str.encode(errors="ignore")
    # Double null bytes is a special case, we check if we can
    # "Fix" them. We should really not have null bytes in the first place so they can be removed
    splits = encoded.split(b"\x00")
    if len(splits) == 1:
        return encoded.decode()

    enumerated = enumerate(splits)
    next(enumerated)  # we skip the first one
    for i, val in enumerated:
        first_two_bytes = val[:2]
        # Check if \x[first two bytes] is a valid unicode character
        if c := is_valid_unicode(first_two_bytes):
            # We have a valid unicode character so we can
            # Replace the first two bytes with the valid character
            splits[i] = c + val[2:]
        else:
            # We don't have a valid unicode character
            # But just in case it's meant to be a null byte we leave the string as is
            splits[i] = val

    return b"".join(splits).decode()


def obfuscate(input_str: str, max_chars: int):
    if len(input_str) <= max_chars:
        return "***"
    return input_str[:max_chars] + "***"


def hash_string(data: str) -> str:
    """A simple hash function that returns a string of 16 characters.
    Not for security."""
    # Using blake2s for speed. We don't need security here
    return hashlib.blake2s(data.encode()).hexdigest()
