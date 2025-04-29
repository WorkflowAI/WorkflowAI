from core.domain.task_io import SerializableTaskIO

from .task_variant import SerializableTaskVariant


class TestComputeHashes:
    def test_simple(self):
        task = SerializableTaskVariant(
            id="",
            task_schema_id=1,
            name="",
            input_schema=SerializableTaskIO.from_json_schema(
                {"type": "object", "properties": {"a": {"type": "string"}}},
            ),
            output_schema=SerializableTaskIO.from_json_schema(
                {"type": "object", "properties": {"b": {"type": "string"}}},
            ),
        )

        input_hash = task.compute_input_hash({"a": "a"})
        assert input_hash == "582af9ef5cdc53d6628f45cb842f874a"
        output_hash = task.compute_output_hash({"b": "b"})
        assert output_hash == "53dd738814f8440b36a9ac19e49e9b8d"

        # Check with extra keys
        input_hash1 = task.compute_input_hash({"a": "a", "b": "b"})
        output_hash1 = task.compute_output_hash({"b": "b", "a": "a"})
        assert input_hash1 == input_hash
        assert output_hash1 == output_hash


class TestModelHash:
    def test_order_matters_for_variant_id(self):
        task = SerializableTaskVariant(
            input_schema=SerializableTaskIO.from_json_schema(
                {
                    "type": "object",
                    "properties": {"a": {"type": "string"}, "c": {"type": "string"}},
                },
            ),
            output_schema=SerializableTaskIO.from_json_schema(
                {
                    "type": "object",
                    "properties": {"b": {"type": "string"}, "d": {"type": "string"}},
                },
            ),
        )
        assert task.id == "bc9f9d381fdcc243f775db72e2a5c2d3"
        assert task.input_schema.version == "bcbd6f7da5b4183bc54f8abee71b5e65"
        assert task.output_schema.version == "41d874dbff03ca2c14c374a0d308d44d"

        # Now change the order of the properties
        task1 = SerializableTaskVariant(
            input_schema=SerializableTaskIO.from_json_schema(
                {
                    "type": "object",
                    "properties": {"c": {"type": "string"}, "a": {"type": "string"}},
                },
            ),
            output_schema=SerializableTaskIO.from_json_schema(
                {
                    "type": "object",
                    "properties": {"d": {"type": "string"}, "b": {"type": "string"}},
                },
            ),
        )
        assert task1.id == "64c7f2b8daea6058de1b9a2ed0be536a" != task.id
        assert task1.input_schema.version == task.input_schema.version
        assert task1.output_schema.version == task.output_schema.version
