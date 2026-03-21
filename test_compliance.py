"""
Tests for compliance.py — control mapping, tagger, and report generation.
"""
import json
import textwrap
from pathlib import Path

import pytest

from compliance import (
    CONTROL_LIBRARY,
    ComplianceConfig,
    ComplianceReport,
    ComplianceTagger,
    Control,
    ControlMapper,
    EndpointCoverage,
    _LIBRARY_BY_FRAMEWORK,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def nist_config():
    return ComplianceConfig.default(["NIST-800-53"])


@pytest.fixture
def hipaa_config():
    return ComplianceConfig.default(["HIPAA"])


@pytest.fixture
def all_config():
    return ComplianceConfig.default()


@pytest.fixture
def nist_mapper(nist_config):
    return ControlMapper(nist_config)


@pytest.fixture
def all_mapper(all_config):
    return ControlMapper(all_config)


SIMPLE_SOURCE = textwrap.dedent("""\
    import pytest

    def test_login_success(api_client):
        pass

    def test_login_invalid(api_client):
        pass
""")


# ── Control dataclass ─────────────────────────────────────────────────────────

class TestControl:
    def test_pytest_mark_computed_from_id(self):
        c = Control(
            id="NIST-IA-2", framework="NIST-800-53",
            title="ID and Auth", description="desc",
        )
        assert c.pytest_mark == "nist_ia_2"

    def test_pytest_mark_hipaa(self):
        c = Control(
            id="HIPAA-164.312.d", framework="HIPAA",
            title="Auth", description="desc",
        )
        assert c.pytest_mark == "hipaa_164_312_d"

    def test_pytest_mark_iso(self):
        c = Control(
            id="ISO-A.9.4.2", framework="ISO-27001",
            title="Log-on", description="desc",
        )
        assert c.pytest_mark == "iso_a_9_4_2"

    def test_custom_pytest_mark_respected(self):
        c = Control(
            id="NIST-IA-2", framework="NIST-800-53",
            title="t", description="d",
            pytest_mark="custom_mark",
        )
        assert c.pytest_mark == "custom_mark"

    def test_frozen(self):
        c = Control(id="X", framework="F", title="T", description="D")
        with pytest.raises((AttributeError, TypeError)):
            c.id = "Y"


# ── CONTROL_LIBRARY ───────────────────────────────────────────────────────────

class TestControlLibrary:
    def test_library_non_empty(self):
        assert len(CONTROL_LIBRARY) >= 21

    def test_all_three_frameworks_present(self):
        frameworks = {c.framework for c in CONTROL_LIBRARY}
        assert "NIST-800-53" in frameworks
        assert "HIPAA" in frameworks
        assert "ISO-27001" in frameworks

    def test_library_by_framework_indexed(self):
        assert "NIST-800-53" in _LIBRARY_BY_FRAMEWORK
        assert len(_LIBRARY_BY_FRAMEWORK["NIST-800-53"]) >= 5

    def test_all_controls_have_marks(self):
        for c in CONTROL_LIBRARY:
            assert c.pytest_mark, f"{c.id} missing pytest_mark"

    def test_no_duplicate_ids(self):
        ids = [c.id for c in CONTROL_LIBRARY]
        assert len(ids) == len(set(ids))


# ── ComplianceConfig ──────────────────────────────────────────────────────────

class TestComplianceConfig:
    def test_default_all_frameworks(self):
        cfg = ComplianceConfig.default()
        assert "NIST-800-53" in cfg.frameworks
        assert "HIPAA" in cfg.frameworks
        assert "ISO-27001" in cfg.frameworks

    def test_default_subset(self):
        cfg = ComplianceConfig.default(["HIPAA"])
        assert cfg.frameworks == ["HIPAA"]

    def test_load_valid_yaml(self, tmp_path):
        yaml_content = "frameworks:\n  - NIST-800-53\n  - HIPAA\n"
        f = tmp_path / "compliance.yaml"
        f.write_text(yaml_content)
        cfg = ComplianceConfig.load(str(f))
        assert "NIST-800-53" in cfg.frameworks
        assert "HIPAA" in cfg.frameworks

    def test_load_normalises_case(self, tmp_path):
        f = tmp_path / "c.yaml"
        f.write_text("frameworks:\n  - hipaa\n  - nist\n")
        cfg = ComplianceConfig.load(str(f))
        assert "HIPAA" in cfg.frameworks
        assert "NIST-800-53" in cfg.frameworks

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            ComplianceConfig.load("/nonexistent/path/compliance.yaml")

    def test_load_custom_mappings(self, tmp_path):
        content = (
            "frameworks:\n  - NIST-800-53\n"
            "custom_mappings:\n"
            "  /payment:\n"
            "    - NIST-SC-8\n"
        )
        f = tmp_path / "c.yaml"
        f.write_text(content)
        cfg = ComplianceConfig.load(str(f))
        assert "/payment" in cfg.custom_mappings
        assert "NIST-SC-8" in cfg.custom_mappings["/payment"]

    def test_load_empty_file(self, tmp_path):
        f = tmp_path / "c.yaml"
        f.write_text("")
        cfg = ComplianceConfig.load(str(f))
        assert cfg.frameworks == []
        assert cfg.custom_mappings == {}


# ── ControlMapper ─────────────────────────────────────────────────────────────

class TestControlMapper:
    def test_auth_path_matches_ia2(self, nist_mapper):
        controls = nist_mapper.map("/auth/login", "POST")
        ids = [c.id for c in controls]
        assert "NIST-IA-2" in ids

    def test_auth_path_matches_ia5(self, nist_mapper):
        controls = nist_mapper.map("/auth/password/reset", "POST")
        ids = [c.id for c in controls]
        assert "NIST-IA-5" in ids

    def test_hipaa_tag_matches_auth(self):
        cfg = ComplianceConfig.default(["HIPAA"])
        mapper = ControlMapper(cfg)
        controls = mapper.map("/login", "POST", tags=["auth"])
        ids = [c.id for c in controls]
        assert "HIPAA-164.312.d" in ids

    def test_global_control_always_applies(self, nist_mapper):
        # NIST-SC-8 has no path/tag keywords → applies everywhere
        controls = nist_mapper.map("/pets", "GET")
        ids = [c.id for c in controls]
        assert "NIST-SC-8" in ids

    def test_method_filter_respected(self, nist_mapper):
        # NIST-AC-6 applies only to GET/PUT/PATCH/DELETE
        get_controls = nist_mapper.map("/admin/role", "GET")
        post_controls = nist_mapper.map("/admin/role", "POST")
        get_ids = [c.id for c in get_controls]
        post_ids = [c.id for c in post_controls]
        assert "NIST-AC-6" in get_ids
        assert "NIST-AC-6" not in post_ids

    def test_tag_keyword_matching(self, nist_mapper):
        controls = nist_mapper.map("/unknown-path", "GET", tags=["audit"])
        ids = [c.id for c in controls]
        assert "NIST-AU-2" in ids

    def test_framework_filter_excludes_others(self, nist_mapper):
        controls = nist_mapper.map("/auth/login", "POST")
        for c in controls:
            assert c.framework == "NIST-800-53"

    def test_map_ids_returns_strings(self, nist_mapper):
        ids = nist_mapper.map_ids("/auth/login", "POST")
        assert all(isinstance(i, str) for i in ids)

    def test_no_duplicates_in_result(self, all_mapper):
        controls = all_mapper.map("/auth/login", "POST")
        ids = [c.id for c in controls]
        assert len(ids) == len(set(ids))

    def test_custom_mapping_adds_control(self, tmp_path):
        content = (
            "frameworks:\n  - NIST-800-53\n"
            "custom_mappings:\n"
            "  /payment:\n"
            "    - NIST-SC-8\n"
        )
        f = tmp_path / "c.yaml"
        f.write_text(content)
        cfg = ComplianceConfig.load(str(f))
        mapper = ControlMapper(cfg)
        controls = mapper.map("/payment/checkout", "POST")
        ids = [c.id for c in controls]
        assert "NIST-SC-8" in ids

    def test_empty_path_and_no_keywords_gets_global_controls(self, nist_mapper):
        controls = nist_mapper.map("/", "GET")
        ids = [c.id for c in controls]
        assert "NIST-SC-8" in ids  # global: no path/tag keywords


# ── ComplianceTagger ──────────────────────────────────────────────────────────

class TestComplianceTagger:
    def _make_control(self, cid, framework="NIST-800-53"):
        return Control(
            id=cid, framework=framework,
            title="Test Control", description="desc",
        )

    def test_tag_injects_mark(self):
        tagger = ComplianceTagger()
        ctrl = self._make_control("NIST-IA-2")
        result = tagger.tag(SIMPLE_SOURCE, [ctrl])
        assert "@pytest.mark.nist_ia_2" in result

    def test_tag_injects_before_both_functions(self):
        tagger = ComplianceTagger()
        ctrl = self._make_control("NIST-IA-2")
        result = tagger.tag(SIMPLE_SOURCE, [ctrl])
        assert result.count("@pytest.mark.nist_ia_2") == 2

    def test_tag_no_controls_returns_unchanged(self):
        tagger = ComplianceTagger()
        result = tagger.tag(SIMPLE_SOURCE, [])
        assert result == SIMPLE_SOURCE

    def test_tag_multiple_controls(self):
        tagger = ComplianceTagger()
        controls = [
            self._make_control("NIST-IA-2"),
            self._make_control("NIST-SC-8"),
        ]
        result = tagger.tag(SIMPLE_SOURCE, controls)
        assert "@pytest.mark.nist_ia_2" in result
        assert "@pytest.mark.nist_sc_8" in result

    def test_tag_comment_line_present(self):
        tagger = ComplianceTagger()
        ctrl = self._make_control("NIST-IA-2")
        result = tagger.tag(SIMPLE_SOURCE, [ctrl])
        assert "# Compliance:" in result
        assert "NIST-IA-2" in result

    def test_tag_function_targets_specific(self):
        tagger = ComplianceTagger()
        ctrl = self._make_control("NIST-IA-2")
        result = tagger.tag_function(SIMPLE_SOURCE, "test_login_success", [ctrl])
        # Decorator should appear once (only before test_login_success)
        assert result.count("@pytest.mark.nist_ia_2") == 1
        assert "def test_login_success" in result

    def test_conftest_markers_output(self):
        tagger = ComplianceTagger()
        ctrl = self._make_control("NIST-IA-2")
        conftest = tagger.conftest_markers([ctrl])
        assert "pytest_configure" in conftest
        assert "nist_ia_2" in conftest
        assert "config.addinivalue_line" in conftest

    def test_conftest_no_duplicate_markers(self):
        tagger = ComplianceTagger()
        # Two controls with same mark
        c1 = self._make_control("NIST-IA-2")
        c2 = Control(
            id="NIST-IA-2-dup", framework="NIST-800-53",
            title="dup", description="d",
            pytest_mark="nist_ia_2",
        )
        conftest = tagger.conftest_markers([c1, c2])
        assert conftest.count("nist_ia_2") == conftest.count("addinivalue_line")

    def test_conftest_empty_controls(self):
        tagger = ComplianceTagger()
        assert tagger.conftest_markers([]) == ""


# ── ComplianceReport ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_coverage():
    return [
        EndpointCoverage(
            method="POST", path="/auth/login",
            control_ids=["NIST-IA-2", "HIPAA-164.312.d"],
            test_names=["test_login_success", "test_login_invalid"],
        ),
        EndpointCoverage(
            method="GET", path="/users",
            control_ids=["NIST-AC-2"],
            test_names=["test_list_users"],
        ),
    ]


class TestComplianceReport:
    def test_generate_text_contains_header(self, sample_coverage, all_config):
        report = ComplianceReport()
        text = report.generate(sample_coverage, all_config)
        assert "COMPLIANCE COVERAGE REPORT" in text

    def test_generate_text_shows_covered_ids(self, sample_coverage, all_config):
        report = ComplianceReport()
        text = report.generate(sample_coverage, all_config)
        assert "NIST-IA-2" in text

    def test_generate_text_shows_uncovered(self, all_config):
        report = ComplianceReport()
        # Empty coverage → everything uncovered
        text = report.generate([], all_config)
        assert "UNCOVERED" in text

    def test_generate_markdown_has_table(self, sample_coverage, all_config):
        report = ComplianceReport()
        md = report.generate_markdown(sample_coverage, all_config)
        assert "| " in md  # table separator
        assert "NIST-IA-2" in md

    def test_generate_json_structure(self, sample_coverage, all_config):
        report = ComplianceReport()
        data = report.generate_json(sample_coverage, all_config)
        assert "frameworks" in data
        assert "covered_controls" in data
        assert "uncovered_controls" in data
        assert isinstance(data["covered_controls"], list)
        assert isinstance(data["uncovered_controls"], list)
        assert isinstance(data["covered"], int)
        assert isinstance(data["uncovered"], int)

    def test_generate_json_covered_ids(self, sample_coverage, all_config):
        report = ComplianceReport()
        data = report.generate_json(sample_coverage, all_config)
        covered_ids = [item["id"] for item in data["covered_controls"]]
        assert "NIST-IA-2" in covered_ids

    def test_generate_json_frameworks_list(self, sample_coverage, all_config):
        report = ComplianceReport()
        data = report.generate_json(sample_coverage, all_config)
        assert set(data["frameworks"]) == {"NIST-800-53", "HIPAA", "ISO-27001"}

    def test_empty_coverage_all_uncovered(self, nist_config):
        report = ComplianceReport()
        data = report.generate_json([], nist_config)
        assert data["covered"] == 0
        assert len(data["uncovered_controls"]) > 0


# ── EndpointCoverage dataclass ────────────────────────────────────────────────

class TestEndpointCoverage:
    def test_basic_fields(self):
        cov = EndpointCoverage(
            method="GET", path="/pets",
            control_ids=["NIST-SC-8"],
            test_names=["test_list_pets"],
        )
        assert cov.method == "GET"
        assert cov.path == "/pets"
        assert "NIST-SC-8" in cov.control_ids
        assert "test_list_pets" in cov.test_names
