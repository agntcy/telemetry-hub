# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Any, Dict, List

COHERENCE_CRITERIA: str = """Coherence evaluates whether the response is logically structured, internally consistent, and easy to follow.
Coherence measures also whether response is succinct and free from unnecessary elaboration, verbosity, or repetition with no contradictions or non sequiturs.
"""

EVALUATION_STEPS_GROUNDEDNESS: List[str] = [
    "If (and ONLY IF the user provided in their input any information retrieval context"
    " (such as information sources, raw documents, etc) to base the answer"
    " on, determine if the assertions and claims provided in the answer "
    "are faithful to the provided retrieval context.",
    "If there is no retrieval context provided, give an average score.",
]
EVALUATION_STEPS_TONALITY: List[str] = [
    "If the situation requires it (e.g if the user seems to be in a "
    "situation where their emotions are not neutral : happy, sad, angry, "
    "etc), check if there is a fair level of understanding, respect and "
    "compassion in the response when applicable.",
    "Determine whether the actual output maintains a professional tone throughout.",
    "Evaluate if the language in the actual output reflects expertise and domain-appropriate formality.",
    "Ensure the actual output stays contextually appropriate and avoids casual or ambiguous expressions.",
    "Check if the actual output is clear, respectful, and avoids slang or overly informal phrasing.",
]

TOOL_DEFINITIONS_EXAMPLE: List[Dict[str, Any]] = [
    {
        "description": "This tool adds 2 numbers.",
        "name": "two_number_adder",
        "parameters": {
            "properties": {
                "first_number": {
                    "description": "first operand",
                    "type": "number",
                },
                "second_number": {
                    "description": "second operand",
                    "type": "number",
                },
            },
            "required": ["first_number", "second_number"],
            "type": "object",
        },
    },
    {
        "description": "This tool multiplies a number by 2.",
        "name": "number_doubler",
        "parameters": {
            "properties": {
                "number_of_interest": {
                    "description": "number to multiply by two",
                    "type": "number",
                }
            },
            "required": ["number_of_interest"],
            "type": "object",
        },
    },
]
CHAT_EXAMPLE: List[Dict[str, Any]] = [
    {
        "content": "You are a helpful assistant. Use the tools that are available to you WHEN NECESSARY",
        "role": "system",
    },
    {"content": "Could you multiply 5 by 2?", "role": "user"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "arguments": {"number_of_interest": 5},
                "id": "call_XXXXXXXXXXXXXXXXXXXXXXXX",
                "name": "number_doubler",
            }
        ],
        "content": "",
    },
    {"content": "10", "role": "tool"},
]

FULL_INPUT_EXAMPLE: Dict[str, Any] = {
    "tool_definitions": TOOL_DEFINITIONS_EXAMPLE,
    "chat_payload": CHAT_EXAMPLE,
}


OUTPUT_EXAMPLE: List[Dict[str, Any]] = [
    {
        "content": "5 multiplied by 2 is 10.",
        "role": "assistant",
        "tool_calls": [],
    }
]

EXPLANATION_OF_THE_INPUT: str = f"""Please also note that 'input' includes the chat history under the 'chat payload' key and eventually the definitions of the tools available to the chat assistant.
 The 'chat payload' will include the list of exchanges between the user, the assistant, the system and eventually the tools.
Please note that when the assistant needs to perform a tool call its message content string can be empty (it puts the tool
to call along with parameters in the 'tool_calls' key. When the content is not empty and the 'tool_calls' key is empty, it usually means that the assistant is answwring the question because it does not need to perform further tool calls.
The 'role' key indicates the identity of the speaker : user, assistant, tool or system.
The example below shows a case of such chat where the user asked the system to multiply a number by two. :
BEGINNING OF THE EXAMPLE
BEGINNING OF THE INPUT:
{json.dumps(FULL_INPUT_EXAMPLE, indent=2)}
END OF THE INPUT
BEGINNING OF THE ACTUAL OUTPUT:
{json.dumps(OUTPUT_EXAMPLE, indent=2)}
END OF THE ACTUAL OUTPUT
END OF THE EXAMPLE
"""

CRITERIA_CORRECTNESS: str = f"""Determine if the 'actual output' is correct based on the 'expected output' if provided.
If the 'expected output' is missing or is empty, analyse the 'input' and the 'actual output' and determine if
 it is correct to the best of your knowledge. Do not hallucinate.
{EXPLANATION_OF_THE_INPUT}
"""

CRITERIA_GENERAL_STRUCTURE: str = """Evaluate the following aspects of the general structure and style of the 'actual output':
1. is the 'actual output' grammatically correctness?
2. how readable it is?
3. is the 'actual output' clear and informative?
"""
