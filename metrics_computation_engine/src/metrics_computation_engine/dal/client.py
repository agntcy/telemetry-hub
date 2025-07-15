# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import requests

from metrics_computation_engine.dal.config import API_BASE_URL


def get_api_response(path, params=None):
    response = requests.get(f"{API_BASE_URL}{path}", verify=False, params=params)
    response.raise_for_status()
    return response.json()


def post_api_request(path, json=None):
    response = requests.post(f"{API_BASE_URL}{path}", json=json)
    response.raise_for_status()
    return response.json()
