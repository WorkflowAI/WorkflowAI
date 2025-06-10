import json
from typing import Any

import pytest

from core.utils.dicts import set_at_keypath_str
from tests.utils import fixtures_json, mock_aiter

from .streams import JSONStreamError, JSONStreamParser, standard_wrap_sse


def _agg_stream(splits: list[str], is_tolerant: bool = False) -> list[tuple[str, Any]]:
    agg: list[tuple[str, Any]] = []

    streamer = JSONStreamParser(is_tolerant=is_tolerant)

    for chunk in splits:
        if c := streamer.process_chunk(chunk):
            agg.extend(c)

    return agg


# Alternative to parametrize to avoid having really long arrays
def _map_stream(raw: Any, chars: int = 3) -> list[tuple[str, Any]]:
    raw_json = json.dumps(raw)
    splits = [raw_json[i : i + chars] for i in range(0, len(raw_json), chars)]
    return _agg_stream(splits)


def _stream_to_dict(raw: Any, chunks: list[str], is_tolerant: bool = True) -> dict[str, Any]:
    for update in _agg_stream(chunks, is_tolerant=is_tolerant):
        set_at_keypath_str(raw, *update)
    return raw


def test_streaming_array_bool() -> None:
    res = _map_stream({"nested_bools": [True, False, True]})

    assert res == [
        ("nested_bools.0", True),
        ("nested_bools.0", True),
        ("nested_bools.1", False),
        ("nested_bools.1", False),
        ("nested_bools.2", True),
        ("nested_bools.2", True),
    ]


def test_streaming_consecutive_arrays() -> None:
    res = _map_stream({"n1": [True, False], "n2": [1, 2]})
    assert res == [
        ("n1.0", True),
        ("n1.0", True),
        ("n1.1", False),
        ("n1.1", False),
        ("n1.1", False),
        ("n2.0", 1),
        ("n2.1", 2),
    ]


def test_streaming_array_int() -> None:
    res = _map_stream({"nested_ints": [1, 2, 3]})

    assert res == [
        ("nested_ints.0", 1),
        ("nested_ints.1", 2),
        ("nested_ints.2", 3),
    ]


def test_streaming_nested_dicts() -> None:
    res = _map_stream({"nested_dicts": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]})

    assert res == [
        ("nested_dicts.0.a", 1),
        ("nested_dicts.0.b", 2),
        ("nested_dicts.1.a", 3),
        ("nested_dicts.1.b", 4),
    ]


def test_streaming_nested_strings() -> None:
    res = _map_stream({"nested_strings": ["12", "23", "34"]})
    assert res == [
        ("nested_strings.0", "12"),
        ("nested_strings.1", "23"),
        ("nested_strings.2", "34"),
    ]


@pytest.fixture
def raw_obj() -> dict[str, Any]:
    return {
        "name": "test",
        "description": "test",
        "special": '",[{}]',
        "nested_bools": [True, False, True],
        "nested_ints": [1, 2, 3],
        "nested_floats": [1.0, 2.0, 3.0],
        "nested_strings": ["12", "23", "34"],
        "nested_dicts": [
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
            {"a": 5, "b": 6},
        ],
    }


def test_streaming_complex(raw_obj: dict[str, Any]) -> None:
    res = _map_stream(raw_obj)

    out: dict[str, Any] = {}

    for k, v in res:
        set_at_keypath_str(out, k, v)

    assert out == raw_obj


def test_streaming_complex_long_chunks(raw_obj: dict[str, Any]) -> None:
    res = _map_stream(raw_obj, 15)
    assert res == [
        ("name", "test"),
        ("description", "test"),
        ("special", '",[{}]'),
        ("nested_bools.0", True),
        ("nested_bools.1", False),
        ("nested_bools.2", True),
        ("nested_ints.0", 1),
        ("nested_ints.1", 2),
        ("nested_ints.2", 3),
        ("nested_floats.0", 1.0),
        ("nested_floats.1", 2.0),
        ("nested_floats.1", 2.0),
        ("nested_floats.2", 3.0),
        ("nested_strings.0", "1"),
        ("nested_strings.0", "12"),
        ("nested_strings.1", "23"),
        ("nested_strings.2", "34"),
        ("nested_dicts.0.a", 1),
        ("nested_dicts.0.b", 2),
        ("nested_dicts.1.a", 3),
        ("nested_dicts.1.b", 4),
        ("nested_dicts.2.a", 5),
        ("nested_dicts.2.b", 6),
    ]

    # Sanity

    out: dict[str, Any] = {}

    for k, v in res:
        set_at_keypath_str(out, k, v)

    assert out == raw_obj


