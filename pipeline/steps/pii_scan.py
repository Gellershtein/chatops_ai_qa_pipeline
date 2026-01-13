
import re

EMAIL = re.compile(r"[\w\.-]+@[\w\.-]+")
PASSWORD = re.compile(r'(password|pass|pwd)\s*[:=]\s*[\'"]?(\S+)[\'"]?', re.IGNORECASE)

def run(ctx):
    masked = ctx["scenarios"]
    masked = EMAIL.sub("[EMAIL_MASKED]", masked)
    masked = PASSWORD.sub(r'\1 [PASSWORD_MASKED]', masked)
    ctx["masked_scenarios"] = masked
