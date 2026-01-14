from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

def run(ctx):
    """
    Scans the text for PII and anonymizes it.
    """
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    text_to_scan = ctx["txt"]

    # Analyze the text for PII entities
    analyzer_results = analyzer.analyze(text=text_to_scan, language='en')

    # Anonymize the detected entities
    anonymized_result = anonymizer.anonymize(
        text=text_to_scan,
        analyzer_results=analyzer_results
    )

    ctx["masked_scenarios"] = anonymized_result.text
