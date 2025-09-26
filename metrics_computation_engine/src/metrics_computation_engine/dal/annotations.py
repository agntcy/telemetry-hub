# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from .client import get_api_response


def get_annotations_results_by_session(session_id: str):
    resp = get_api_response("/annotations")
    for d in resp["data"]:
        if d["session_id"] == session_id:
            return d["annotation_value"]
    return ""
