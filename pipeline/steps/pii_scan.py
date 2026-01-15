"""
This module implements the PII (Personally Identifiable Information) Masking step of the QA pipeline.
It utilizes the Presidio library to detect sensitive information like passwords and email addresses
within the input text and then replaces them with masked placeholders to protect privacy.
"""
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.predefined_recognizers import EmailRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from typing import List, Any

def _dedupe_results(results: List[Any]) -> List[Any]:
    """
    Removes duplicate PII detection results based on their start, end, and entity type.
    This is necessary because Presidio's analyzer might return overlapping or identical
    results for the same detected entity.

    Args:
        results (List[Any]): A list of PII detection results from Presidio's AnalyzerEngine.
                             Each result object is expected to have 'start', 'end', and 'entity_type' attributes.

    Returns:
        List[Any]: A new list containing only unique PII detection results.
    """
    seen = set()
    unique = []
    for r in results:
        key = (r.start, r.end, r.entity_type)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def run(ctx: dict) -> None:
    """
    Executes the PII Scan and Masking step. This function analyzes the input text
    (`ctx["txt"]`) for Personally Identifiable Information (PII), specifically
    passwords and email addresses, using Presidio. Detected entities are then
    replaced with masked placeholders. The processed text is stored as `masked_scenarios` in the context.

    Args:
        ctx (dict): The pipeline context dictionary, which must contain:
                    - 'txt' (str): The raw input text (e.g., checklist) to be scanned for PII.
    """

    # Define a regex pattern for potential passwords.
    # The pattern looks for keywords like 'password', 'secret', 'token', etc.,
    # followed by a colon or equals sign, and then non-whitespace characters.
    password_pattern = (
        r"(?i)"  # Case-insensitive matching
        r"(password|pass|pwd|pswd|passwd|secret|token|api[_-]?key|apikey|auth|authorization)"
        r"\s*[:=]\s*"  # Matches space, colon/equals, space
        r"[^\s,;]+"  # Matches any non-whitespace, non-comma, non-semicolon characters
    )

    # Define context words that might appear near a password to improve detection accuracy.
    context_words = [
        "password", "pass", "pwd", "pswd", "passwd",
        "secret", "token", "api_key", "apikey",
        "auth", "authorization"
    ]

    # Create a custom PatternRecognizer for PASSWORD entities using the defined regex and context words.
    password_recognizer = PatternRecognizer(
        supported_entity="PASSWORD",
        patterns=[Pattern(name="credential_pattern", regex=password_pattern, score=0.95)],
        context=context_words,
    )

    # Initialize Presidio AnalyzerEngine and add custom/predefined recognizers.
    analyzer = AnalyzerEngine()
    analyzer.registry.add_recognizer(password_recognizer)
    analyzer.registry.add_recognizer(EmailRecognizer()) # Use Presidio's built-in email recognizer

    # Initialize Presidio AnonymizerEngine for replacing detected PII.
    anonymizer = AnonymizerEngine()
    text_to_scan = ctx.get("txt", "")

    all_results = [] # Collect all PII detection results

    # --- Scan for PASSWORD entities ---
    # Analyze text for PASSWORD in English only, with a minimum score of 0.5 for confidence.
    results = analyzer.analyze(
        text=text_to_scan,
        language="en",
        entities=["PASSWORD"],
        score_threshold=0.5
    )
    all_results.extend(results)

    # --- Scan for EMAIL_ADDRESS entities ---
    # Analyze text for EMAIL_ADDRESS in English only, with a minimum score of 0.5.
    results = analyzer.analyze(
        text=text_to_scan,
        language="en",
        entities=["EMAIL_ADDRESS"],
        score_threshold=0.5
    )
    all_results.extend(results)

    # Deduplicate results as the analyzer might return overlapping or redundant detections.
    analyzer_results = _dedupe_results(all_results)

    # If any PII is detected, proceed with anonymization.
    if analyzer_results:
        # Define how each entity type should be anonymized (replaced with a placeholder).
        anonymized_result = anonymizer.anonymize(
            text=text_to_scan,
            analyzer_results=analyzer_results,
            operators={
                "PASSWORD": OperatorConfig(operator_name="replace", params={"new_value": "[PASSWORD_MASKED]"}),
                "EMAIL_ADDRESS": OperatorConfig(operator_name="replace", params={"new_value": "[EMAIL_MASKED]"}),
            },
        )
        ctx["masked_scenarios"] = anonymized_result.text
        print("🔒 PII detected and masked successfully.")
    else:
        # If no PII is found, the original text is used.
        ctx["masked_scenarios"] = text_to_scan
        print("✅ No PII detected. Scenarios not modified.")