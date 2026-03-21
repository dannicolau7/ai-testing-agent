"""
compliance.py — Compliance tagging for AI-generated pytest suites

Maps API endpoints to regulatory control IDs (HIPAA, NIST 800-53, ISO 27001),
injects pytest marks into generated test code, and produces a coverage report
showing which controls have tests and which have gaps.

Public API:

    config  = ComplianceConfig.load("compliance.yaml")
    mapper  = ControlMapper(config)
    tagger  = ComplianceTagger()
    reporter = ComplianceReport()

    # Given an endpoint path + method, find which controls apply
    controls = mapper.map(path="/auth/login", method="POST", tags=["auth"])

    # Inject marks into already-generated pytest source
    tagged_code = tagger.tag(source_code, controls)

    # After generating tests for the whole spec, build a coverage report
    report = reporter.generate(coverage_data, config)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Control library ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Control:
    """A single compliance control."""
    id: str           # e.g. "NIST-IA-2", "HIPAA-164.312.d", "ISO-A.9.4.2"
    framework: str    # "NIST-800-53", "HIPAA", "ISO-27001"
    title: str        # Human-readable name
    description: str  # One-line description
    # Endpoint patterns that trigger this control (any match = applies)
    path_keywords: List[str] = field(default_factory=list)   # substring in path
    tag_keywords: List[str] = field(default_factory=list)    # substring in tag
    methods: List[str] = field(default_factory=list)         # HTTP methods (empty = all)
    pytest_mark: str = ""   # auto-computed from id if empty

    def __post_init__(self):
        if not self.pytest_mark:
            # e.g. "NIST-IA-2" → "nist_ia_2"
            object.__setattr__(
                self,
                "pytest_mark",
                re.sub(r"[^a-z0-9]", "_", self.id.lower()).strip("_"),
            )


# ── Built-in control library ──────────────────────────────────────────────────

_NIST = "NIST-800-53"
_HIPAA = "HIPAA"
_ISO = "ISO-27001"

CONTROL_LIBRARY: List[Control] = [

    # ── NIST 800-53 ───────────────────────────────────────────────────────────
    Control(
        id="NIST-AC-2", framework=_NIST,
        title="Account Management",
        description="Manage system accounts and enforce lifecycle policies.",
        path_keywords=["user", "account", "member", "register", "signup", "profile"],
        tag_keywords=["user", "account", "member"],
    ),
    Control(
        id="NIST-AC-3", framework=_NIST,
        title="Access Enforcement",
        description="Enforce approved authorizations for access to resources.",
        path_keywords=["admin", "role", "permission", "privilege", "access", "grant", "revoke"],
        tag_keywords=["admin", "role", "authorization"],
    ),
    Control(
        id="NIST-AC-6", framework=_NIST,
        title="Least Privilege",
        description="Employ least privilege, allowing only authorized access.",
        path_keywords=["admin", "role", "scope", "permission"],
        tag_keywords=["admin", "role"],
        methods=["GET", "PUT", "PATCH", "DELETE"],
    ),
    Control(
        id="NIST-AC-17", framework=_NIST,
        title="Remote Access",
        description="Establish and document restrictions for remote access.",
        path_keywords=["api", "v1", "v2", "v3", "external", "remote"],
        tag_keywords=["api", "external"],
    ),
    Control(
        id="NIST-IA-2", framework=_NIST,
        title="Identification and Authentication",
        description="Uniquely identify and authenticate organizational users.",
        path_keywords=["login", "auth", "signin", "authenticate", "token", "jwt",
                       "oauth", "sso", "session", "whoami", "me"],
        tag_keywords=["auth", "authentication", "identity"],
    ),
    Control(
        id="NIST-IA-5", framework=_NIST,
        title="Authenticator Management",
        description="Manage authenticators including passwords and tokens.",
        path_keywords=["password", "credential", "reset", "secret", "key",
                       "apikey", "api-key", "token", "refresh"],
        tag_keywords=["auth", "credential", "password"],
    ),
    Control(
        id="NIST-AU-2", framework=_NIST,
        title="Audit Events",
        description="Identify the types of events the system can audit.",
        path_keywords=["audit", "log", "event", "history", "activity", "track"],
        tag_keywords=["audit", "log", "event"],
    ),
    Control(
        id="NIST-AU-3", framework=_NIST,
        title="Audit Record Content",
        description="Audit records capture sufficient detail for post-incident analysis.",
        path_keywords=["audit", "log", "report", "trail"],
        tag_keywords=["audit", "log"],
    ),
    Control(
        id="NIST-SI-10", framework=_NIST,
        title="Information Input Validation",
        description="Check inputs for accuracy, completeness, and validity.",
        path_keywords=[],          # applies to any POST/PUT/PATCH endpoint
        tag_keywords=[],
        methods=["POST", "PUT", "PATCH"],
    ),
    Control(
        id="NIST-SC-8", framework=_NIST,
        title="Transmission Confidentiality and Integrity",
        description="Implement cryptographic protections for transmitted information.",
        path_keywords=[],          # applies to all endpoints (transport-level)
        tag_keywords=[],
    ),

    # ── HIPAA Technical Safeguards (45 CFR §164.312) ──────────────────────────
    Control(
        id="HIPAA-164.312.a.1", framework=_HIPAA,
        title="Access Control",
        description="Allow access only to authorized persons or software programs.",
        path_keywords=["user", "account", "admin", "role", "permission", "access"],
        tag_keywords=["user", "account", "admin"],
    ),
    Control(
        id="HIPAA-164.312.a.2.i", framework=_HIPAA,
        title="Unique User Identification",
        description="Assign a unique name/number to each user for tracking access.",
        path_keywords=["user", "account", "register", "signup", "id", "profile"],
        tag_keywords=["user", "identity"],
    ),
    Control(
        id="HIPAA-164.312.b", framework=_HIPAA,
        title="Audit Controls",
        description="Record and examine activity in systems containing ePHI.",
        path_keywords=["audit", "log", "event", "history", "track", "activity"],
        tag_keywords=["audit", "log"],
    ),
    Control(
        id="HIPAA-164.312.d", framework=_HIPAA,
        title="Person or Entity Authentication",
        description="Verify that a person or entity seeking access is who claimed.",
        path_keywords=["login", "auth", "authenticate", "token", "session",
                       "oauth", "mfa", "2fa", "verify"],
        tag_keywords=["auth", "authentication"],
    ),
    Control(
        id="HIPAA-164.312.e.1", framework=_HIPAA,
        title="Transmission Security",
        description="Guard against unauthorized access to ePHI during transmission.",
        path_keywords=["patient", "health", "phi", "ehr", "medical", "diagnosis",
                       "prescription", "record", "clinical"],
        tag_keywords=["patient", "health", "phi", "medical"],
    ),

    # ── ISO/IEC 27001:2022 ────────────────────────────────────────────────────
    Control(
        id="ISO-A.9.2.1", framework=_ISO,
        title="User Registration and De-registration",
        description="Implement a formal user registration and de-registration process.",
        path_keywords=["user", "register", "signup", "deactivate", "delete", "account"],
        tag_keywords=["user", "account"],
        methods=["POST", "DELETE"],
    ),
    Control(
        id="ISO-A.9.4.2", framework=_ISO,
        title="Secure Log-on Procedures",
        description="Control access using a secure log-on procedure.",
        path_keywords=["login", "auth", "signin", "session", "oauth", "token"],
        tag_keywords=["auth", "login"],
    ),
    Control(
        id="ISO-A.9.4.3", framework=_ISO,
        title="Password Management System",
        description="Ensure quality passwords via an interactive management system.",
        path_keywords=["password", "credential", "reset", "change-password", "secret"],
        tag_keywords=["password", "credential"],
    ),
    Control(
        id="ISO-A.12.4.1", framework=_ISO,
        title="Event Logging",
        description="Produce, protect, and retain event logs recording user activities.",
        path_keywords=["log", "audit", "event", "activity", "history", "trail"],
        tag_keywords=["log", "audit", "event"],
    ),
    Control(
        id="ISO-A.14.1.2", framework=_ISO,
        title="Securing Application Services",
        description="Protect information transacting over public networks.",
        path_keywords=["payment", "checkout", "order", "transaction", "billing", "invoice"],
        tag_keywords=["payment", "billing", "order"],
    ),
    Control(
        id="ISO-A.14.2.8", framework=_ISO,
        title="System Security Testing",
        description="Test security functionality during development.",
        path_keywords=[],   # Applies broadly — any tested endpoint counts
        tag_keywords=[],
    ),
]

# Group by framework for quick lookup
_LIBRARY_BY_FRAMEWORK: Dict[str, List[Control]] = {}
for _c in CONTROL_LIBRARY:
    _LIBRARY_BY_FRAMEWORK.setdefault(_c.framework, []).append(_c)


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class ComplianceConfig:
    """
    Loaded from a compliance.yaml file.

    frameworks: which regulatory frameworks apply (subset of HIPAA, NIST-800-53, ISO-27001)
    custom_mappings: path prefix → list of extra control IDs to always apply
    """
    frameworks: List[str] = field(default_factory=list)
    custom_mappings: Dict[str, List[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "ComplianceConfig":
        """Load a compliance.yaml file. Returns an empty config if file not found."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Compliance config not found: {path}")

        try:
            import yaml  # type: ignore
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except ImportError as exc:
            raise ImportError("PyYAML required: pip install PyYAML") from exc

        frameworks = raw.get("frameworks", [])
        # Normalise: "NIST" → "NIST-800-53", "nist" → "NIST-800-53"
        normalised = []
        _aliases = {
            "nist": "NIST-800-53",
            "nist-800-53": "NIST-800-53",
            "nist800-53": "NIST-800-53",
            "hipaa": "HIPAA",
            "iso": "ISO-27001",
            "iso-27001": "ISO-27001",
            "iso27001": "ISO-27001",
        }
        for fw in frameworks:
            normalised.append(_aliases.get(fw.lower(), fw.upper()))

        custom = {}
        for path_pattern, controls in raw.get("custom_mappings", {}).items():
            custom[path_pattern] = list(controls)

        return cls(frameworks=normalised, custom_mappings=custom)

    @classmethod
    def default(cls, frameworks: Optional[List[str]] = None) -> "ComplianceConfig":
        """Create a config with sensible defaults (all three frameworks)."""
        return cls(
            frameworks=frameworks or ["NIST-800-53", "HIPAA", "ISO-27001"],
        )


