from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.predefined_recognizers import EmailRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


def _dedupe_results(results):
    seen = set()
    unique = []
    for r in results:
        key = (r.start, r.end, r.entity_type)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def run(ctx):
    """
    Scan text for credentials (PASSWORD) and EMAIL_ADDRESS in English only.
    """

    password_pattern = (
        r"(?i)"
        r"(password|pass|pwd|pswd|passwd|secret|token|api[_-]?key|apikey|auth|authorization)"
        r"\s*[:=]\s*"
        r"[^\s,;]+"
    )

    context = [
        "password", "pass", "pwd", "pswd", "passwd",
        "secret", "token", "api_key", "apikey",
        "auth", "authorization"
    ]

    password_recognizer = PatternRecognizer(
        supported_entity="PASSWORD",
        patterns=[Pattern(name="credential_pattern", regex=password_pattern, score=0.95)],
        context=context,
    )

    analyzer = AnalyzerEngine()
    analyzer.registry.add_recognizer(password_recognizer)
    analyzer.registry.add_recognizer(EmailRecognizer())

    anonymizer = AnonymizerEngine()
    text_to_scan = ctx.get("txt", "")

    all_results = []

    # Scan for PASSWORD in English only
    results = analyzer.analyze(
        text=text_to_scan,
        language="en",
        entities=["PASSWORD"],
    )
    all_results.extend(results)

    # Scan for EMAIL_ADDRESS in English only
    results = analyzer.analyze(
        text=text_to_scan,
        language="en",
        entities=["EMAIL_ADDRESS"],
    )
    all_results.extend(results)

    analyzer_results = _dedupe_results(all_results)

    if analyzer_results:
        anonymized_result = anonymizer.anonymize(
            text=text_to_scan,
            analyzer_results=analyzer_results,
            operators={
                "PASSWORD": OperatorConfig(operator_name="replace", params={"new_value": "[PASSWORD_MASKED]"}),
                "EMAIL_ADDRESS": OperatorConfig(operator_name="replace", params={"new_value": "[EMAIL_MASKED]"}),
            },
        )
        ctx["masked_scenarios"] = anonymized_result.text
    else:
        ctx["masked_scenarios"] = text_to_scan