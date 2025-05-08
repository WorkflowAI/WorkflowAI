from pydantic import BaseModel, Field


class DocumentationSection(BaseModel):
    title: str = Field(description="The title of the documentation section")
    content: str = Field(description="The content of the documentation section")

    def __hash__(self) -> int:
        # Needed to deduplicate picked documentation sections
        return hash((self.title, self.content))
