# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from .client import get_api_response


def get_annotations_results_by_session(session_id: str):
    page = 1
    limit = 100

    while True:
        params = {"page": page, "limit": limit}
        resp = get_api_response(f"/annotations/session/{session_id}", params=params)

        data = resp.get("data", [])
        if not data:
            break

        # TMP: Need to figure out how to best handle human labeling where each label consists of N different evaluators
        # For now, we will just return the first annotation value
        for d in data:
            if d.get("session_id") == session_id:
                return d.get("annotation_value", "")

        if not resp.get("has_next", False):
            break

        page += 1

    return ""
