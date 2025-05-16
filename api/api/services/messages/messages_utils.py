from typing import Any, Iterable

from core.domain.message import Message
from core.utils.schema_sanitation import streamline_schema
from core.utils.templates import extract_variable_schema


def json_schema_for_template(
    messages: Iterable[Message],
    base_schema: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, int]:
    """Returns a json schema for template variables present in the messages and the index
    of the last templated message"""

    # TODO: handle files as strings in templates
    # var_regexp = re.compile(r"\{\{([^}]+)\}\}")

    # files: dict[str, FileKind | str] = {}
    schema: dict[str, Any] | None = None
    last_templated_index = -1
    for i, m in enumerate(messages):
        # If format is not provided, then we treat as a plain string
        # if not format:
        #     templatable_parts.append(m)
        #     continue
        # # If format is provided and the whole content is a variable
        # if match := var_regexp.match(m):
        #     files[match.group(1)] = format
        #     continue
        # We are in a case where the content is a mix of variables and plain text so we can't
        # really extract the file
        for c, _ in m.content_iterator():
            schema, is_templated = extract_variable_schema(c, start_schema=schema, use_types_from=base_schema)
            if is_templated:
                last_templated_index = i

    # for var, kind in files.items():
    #     # We just add the format here
    #     # It will be streamlined and replace with the proper
    #     schema.setdefault("properties", {})[var] = {"$ref": "#/$defs/File", "format": kind}
    return streamline_schema(schema) if schema else None, last_templated_index
