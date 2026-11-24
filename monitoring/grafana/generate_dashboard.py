"""Dashboard-as-code: generates dashboards/taskmanager.json.

    python monitoring/grafana/generate_dashboard.py

Each panel carries two queries where needed - one for Docker Compose (cAdvisor `name` label)
and one for Kubernetes (`namespace`/`pod` labels) - so the same dashboard works in both.
"""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}
_panel_id = 0


def panel(title, targets, x, y, w=12, h=8, kind="timeseries", unit="short", thresholds=None):
    global _panel_id
    _panel_id += 1
    p = {
        "id": _panel_id, "type": kind, "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": l, "datasource": DS}
                    for i, (e, l) in enumerate(targets)],
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {},
    }
    if thresholds:
        p["fieldConfig"]["defaults"]["thresholds"] = {
            "mode": "absolute",
            "steps": [{"color": c, "value": v} for v, c in thresholds]}
        p["fieldConfig"]["defaults"]["color"] = {"mode": "thresholds"}
    if kind == "stat":
        p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background"}
    return p


def row(title, y):
    global _panel_id
    _panel_id += 1
    return {"id": _panel_id, "type": "row", "title": title, "collapsed": False,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


K8S = 'namespace="taskmanager", container="taskmanager"'
panels = [
    row("Container health", 0),
    panel("App up", [('min(up{job=~"taskmanager|.*taskmanager.*"})', "up")], 0, 1, w=4, h=4,
          kind="stat", thresholds=[(None, "red"), (1, "green")]),
    panel("Running app containers / pods",
          [('count(container_last_seen{name=~".*app.*"})', "compose"),
           ('count(kube_pod_status_ready{namespace="taskmanager", condition="true"})', "k8s ready pods")],
          4, 1, w=5, h=4, kind="stat"),
    panel("Container restarts (1h)",
          [(f'sum(increase(kube_pod_container_status_restarts_total{{{K8S}}}[1h]))', "k8s")],
          9, 1, w=5, h=4, kind="stat", thresholds=[(None, "green"), (1, "orange"), (5, "red")]),
    panel("Live colour", [('max by (deploy_color) (taskmanager_app_info)', "{{deploy_color}}")],
          14, 1, w=5, h=4, kind="stat"),
    panel("Registered users", [("max(taskmanager_users)", "users")], 19, 1, w=5, h=4, kind="stat"),

    row("CPU & memory", 5),
    panel("Container CPU (cores)",
          [('sum by (name) (rate(container_cpu_usage_seconds_total{name=~".*(app|db|nginx).*"}[1m]))', "{{name}}"),
           (f'sum by (pod) (rate(container_cpu_usage_seconds_total{{{K8S}}}[1m]))', "{{pod}}")],
          0, 6, unit="short"),
    panel("Container memory (working set)",
          [('sum by (name) (container_memory_working_set_bytes{name=~".*(app|db|nginx).*"})', "{{name}}"),
           (f'sum by (pod) (container_memory_working_set_bytes{{{K8S}}})', "{{pod}}")],
          12, 6, unit="bytes"),
    panel("Host CPU utilisation %",
          [('100 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100', "{{instance}}")],
          0, 14, unit="percent"),
    panel("Host memory utilisation %",
          [("(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100", "{{instance}}")],
          12, 14, unit="percent"),

    row("Application metrics", 22),
    panel("Requests per second by endpoint",
          [("sum by (endpoint) (rate(taskmanager_http_requests_total[1m]))", "{{endpoint}}")],
          0, 23, unit="reqps"),
    panel("Error rate (5xx) %",
          [('100 * sum(rate(taskmanager_http_requests_total{status=~"5.."}[5m])) '
            '/ clamp_min(sum(rate(taskmanager_http_requests_total[5m])), 1e-9)', "5xx %")],
          12, 23, unit="percent"),
    panel("Latency p50 / p95 / p99",
          [(f"histogram_quantile({q}, sum by (le) (rate(taskmanager_http_request_duration_seconds_bucket[5m])))",
            f"p{int(q * 100)}") for q in (0.5, 0.95, 0.99)],
          0, 31, unit="s"),
    panel("Tasks by status", [("sum by (status) (taskmanager_tasks)", "{{status}}")], 12, 31),
    panel("HTTP status codes", [("sum by (status) (rate(taskmanager_http_requests_total[1m]))", "{{status}}")],
          0, 39),
    panel("In-flight requests", [("sum(taskmanager_http_requests_in_progress)", "in flight")], 12, 39),

    row("Product usage", 47),
    panel("Tasks created / hour by source",
          [("sum by (source) (increase(taskmanager_tasks_created_total[1h]))", "{{source}}")], 0, 48, w=8),
    panel("Tasks completed / hour by priority",
          [("sum by (priority) (increase(taskmanager_tasks_completed_total[1h]))", "{{priority}}")], 8, 48, w=8),
    panel("Focus minutes / hour", [("sum(increase(taskmanager_focus_minutes_total[1h]))", "minutes")], 16, 48, w=8),
]

dashboard = {
    "uid": "taskmanager-overview",
    "title": "Task Manager - Overview",
    "tags": ["taskmanager", "capstone"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "10s",
    "time": {"from": "now-1h", "to": "now"},
    "panels": panels,
}

out = Path(__file__).parent / "dashboards" / "taskmanager.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(dashboard, indent=2) + "\n")
print(f"wrote {out}")

# Same dashboard as a ConfigMap for the Grafana sidecar in kube-prometheus-stack.
indented = "\n".join("    " + line for line in json.dumps(dashboard, indent=2).splitlines())
cm = (
    "# Generated by monitoring/grafana/generate_dashboard.py - do not edit by hand.\n"
    "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: taskmanager-dashboard\n  namespace: monitoring\n"
    "  labels:\n    grafana_dashboard: \"1\"\ndata:\n  taskmanager.json: |\n" + indented + "\n"
)
cm_out = Path(__file__).parents[1] / "k8s" / "grafana-dashboard.yaml"
cm_out.write_text(cm)
print(f"wrote {cm_out}")
