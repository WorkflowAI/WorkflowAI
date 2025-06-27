from pydantic import BaseModel, Field


class DocumentationSection(BaseModel):
    # The title is the path to the documentation section, e.g. "reference/authentication"
    file_path: str = Field(description="The title of the documentation section")
    content: str = Field(description="The content of the documentation section")

    def __hash__(self) -> int:
        # Needed to deduplicate picked documentation sections
        return hash((self.file_path, self.content))
