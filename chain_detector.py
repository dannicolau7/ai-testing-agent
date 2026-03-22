"""
chain_detector.py — Multi-endpoint test chain detection

Analyzes a list of EndpointSpec objects and detects sequences of API calls
that can be chained into meaningful integration tests:

  - CRUD chains:  POST (create) → GET (read) → PUT/PATCH (update) → DELETE
  - Auth chains:  POST /login → GET /profile (with token)
  - Nested chains: POST /users → POST /users/{userId}/posts

Public API:

    detector = ChainDetector()
    chains   = detector.detect_chains(endpoints)  # List[EndpointChain]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from spec_ingestion import EndpointSpec


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ChainStep:
    """One step in an endpoint chain."""
    endpoint: EndpointSpec
    # Fields captured from this step's response: {response_field: variable_name}
    captures: Dict[str, str] = field(default_factory=dict)
    # Variables consumed from prior steps: {variable_name: location_hint}
    # location_hint: "path:{param}", "query:{param}", or "header:Authorization"
    uses: Dict[str, str] = field(default_factory=dict)


@dataclass
class EndpointChain:
    """An ordered sequence of API calls forming a meaningful test flow."""
    name: str
    description: str
    chain_type: str          # "crud" | "auth" | "nested"
    steps: List[ChainStep]


# ── Main class ────────────────────────────────────────────────────────────────

class ChainDetector:
    """
    Detects chains of dependent API endpoints from an OpenAPI spec.

    Works from the EndpointSpec data model produced by SpecIngestion.
    No AI required — uses structural analysis of response schemas, path
    parameters, and security requirements.
    """

    # Auth-related path segments
    _AUTH_PATH = re.compile(
        r'/(auth|login|signin|sign-in|token|oauth|session)(/|$)',
        re.IGNORECASE,
    )

    # Response field names that carry auth tokens
    _TOKEN_FIELDS = frozenset({
        'token', 'access_token', 'accessToken',
        'jwt', 'refresh_token', 'refreshToken',
        'id_token', 'idToken',
    })

    # Response field names that carry resource IDs
    _ID_FIELDS = frozenset({'id', 'uuid', 'slug'})

    def detect_chains(self, endpoints: List[EndpointSpec]) -> List[EndpointChain]:
        """
        Detect all endpoint chains from a list of EndpointSpec objects.

        Args:
            endpoints: Parsed EndpointSpec list from SpecIngestion.

        Returns:
            List of EndpointChain objects, deduplicated by name.
        """
        chains: List[EndpointChain] = []
        chains.extend(self._detect_crud_chains(endpoints))
        chains.extend(self._detect_auth_chains(endpoints))
        chains.extend(self._detect_nested_chains(endpoints))

        # Deduplicate by name (same resource may match multiple heuristics)
        seen: set = set()
        unique = []
        for chain in chains:
            if chain.name not in seen:
                seen.add(chain.name)
                unique.append(chain)
        return unique

    # ── CRUD chain detection ──────────────────────────────────────────────────

    def _detect_crud_chains(
        self, endpoints: List[EndpointSpec]
    ) -> List[EndpointChain]:
        """
        Detect create → read → (update) → delete chains.

        Looks for a POST to /resource that returns an id field, then pairs it
        with GET/PUT/PATCH/DELETE endpoints at /resource/{resourceId}.
        """
        chains = []

        creators = [
            e for e in endpoints
            if e.method == 'POST' and self._get_id_field(e)
        ]

        for creator in creators:
            resource = self._resource_name(creator.path)
            id_field = self._get_id_field(creator)
            variable = f'{resource}_id'

            consumers = self._find_consumers(creator, endpoints)
            if not consumers:
                continue

            steps = [ChainStep(
                endpoint=creator,
                captures={id_field: variable},
                uses={},
            )]

            order = {'GET': 0, 'PUT': 1, 'PATCH': 2, 'DELETE': 3}
            for consumer in sorted(consumers, key=lambda e: order.get(e.method, 99)):
                param_name = self._first_path_param(consumer.path)
                uses = {variable: f'path:{{{param_name}}}'} if param_name else {}

                # GET also re-captures id to verify round-trip
                extra_captures = {id_field: variable} if consumer.method == 'GET' else {}

                steps.append(ChainStep(
                    endpoint=consumer,
                    captures=extra_captures,
                    uses=uses,
                ))

            if len(steps) >= 2:
                method_list = ' → '.join(s.endpoint.method for s in steps)
                chains.append(EndpointChain(
                    name=f'crud_{resource}',
                    description=f'CRUD chain for {resource}: {method_list}',
                    chain_type='crud',
                    steps=steps,
                ))

        return chains

    # ── Auth chain detection ──────────────────────────────────────────────────

    def _detect_auth_chains(
        self, endpoints: List[EndpointSpec]
    ) -> List[EndpointChain]:
        """
        Detect login → protected endpoint chains.

        Looks for POST to an auth path returning a token field, then pairs it
        with endpoints that declare security requirements.
        """
        chains = []

        auth_endpoints = [
            e for e in endpoints
            if e.method == 'POST'
            and self._AUTH_PATH.search(e.path)
            and self._get_token_field(e)
        ]

        protected = [
            e for e in endpoints
            if e.security
            and e.method in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')
            and not self._AUTH_PATH.search(e.path)
        ]

        for auth_ep in auth_endpoints:
            token_field = self._get_token_field(auth_ep)
            token_var = 'access_token'

            # Prefer short GET paths for the paired protected endpoint
            targets = sorted(
                protected,
                key=lambda e: (0 if e.method == 'GET' else 1, len(e.path)),
            )

            for target in targets[:2]:   # cap at 2 chains per auth endpoint
                auth_step = ChainStep(
                    endpoint=auth_ep,
                    captures={token_field: token_var},
                    uses={},
                )
                target_step = ChainStep(
                    endpoint=target,
                    captures={},
                    uses={token_var: 'header:Authorization'},
                )

                auth_slug = re.sub(r'[^a-z0-9]', '_', auth_ep.path.lower()).strip('_')
                target_slug = re.sub(r'[^a-z0-9]', '_', target.path.lower()).strip('_')

                chains.append(EndpointChain(
                    name=f'auth_{auth_slug}_then_{target_slug}',
                    description=(
                        f'Auth chain: {auth_ep.method} {auth_ep.path} '
                        f'→ {target.method} {target.path}'
                    ),
                    chain_type='auth',
                    steps=[auth_step, target_step],
                ))

        return chains

    # ── Nested resource chain detection ──────────────────────────────────────

    def _detect_nested_chains(
        self, endpoints: List[EndpointSpec]
    ) -> List[EndpointChain]:
        """
        Detect chains across nested resources.

        Example: POST /users → POST /users/{userId}/posts → GET /users/{userId}/posts/{postId}
        Only builds chains where every path param has a matching POST creator.
        """
        chains = []

        # Endpoints with 2+ path params are candidates
        nested = [
            e for e in endpoints
            if len(re.findall(r'\{(\w+)\}', e.path)) >= 2
        ]

        for ep in nested:
            params = re.findall(r'\{(\w+)\}', ep.path)
            steps: List[ChainStep] = []
            consumed_vars: List[tuple] = []

            for param in params:
                resource = self._strip_id_suffix(param)
                creator = self._find_creator_for_resource(resource, endpoints)
                if not creator:
                    break
                id_field = self._get_id_field(creator)
                if not id_field:
                    break
                variable = f'{resource}_id'
                consumed_vars.append((param, variable))
                steps.append(ChainStep(
                    endpoint=creator,
                    captures={id_field: variable},
                    uses={},
                ))

            if len(steps) < 2:
                continue

            # Add the nested endpoint itself as the final step
            final_uses = {var: f'path:{{{param}}}' for param, var in consumed_vars}
            steps.append(ChainStep(
                endpoint=ep,
                captures=self._simple_captures(ep),
                uses=final_uses,
            ))

            slug = re.sub(r'[^a-z0-9]', '_', ep.path.lower()).strip('_')
            chains.append(EndpointChain(
                name=f'nested_{slug}',
                description=f'Nested chain → {ep.method} {ep.path}',
                chain_type='nested',
                steps=steps,
            ))

        return chains

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resource_name(self, path: str) -> str:
        """
        Extract the primary resource name from a path.

        /pets         → pet
        /api/v1/users → user
        /pets/{petId} → pet
        """
        parts = [p for p in path.split('/') if p and '{' not in p]
        if not parts:
            return 'resource'
        name = parts[-1].rstrip('s')   # simple depluralization: pets→pet, users→user
        return name.lower()

    def _first_path_param(self, path: str) -> Optional[str]:
        """Return the first {param} name in a path, or None."""
        match = re.search(r'\{(\w+)\}', path)
        return match.group(1) if match else None

    def _strip_id_suffix(self, param: str) -> str:
        """petId → pet, user_id → user, userId → user."""
        for suffix in ('_id', 'Id', 'ID', '_uuid', 'Uuid', 'UUID'):
            if param.endswith(suffix) and len(param) > len(suffix):
                return param[:-len(suffix)].lower()
        return param.lower()

    def _get_id_field(self, endpoint: EndpointSpec) -> Optional[str]:
        """
        Return the first ID field name found in a 200/201 response schema.
        Checks top-level properties and array item properties.
        """
        for response in endpoint.responses:
            if response.status_code in ('200', '201'):
                props = response.schema.get('properties', {})
                for field_name in self._ID_FIELDS:
                    if field_name in props:
                        return field_name
                # Check array responses: {type: array, items: {properties: ...}}
                items = response.schema.get('items', {})
                if items:
                    item_props = items.get('properties', {})
                    for field_name in self._ID_FIELDS:
                        if field_name in item_props:
                            return field_name
        return None

    def _get_token_field(self, endpoint: EndpointSpec) -> Optional[str]:
        """Return the token field name from a 200/201 response schema, or None."""
        for response in endpoint.responses:
            if response.status_code in ('200', '201'):
                props = response.schema.get('properties', {})
                for field_name in self._TOKEN_FIELDS:
                    if field_name in props:
                        return field_name
        return None

    def _find_consumers(
        self, creator: EndpointSpec, endpoints: List[EndpointSpec]
    ) -> List[EndpointSpec]:
        """
        Find endpoints that consume the resource created by `creator`.

        A consumer's path must be creator.path + /{param}, where the param
        name relates to the creator's resource (e.g. /pets → /pets/{petId}).
        """
        base = creator.path.rstrip('/')
        resource = self._resource_name(creator.path)

        consumers = []
        for ep in endpoints:
            if ep is creator:
                continue
            ep_path = ep.path.rstrip('/')
            if not ep_path.startswith(base + '/'):
                continue
            suffix = ep_path[len(base):]
            if not re.fullmatch(r'/\{[^/]+\}', suffix):
                continue
            param = re.search(r'\{(\w+)\}', suffix).group(1)
            normalized = self._strip_id_suffix(param)
            # Accept if the normalized param name shares a 3-char prefix with resource
            if (normalized.startswith(resource[:3])
                    or resource.startswith(normalized[:3])):
                consumers.append(ep)

        return consumers

    def _find_creator_for_resource(
        self, resource: str, endpoints: List[EndpointSpec]
    ) -> Optional[EndpointSpec]:
        """Find a POST endpoint that creates a resource matching `resource`."""
        for ep in endpoints:
            if ep.method != 'POST':
                continue
            ep_resource = self._resource_name(ep.path)
            if (ep_resource.startswith(resource[:3])
                    or resource.startswith(ep_resource[:3])):
                if self._get_id_field(ep):
                    return ep
        return None

    def _simple_captures(self, endpoint: EndpointSpec) -> Dict[str, str]:
        """Return a capture dict for the first id field in the response."""
        id_field = self._get_id_field(endpoint)
        if id_field:
            resource = self._resource_name(endpoint.path)
            return {id_field: f'{resource}_id'}
        return {}