def test_stream_empty_array() -> None:
    chunks = ["{\n", " ", ' "', "categories", '":', " []\n", "}\n"]
    # Making sure this is a valid json
    assert json.loads("".join(chunks)) == {"categories": []}
    agg = _agg_stream(chunks)
    assert agg == [("categories", [])]


def test_stream_empty_obj() -> None:
    chunks = ["{\n", " ", ' "', "categories", '":', " {}\n", "}\n"]
    # Making sure this is a valid json
    assert json.loads("".join(chunks)) == {"categories": {}}
    agg = _agg_stream(chunks)
    assert agg == [("categories", {})]


def test_stream_empty_str() -> None:
    chunks = ["{\n", " ", ' "', "categories", '":', ' "', '"}\n']
    # Making sure this is a valid json
    assert json.loads("".join(chunks)) == {"categories": ""}
    agg = _agg_stream(chunks)
    assert agg == [("categories", "")]


def test_stream_empty_not_json() -> None:
    chunks = ["balb", "{\n", " ", ' "', "categories", '":', ' "', '"}\n', "balb"]
    agg = _agg_stream(chunks)
    assert agg == [("categories", "")]


@pytest.mark.parametrize(
    "chunks",
    [
        # - is at the end of a chunk so it will not be sent
        ["{\n", " ", ' "', "categories", '":', " -", "5}\n"],
        # - is within a chunk
        ["{\n", " ", ' "', "categories", '":', " -5", "}\n"],
    ],
)
def test_stream_negative_number(chunks: list[str]) -> None:
    assert json.loads("".join(chunks)) == {"categories": -5}
    # Making sure this is a valid json
    agg = _agg_stream(chunks)
    assert agg == [("categories", -5)]


def test_new_line_in_string() -> None:
    chunks = ["{\n", " ", ' "', "answer", '":', ' "', "Red", "\\n", "Orange", '"\n', "}"]
    assert json.loads("".join(chunks)) == {"answer": "Red\nOrange"}
    agg = _agg_stream(chunks)
    assert agg[-1] == ("answer", "Red\nOrange")


def test_new_line_and_quote() -> None:
    chunks = ["{\n", " ", ' "', "answer", '":', ' "\\"', "Red", '\\"\\', "n", '\\"', "Blue", '\\"', '"\n', "}"]
    assert json.loads("".join(chunks)) == {"answer": '"Red"\n"Blue"'}
    agg = _agg_stream(chunks)
    assert agg[-1] == ("answer", '"Red"\n"Blue"')


def test_unicode_escape_across_chunks() -> None:
    chunks = ['{"a": "\\u202', '2"}']
    agg = _agg_stream(chunks)
    assert agg == [("a", "•")]


def test_invalid_json_with_comma() -> None:
    chunks = ["{\n", "}", ","]
    # The last comma is not part of the json so we check the json without it
    assert json.loads("".join(chunks)[:-1]) == {}, "sanity"

    assert _agg_stream(chunks) == []


