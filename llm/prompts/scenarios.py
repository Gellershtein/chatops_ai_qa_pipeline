"""
This module defines the Large Language Model (LLM) prompt used for generating
test scenarios based on a provided checklist for login functionality.
"""

PROMPT = """
# Test Scenario Generation Prompt for LLM

You are a senior QA engineer. Your primary task is to generate comprehensive
test scenarios specifically for **login functionality**.

## Rules for Scenario Generation:
-   **Use only information from the provided `Checklist`**. Do not introduce external details.
-   **Do not invent functionality** that is not explicitly mentioned in the checklist.
-   **Output ONLY test scenarios**. No conversational text, explanations, or extraneous information.
-   **No markdown formatting** in the output scenarios themselves.
-   Present scenarios in a **human-like format**, not a BDD (Behavior-Driven Development) format.
-   Ensure a **clear and logical structure** for all generated scenarios.

---

**Checklist (provided for scenario generation):**
{checklist}
"""
