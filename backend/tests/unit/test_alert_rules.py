"""Structural checks on the committed Prometheus alert rules.

``promtool`` validates syntax and (via docs/alerts/tests/) firing
behaviour. It cannot check the conventions this repo layers on top:

  * every rule carries a ``runbook_url`` that resolves to a real file —
    CLAUDE.md §14.4, and docs/alerts/README.md makes it mandatory,
    because an alert without a recovery procedure is pager noise;
  * ``severity`` is drawn from the two values the Alertmanager routing
    tree actually matches. A rule labelled anything else lands on the
    default receiver instead of paging — which is how a silent failure
    stays silent. The backup rules shipped with ``critical``/``warning``
    and would have done exactly that.

Pure YAML parsing, no ``app.*`` imports, so this stays a unit test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALERTS_DIR = _REPO_ROOT / "docs" / "alerts"
_RUNBOOKS_DIR = _REPO_ROOT / "docs" / "runbooks"
_PROM_CONFIG = _REPO_ROOT / "infra" / "observability" / "prometheus.yml"
_ALERTMANAGER_CONFIG = _REPO_ROOT / "infra" / "observability" / "alertmanager.yml"

# The values the routing tree in alertmanager.yml matches on.
_ROUTED_SEVERITIES = {"page", "warn"}


def _rule_files() -> list[Path]:
    return sorted(_ALERTS_DIR.glob("*.rules.yml"))


def _all_rules():
    for path in _rule_files():
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for group in doc.get("groups", []):
            for rule in group.get("rules", []):
                if "alert" in rule:
                    yield path, rule


def test_there_are_rule_files_at_all():
    assert _rule_files(), "docs/alerts/ has no *.rules.yml files"


@pytest.mark.parametrize(
    "path,rule", list(_all_rules()), ids=lambda v: getattr(v, "name", None) or v.get("alert", "?")
)
class TestEveryRule:
    def test_has_a_runbook_url(self, path, rule):
        annotations = rule.get("annotations") or {}
        assert "runbook_url" in annotations, (
            f"{rule['alert']} in {path.name} has no runbook_url — "
            "CLAUDE.md §14.4 requires every alert to link a recovery "
            "procedure"
        )

    def test_runbook_url_resolves_to_a_real_file(self, path, rule):
        url = (rule.get("annotations") or {}).get("runbook_url", "")
        # Rule files use paths relative to docs/alerts/, e.g.
        # "../runbooks/db-restore.md".
        target = (_ALERTS_DIR / url).resolve()
        assert target.is_file(), (
            f"{rule['alert']} points at {url!r}, which resolves to "
            f"{target} — no such file. A dangling runbook link is worse "
            "than none: it looks handled."
        )

    def test_runbook_lives_under_docs_runbooks(self, path, rule):
        url = (rule.get("annotations") or {}).get("runbook_url", "")
        target = (_ALERTS_DIR / url).resolve()
        assert _RUNBOOKS_DIR in target.parents, (
            f"{rule['alert']} links outside docs/runbooks/: {target}"
        )

    def test_severity_is_one_the_router_matches(self, path, rule):
        severity = (rule.get("labels") or {}).get("severity")
        assert severity in _ROUTED_SEVERITIES, (
            f"{rule['alert']} in {path.name} has severity={severity!r}. "
            f"alertmanager.yml only routes {sorted(_ROUTED_SEVERITIES)}; "
            "anything else silently falls through to the default "
            "receiver instead of paging."
        )


class TestPrometheusLoadsEveryRuleFile:
    """A rule file nobody loads is a text file."""

    def test_every_rule_file_is_in_rule_files(self):
        config = yaml.safe_load(_PROM_CONFIG.read_text(encoding="utf-8"))
        loaded = {Path(p).name for p in config.get("rule_files", [])}
        on_disk = {p.name for p in _rule_files()}
        missing = on_disk - loaded
        assert not missing, (
            f"{missing} exist under docs/alerts/ but are not listed in "
            "prometheus.yml rule_files — they would never be evaluated"
        )

    def test_scrape_job_name_matches_the_liveness_alert(self):
        # SiegeApiDown alerts on up{job="siege-range-api"}; that series
        # exists only because of the scrape job's name.
        config = yaml.safe_load(_PROM_CONFIG.read_text(encoding="utf-8"))
        jobs = {j["job_name"] for j in config.get("scrape_configs", [])}
        assert "siege-range-api" in jobs, (
            "renaming the API scrape job silently disables SiegeApiDown"
        )


class TestAlertmanagerRouting:
    def test_routes_cover_every_severity_in_use(self):
        config = yaml.safe_load(
            _ALERTMANAGER_CONFIG.read_text(encoding="utf-8")
        )
        matched = set()
        for route in (config.get("route") or {}).get("routes", []):
            for matcher in route.get("matchers", []):
                if matcher.startswith("severity ="):
                    matched.add(matcher.split('"')[1])

        in_use = {
            (rule.get("labels") or {}).get("severity")
            for _, rule in _all_rules()
        }
        assert in_use <= matched, (
            f"severities {in_use - matched} are used by rules but have no "
            "route in alertmanager.yml"
        )

    def test_default_receiver_exists_as_a_fallthrough(self):
        config = yaml.safe_load(
            _ALERTMANAGER_CONFIG.read_text(encoding="utf-8")
        )
        names = {r["name"] for r in config.get("receivers", [])}
        assert (config.get("route") or {}).get("receiver") in names, (
            "the top-level route must name a receiver that exists, so a "
            "rule with an unrouted severity makes noise rather than "
            "vanishing"
        )
