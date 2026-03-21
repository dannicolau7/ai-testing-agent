"""
Tests for spec_ingestion.py

Covers: YAML loading, JSON loading, endpoint extraction, $ref resolution,
parameter parsing, request body parsing, response schema extraction,
security parsing, base URL extraction, and tag grouping.
"""

import json
import textwrap
import tempfile
from pathlib import Path

import pytest

from spec_ingestion import (
    SpecIngestion,
    EndpointSpec,
    ParameterSpec,
    ResponseSpec,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

PETSTORE_YAML = textwrap.dedent("""
openapi: "3.0.0"
info:
  title: Petstore
  version: "1.0.0"
servers:
  - url: https://petstore.swagger.io/v2
paths:
  /pets:
    get:
      summary: List all pets
      operationId: listPets
      tags: [pets]
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
            default: 20
      responses:
        "200":
          description: A list of pets
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/Pet"
        "400":
          description: Bad request
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
    post:
      summary: Create a pet
      operationId: createPet
      tags: [pets]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/NewPet"
      responses:
        "201":
          description: Created
  /pets/{petId}:
    get:
      summary: Get a pet by ID
      operationId: getPet
      tags: [pets]
      parameters:
        - name: petId
          in: path
          required: true
          schema:
            type: integer
      responses:
        "200":
          description: Pet found
        "404":
          description: Not found
components:
  schemas:
    Pet:
      type: object
      required: [id, name]
      properties:
        id:
          type: integer
          example: 1
        name:
          type: string
          example: Fluffy
        tag:
          type: string
    NewPet:
      type: object
      required: [name]
      properties:
        name:
          type: string
        tag:
          type: string
    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: integer
        message:
          type: string
""").strip()

SWAGGER2_YAML = textwrap.dedent("""
swagger: "2.0"
info:
  title: Simple API
  version: "1.0"
host: api.example.com
basePath: /v1
schemes: [https]
paths:
  /users:
    get:
      summary: List users
      operationId: listUsers
      tags: [users]
      parameters:
        - name: page
          in: query
          required: false
          type: integer
      responses:
        200:
          description: OK
""").strip()


@pytest.fixture
def ingestion():
    return SpecIngestion()


@pytest.fixture
def petstore_spec(ingestion):
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(PETSTORE_YAML)
        name = f.name
    yield ingestion.load(name)
    Path(name).unlink(missing_ok=True)


@pytest.fixture
def petstore_endpoints(ingestion, petstore_spec):
    return ingestion.extract_endpoints(petstore_spec)


# ── Loading ────────────────────────────────────────────────────────────────────

def test_load_yaml_file(ingestion):
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(PETSTORE_YAML)
        name = f.name
    try:
        spec = ingestion.load(name)
        assert spec["info"]["title"] == "Petstore"
        assert "paths" in spec
    finally:
        Path(name).unlink(missing_ok=True)


def test_load_json_file(ingestion):
    # Convert petstore to JSON and reload
    import yaml
    spec_dict = yaml.safe_load(PETSTORE_YAML)
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False, encoding="utf-8"
    ) as f:
        json.dump(spec_dict, f)
        name = f.name
    try:
        spec = ingestion.load(name)
        assert spec["info"]["title"] == "Petstore"
    finally:
        Path(name).unlink(missing_ok=True)


def test_load_missing_file_raises(ingestion):
    with pytest.raises(FileNotFoundError):
        ingestion.load("/nonexistent/path/spec.yaml")


def test_load_invalid_yaml_raises(ingestion):
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("key: [unclosed bracket")
        name = f.name
    try:
        with pytest.raises(ValueError):
            ingestion.load(name)
    finally:
        Path(name).unlink(missing_ok=True)


# ── Endpoint extraction ────────────────────────────────────────────────────────

def test_extracts_correct_number_of_endpoints(petstore_endpoints):
    # /pets GET, /pets POST, /pets/{petId} GET = 3 endpoints
    assert len(petstore_endpoints) == 3


def test_endpoint_methods_are_uppercase(petstore_endpoints):
    methods = {ep.method for ep in petstore_endpoints}
    assert methods == {"GET", "POST"}


def test_endpoint_paths_extracted(petstore_endpoints):
    paths = {ep.path for ep in petstore_endpoints}
    assert "/pets" in paths
    assert "/pets/{petId}" in paths


def test_operation_id_extracted(petstore_endpoints):
    list_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "listPets")
    assert list_ep.method == "GET"
    assert list_ep.path == "/pets"


def test_summary_extracted(petstore_endpoints):
    list_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "listPets")
    assert list_ep.summary == "List all pets"


