# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import ast
import json
import re
from typing import Dict, Optional


def safe_json_from_llm(content: str) -> Optional[Dict]:
    """
    Sanitize and safely parse LLM output into a Python dict.
    Supports both JSON and Python-like string dicts.
    """
    content = content.strip()
    content = re.sub(r"^```[a-zA-Z]*\n?", "", content)  # opening ```
    content = re.sub(r"```$", "", content)  # closing ```

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    try:
        return ast.literal_eval(content)
    except Exception:
        return None


def parse_key_from_nested_dict(nested_dict: Dict, target_key: str, default=None):
    """
    Recursively search for a key in a nested dictionary and return its value.

    Args:
        nested_dict: The dictionary to search through
        target_key: The key to search for
        default: The value to return if the key is not found

    Returns:
        The value associated with the target_key, or default if not found
    """
    if not isinstance(nested_dict, dict):
        return default

    if target_key in nested_dict:
        return nested_dict[target_key]

    for key, value in nested_dict.items():
        if isinstance(value, dict):
            result = parse_key_from_nested_dict(value, target_key, default)
            if result != default:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = parse_key_from_nested_dict(item, target_key, default)
                    if result != default:
                        return result

    return default
