from typing import List

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