# ── Control mapper ────────────────────────────────────────────────────────────

class ControlMapper:
    """
    Maps an API endpoint (path, method, tags) to a list of applicable controls.

    Matching logic (all conditions must pass for a control to apply):
    1. Control's framework is in the requested frameworks.
    2. At least one of the following is true:
       a. A control path_keyword is a substring of the endpoint path (lowercased).
       b. A control tag_keyword is a substring of any endpoint tag (lowercased).
       c. The control has no path_keywords AND no tag_keywords (applies globally).
    3. If the control specifies HTTP methods, the endpoint method is in that list.
    """

    def __init__(self, config: ComplianceConfig):
        self.config = config
        self._library = [
            c for c in CONTROL_LIBRARY
            if c.framework in config.frameworks
        ]

    def map(
        self,
        path: str,
        method: str,
        tags: Optional[List[str]] = None,
    ) -> List[Control]:
        """Return all controls that apply to this endpoint."""
        path_lower = path.lower()
        tag_lower = [t.lower() for t in (tags or [])]
        method_upper = method.upper()

        applicable: List[Control] = []

        for control in self._library:
            # Method filter
            if control.methods and method_upper not in control.methods:
                continue

            # Path / tag / global keyword match
            path_match = any(kw in path_lower for kw in control.path_keywords)
            tag_match = any(
                kw in tg for kw in control.tag_keywords for tg in tag_lower
            )
            global_control = not control.path_keywords and not control.tag_keywords

            if path_match or tag_match or global_control:
                applicable.append(control)

        # Apply custom mappings from config
        for pattern, extra_ids in self.config.custom_mappings.items():
            if pattern.lower() in path_lower:
                for cid in extra_ids:
                    if not any(c.id == cid for c in applicable):
                        # Find in full library
                        match = next(
                            (c for c in CONTROL_LIBRARY if c.id == cid), None
                        )
                        if match:
                            applicable.append(match)

        # Deduplicate while preserving order
        seen = set()
        result = []
        for c in applicable:
            if c.id not in seen:
                seen.add(c.id)
                result.append(c)

        return result

    def map_ids(
        self,
        path: str,
        method: str,
        tags: Optional[List[str]] = None,
    ) -> List[str]:
        """Convenience wrapper — returns just the control IDs."""
        return [c.id for c in self.map(path, method, tags)]


