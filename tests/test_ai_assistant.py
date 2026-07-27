"""Reliability tests for the PawPal+ AI assistant layer.

These deliberately test everything EXCEPT the live model call, so they run with
no API key and no network — a grader can reproduce them instantly. They cover
the three things the AI feature depends on being correct:

  * retrieval (RAG) surfaces the right guidelines,
  * the guardrail validator catches over-budget / conflicting suggestions,
  * memory persists and the assistant degrades gracefully with no key.
"""

import ai_assistant
from ai_assistant import (
    ChatResult,
    PawPalAssistant,
    SuggestedTask,
    _validate_suggestions,
    load_memory,
    retrieve_guidelines,
    retrieve_memory,
    save_memory,
)
from pawpal_system import Memory, Owner, Pet, Task


# --- RAG retrieval ---------------------------------------------------------
def test_retrieval_matches_pet_by_tag():
    """A hyper Labrador should retrieve the high-energy exercise guideline."""
    pet = Pet(name="Rex", breed="labrador")
    snippets = retrieve_guidelines(pet, "she seems hyper", k=3)

    assert snippets, "expected at least one matching guideline"
    assert any("high-energy" in s.lower() or "exercise" in s.lower() for s in snippets)


def test_retrieval_respects_k_limit():
    """Retrieval never returns more than k snippets."""
    pet = Pet(name="Rex", breed="dog", health_conditions="overweight")
    snippets = retrieve_guidelines(pet, "food and grooming and meds", k=2)

    assert len(snippets) <= 2


def test_retrieval_handles_missing_file():
    """A missing knowledge base returns [] instead of crashing."""
    pet = Pet(name="Rex", breed="dog")
    assert retrieve_guidelines(pet, "walk", path="does_not_exist.md") == []


# --- Memory ----------------------------------------------------------------
def test_memory_dedupes_preferences():
    """The same preference stored twice should only be kept once."""
    memory = Memory()
    memory.remember_preference("Mochi hates dry food")
    memory.remember_preference("Mochi hates dry food")

    assert memory.preferences == ["Mochi hates dry food"]


def test_memory_recent_returns_last_n():
    """recent(n) returns only the last n messages."""
    memory = Memory()
    for i in range(10):
        memory.add_message("user", f"message {i}")

    recent = memory.recent(3)
    assert len(recent) == 3
    assert recent[-1].text == "message 9"


def test_memory_round_trips_to_dict():
    """to_dict()/from_dict() should preserve messages and preferences."""
    memory = Memory()
    memory.add_message("user", "hi")
    memory.remember_preference("prefers morning walks")

    restored = Memory.from_dict(memory.to_dict())

    assert restored.messages[0].text == "hi"
    assert restored.preferences == ["prefers morning walks"]


def test_memory_persists_to_disk(tmp_path):
    """save_memory then load_memory should return equivalent memory."""
    path = str(tmp_path / "mem.json")
    memory = Memory()
    memory.add_message("assistant", "welcome back")
    memory.remember_preference("Rex is hyper")

    save_memory(memory, path)
    loaded = load_memory(path)

    assert loaded.messages[0].text == "welcome back"
    assert loaded.preferences == ["Rex is hyper"]


def test_load_memory_missing_file_returns_empty(tmp_path):
    """Loading when no file exists yields an empty Memory, not an error."""
    loaded = load_memory(str(tmp_path / "nope.json"))
    assert loaded.messages == [] and loaded.preferences == []


# --- Guardrail validation (the agentic 'check' step) -----------------------
def _owner_with_budget(minutes: int) -> tuple[Owner, Pet]:
    owner = Owner(name="Sam", minutes_available=minutes)
    pet = Pet(name="Rex", breed="dog")
    owner.add_pet(pet)
    return owner, pet


def test_validation_flags_over_budget():
    """Suggestions exceeding the time budget must be reported."""
    owner, pet = _owner_with_budget(30)
    suggestions = [
        SuggestedTask(
            description="Long walk", duration_minutes=45, priority="high",
            start_time="08:00", frequency="daily", reason="exercise",
        )
    ]

    problems = _validate_suggestions(owner, pet, suggestions)
    assert any("minutes" in p for p in problems)


def test_validation_flags_conflict_with_existing_task():
    """A suggestion at a time already taken must be flagged as a clash."""
    owner, pet = _owner_with_budget(120)
    pet.add_task(Task("Feed", duration_minutes=10, start_time="08:00"))
    suggestions = [
        SuggestedTask(
            description="Walk", duration_minutes=20, priority="high",
            start_time="08:00", frequency="daily", reason="exercise",
        )
    ]

    problems = _validate_suggestions(owner, pet, suggestions)
    assert any("08:00" in p for p in problems)


def test_validation_passes_clean_suggestions():
    """Suggestions that fit the budget and have no clash produce no problems."""
    owner, pet = _owner_with_budget(120)
    pet.add_task(Task("Feed", duration_minutes=10, start_time="08:00"))
    suggestions = [
        SuggestedTask(
            description="Walk", duration_minutes=20, priority="high",
            start_time="17:00", frequency="daily", reason="exercise",
        )
    ]

    assert _validate_suggestions(owner, pet, suggestions) == []


# --- Graceful degradation (guardrail) --------------------------------------
def test_chat_without_api_key_degrades_gracefully(monkeypatch, tmp_path):
    """With no API key, chat() returns ok=False and a helpful message, no crash."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assistant = PawPalAssistant(memory_path=str(tmp_path / "mem.json"))
    owner, pet = _owner_with_budget(60)

    result = assistant.chat(owner, pet, "any ideas?")

    assert isinstance(result, ChatResult)
    assert result.ok is False
    assert "api key" in result.message.lower()