def test_tags_extracted(petstore_endpoints):
    for ep in petstore_endpoints:
        assert ep.tags == ["pets"]


# ── Parameter parsing ──────────────────────────────────────────────────────────

def test_query_parameter_extracted(petstore_endpoints):
    list_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "listPets")
    assert len(list_ep.parameters) == 1
    param = list_ep.parameters[0]
    assert param.name == "limit"
    assert param.location == "query"
    assert param.schema_type == "integer"
    assert param.required is False
    assert param.default == 20


def test_path_parameter_extracted(petstore_endpoints):
    get_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "getPet")
    assert len(get_ep.parameters) == 1
    param = get_ep.parameters[0]
    assert param.name == "petId"
    assert param.location == "path"
    assert param.required is True
    assert param.schema_type == "integer"


# ── Request body parsing ───────────────────────────────────────────────────────

def test_request_body_extracted(petstore_endpoints):
    create_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "createPet")
    rb = create_ep.request_body
    assert rb is not None
    assert rb["required"] is True
    assert rb["content_type"] == "application/json"
    schema = rb["schema"]
    assert "properties" in schema
    assert "name" in schema["properties"]


def test_no_request_body_for_get(petstore_endpoints):
    list_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "listPets")
    assert list_ep.request_body is None


# ── Response parsing ───────────────────────────────────────────────────────────

def test_response_status_codes_extracted(petstore_endpoints):
    list_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "listPets")
    codes = {r.status_code for r in list_ep.responses}
    assert "200" in codes
    assert "400" in codes


def test_response_schema_resolved_from_ref(petstore_endpoints):
    list_ep = next(ep for ep in petstore_endpoints if ep.operation_id == "listPets")
    ok_resp = next(r for r in list_ep.responses if r.status_code == "200")
    # Array of Pet; items schema should have 'properties' with id and name
    schema = ok_resp.schema
    assert schema.get("type") == "array"
    items = schema.get("items", {})
    assert "properties" in items
    assert "id" in items["properties"]
    assert "name" in items["properties"]


# ── Base URL ───────────────────────────────────────────────────────────────────

def test_base_url_openapi3(ingestion, petstore_spec):
    assert ingestion.get_base_url(petstore_spec) == "https://petstore.swagger.io/v2"


def test_base_url_swagger2(ingestion):
    import yaml
    spec = yaml.safe_load(SWAGGER2_YAML)
    url = ingestion.get_base_url(spec)
    assert url == "https://api.example.com/v1"


def test_base_url_empty_when_no_server(ingestion):
    spec = {"openapi": "3.0.0", "paths": {}}
    assert ingestion.get_base_url(spec) == ""


# ── Spec version detection ─────────────────────────────────────────────────────

def test_spec_version_openapi3(ingestion, petstore_spec):
    assert ingestion.spec_version(petstore_spec) == "3"


def test_spec_version_swagger2(ingestion):
    import yaml
    spec = yaml.safe_load(SWAGGER2_YAML)
    assert ingestion.spec_version(spec) == "2"


# ── Tag grouping ───────────────────────────────────────────────────────────────

def test_group_by_tag(ingestion, petstore_endpoints):
    groups = ingestion.group_by_tag(petstore_endpoints)
    assert "pets" in groups
    assert len(groups["pets"]) == 3


def test_group_by_tag_default_for_untagged(ingestion):
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/health": {
                "get": {
                    "summary": "Health check",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    endpoints = ingestion.extract_endpoints(spec)
    groups = ingestion.group_by_tag(endpoints)
    assert "default" in groups


# ── Swagger 2.x support ────────────────────────────────────────────────────────

def test_swagger2_endpoints_extracted(ingestion):
    import yaml
    spec = yaml.safe_load(SWAGGER2_YAML)
    endpoints = ingestion.extract_endpoints(spec)
    assert len(endpoints) == 1
    assert endpoints[0].method == "GET"
    assert endpoints[0].path == "/users"
    assert endpoints[0].operation_id == "listUsers"


# ── Load the actual petstore spec from test_specs/ ────────────────────────────

def test_load_petstore_yaml_from_file(ingestion):
    spec_path = Path(__file__).parent / "test_specs" / "petstore.yaml"
    if not spec_path.exists():
        pytest.skip("test_specs/petstore.yaml not found")
    spec = ingestion.load(str(spec_path))
    endpoints = ingestion.extract_endpoints(spec)
    assert len(endpoints) == 4   # GET /pets, POST /pets, GET /pets/{petId}, DELETE /pets/{petId}
    methods = {ep.method for ep in endpoints}
    assert "GET" in methods
    assert "POST" in methods
    assert "DELETE" in methods
