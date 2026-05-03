"""Sigma Rule Challenge - Write detection rules and test against logs."""

import json
import re
import yaml
from flask import Flask, request, render_template_string

app = Flask(__name__)

with open("/data/logs.json") as f:
    LOGS = json.load(f)

FLAG = "CTF{REDACTED}"

# Attack log indices (0-based) that must be detected
ATTACK_INDICES = {3, 4}  # encoded powershell and schtasks persistence

HTML = """<!DOCTYPE html>
<html>
<head>
<title>Sigma Rule Lab</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: monospace; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; padding: 20px; }
.container { max-width: 1000px; margin: 0 auto; }
h1 { color: #00c8ff; margin-bottom: 8px; font-size: 22px; text-align: center; }
.subtitle { text-align: center; color: #888; margin-bottom: 20px; font-size: 13px; }
.panels { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.panel { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 16px; }
.panel h2 { color: #00c8ff; font-size: 14px; margin-bottom: 8px; }
textarea { width: 100%; height: 300px; background: #0a0a0a; border: 1px solid #333; border-radius: 4px; color: #e0e0e0; font-family: monospace; font-size: 12px; padding: 10px; resize: vertical; }
button { padding: 12px 24px; background: #00c8ff; color: #0a0a0a; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-family: monospace; display: block; margin: 0 auto 16px; }
.results { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 16px; }
.results h2 { color: #00c8ff; font-size: 14px; margin-bottom: 8px; }
.match { background: rgba(0,229,160,0.1); border: 1px solid #00e5a0; padding: 8px; border-radius: 4px; margin-bottom: 8px; font-size: 12px; }
.miss { background: rgba(255,62,108,0.1); border: 1px solid #ff3e6c; padding: 8px; border-radius: 4px; margin-bottom: 8px; font-size: 12px; }
.flag { background: rgba(240,180,41,0.1); border: 1px solid #f0b429; padding: 16px; border-radius: 4px; text-align: center; margin-top: 12px; }
.flag span { color: #f0b429; font-size: 18px; font-weight: bold; }
.info { color: #888; font-size: 12px; margin-bottom: 8px; }
.error { color: #ff3e6c; }
.log-viewer { max-height: 300px; overflow-y: auto; }
.log-entry { background: #0a0a0a; padding: 6px 8px; margin-bottom: 4px; border-radius: 4px; font-size: 11px; border-left: 3px solid #333; }
.log-entry.attack { border-left-color: #ff3e6c; }
pre { white-space: pre-wrap; }
</style>
</head>
<body>
<div class="container">
    <h1>Sigma Detection Lab</h1>
    <p class="subtitle">Write Sigma rules to detect the attack patterns hidden in the Windows event logs</p>

    <div class="panels">
        <div class="panel">
            <h2>Log Events ({{ logs|length }} events)</h2>
            <div class="log-viewer">
            {% for log in logs %}
                <div class="log-entry {{ 'attack' if loop.index0 in attack_indices else '' }}">
                    <strong>[{{ log.TimeCreated }}]</strong> EventID:{{ log.EventID }}
                    {% if log.Image %}Image: {{ log.Image.split('\\\\')[-1] }}{% endif %}
                    {% if log.CommandLine %}<br>Cmd: {{ log.CommandLine[:80] }}{% if log.CommandLine|length > 80 %}...{% endif %}{% endif %}
                </div>
            {% endfor %}
            </div>
        </div>
        <div class="panel">
            <h2>Your Sigma Rule (YAML)</h2>
            <form method="POST">
                <textarea name="rule" placeholder="title: My Detection Rule
status: experimental
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\\powershell.exe'
        CommandLine|contains: '-EncodedCommand'
    condition: selection
level: high">{{ submitted_rule }}</textarea>
                <br><br>
                <button type="submit">Test Rule</button>
            </form>
        </div>
    </div>

    {% if results is not none %}
    <div class="results">
        <h2>Results</h2>
        {% if parse_error %}
            <p class="error">{{ parse_error }}</p>
        {% else %}
            <p class="info">Matched {{ matched_count }} / {{ total_logs }} log events</p>
            <p class="info">Attacks detected: {{ attacks_detected }} / {{ total_attacks }}</p>

            {% for r in results %}
                <div class="{{ 'match' if r.matched else 'miss' }}">
                    [{{ r.log.TimeCreated }}] EventID:{{ r.log.EventID }}
                    {% if r.log.Image %} | {{ r.log.Image.split('\\\\')[-1] }}{% endif %}
                    {% if r.matched %} ✓ DETECTED{% endif %}
                </div>
            {% endfor %}

            {% if attacks_detected == total_attacks %}
            <div class="flag">
                <p>All attack patterns detected!</p>
                <span>{{ flag }}</span>
            </div>
            {% else %}
            <p class="info" style="margin-top: 12px;">
                Detect all {{ total_attacks }} attack events to reveal the flag.
                Hint: Look for encoded PowerShell and suspicious scheduled tasks.
            </p>
            {% endif %}
        {% endif %}
    </div>
    {% endif %}
</div>
</body>
</html>"""


