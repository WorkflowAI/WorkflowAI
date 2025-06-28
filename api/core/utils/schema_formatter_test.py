# pyright: reportPrivateUsage=false
from pydantic import BaseModel, Field

from core.utils.schema_formatter import format_schema_as_yaml_description


def test_format_schema_as_yaml_description():
    """Test the format_schema_as_yaml_description function with a simple Pydantic model"""

    class Address(BaseModel):
        street: str = Field(description="Street address")
        city: str = Field(description="City name")

    class SimpleModel(BaseModel):
        name: str = Field(description="The name")
        age: int = Field(description="The age")
        active: bool = Field(description="Whether active")
        addresses: list[Address] = Field(description="List of addresses")
        empty_desc: str = Field(description="")
        no_desc: str

    result = format_schema_as_yaml_description(SimpleModel)

    expected_description = """name: The name
age: The age
active: Whether active
addresses: List of addresses
  street: Street address
  city: City name
empty_desc:
no_desc:"""

    assert result == expected_description
