"""Reproducible demo of the PawPal+ AI feature — no API key required.

The live chat needs an Anthropic API key, but the parts of the AI feature that
*guard* the model — retrieval (RAG), the constraint validator, and graceful
degradation — are deterministic and can be demonstrated with no key and no
network. Run this to produce the execution evidence shown in the README:

    python ai_demo.py
"""

from ai_assistant import (
    PawPalAssistant,
    SuggestedTask,
    _validate_suggestions,
    retrieve_guidelines,
    retrieve_memory,
)
from pawpal_system import Owner, Pet


def banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    # A hyper Labrador whose owner has 90 minutes a day.
    owner = Owner(name="Ishaan", minutes_available=90)
    rex = Pet(name="Rex", breed="labrador", health_conditions="")
    owner.add_pet(rex)

    # --- 1. RAG retrieval -------------------------------------------------
    banner("1 | RETRIEVAL (RAG): grounding advice in care_guidelines.md")
    query = "Rex seems really hyper lately, what should I do?"
    print(f"Input query : {query}")
    print(f"Pet profile : {rex.name}, {rex.breed}")
    print("Retrieved knowledge snippets:")
    for snippet in retrieve_guidelines(rex, query):
        print(f"  - {snippet}")

    # --- 2. Personalization / memory -------------------------------------
    banner("2 | MEMORY: personalization from what the owner told us")
    owner.memory.remember_preference("Rex hates dry kibble")
    owner.memory.add_message("user", "Rex hates dry kibble")
    recent, prefs = retrieve_memory(owner)
    print(f"Remembered preferences : {prefs}")
    print(f"Recent conversation    : {recent}")

    # --- 3. Guardrail validation (the agent's 'check' step) --------------
    banner("3 | GUARDRAIL: validating the AI's proposed tasks")
    over_budget = [
        SuggestedTask(description="Walk A", duration_minutes=40, priority="high",
                      start_time="08:00", frequency="daily", reason="exercise"),
        SuggestedTask(description="Walk B", duration_minutes=40, priority="high",
                      start_time="08:00", frequency="daily", reason="exercise"),
    ]
    print("Proposed tasks: two 40-min walks, both at 08:00 (owner has 90 min).")
    problems = _validate_suggestions(owner, rex, over_budget)
    print("Guardrail found these problems:")
    for p in problems:
        print(f"  ! {p}")

    fixed = [
        SuggestedTask(description="Morning walk", duration_minutes=35, priority="high",
                      start_time="08:00", frequency="daily", reason="exercise"),
        SuggestedTask(description="Evening walk", duration_minutes=35, priority="high",
                      start_time="18:00", frequency="daily", reason="exercise"),
    ]
    print("\nRevised tasks: 35-min walks at 08:00 and 18:00 (total 70 min).")
    problems = _validate_suggestions(owner, rex, fixed)
    print(f"Guardrail result: {'PASS - no problems' if not problems else problems}")

    # --- 4. Graceful degradation (no API key) ----------------------------
    banner("4 | GUARDRAIL: graceful degradation with no API key")
    assistant = PawPalAssistant()
    print(f"API key configured? {assistant.is_configured()}")
    result = assistant.chat(owner, rex, "any ideas?")
    print(f"chat() ok flag    : {result.ok}")
    print(f"chat() message    : {result.message}")


if __name__ == "__main__":
    main()