# ── Compliance tagger ─────────────────────────────────────────────────────────

class ComplianceTagger:
    """
    Injects pytest compliance marks into generated test source code.

    Each test function gets a @pytest.mark.compliance_<FRAMEWORK>("<ID>")
    decorator for every applicable control, plus a comment listing the
    control titles for readability.

    Also produces a conftest snippet that registers all markers so pytest
    does not emit "unknown mark" warnings.
    """

    _FUNC_RE = re.compile(
        r"^(def test_\w+\(.*?\):)",
        re.MULTILINE,
    )

    def tag(
        self,
        source: str,
        controls: List[Control],
        *,
        per_function: bool = False,
    ) -> str:
        """
        Insert compliance decorators above every test function in source.

        Args:
            source:       Raw pytest source code.
            controls:     Controls to apply (same set for all functions in file).
            per_function: If True, use per-function mapping (not implemented here;
                          set controls individually before calling).

        Returns:
            Source code with decorators injected.
        """
        if not controls:
            return source

        decorator_block = self._build_decorator_block(controls)

        def insert_decorators(match: re.Match) -> str:
            return decorator_block + match.group(1)

        return self._FUNC_RE.sub(insert_decorators, source)

    def tag_function(
        self,
        source: str,
        func_name: str,
        controls: List[Control],
    ) -> str:
        """Insert decorators only before a specific named test function."""
        if not controls:
            return source

        pattern = re.compile(
            rf"^(def {re.escape(func_name)}\(.*?\):)",
            re.MULTILINE,
        )
        decorator_block = self._build_decorator_block(controls)
        return pattern.sub(decorator_block + r"\1", source, count=1)

    def conftest_markers(self, controls: List[Control]) -> str:
        """
        Generate the markers registration block for conftest.py.

        Pytest requires custom marks to be declared to avoid warnings.
        Returns a string to append to (or create in) conftest.py.
        """
        if not controls:
            return ""

        lines = [
            "# Compliance markers — auto-generated by AI Testing Agent",
            "import pytest",
            "",
            "def pytest_configure(config):",
        ]
        seen: set[str] = set()
        for c in controls:
            if c.pytest_mark not in seen:
                seen.add(c.pytest_mark)
                lines.append(
                    f'    config.addinivalue_line("markers", '
                    f'"{c.pytest_mark}: {c.framework} — {c.title}")'
                )
        return "\n".join(lines) + "\n"

    def _build_decorator_block(self, controls: List[Control]) -> str:
        """Build the @pytest.mark.* decorator block for a set of controls."""
        lines = []
        # Group comment
        ids_str = ", ".join(c.id for c in controls)
        lines.append(f"# Compliance: {ids_str}")
        for c in controls:
            lines.append(f"@pytest.mark.{c.pytest_mark}")
        return "\n".join(lines) + "\n"


