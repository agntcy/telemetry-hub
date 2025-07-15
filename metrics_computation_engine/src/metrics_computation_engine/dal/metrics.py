# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from .client import get_api_response, post_api_request
from .utils import format_metric_payload


def get_metric_results_by_session(session_id: str):
    return get_api_response(f"/metrics/session/{session_id}")


def get_metric_results_by_span(span_id: str):
    return get_api_response(f"/metrics/span/{span_id}")


def write_metrics(mce_output):
    metric_type_to_path = {
        "span_metrics": "/metrics/span",
        "session_metrics": "/metrics/session",
        "population_metrics": "/metrics/population",
    }

    summary = {
        "span": {"success": 0, "error": 0, "details": []},
        "session": {"success": 0, "error": 0, "details": []},
        "population": {"success": 0, "error": 0, "details": []},
    }

    for metric_type, metrics_list in mce_output.items():
        if metric_type == "population_metrics":
            print(f"⚠️ Skipping {metric_type}: endpoint not implemented.")
            continue  # Skip this metric type entirely
        path = metric_type_to_path.get(metric_type)
        if not path:
            continue

        type_key = metric_type.replace("_metrics", "")  # span/session/population

        for metric in metrics_list:
            try:
                payload = format_metric_payload(
                    metric, app_id="", app_name="", trace_id=""
                )
                response = post_api_request(path, json=payload)
                summary[type_key]["success"] += 1
                summary[type_key]["details"].append(
                    {
                        "metric": metric.metric_name
                        if hasattr(metric, "metric_name")
                        else "unknown",
                        "status": "success",
                        "response": response,
                    }
                )
            except Exception as e:
                summary[type_key]["error"] += 1
                summary[type_key]["details"].append(
                    {
                        "metric": getattr(metric, "metric_name", "unknown"),
                        "status": "error",
                        "error": str(e),
                    }
                )

    return summary
