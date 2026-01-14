from pipeline.steps.pii_scan import run

def test_pii_scan_with_email():
    ctx = {"txt": "My email is test@example.com"}
    run(ctx)
    assert ctx["masked_scenarios"] == "My email is <EMAIL_ADDRESS>"

def test_pii_scan_with_us_phone_number():
    ctx = {"txt": "My phone number is (123) 456-7890"}
    run(ctx)
    assert ctx["masked_scenarios"] == "My phone number is <PHONE_NUMBER>"

def test_pii_scan_with_no_pii():
    ctx = {"txt": "This is a normal sentence."}
    run(ctx)
    assert ctx["masked_scenarios"] == "This is a normal sentence."

def test_pii_scan_with_multiple_pii():
    ctx = {"txt": "My email is test@example.com and my phone is (123) 456-7890"}
    run(ctx)
    assert ctx["masked_scenarios"] == "My email is <EMAIL_ADDRESS> and my phone is <PHONE_NUMBER>"