# ── Compliance report ─────────────────────────────────────────────────────────

@dataclass
class EndpointCoverage:
    """Coverage record for one endpoint."""
    method: str
    path: str
    control_ids: List[str]
    test_names: List[str]


class ComplianceReport:
    """
    Builds a coverage report showing which controls have tests and which don't.

    Usage:
        report = ComplianceReport()
        text = report.generate(coverage_list, config)
        md   = report.generate_markdown(coverage_list, config)
    """

    def generate(
        self,
        coverage: List[EndpointCoverage],
        config: ComplianceConfig,
    ) -> str:
        """Return a human-readable terminal report."""
        covered, uncovered = self._split_coverage(coverage, config)
        total = len(covered) + len(uncovered)

        lines = [
            "",
            "=" * 70,
            f"  COMPLIANCE COVERAGE REPORT",
            f"  Frameworks: {', '.join(config.frameworks)}",
            "=" * 70,
        ]

        if covered:
            lines += ["", f"  COVERED CONTROLS ({len(covered)}/{total}):", ""]
            for ctrl, endpoints in covered.items():
                control = self._find_control(ctrl)
                title = control.title if control else ctrl
                lines.append(f"  ✅  {ctrl:<30}  {title}")
                for ep in endpoints[:3]:
                    tests = ", ".join(ep.test_names[:2]) or "(generated)"
                    lines.append(f"       {ep.method} {ep.path} → {tests}")

        if uncovered:
            lines += ["", f"  UNCOVERED CONTROLS ({len(uncovered)}/{total}):", ""]
            for ctrl in uncovered:
                control = self._find_control(ctrl)
                title = control.title if control else ctrl
                lines.append(f"  ❌  {ctrl:<30}  {title}")
                if control:
                    lines.append(f"       Hint: add endpoints matching: "
                                 f"{', '.join(control.path_keywords[:4]) or 'any'}")

        pct = int(100 * len(covered) / total) if total else 0
        lines += [
            "",
            f"  Coverage: {pct}% ({len(covered)}/{total} controls)",
            "=" * 70,
            "",
        ]
        return "\n".join(lines)

    def generate_markdown(
        self,
        coverage: List[EndpointCoverage],
        config: ComplianceConfig,
    ) -> str:
        """Return a Markdown report suitable for a PR comment or wiki page."""
        covered, uncovered = self._split_coverage(coverage, config)
        total = len(covered) + len(uncovered)
        pct = int(100 * len(covered) / total) if total else 0

        lines = [
            f"# Compliance Coverage Report",
            f"",
            f"**Frameworks:** {', '.join(config.frameworks)}  ",
            f"**Coverage:** {pct}% ({len(covered)}/{total} controls)",
            f"",
            f"## ✅ Covered Controls",
            f"",
            f"| Control ID | Title | Endpoints |",
            f"|---|---|---|",
        ]
        for ctrl, endpoints in covered.items():
            control = self._find_control(ctrl)
            title = control.title if control else ctrl
            ep_str = "; ".join(f"`{ep.method} {ep.path}`" for ep in endpoints[:2])
            lines.append(f"| `{ctrl}` | {title} | {ep_str} |")

        lines += [
            f"",
            f"## ❌ Uncovered Controls",
            f"",
            f"| Control ID | Title | Suggested endpoint patterns |",
            f"|---|---|---|",
        ]
        for ctrl in uncovered:
            control = self._find_control(ctrl)
            title = control.title if control else ctrl
            hints = ", ".join(control.path_keywords[:3]) if control else "—"
            lines.append(f"| `{ctrl}` | {title} | `{hints}` |")

        return "\n".join(lines) + "\n"

    def generate_json(
        self,
        coverage: List[EndpointCoverage],
        config: ComplianceConfig,
    ) -> dict:
        """Return a structured dict for JSON export or CI integration."""
        covered, uncovered = self._split_coverage(coverage, config)
        total = len(covered) + len(uncovered)
        return {
            "frameworks": config.frameworks,
            "total_controls": total,
            "covered": len(covered),
            "uncovered": len(uncovered),
            "coverage_percent": int(100 * len(covered) / total) if total else 0,
            "covered_controls": [
                {
                    "id": ctrl,
                    "endpoints": [
                        {"method": ep.method, "path": ep.path}
                        for ep in eps
                    ],
                }
                for ctrl, eps in covered.items()
            ],
            "uncovered_controls": list(uncovered),
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _split_coverage(
        self,
        coverage: List[EndpointCoverage],
        config: ComplianceConfig,
    ) -> tuple[dict[str, list[EndpointCoverage]], list[str]]:
        """
        Return (covered_dict, uncovered_list).

        covered_dict maps control_id → list of EndpointCoverage that test it.
        uncovered_list is all control IDs from the config frameworks that
        have no endpoint coverage.
        """
        # Build set of all control IDs that appear in coverage
        covered: Dict[str, List[EndpointCoverage]] = {}
        for ep in coverage:
            for cid in ep.control_ids:
                covered.setdefault(cid, []).append(ep)

        # All controls in the requested frameworks
        all_controls = [
            c.id
            for c in CONTROL_LIBRARY
            if c.framework in config.frameworks
        ]
        uncovered = [cid for cid in all_controls if cid not in covered]

        return covered, uncovered

    def _find_control(self, control_id: str) -> Optional[Control]:
        return next((c for c in CONTROL_LIBRARY if c.id == control_id), None)
