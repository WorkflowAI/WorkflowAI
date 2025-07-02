import asyncio
import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from cachetools import LRUCache
from jinja2 import Environment, Template, TemplateError, nodes
from jinja2.meta import find_undeclared_variables
from jinja2.visitor import NodeVisitor

from core.domain.types import TemplateRenderer
from core.utils.schemas import JsonSchema
from core.utils.strings import hash_string

# Compiled regepx to check if instructions are a template
# Jinja templates use  {%%} for expressions {{}} for variables and {# ... #} for comments

_template_regex = re.compile(rf"({re.escape('{%')}|{re.escape('{{')}|{re.escape('{#')})")


class InvalidTemplateError(Exception):
    def __init__(
        self,
        message: str,
        line_number: int | None = None,
        source: str | None = None,
        unexpected_char: str | None = None,
    ):
        self.message = message
        self.line_number = line_number
        self.source = source
        self.unexpected_char = unexpected_char

    def __str__(self) -> str:
        return f"{self.message} (line {self.line_number})"

    @classmethod
    def from_jinja(cls, e: TemplateError):
        lineno = cast(int | None, getattr(e, "lineno", None))
        source = cast(str | None, getattr(e, "source", None))

        if source and lineno:
            # We split to only show the offending line in the source
            lines = source.splitlines()
            if len(lines) > lineno:
                source = lines[lineno - 1]

        msg = e.message or str(e)
        unexpected_char = re.findall(r"unexpected '(.*)'", msg)
        if unexpected_char:
            unexpected_char = unexpected_char[0]
        else:
            unexpected_char = None

        return cls(e.message or str(e), line_number=lineno, source=source, unexpected_char=unexpected_char)

    def serialize_details(self) -> dict[str, Any]:
        return {
            "line_number": self.line_number,
            "unexpected_char": self.unexpected_char,
            "source": self.source,
        }


class TemplateManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._template_cache = LRUCache[str, tuple[Template, set[str]]](maxsize=10)
        self._template_env = Environment(enable_async=True)

    def _key(self, template: str) -> str:
        return hash_string(template)

    @classmethod
    def is_template(cls, template: str) -> bool:
        return bool(_template_regex.search(template))

    @classmethod
    async def compile_template(cls, template: str) -> tuple[Template, set[str]]:
        try:
            env = Environment(enable_async=True)
            source = env.parse(source=template)
            variables = find_undeclared_variables(source)
            compiled = env.from_string(source=template)
            return compiled, variables
        except TemplateError as e:
            raise InvalidTemplateError.from_jinja(e)

    async def add_template(self, template: str, key: str | None = None) -> tuple[Template, set[str]]:
        async with self._lock:
            try:
                return self._template_cache[key or self._key(template)]
            except KeyError:
                pass

        compiled = await self.compile_template(template)
        async with self._lock:
            self._template_cache[self._key(template)] = compiled
        return compiled

    async def get_template(self, key: str) -> tuple[Template, set[str]] | None:
        try:
            return self._template_cache[key]
        except KeyError:
            return None

    @classmethod
    async def render_compiled(cls, template: Template, data: dict[str, Any]):
        return await template.render_async(data)

    async def render_template(self, template: str, data: dict[str, Any]):
        """Render the template. Returns the variables that were used in the template"""
        compiled, variables = await self.add_template(template)

        rendered = await self.render_compiled(compiled, data)
        return rendered, variables

    @classmethod
    async def _noop_renderer(cls, template: str | None) -> str | None:
        return template

    def renderer(self, data: dict[str, Any] | None) -> TemplateRenderer:
        if not data:
            return self._noop_renderer

        async def _render(template: str | None):
            if not template:
                return template
            rendered, _ = await self.render_template(template, data)
            return rendered

        return _render


