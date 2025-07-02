# pyright: reportPrivateUsage=false

import pytest

from core.utils.templates import InvalidTemplateError, TemplateManager, extract_variable_schema


@pytest.fixture
def template_manager():
    return TemplateManager()


class TestCompileTemplate:
    async def test_compile_template(self, template_manager: TemplateManager):
        compiled, variables = await template_manager.compile_template("Hello, {{ name }}!")
        assert compiled
        assert variables == {"name"}

    async def test_compile_complex_template(self, template_manager: TemplateManager):
        template = """
Team Members:
{% for member in team.members %}
- {{ member.name }} ({{ member.role }})
    Projects:
    {% for project in member.projects %}
    * {{ project.name }} - Status: {{ project.status }}
    {% endfor %}
{% endfor %}

{% for project in projects %}
* {{ project.name }} - Status: {{ project.status }}
{% endfor %}

{% if customer.name == "John" %}
Hello, John!
{% else %}
Hello, {{ customer.name }}!
{% endif %}
"""
        compiled, variables = await template_manager.compile_template(template)
        assert compiled
        assert variables == {"team", "projects", "customer"}

    async def test_error_on_missing_variable(self, template_manager: TemplateManager):
        with pytest.raises(InvalidTemplateError) as e:
            await template_manager.compile_template("Hello, {{ name }!")
        assert e.value.message == "unexpected '}'"
        assert e.value.line_number == 1


class TestRenderTemplate:
    async def test_render_template(self, template_manager: TemplateManager):
        data = {"name": "John"}
        rendered, variables = await template_manager.render_template("Hello, {{ name }}!", data)
        assert rendered == "Hello, John!"
        assert variables == {"name"}
        assert data == {"name": "John"}

    async def test_render_template_remaining(self, template_manager: TemplateManager):
        data = {"name": "John", "hello": "world"}
        rendered, variables = await template_manager.render_template(
            "Hello, {{ name }}!",
            data,
        )
        assert rendered == "Hello, John!"
        assert variables == {"name"}
        assert data == {"name": "John", "hello": "world"}


