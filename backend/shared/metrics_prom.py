"""Prometheus text exposition (format 0.0.4) without a client dependency.

Pure functions so they're unit-testable without spinning up the FastAPI app.
"""
import re
from typing import Any, Dict, List, Optional, Tuple


def sanitize(name: str) -> str:
    """'Signals Generated' -> 'signals_generated' (valid metric name part)."""
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower()).strip("_")


def _labels(d: Optional[Dict[str, Any]]) -> str:
    if not d:
        return ""
    inner = ",".join(f'{k}="{str(v)}"' for k, v in d.items())
    return "{" + inner + "}"


def render(groups: List[Dict[str, Any]]) -> str:
    """Render metric groups to exposition text.

    group = {name, type, help, samples:[(labels_dict|None, value)]}
    """
    out: List[str] = []
    for g in groups:
        name = g["name"]
        if g.get("help"):
            out.append(f"# HELP {name} {g['help']}")
        out.append(f"# TYPE {name} {g.get('type', 'gauge')}")
        for labels, value in g["samples"]:
            out.append(f"{name}{_labels(labels)} {value}")
    return "\n".join(out) + "\n"


def core_metrics_text(
    global_metrics: Dict[str, Any],
    nan_count: int,
    correlation_rejections: int,
    active_tasks: int,
    feeds: List[Dict[str, Any]],
) -> str:
    """Build the Core (FastAPI) exposition from runtime counters + feed health."""
    groups: List[Dict[str, Any]] = []

    for k, v in global_metrics.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        groups.append({
            "name": f"ai_trading_{sanitize(k)}",
            "type": "gauge",
            "help": k,
            "samples": [(None, v)],
        })

    groups.append({"name": "ai_trading_nan_detection_total", "type": "counter",
                   "help": "NaN/Inf values caught by guards", "samples": [(None, nan_count)]})
    groups.append({"name": "ai_trading_correlation_rejection_total", "type": "counter",
                   "help": "Signals rejected by correlation cap", "samples": [(None, correlation_rejections)]})
    groups.append({"name": "ai_trading_active_background_tasks", "type": "gauge",
                   "help": "Engine async tasks currently running", "samples": [(None, active_tasks)]})

    if feeds:
        age_samples: List[Tuple[Dict[str, Any], Any]] = []
        live_samples: List[Tuple[Dict[str, Any], Any]] = []
        for f in feeds:
            sym = f.get("symbol")
            age = f.get("age")
            age_samples.append(({"symbol": sym, "source": f.get("source") or "none"},
                                age if age is not None else -1))
            live_samples.append(({"symbol": sym}, 1 if f.get("status") == "live" else 0))
        groups.append({"name": "ai_trading_feed_age_seconds", "type": "gauge",
                       "help": "Seconds since last tick per symbol", "samples": age_samples})
        groups.append({"name": "ai_trading_feed_live", "type": "gauge",
                       "help": "1 if feed is live, else 0", "samples": live_samples})

    return render(groups)
