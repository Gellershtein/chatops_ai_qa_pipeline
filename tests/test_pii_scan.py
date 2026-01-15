
"""
This module contains unit tests for the PII (Personally Identifiable Information) scanning
and masking functionality implemented in `pipeline.steps.pii_scan`.
"""
from pipeline.steps.pii_scan import run

def test_pii_scan_with_email():
    """
    Tests the PII scanner's ability to detect and mask an email address.
    """
    ctx = {"txt": "My email is test@example.com"}
    run(ctx)
    assert ctx["masked_scenarios"] == "My email is [EMAIL_MASKED]"

def test_pii_scan_with_password():
    """
    Tests the PII scanner's ability to detect and mask a password.
    (Note: pii_scan is configured to mask PASSWORD, not PHONE_NUMBER by default)
    """
    ctx = {"txt": "My password is secret123"}
    run(ctx)
    assert ctx["masked_scenarios"] == "My password is [PASSWORD_MASKED]"

def test_pii_scan_with_no_pii():
    """
    Tests the PII scanner's behavior when no PII is present in the text.
    """
    ctx = {"txt": "This is a normal sentence."}
    run(ctx)
    assert ctx["masked_scenarios"] == "This is a normal sentence."

def test_pii_scan_with_multiple_pii():
    """
    Tests the PII scanner's ability to detect and mask multiple types of PII
    (email and password) in a single text.
    """
    ctx = {"txt": "My email is test@example.com and my password is secret123"}
    run(ctx)
    assert ctx["masked_scenarios"] == "My email is [EMAIL_MASKED] and my password is [PASSWORD_MASKED]"