class TestExtractVariableSchema:
    def test_extract_variable_schema(self):
        schema, _ = extract_variable_schema("Hello, {{ name }}!")
        assert schema == {"type": "object", "properties": {"name": {}}}

    def test_attribute_access(self):
        schema, _ = extract_variable_schema("User: {{ user.name }}")
        assert schema == {
            "type": "object",
            "properties": {"user": {"type": "object", "properties": {"name": {}}}},
        }

    def test_nested_attribute_access(self):
        schema, _ = extract_variable_schema("Email: {{ user.profile.email }}")
        assert schema == {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "profile": {
                            "type": "object",
                            "properties": {"email": {}},
                        },
                    },
                },
            },
        }

    def test_item_access_as_array(self):
        # Note: Getitem is always treated as array access ('*') by the current implementation
        schema, _ = extract_variable_schema("First user: {{ users[0].name }}")
        assert schema == {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": {}},
                    },
                },
            },
        }

    def test_for_loop(self):
        template = "{% for item in items %}{{ item.name }}{% endfor %}"
        schema, _ = extract_variable_schema(template)
        assert schema == {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": {}},
                    },
                },
            },
        }

    def test_nested_for_loop(self):
        template = "{% for user in users %}{% for post in user.posts %}{{ post.title }}{% endfor %}{% endfor %}"
        schema, _ = extract_variable_schema(template)
        assert schema == {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "posts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"title": {}},
                                },
                            },
                        },
                    },
                },
            },
        }

    def test_conditional(self):
        template = "{% if user.is_admin %}{{ user.name }}{% else %}Guest{% endif %}"
        schema, _ = extract_variable_schema(template)
        assert schema == {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "is_admin": {},  # Type defaults to string
                        "name": {},
                    },
                },
            },
        }

    def test_combined(self):
        template = "{{ user.name }} {% for project in user.projects %}{{ project.id }}{% endfor %}"
        schema, _ = extract_variable_schema(template)
        assert schema == {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {},
                        "projects": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"id": {}},
                            },
                        },
                    },
                },
            },
        }

    def test_no_variables(self):
        schema, _ = extract_variable_schema("Just plain text.")
        assert schema is None

    def test_function_call_raises_error(self):
        # Functions are not supported
        with pytest.raises(InvalidTemplateError, match="Template functions are not supported"):
            extract_variable_schema("{{ my_func() }}")

    def test_single_array(self):
        schema, _ = extract_variable_schema("{% for item in seq %}{{ item }}{% endfor %}")
        assert schema == {
            "type": "object",
            "properties": {"seq": {"type": "array", "items": {}}},
        }

    def test_existing_schema(self):
        schema, _ = extract_variable_schema(
            "{{ name }} {{ counter}}",
            use_types_from={
                "type": "object",
                "properties": {
                    "counter": {"type": "integer", "description": "The counter"},
                },
            },
        )
        assert schema == {
            "type": "object",
            "properties": {
                "name": {},
                "counter": {"type": "integer", "description": "The counter"},
            },
        }

    def test_existing_schema_with_array(self):
        schema, _ = extract_variable_schema(
            "{% for user in users %}{{ user.name }} {{ user.counter }} {% endfor %}",
            use_types_from={
                "type": "object",
                "properties": {
                    "users": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"name": {"type": "string", "description": "The name of the user"}},
                        },
                    },
                },
            },
        )
        assert schema == {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "The name of the user"},
                            "counter": {},
                        },
                    },
                },
            },
        }

    def test_start_schema(self):
        schema, _ = extract_variable_schema(
            "Hello, {{ name }}!",
            start_schema={"type": "object", "properties": {"hello": {}}},
        )
        assert schema == {
            "type": "object",
            "properties": {"hello": {}, "name": {}},
        }

    def test_invalid_template(self):
        with pytest.raises(InvalidTemplateError) as e:
            extract_variable_schema("Hello {{ name }} {{ blabla }} hello\n{{name}")
        assert e.value.message == "unexpected '}'"
        assert e.value.line_number == 2
        assert e.value.unexpected_char == "}"

    def test_format_at_root_in_base_schema(self):
        schema, _ = extract_variable_schema(
            "{{ name  }}",
            use_types_from={"type": "object", "format": "messages"},
        )
        assert schema == {
            "type": "object",
            "format": "messages",
            "properties": {"name": {}},
        }

    def test_refs_are_maintained(self):
        schema, _ = extract_variable_schema(
            "{{ audio  }} {{ image}}",
            use_types_from={
                "type": "object",
                "format": "messages",
                "properties": {
                    "audio": {"$ref": "Audio"},
                },
            },
        )
        assert schema == {
            "type": "object",
            "format": "messages",
            "properties": {
                "audio": {"$ref": "Audio"},
                "image": {},
            },
        }


class TestAddTemplate:
    async def test_add_template(self, template_manager: TemplateManager):
        await template_manager.add_template("Hello, {{ name }}!")
        assert len(template_manager._template_cache) == 1
        assert list(template_manager._template_cache.keys()) == [
            "ef6da98fa71e430e09204eec97a368c2823a93bf7d6338c29f2aab8643960862",
        ]
        # Add again
        await template_manager.add_template("Hello, {{ name }}!")
        assert len(template_manager._template_cache) == 1
        assert template_manager.get_template("ef6da98fa71e430e09204eec97a368c2823a93bf7d6338c29f2aab8643960862")

    async def test_add_template_with_key(self, template_manager: TemplateManager):
        await template_manager.add_template("Hello, {{ name }}!", key="hello_name")
        assert len(template_manager._template_cache) == 1
        assert list(template_manager._template_cache.keys()) == [
            "hello_name",
        ]
        assert template_manager.get_template("hello_name")
