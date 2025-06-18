# pyright: reportPrivateUsage=false

from pydantic import BaseModel

from api.routers._common import _skipJsonSchemaAnnotation


class TestSkipJsonSchemaAnnotation:
    def test_include_private(self):
        IncludeAnn = _skipJsonSchemaAnnotation(True)
        NotIncludeAnn = _skipJsonSchemaAnnotation(False)

        class Model(BaseModel):
            a: IncludeAnn[int]  # type: ignore
            b: NotIncludeAnn[str]  # type: ignore
            c: int

        assert Model.model_json_schema() == {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "title": "A"},
                "c": {"type": "integer", "title": "C"},
            },
            "required": ["a", "c"],
            "title": "Model",
        }
