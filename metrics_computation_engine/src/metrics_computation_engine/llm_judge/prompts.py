# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

judge_system_prompt = "You are a fair judge assistant tasked with grading a response."

tool_utilization_accuracy_prompt = """
    You are an evaluator tasked with assessing the Tool Utilization Accuracy made by an AI agent for a given query.

    Input: {tool_input}

    Tool Called: {tool_name}

    Tool Definition: {tool_definition}

    Output: {tool_output}

    Evaluation Task - Determine if the tool called was reasonable in response to the input. Further determine if the tool was able to provide output to address the needs in the input.

    Scoring Rubric:
    1: The tool call was completeley reasonable addressed the input.
    0: It is unclear why this tool was called and/or it failed to provide useful output.
    """

groundedness_prompt = """
    You are an evaluator of Groundedness Evaluate how well each response is grounded in verifiable data and avoids speculation or hallucinations.

    Here is the evaluation criteria to follow: (1) Is the response based on verifiable information from the provided data, knowledge bases, or tool outputs? (2) Does the response avoid speculation, hallucinations, or misleading statements? (3) Is the factual accuracy of the response maintained throughout the conversation?

    Scoring Rubric:
        1: Respone by the system is fully grounded by the context available through the tools and conversation.
        0: There are details in the response that are not grounded by the context available through tools and conversation.

    CONVERSATION {conversation}
"""