def evaluate_sigma_rule(rule_yaml, logs):
    """Evaluate a simplified Sigma rule against log events."""
    try:
        rule = yaml.safe_load(rule_yaml)
    except yaml.YAMLError as e:
        return None, f"YAML parse error: {e}"

    if not isinstance(rule, dict):
        return None, "Rule must be a YAML mapping"

    detection = rule.get("detection", {})
    if not detection:
        return None, "Rule must have a 'detection' section"

    condition = detection.get("condition", "")
    if not condition:
        return None, "Detection must have a 'condition'"

    # Extract selection names from condition
    # Support: selection, selection1 or selection2, selection and not filter
    selections = {}
    filters = {}
    for key, value in detection.items():
        if key == "condition":
            continue
        if key.startswith("filter"):
            filters[key] = value
        else:
            selections[key] = value

    results = []
    for log in logs:
        matched = evaluate_condition(condition, selections, filters, log)
        results.append({"log": log, "matched": matched})

    return results, None


def field_match(log, field_spec, values):
    """Match a field with optional modifiers (|contains, |endswith, |startswith, |re)."""
    parts = field_spec.split("|")
    field_name = parts[0]
    modifiers = parts[1:]

    log_value = log.get(field_name, "")
    if log_value is None:
        log_value = ""
    log_value = str(log_value)

    if not isinstance(values, list):
        values = [values]

    for val in values:
        val = str(val)
        matched = False
        if "endswith" in modifiers:
            matched = log_value.lower().endswith(val.lower())
        elif "startswith" in modifiers:
            matched = log_value.lower().startswith(val.lower())
        elif "contains" in modifiers:
            matched = val.lower() in log_value.lower()
        elif "re" in modifiers:
            try:
                matched = bool(re.search(val, log_value, re.IGNORECASE))
            except re.error:
                matched = False
        else:
            matched = log_value.lower() == val.lower()

        if matched:
            return True
    return False


def evaluate_selection(selection, log):
    """All fields in a selection must match (AND)."""
    if not isinstance(selection, dict):
        return False
    for field_spec, values in selection.items():
        if not field_match(log, field_spec, values):
            return False
    return True


def evaluate_condition(condition, selections, filters, log):
    """Evaluate condition string against selections/filters."""
    condition = condition.strip()

    # Handle "selection and not filter"
    if " and not " in condition:
        parts = condition.split(" and not ")
        sel_name = parts[0].strip()
        filter_name = parts[1].strip()
        sel_match = evaluate_selection(selections.get(sel_name, {}), log)
        fil_match = evaluate_selection(filters.get(filter_name, {}), log)
        return sel_match and not fil_match

    # Handle "sel1 or sel2"
    if " or " in condition:
        parts = condition.split(" or ")
        return any(
            evaluate_selection(selections.get(p.strip(), {}), log)
            for p in parts
        )

    # Handle "sel1 and sel2"
    if " and " in condition:
        parts = condition.split(" and ")
        return all(
            evaluate_selection(selections.get(p.strip(), {}), log)
            for p in parts
        )

    # Simple: just a selection name
    sel = selections.get(condition, {})
    return evaluate_selection(sel, log)


@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    parse_error = None
    matched_count = 0
    attacks_detected = 0
    submitted_rule = ""

    if request.method == "POST":
        submitted_rule = request.form.get("rule", "")
        results, parse_error = evaluate_sigma_rule(submitted_rule, LOGS)

        if results:
            matched_count = sum(1 for r in results if r["matched"])
            # Check which attack events were detected
            for idx in ATTACK_INDICES:
                if idx < len(results) and results[idx]["matched"]:
                    attacks_detected += 1

    return render_template_string(
        HTML,
        logs=LOGS,
        attack_indices=ATTACK_INDICES,
        results=results,
        parse_error=parse_error,
        matched_count=matched_count,
        total_logs=len(LOGS),
        attacks_detected=attacks_detected,
        total_attacks=len(ATTACK_INDICES),
        flag=FLAG,
        submitted_rule=submitted_rule,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
