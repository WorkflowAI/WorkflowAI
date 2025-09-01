from uuid import UUID

from core.storage.clickhouse.query_builder import WJSON, Q, W, WJSONArray


class TestToSQL:
    def test_with_params(self):
        w = W("k1", "v") & W("k2", "v2", type="String") | W("k3", 1)
        sql = w.to_sql()
        assert sql
        assert sql[0] == "k1 = {v0:String} AND k2 = {v1:String} OR k3 = {v2:Int}"
        assert sql[1] == {"v0": "v", "v1": "v2", "v2": 1}

    def test_complex_and_or_combinations(self) -> None:
        # Test complex nested AND/OR conditions
        w = (W("field1", 1) & W("field2", "test")) | (W("field3", True) & W("field4", 2.5))
        sql = w.to_sql()
        assert sql
        assert sql[0] == "field1 = {v0:Int} AND field2 = {v1:String} OR field3 = {v2:Bool} AND field4 = {v3:Float}"
        assert sql[1] == {"v0": 1, "v1": "test", "v2": True, "v3": 2.5}

    def test_different_data_types(self) -> None:
        # Test various data types including UUID
        uuid_val = UUID("123e4567-e89b-12d3-a456-426614174000")
        w = W("int_field", 42) & W("float_field", 3.14) & W("bool_field", True) & W("uuid_field", uuid_val)
        sql = w.to_sql()
        assert sql
        assert (
            sql[0]
            == "int_field = {v0:Int} AND float_field = {v1:Float} AND bool_field = {v2:Bool} AND uuid_field = {v3:UUID}"
        )
        assert sql[1] == {"v0": 42, "v1": 3.14, "v2": True, "v3": uuid_val}

    def test_between_operator(self) -> None:
        # Test BETWEEN operator with different types
        w = W("age", (18, 65), operator=W.BETWEEN) & W("score", (0.0, 100.0), type="Float", operator=W.BETWEEN)
        sql = w.to_sql()
        assert sql
        assert sql[0] == "age BETWEEN {v0:Int} AND {v1:Int} AND score BETWEEN {v2:Float} AND {v3:Float}"
        assert sql[1] == {"v0": 18, "v1": 65, "v2": 0.0, "v3": 100.0}

    def test_query_builder(self) -> None:
        # Test Q function with various parameters
        where = W("status", "active") & W("age", 21)
        query, params = Q(
            "users",
            select=["id", "name", "age"],
            where=where,
            limit=10,
            offset=20,
        )
        assert (
            query == "SELECT id, name, age FROM users WHERE status = {v0:String} AND age = {v1:Int} LIMIT 10 OFFSET 20"
        )
        assert params == {"v0": "active", "v1": 21}

    def test_null_conditions(self) -> None:
        # Test handling of None values
        w = W("field1", None)
        sql = w.to_sql()
        assert sql == ("field1", {})

    def test_custom_operators(self) -> None:
        # Test custom operators
        w = W("age", 18, operator=">=") & W("name", "test%", operator="LIKE")
        sql = w.to_sql()
        assert sql
        assert sql[0] == "age >= {v0:Int} AND name LIKE {v1:String}"
        assert sql[1] == {"v0": 18, "v1": "test%"}

    def test_empty_operator(self) -> None:
        w = W("field1", None, operator="EMPTY", type="String")
        sql = w.to_sql()
        assert sql
        assert sql[0] == "empty(field1)"
        assert sql[1] == {}

    def test_in_queries(self) -> None:
        # Test IN queries with different types
        w1 = W("id", [1, 2, 3], type="Int")  # Numeric IN query
        sql1 = w1.to_sql()
        assert sql1
        assert sql1[0] == "id IN ({v0_0:Int}, {v0_1:Int}, {v0_2:Int})"
        assert sql1[1] == {"v0_0": 1, "v0_1": 2, "v0_2": 3}

        w2 = W("status", ["active", "pending"], type="String")  # String IN query
        sql2 = w2.to_sql()
        assert sql2
        assert sql2[0] == "status IN ({v0_0:String}, {v0_1:String})"
        assert sql2[1] == {"v0_0": "active", "v0_1": "pending"}

    def test_not_in_queries(self) -> None:
        w = W("status", ["active", "pending"], operator="!=", type="String")
        sql = w.to_sql()
        assert sql
        assert sql[0] == "status NOT IN ({v0_0:String}, {v0_1:String})"
        assert sql[1] == {"v0_0": "active", "v0_1": "pending"}

    def test_prewhere_clause(self) -> None:
        # Test PREWHERE clause in query builder
        prewhere = W("status", "active") & W("created_at", "2023-01-01", operator=">=", type="Date")
        where = W("age", 21)
        query, params = Q(
            "users",
            select=["id", "name"],
            prewhere=prewhere,
            where=where,
            limit=5,
        )
        expected_query = (
            "SELECT id, name FROM users "
            "PREWHERE status = {v0:String} AND created_at >= {v1:Date} "
            "WHERE age = {v2:Int} LIMIT 5"
        )
        assert query == expected_query
        assert params == {"v0": "active", "v1": "2023-01-01", "v2": 21}


class TestJsonExtractedKey:
    def test_simple_key(self):
        assert WJSON._json_extracted_key("String", "key", "test") == "simpleJSONExtractString(key, 'test')"  # pyright: ignore [reportPrivateUsage]

    def test_nested_key(self):
        assert WJSON._json_extracted_key("String", "key", "test1.test2") == "JSONExtractString(key, 'test1', 'test2')"  # pyright: ignore [reportPrivateUsage]


class TestWJSONArray:
    def test_string_array(self):
        w = WJSONArray(key="column", path="test", clause=W(key="", value="v1"))
        assert (
            w.to_sql_req()[0]
            == """
arrayExists(
    x -> x = {v0:String},
     JSONExtract(column, 'test', 'Array(String)')
)""".replace("\n", "").replace("    ", "")
        )

    def test_nested_object_array(self):
        w = WJSONArray(key="column", path="test", clause=WJSON(key="", path="k1", value="v1"))
        assert (
            w.to_sql_req()[0]
            == """
arrayExists(
            x -> simpleJSONExtractString(x, 'k1') = {v0:String},
             JSONExtractArrayRaw(column, 'test')
        )""".replace("\n", "").replace("    ", "")
        )
