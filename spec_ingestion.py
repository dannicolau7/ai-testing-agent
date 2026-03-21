"""
spec_ingestion.py — OpenAPI / Swagger spec parser

Loads an OpenAPI 3.x or Swagger 2.x spec (YAML or JSON) and extracts
rich endpoint metadata that the AI agent uses to generate precise pytest suites.

Public API:

    ingestion = SpecIngestion()
    spec      = ingestion.load("openapi.yaml")         # or .json
    endpoints = ingestion.extract_endpoints(spec)       # list[EndpointSpec]
    base_url  = ingestion.get_base_url(spec)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ParameterSpec:
    name: str
    location: str          # 'query' | 'path' | 'header' | 'cookie'
    required: bool
    schema_type: str       # 'string' | 'integer' | 'boolean' | 'array' | …
    description: str = ""
    enum: List[Any] = field(default_factory=list)
    example: Any = None
    default: Any = None


@dataclass
class ResponseSpec:
    status_code: str       # '200', '201', '400', 'default', …
    description: str
    schema: Dict[str, Any] = field(default_factory=dict)   # JSON Schema fragment


@dataclass
class EndpointSpec:
    method: str            # 'GET', 'POST', …
    path: str              # '/pets', '/pets/{petId}', …
    operation_id: str
    summary: str
    description: str
    tags: List[str]
    parameters: List[ParameterSpec]
    request_body: Optional[Dict[str, Any]]   # {required, schema, content_type}
    responses: List[ResponseSpec]
    security: List[str]    # names of security schemes that apply


# ── Main class ────────────────────────────────────────────────────────────────

class SpecIngestion:
    """
    Loads and parses OpenAPI 3.x / Swagger 2.x specs.

    Handles:
    - YAML and JSON file formats
    - $ref resolution (components/definitions)
    - parameters array (query, path, header, cookie)
    - requestBody (OpenAPI 3.x) and body parameters (Swagger 2.x)
    - response schemas for all status codes
    - security requirements
    - base URL from servers (3.x) or host + basePath (2.x)
    """

    # ── Public methods ─────────────────────────────────────────────────────

    def load(self, path: str) -> Dict[str, Any]:
        """
        Load a YAML or JSON spec file and return the parsed dict.

        Args:
            path: Path to openapi.yaml, openapi.json, swagger.yaml, etc.

        Returns:
            Parsed spec dictionary.

        Raises:
            FileNotFoundError: if the file does not exist.
            ValueError: if the file cannot be parsed as YAML or JSON.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Spec file not found: {path}")

        raw = p.read_text(encoding="utf-8")

        if p.suffix.lower() in (".yaml", ".yml"):
            return self._load_yaml(raw, path)
        elif p.suffix.lower() == ".json":
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Cannot parse JSON spec: {exc}") from exc
        else:
            # Try YAML first (it's a superset of JSON), then JSON
            try:
                return self._load_yaml(raw, path)
            except Exception:
                try:
                    return json.loads(raw)
                except Exception as exc:
                    raise ValueError(
                        f"Cannot parse spec as YAML or JSON: {path}"
                    ) from exc

    def extract_endpoints(self, spec: Dict[str, Any]) -> List[EndpointSpec]:
        """
        Extract all endpoints from the spec.

        Returns a list of EndpointSpec, one per (path, method) pair.
        Skips non-operation keys like 'summary', 'servers', 'parameters'.
        """
        endpoints: List[EndpointSpec] = []
        http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}

        global_security = spec.get("security", [])

        for path, path_item in spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue

            # Path-level parameters apply to all methods under this path
            path_level_params = path_item.get("parameters", [])

            for method, operation in path_item.items():
                if method.lower() not in http_methods:
                    continue
                if not isinstance(operation, dict):
                    continue

                operation = self._resolve_obj(spec, operation)

                # Merge path-level params with operation-level params
                op_params = operation.get("parameters", [])
                merged_params = self._merge_parameters(
                    path_level_params, op_params, spec
                )

                parameters = self._parse_parameters(merged_params, spec)
                request_body = self._parse_request_body(operation, spec)
                responses = self._parse_responses(operation, spec)
                security = self._parse_security(
                    operation, global_security, spec
                )

                endpoints.append(EndpointSpec(
                    method=method.upper(),
                    path=path,
                    operation_id=operation.get("operationId", ""),
                    summary=operation.get("summary", ""),
                    description=operation.get("description", ""),
                    tags=operation.get("tags", []),
                    parameters=parameters,
                    request_body=request_body,
                    responses=responses,
                    security=security,
                ))

        return endpoints

    def get_base_url(self, spec: Dict[str, Any]) -> str:
        """
        Return the base URL from the spec.

        OpenAPI 3.x: uses spec['servers'][0]['url']
        Swagger 2.x: constructs from host + basePath + schemes
        Falls back to empty string if nothing is defined.
        """
        # OpenAPI 3.x
        servers = spec.get("servers")
        if servers and isinstance(servers, list):
            url = servers[0].get("url", "")
            if url:
                return url.rstrip("/")

        # Swagger 2.x
        host = spec.get("host", "")
        base_path = spec.get("basePath", "/")
        if host:
            schemes = spec.get("schemes", ["https"])
            scheme = schemes[0] if schemes else "https"
            return f"{scheme}://{host}{base_path}".rstrip("/")

        return ""

    def spec_version(self, spec: Dict[str, Any]) -> str:
        """Return '3' for OpenAPI 3.x or '2' for Swagger 2.x."""
        if "openapi" in spec:
            return "3"
        if "swagger" in spec:
            return "2"
        return "unknown"

    def group_by_tag(
        self, endpoints: List[EndpointSpec]
    ) -> Dict[str, List[EndpointSpec]]:
        """
        Group endpoints by their first tag.
        Endpoints with no tags go under 'default'.
        """
        groups: Dict[str, List[EndpointSpec]] = {}
        for ep in endpoints:
            tag = ep.tags[0] if ep.tags else "default"
            groups.setdefault(tag, []).append(ep)
        return groups

    # ── Private helpers ────────────────────────────────────────────────────

    def _load_yaml(self, raw: str, path: str) -> Dict[str, Any]:
        try:
            import yaml  # type: ignore
            result = yaml.safe_load(raw)
            if not isinstance(result, dict):
                raise ValueError(f"YAML spec did not parse to a dict: {path}")
            return result
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to parse YAML specs. "
                "Install with: pip install PyYAML"
            ) from exc
        except Exception as exc:
            raise ValueError(f"Cannot parse YAML spec ({path}): {exc}") from exc

    def _resolve_ref(self, spec: Dict[str, Any], ref: str) -> Dict[str, Any]:
        """
        Resolve a JSON Pointer $ref like '#/components/schemas/Pet'.
        Only local (same-file) refs are supported.
        """
        if not ref.startswith("#/"):
            return {}
        parts = ref[2:].split("/")
        node = spec
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict):
                node = node.get(part, {})
            else:
                return {}
        return node if isinstance(node, dict) else {}

    def _resolve_obj(self, spec: Dict[str, Any], obj: Any) -> Dict[str, Any]:
        """If obj has a $ref, resolve it; otherwise return obj unchanged."""
        if isinstance(obj, dict) and "$ref" in obj:
            return self._resolve_ref(spec, obj["$ref"])
        return obj if isinstance(obj, dict) else {}

    def _merge_parameters(
        self,
        path_params: List[Any],
        op_params: List[Any],
        spec: Dict[str, Any],
    ) -> List[Any]:
        """
        Merge path-level and operation-level parameters.
        Operation-level parameters override path-level ones with the same
        (name, in) combination.
        """
        resolved_path = [self._resolve_obj(spec, p) for p in path_params]
        resolved_op = [self._resolve_obj(spec, p) for p in op_params]

        op_keys = {
            (p.get("name"), p.get("in"))
            for p in resolved_op
            if p
        }

        merged = [
            p for p in resolved_path
            if p and (p.get("name"), p.get("in")) not in op_keys
        ]
        merged.extend(p for p in resolved_op if p)
        return merged

    def _parse_parameters(
        self, params: List[Any], spec: Dict[str, Any]
    ) -> List[ParameterSpec]:
        """Parse a list of raw parameter dicts into ParameterSpec objects."""
        result = []
        for raw in params:
            raw = self._resolve_obj(spec, raw)
            if not raw:
                continue

            # OpenAPI 3.x: schema is nested; Swagger 2.x: type is inline
            schema = raw.get("schema") or {}
            if "$ref" in schema:
                schema = self._resolve_ref(spec, schema["$ref"])

            schema_type = (
                schema.get("type")
                or raw.get("type")
                or "string"
            )
            enum = schema.get("enum") or raw.get("enum") or []
            example = schema.get("example") or raw.get("example")
            default = schema.get("default") or raw.get("default")

            result.append(ParameterSpec(
                name=raw.get("name", ""),
                location=raw.get("in", "query"),
                required=bool(raw.get("required", False)),
                schema_type=schema_type,
                description=raw.get("description", ""),
                enum=enum,
                example=example,
                default=default,
            ))
        return result

    def _parse_request_body(
        self, operation: Dict[str, Any], spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract request body schema.

        OpenAPI 3.x: operation.requestBody.content['application/json'].schema
        Swagger 2.x: body parameter with schema
        """
        # OpenAPI 3.x
        rb = operation.get("requestBody")
        if rb:
            rb = self._resolve_obj(spec, rb)
            required = rb.get("required", False)
            content = rb.get("content", {})
            for content_type, media in content.items():
                if not isinstance(media, dict):
                    continue
                schema = media.get("schema", {})
                if "$ref" in schema:
                    schema = self._resolve_ref(spec, schema["$ref"])
                if schema:
                    return {
                        "required": required,
                        "content_type": content_type,
                        "schema": self._flatten_schema(schema, spec),
                    }

        # Swagger 2.x: look for 'in: body' parameter
        for param in operation.get("parameters", []):
            param = self._resolve_obj(spec, param)
            if param.get("in") == "body":
                schema = param.get("schema", {})
                if "$ref" in schema:
                    schema = self._resolve_ref(spec, schema["$ref"])
                return {
                    "required": param.get("required", False),
                    "content_type": "application/json",
                    "schema": self._flatten_schema(schema, spec),
                }

        return None

    def _parse_responses(
        self, operation: Dict[str, Any], spec: Dict[str, Any]
    ) -> List[ResponseSpec]:
        """Extract response specs for all documented status codes."""
        result = []
        for status_code, raw_resp in operation.get("responses", {}).items():
            raw_resp = self._resolve_obj(spec, raw_resp)
            description = raw_resp.get("description", "")

            schema: Dict[str, Any] = {}

            # OpenAPI 3.x
            content = raw_resp.get("content", {})
            for _ct, media in content.items():
                if not isinstance(media, dict):
                    continue
                s = media.get("schema", {})
                if "$ref" in s:
                    s = self._resolve_ref(spec, s["$ref"])
                if s:
                    schema = self._flatten_schema(s, spec)
                    break

            # Swagger 2.x
            if not schema:
                s = raw_resp.get("schema", {})
                if "$ref" in s:
                    s = self._resolve_ref(spec, s["$ref"])
                if s:
                    schema = self._flatten_schema(s, spec)

            result.append(ResponseSpec(
                status_code=str(status_code),
                description=description,
                schema=schema,
            ))

        return result

    def _parse_security(
        self,
        operation: Dict[str, Any],
        global_security: List[Any],
        spec: Dict[str, Any],
    ) -> List[str]:
        """Return list of security scheme names that apply to the operation."""
        # Operation-level security overrides global; empty list [] means no auth
        security_reqs = operation.get("security")
        if security_reqs is None:
            security_reqs = global_security

        names = []
        for req in security_reqs:
            if isinstance(req, dict):
                names.extend(req.keys())
        return names

    def _flatten_schema(
        self, schema: Dict[str, Any], spec: Dict[str, Any], depth: int = 0
    ) -> Dict[str, Any]:
        """
        Resolve $refs within a schema and return a simplified representation.
        Limits recursion depth to 3 to handle circular refs gracefully.
        """
        if depth > 3:
            return schema

        if "$ref" in schema:
            schema = self._resolve_ref(spec, schema["$ref"])

        result = {k: v for k, v in schema.items() if k != "$ref"}

        # Flatten properties
        props = result.get("properties", {})
        if props:
            flat_props = {}
            for name, prop_schema in props.items():
                prop_schema = self._resolve_obj(spec, prop_schema)
                flat_props[name] = {
                    "type": prop_schema.get("type", "string"),
                    "description": prop_schema.get("description", ""),
                    "enum": prop_schema.get("enum", []),
                    "example": prop_schema.get("example"),
                }
            result["properties"] = flat_props

        # Flatten array items
        items = result.get("items", {})
        if items:
            items = self._resolve_obj(spec, items)
            if "$ref" in items:
                items = self._resolve_ref(spec, items["$ref"])
            result["items"] = self._flatten_schema(items, spec, depth + 1)

        return result