class _SchemaBuilder(NodeVisitor):
    def __init__(self):
        # A graph of visited paths
        self._visited_paths: dict[str, Any] = {}
        self._aliases: list[Mapping[str, Any]] = []

    def build_schema(
        self,
        start_schema: dict[str, Any] | None = None,
        use_types_from: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        schema: dict[str, Any] | None = start_schema
        if not schema and use_types_from:
            _carried_over_keys = {"format", "description", "examples"}
            schema = {k: v for k, v in use_types_from.items() if k in _carried_over_keys}
        if not schema:
            schema = {}
        self._handle_components(
            schema=schema,
            existing=JsonSchema(use_types_from) if use_types_from else None,
            components=self._visited_paths,
        )
        return schema

    def is_empty(self) -> bool:
        return not self._visited_paths

    def _ensure_path(self, path: Sequence[str]):
        """
        Given a tuple like ('order', 'items', '*', 'price')
        add the path to the visited graph
        """
        cur = self._visited_paths
        for p in path:
            cur = cur.setdefault(p, {})

    def _handle_components(self, schema: dict[str, Any], existing: JsonSchema | None, components: dict[str, Any]):
        if not components:
            # No component so we are in a leaf
            if existing:
                # If existing, we use whatever we have in the existing schema
                schema.update(copy.deepcopy(existing.schema))
            # Otherwise, we leave the schema as is. Meaning that Any type will be accepted
            return

        if len(components) == 1 and "*" in components:
            # We are in an array. We can just add the array type and dive
            existing = existing.safe_child_schema(0, follow_refs=False) if existing else None
            schema["type"] = "array"
            schema["items"] = {}
            schema = schema["items"]
            components = components["*"]

            self._handle_components(schema, existing, components)
            return

        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        schema = schema["properties"]

        for k, v in components.items():
            self._handle_components(
                schema=schema.setdefault(k, {}),
                existing=existing.safe_child_schema(k, follow_refs=False) if existing else None,
                components=v,
            )

    def _push_scope(self, mapping: Mapping[str, Any] | None):
        self._aliases.append(mapping or {})

    def _pop_scope(self):
        self._aliases.pop()

    def _lookup_alias(self, name: str) -> Any | None:
        # walk stack from innermost to outermost
        for scope in reversed(self._aliases):
            if name in scope:
                return scope[name]
        return None

    def _expr_to_path(self, node: nodes.Node) -> list[str] | None:
        """Return tuple path for Name/Getattr/Getitem chains, else None."""
        path: list[str] = []
        while isinstance(node, (nodes.Getattr, nodes.Getitem)):
            if isinstance(node, nodes.Getattr):
                path.insert(0, node.attr)
                node = node.node
            else:  # Getitem  -> wildcard
                path.insert(0, "*")
                node = node.node
        if isinstance(node, nodes.Name):
            alias = self._lookup_alias(node.name)
            if alias is not None:
                path = list(alias) + path  # expand alias
            else:
                path.insert(0, node.name)
            return path
        return None

    # ---- NodeVisitor interface -------------------------------------------
    # No overrides below, names are dynamically generated

    def visit_Name(self, node: nodes.Name):
        path = self._expr_to_path(node)
        if path:
            self._ensure_path(path)

    def visit_Getattr(self, node: nodes.Getattr):
        path = self._expr_to_path(node)
        if path:
            self._ensure_path(path)

    def visit_Getitem(self, node: nodes.Getitem):
        path = self._expr_to_path(node)
        if path:
            self._ensure_path(path)

    def visit_For(self, node: nodes.For):
        # {% for item in order.items %}  -> order.items is iterable
        # 1) resolve iterable path and mark it as array
        iter_path = self._expr_to_path(node.iter)
        if iter_path is None:
            self.generic_visit(node)
            return

        if iter_path[-1] != "*":
            iter_path.append("*")
        self._ensure_path(iter_path)

        # 2) create alias mapping(s) for loop target(s)
        alias_map: dict[str, list[str]] = {}

        def add_alias(target: nodes.Node, base_path: list[str]):
            if isinstance(target, nodes.Name):
                alias_map[target.name] = base_path
            elif isinstance(target, nodes.Tuple):
                for t in target.items:
                    add_alias(t, base_path + ["*"])

        add_alias(node.target, iter_path)
        self._push_scope(alias_map)

        # 3) process the loop body
        self.generic_visit(node)

        # 4) pop alias scope
        self._pop_scope()

    def visit_Call(self, node: nodes.Call):
        raise InvalidTemplateError("Template functions are not supported")


def extract_variable_schema(
    template: str,
    start_schema: dict[str, Any] | None = None,
    use_types_from: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    """Returns the new schema and a boolean indicating if the argument was indeed templated"""
    env = Environment()
    try:
        ast = env.parse(template)
    except TemplateError as e:
        raise InvalidTemplateError.from_jinja(e)

    builder = _SchemaBuilder()
    builder.visit(ast)
    if builder.is_empty():
        return start_schema, False
    return builder.build_schema(start_schema=start_schema, use_types_from=use_types_from), True
