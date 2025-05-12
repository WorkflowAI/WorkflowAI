import asyncio
import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from cachetools import LRUCache
from jinja2 import Environment, Template, TemplateError, nodes
from jinja2.meta import find_undeclared_variables
from jinja2.visitor import NodeVisitor

from core.domain.errors import BadRequestError
from core.domain.types import TemplateRenderer
from core.utils.schemas import JsonSchema

# Compiled regepx to check if instructions are a template
# Jinja templates use  {%%} for expressions {{}} for variables and {# ... #} for comments

_template_regex = re.compile(rf"({re.escape('{%')}|{re.escape('{{')}|{re.escape('{#')})")


class InvalidTemplateError(Exception):
    def __init__(self, message: str, lineno: int | None):
        self.message = message
        self.line_number = lineno

    def __str__(self) -> str:
        return f"{self.message} (line {self.line_number})"

    @classmethod
    def from_jinja(cls, e: TemplateError):
        return cls(e.message or str(e), getattr(e, "lineno", None))


class TemplateManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._template_cache = LRUCache[int, tuple[Template, set[str]]](maxsize=10)
        self._template_env = Environment(enable_async=True)

    def _key(self, template: str) -> int:
        return hash(template)

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

    async def add_template(self, template: str) -> tuple[Template, set[str]]:
        async with self._lock:
            try:
                return self._template_cache[self._key(template)]
            except KeyError:
                pass

        compiled = await self.compile_template(template)
        async with self._lock:
            self._template_cache[self._key(template)] = compiled
        return compiled

    async def render_template(self, template: str, data: dict[str, Any]):
        """Render the template. Returns the variables that were used in the template"""
        compiled, variables = await self.add_template(template)

        rendered = await compiled.render_async(data)
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
    def __init__(self, existing_schema: dict[str, Any] | None = None):
        # A graph of visited paths
        self._visited_paths: dict[str, Any] = {}
        self._aliases: list[Mapping[str, Any]] = []
        self._existing_schema = JsonSchema(existing_schema) if existing_schema else None

    def build_schema(self) -> dict[str, Any]:
        if not self._visited_paths:
            return {}
        schema: dict[str, Any] = {}
        self._handle_components(schema=schema, existing=self._existing_schema, components=self._visited_paths)
        return schema

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
            existing = existing.safe_child_schema(0) if existing else None
            schema["type"] = "array"
            schema["items"] = {}
            schema = schema["items"]
            components = components["*"]

            self._handle_components(schema, existing, components)
            return

        schema["type"] = "object"
        schema["properties"] = {}
        schema = schema["properties"]

        for k, v in components.items():
            self._handle_components(
                schema=schema.setdefault(k, {}),
                existing=existing.safe_child_schema(k) if existing else None,
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
        raise BadRequestError("Template functions are not supported", capture=True)


def extract_variable_schema(template: str, existing_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    env = Environment()
    try:
        ast = env.parse(template)
    except TemplateError as e:
        raise InvalidTemplateError.from_jinja(e)

    builder = _SchemaBuilder(existing_schema)
    builder.visit(ast)
    return builder.build_schema()