class TestSmartQuoteEscapting:
    def test_cuts_right_after_quote(self) -> None:
        chunks = ['{"a": "b"', "}"]
        assert json.loads("".join(chunks)) == {"a": "b"}
        agg = _agg_stream(chunks)
        assert agg == [("a", "b")]

    def test_cuts_right_after_quote_multiple_updates(self) -> None:
        # Checks when a chunk ends right after a quote but the chunk contains multiple updates
        chunks = ['{"a": "b", "c": "d"', "}"]
        assert json.loads("".join(chunks)) == {"a": "b", "c": "d"}
        agg = _agg_stream(chunks)
        assert agg == [("a", "b"), ("c", "d")]

    _JSON_WITH_INVALID_QUOTES = '{"a": "b"e", "c": "" d"}'

    def test_json_with_invalid_quote_sanity(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            json.loads(self._JSON_WITH_INVALID_QUOTES)

    @pytest.mark.parametrize("cut_idx", range(len(_JSON_WITH_INVALID_QUOTES)))
    def test_escape_quote_in_string_with_cut_after_quote(self, cut_idx: int) -> None:
        chunks = [self._JSON_WITH_INVALID_QUOTES[:cut_idx], self._JSON_WITH_INVALID_QUOTES[cut_idx:]]

        agg = _agg_stream(chunks)
        assert len(agg) >= 2
        assert ("a", 'b"e') in agg
        assert ("c", '" d') in agg


def test_invalid_json_llama_70b() -> None:
    # Weird payload we received when running llama 70b
    chunks: list[str] = fixtures_json("streams/invalid_llama_70b.json")
    with pytest.raises(JSONStreamError) as e:
        _agg_stream(chunks)

    assert str(e.value) == "Cannot increment array index when not in an array"


_DIRTY_JSON = '{\\n  "filtered_contacts": [\\n    {\\n      "contact_user_id": "USR82132",\\n      "phone_number": "+1780987654",\\n      "first_name": "Victoria",\\n      "last_name": "Reed",\\n      "nickname": "Vicky",\\n      "birthdate": "1993-03-03",\\n      "street_address": "1001 Red Rock",\\n      "city": "Las Vegas",\\n      "state": "Nevada",\\n      "postal_code": "89109",\\n      "country": "USA",\\n      "email": "victoria.reed@example.com",\\n      "organization": "CasinoRoyale",\\n      "job_title": "Gaming Manager"\\n    },\\n    {\\n      "contact_user_id": "USR90234",\\n      "phone_number": "+1321456789",\\n      "first_name": "Jeremy",\\n      "last_name": "Tucker",\\n      "nickname": "Jerm",\\n      "birthdate": "1986-07-21",\\n      "street_address": "888 Desert View",\\n      "city": "Reno",\\n      "state": "Nevada",\\n      "postal_code": "89501",\\n      "country": "USA",\\n      "email": "jeremy.tucker@example.com",\\n      "organization": "NVTech",\\n      "job_title": "Systems Analyst"\\n    }\\n  ]\\n}'
_PARSED_JSON = json.loads(_DIRTY_JSON.replace("\\n", "\n"))


def test_full_payload_with_weird_spaces():
    # Single chunk with dirty spaces
    cleaned = '{"filtered_contacts":[{"contact_user_id":"USR82132","phone_number":"+1780987654","first_name":"Victoria","last_name":"Reed","nickname":"Vicky","birthdate":"1993-03-03","street_address":"1001 Red Rock","city":"Las Vegas","state":"Nevada","postal_code":"89109","country":"USA","email":"victoria.reed@example.com","organization":"CasinoRoyale","job_title":"Gaming Manager"},{"contact_user_id":"USR90234","phone_number":"+1321456789","first_name":"Jeremy","last_name":"Tucker","nickname":"Jerm","birthdate":"1986-07-21","street_address":"888 Desert View","city":"Reno","state":"Nevada","postal_code":"89501","country":"USA","email":"jeremy.tucker@example.com","organization":"NVTech","job_title":"Systems Analyst"}]}'
    from_cleaned = _stream_to_dict({}, [cleaned])
    assert from_cleaned == json.loads(cleaned)

    from_dirty = _stream_to_dict({}, [_DIRTY_JSON])
    assert from_dirty == from_cleaned


@pytest.mark.parametrize("cut_idx", range(len(_DIRTY_JSON)))
def test_all_splits_in_json(cut_idx: int):
    chunks = [_DIRTY_JSON[:cut_idx], _DIRTY_JSON[cut_idx:]]
    parsed = _stream_to_dict({}, chunks)
    assert parsed == _PARSED_JSON


def test_4o_mini_tabs():
    # 4o mini returns a bunch of tabs which breaks the json
    raw_str = """{"characters":{\n \t\t\t},"bla":"bla"}"""
    parsed = _stream_to_dict({}, [raw_str])
    assert parsed == {"characters": {}, "bla": "bla"}


class TestFailures:
    def test_unfixable_json(self) -> None:
        txt = '{meal_plan": "hello"}'
        with pytest.raises(JSONStreamError):
            _stream_to_dict({}, [txt], is_tolerant=False)

        # The same one should not fail in tolerant mode
        assert _stream_to_dict({}, [txt], is_tolerant=True) == {}


class TestWrapSSE:
    async def test_openai(self):
        iter = mock_aiter(
            b"data: 1",
            b"2\n\ndata: 3\n\n",
        )

        wrapped = standard_wrap_sse(iter)
        chunks = [chunk async for chunk in wrapped]
        assert chunks == [b"12", b"3"]

    async def test_multiple_events_in_single_chunk(self):
        iter = mock_aiter(
            b"data: 1\n\ndata: 2\n\ndata: 3\n\n",
        )
        chunks = [chunk async for chunk in standard_wrap_sse(iter)]
        assert chunks == [b"1", b"2", b"3"]

    async def test_split_at_newline(self):
        # Test that we correctly handle when a split happens between the new line chars
        iter = mock_aiter(
            b"data: 1\n",
            b"\ndata: 2\n\n",
        )
        chunks = [chunk async for chunk in standard_wrap_sse(iter)]
        assert chunks == [b"1", b"2"]

    async def test_split_at_data(self):
        # Test that we correctly handle when a split happens between the new line chars
        iter = mock_aiter(
            b"da",
            b"ta: 1\n",
            b"\ndata: 2\n\n",
        )
        chunks = [chunk async for chunk in standard_wrap_sse(iter)]
        assert chunks == [b"1", b"2"]
