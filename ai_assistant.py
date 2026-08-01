"""PawPal+ AI assistant layer.

This module is the AI brain that sits on top of the rule-based logic in
pawpal_system.py. It ties together three things the plain scheduler can't do:

1. RETRIEVAL (RAG): before answering, it pulls relevant snippets from two
   sources — the static care knowledge base (care_guidelines.md) and the
   owner's own memory (past chat + saved preferences). Those snippets go into
   the prompt so advice is grounded and personalized, not made up.

2. AGENTIC LOOP (plan -> check -> revise): when the AI proposes care tasks, we
   validate them against the SAME constraints the Scheduler enforces (the
   owner's time budget and scheduling conflicts). If a check fails, we hand the
   specific problem back to the model and let it revise its own suggestion.

3. GUARDRAILS: a scoped system prompt, structured/validated JSON output, error
   handling with logging, and graceful degradation when no API key is set (the
   app keeps working; the chat just explains how to enable itself).

Everything the model returns is validated against a Pydantic schema, so the
rest of the app always gets well-formed data or a clear, logged failure.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from pawpal_system import Memory, Owner, Pet, Scheduler, Task

# Load ANTHROPIC_API_KEY (and anything else) from a local .env file if present.
load_dotenv()

# --- Configuration ---------------------------------------------------------
MODEL = "claude-opus-4-8"          # the Claude model the assistant talks to
MAX_REVISIONS = 3                  # how many times the agent may fix its own plan
MEMORY_FILE = "pawpal_memory.json" # where per-owner memory is persisted
GUIDELINES_FILE = "care_guidelines.md"  # the RAG knowledge base
TOP_K_GUIDELINES = 3               # how many knowledge snippets to retrieve

# When PAWPAL_DEMO_MODE is set (see .env), the assistant answers WITHOUT calling
# Claude — useful when you have no API credits. The real retrieval (RAG) step and
# the real plan->check->revise validation loop still run; only the language-model
# call is replaced by a deterministic stand-in. Replies are clearly labelled.
DEMO_ENV_VAR = "PAWPAL_DEMO_MODE"
DEMO_NOTE = "\n\n_(Offline demo reply — no AI credits used. Add credits and unset PAWPAL_DEMO_MODE for the full model.)_"
# Words that should trigger a "see a vet" nudge in the offline reply.
_SYMPTOM_WORDS = (
    "sick", "vomit", "throw up", "not eating", "won't eat", "lethargic",
    "limp", "blood", "diarrhea", "hurt", "pain", "injured", "seizure", "cough",
)

# --- Logging ---------------------------------------------------------------
# Everything the assistant does (retrieval, API calls, validation, failures)
# is logged both to the console and to a file, so behaviour is auditable.
logger = logging.getLogger("pawpal.assistant")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _file = logging.FileHandler("pawpal_assistant.log", encoding="utf-8")
    _file.setFormatter(_fmt)
    logger.addHandler(_file)
    _console = logging.StreamHandler()
    _console.setFormatter(_fmt)
    logger.addHandler(_console)


# --- Structured output schema ----------------------------------------------
# The model is forced to return JSON matching these shapes. Validation happens
# at the SDK layer, so a malformed response is retried automatically rather
# than crashing our code.
class SuggestedTask(BaseModel):
    """One care task the assistant proposes the owner add."""

    description: str = Field(description="Short task name, e.g. 'Evening walk'.")
    duration_minutes: int = Field(description="Estimated minutes the task takes.")
    priority: str = Field(description="One of: low, medium, high.")
    start_time: str = Field(description="Clock time 'HH:MM' (24h), or '' if flexible.")
    frequency: str = Field(description="One of: once, daily, weekly.")
    reason: str = Field(description="Why this is suggested (tie it to the pet/guidelines).")


class AssistantReply(BaseModel):
    """The full structured reply from the assistant for one chat turn."""

    message: str = Field(description="Friendly reply shown to the owner.")
    suggested_tasks: list[SuggestedTask] = Field(
        default_factory=list,
        description="Tasks the owner can add. Empty unless concretely proposing tasks.",
    )
    learned_preferences: list[str] = Field(
        default_factory=list,
        description="Durable facts the owner stated to remember, e.g. 'Mochi hates dry food'.",
    )


@dataclass
class ChatResult:
    """What chat() hands back to the UI for one turn."""

    message: str
    suggested_tasks: list[SuggestedTask] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # constraint issues we couldn't fully fix
    revisions: int = 0                                  # how many self-corrections it took
    ok: bool = True                                     # False when the AI call failed
    demo: bool = False                                  # True when produced offline (no model call)


# --- RAG: retrieval ---------------------------------------------------------
def _parse_guidelines(path: str) -> list[dict]:
    """Read care_guidelines.md into a list of {title, tags, body} entries.

    Each entry in the file starts with a '### Title' heading, followed by a
    'Tags: a, b, c' line, followed by the body text. We split on the headings
    and pull those three pieces out.
    """
    text = Path(path).read_text(encoding="utf-8")
    entries: list[dict] = []
    # Split on '### ' headings; the first chunk is the file's intro, so skip it.
    for chunk in text.split("### ")[1:]:
        lines = chunk.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        tags: list[str] = []
        body_lines: list[str] = []
        for line in lines[1:]:
            if line.lower().startswith("tags:"):
                tags = [t.strip().lower() for t in line[len("tags:"):].split(",")]
            else:
                body_lines.append(line)
        entries.append(
            {"title": title, "tags": tags, "body": " ".join(body_lines).strip()}
        )
    return entries


def retrieve_guidelines(
    pet: Pet | None, query: str, path: str = GUIDELINES_FILE, k: int = TOP_K_GUIDELINES
) -> list[str]:
    """Return the k most relevant care-guideline snippets (RAG step).

    Relevance is a simple keyword overlap: we build a bag of words from the
    pet's species/breed/health conditions plus the owner's question, then score
    each entry by how many of its tags appear in that bag. Entries with at
    least one tag hit are returned, best first. This is deliberately lightweight
    (no embeddings/vector DB) so the project runs anywhere with no extra setup.
    """
    try:
        entries = _parse_guidelines(path)
    except FileNotFoundError:
        logger.warning("Guidelines file %s not found; skipping retrieval.", path)
        return []

    # We score tags against two separate texts: the pet's own attributes
    # (breed / health conditions) and the owner's question. A tag that matches
    # a PET attribute is worth more than one that only matches a query word, so
    # a dog's question won't surface a cat guideline just because they share a
    # generic tag like "hyper".
    query_text = query.lower()
    attr_text = ""
    if pet is not None:
        attr_text = " ".join([pet.name, pet.breed, pet.health_conditions]).lower()

    scored: list[tuple[int, int, str]] = []  # (attr_hits, weighted_score, text)
    for entry in entries:
        attr_hits = sum(1 for tag in entry["tags"] if attr_text and tag in attr_text)
        query_hits = sum(1 for tag in entry["tags"] if tag in query_text)
        if attr_hits or query_hits:
            score = attr_hits * 2 + query_hits
            scored.append((attr_hits, score, f"{entry['title']}: {entry['body']}"))

    # Prefer entries grounded in the pet's own attributes; fall back to plain
    # query matches only when nothing matched the pet directly.
    grounded = [s for s in scored if s[0] > 0]
    pool = grounded if grounded else scored
    pool.sort(key=lambda s: s[1], reverse=True)

    snippets = [text for _, _, text in pool[:k]]
    logger.info("Retrieved %d guideline snippet(s) for query.", len(snippets))
    return snippets


def retrieve_memory(owner: Owner, n_messages: int = 6) -> tuple[list[str], list[str]]:
    """Return (recent chat lines, saved preferences) for the prompt (RAG step).

    The second half of retrieval: instead of a knowledge base, this pulls from
    the owner's own history so the assistant's advice reflects past chats.
    """
    recent = [f"{m.role}: {m.text}" for m in owner.memory.recent(n_messages)]
    prefs = list(owner.memory.preferences)
    logger.info(
        "Loaded %d memory message(s) and %d preference(s).", len(recent), len(prefs)
    )
    return recent, prefs


# --- Memory persistence -----------------------------------------------------
def load_memory(path: str = MEMORY_FILE) -> Memory:
    """Load persisted memory from JSON, or an empty Memory if none exists."""
    import json

    file = Path(path)
    if not file.exists():
        return Memory()
    try:
        return Memory.from_dict(json.loads(file.read_text(encoding="utf-8")))
    except (ValueError, OSError) as err:
        logger.warning("Could not load memory (%s); starting fresh.", err)
        return Memory()


def save_memory(memory: Memory, path: str = MEMORY_FILE) -> None:
    """Persist memory to JSON so personalization survives app restarts."""
    import json

    try:
        Path(path).write_text(
            json.dumps(memory.to_dict(), indent=2), encoding="utf-8"
        )
    except OSError as err:
        logger.warning("Could not save memory (%s).", err)


# --- The assistant ----------------------------------------------------------
SYSTEM_PROMPT = """You are PawPal+, a warm, practical pet-care assistant inside \
a pet-care planning app. You help an owner care for their pet: suggesting or \
swapping care tasks, advising on food and routines, and helping when a pet \
seems unwell.

Follow these rules strictly (they are your guardrails):
- STAY IN SCOPE: only discuss pet care. Politely decline anything else.
- YOU ARE NOT A VET: for serious, worsening, or persistent symptoms, tell the \
owner to contact a veterinarian. You may still suggest gentle, safe adjustments.
- USE THE PROVIDED CONTEXT: base advice on the care guidelines and the owner's \
remembered preferences given below. Never contradict a stated preference \
(e.g. if a food is disliked, do not recommend it).
- RESPECT THE TIME BUDGET: do not suggest tasks whose durations total more than \
the owner's available minutes, and never schedule two tasks at the same start_time.
- SUGGEST TASKS ONLY WHEN CONCRETE: fill suggested_tasks only when you are \
actually proposing tasks to add; otherwise leave it empty and just reply.
- REMEMBER: put any durable fact the owner states (preferences, dislikes, the \
pet's temperament) into learned_preferences so future chats can use it."""


def _pet_profile(pet: Pet | None) -> str:
    """Format a pet's details for the prompt."""
    if pet is None:
        return "No specific pet selected."
    parts = [f"name={pet.name}", f"breed/species={pet.breed or 'unknown'}"]
    if pet.age:
        parts.append(f"age={pet.age}")
    if pet.weight:
        parts.append(f"weight={pet.weight}")
    if pet.health_conditions:
        parts.append(f"health_conditions={pet.health_conditions}")
    existing = [
        f"{t.description} @ {t.start_time or 'flexible'} ({t.priority}, {t.duration_minutes}m)"
        for t in pet.pending_tasks()
    ]
    parts.append("current_tasks=[" + "; ".join(existing) + "]")
    return ", ".join(parts)


def _validate_suggestions(
    owner: Owner, pet: Pet | None, suggestions: list[SuggestedTask]
) -> list[str]:
    """Check the AI's suggestions against the Scheduler's real constraints.

    This is the 'check its own work' step of the agentic loop, and it reuses
    the exact rules the rest of the app enforces:
      - time budget: suggested minutes must fit the owner's available minutes
      - conflicts: Scheduler.detect_conflicts() must not flag a clash caused by
        a newly suggested start_time

    Returns a list of human-readable problem strings (empty = all good).
    """
    problems: list[str] = []

    # 1. Time budget.
    total = sum(s.duration_minutes for s in suggestions)
    if owner.minutes_available and total > owner.minutes_available:
        problems.append(
            f"Suggested tasks total {total} minutes, but only "
            f"{owner.minutes_available} minutes are available."
        )

    # 2. Conflicts — build throwaway Task objects and reuse the Scheduler's
    #    own conflict detector on the existing tasks + the suggestions.
    suggestion_tasks: list[Task] = []
    for s in suggestions:
        task = Task(
            description=s.description,
            duration_minutes=s.duration_minutes,
            priority=s.priority,
            frequency=s.frequency,
            start_time=s.start_time,
        )
        task.pet = pet  # so the warning can name the pet
        suggestion_tasks.append(task)

    suggested_times = {t.start_time for t in suggestion_tasks if t.start_time}
    if suggested_times:
        scheduler = Scheduler(owner=owner)
        combined = owner.get_all_tasks() + suggestion_tasks
        for warning in scheduler.detect_conflicts(combined):
            # Only surface a clash if it involves a time we're newly suggesting;
            # pre-existing clashes aren't the AI's fault to fix here.
            if any(f"at {t}:" in warning for t in suggested_times):
                problems.append(warning.replace("WARNING: ", ""))

    if problems:
        logger.info("Validation found %d problem(s) in suggestions.", len(problems))
    return problems


# --- Offline demo responder -------------------------------------------------
# These build a deterministic reply when PAWPAL_DEMO_MODE is on. They stand in
# ONLY for the language-model call — retrieval and validation still run for real,
# so the whole pipeline (RAG -> plan -> check -> revise) is genuinely exercised.
def _demo_suggestion(
    pet: Pet | None, user_message: str, guidelines: list[str]
) -> SuggestedTask:
    """Pick one sensible care task from the message keywords + top guideline."""
    msg = user_message.lower()
    ground = guidelines[0].split(":")[0] if guidelines else "general care guidelines"
    if any(w in msg for w in ("hyper", "energy", "bored", "restless", "destructive", "anxious")):
        desc, dur = "Enrichment play session", 20
    elif any(w in msg for w in ("food", "eat", "diet", "meal", "hungry", "treat", "weight")):
        desc, dur = "Portion-controlled feeding", 10
    elif any(w in msg for w in ("walk", "exercise", "outside", "potty")):
        desc, dur = "Structured walk", 30
    else:
        desc, dur = "Daily wellness check-in", 15
    # Prefer a start time this pet isn't already using; fall back to flexible.
    used = {t.start_time for t in (pet.pending_tasks() if pet else []) if t.start_time}
    start = next((c for c in ("09:00", "12:00", "15:00", "18:00") if c not in used), "")
    return SuggestedTask(
        description=desc,
        duration_minutes=dur,
        priority="medium",
        start_time=start,
        frequency="daily",
        reason=f"Grounded in {ground}.",
    )


def _demo_fix(owner: Owner, suggestions: list[SuggestedTask]) -> None:
    """Deterministically resolve validator problems, in place.

    Clearing the fixed start_time makes a task 'flexible', which can never clash;
    capping duration to a per-task share of the budget keeps the total in range.
    This is the offline stand-in for the model 'revising its own plan'.
    """
    for s in suggestions:
        s.start_time = ""  # flexible time can never conflict
    if owner.minutes_available:
        budget_each = max(5, owner.minutes_available // max(1, len(suggestions)))
        for s in suggestions:
            s.duration_minutes = min(s.duration_minutes, budget_each)


def _demo_message(
    pet: Pet | None, user_message: str, guidelines: list[str],
    prefs: list[str], revisions: int,
) -> str:
    """Compose the friendly offline reply text, grounded in what was retrieved."""
    name = pet.name if pet else "your pet"
    parts = [f"Here's a safe starting idea for {name}, based on the care guidelines."]
    if guidelines:
        parts.append(f"I drew on: {guidelines[0].split(':')[0]}.")
    if prefs:
        parts.append(f"I kept your {len(prefs)} saved preference(s) in mind.")
    if revisions:
        parts.append(
            f"I adjusted the plan {revisions} time(s) to fit your time budget "
            "and avoid clashes."
        )
    if any(w in user_message.lower() for w in _SYMPTOM_WORDS):
        parts.append(
            "Since that could be a health concern, please check with a vet if it "
            "continues or worsens — I'm not a substitute for one."
        )
    parts.append("Add the suggested task below if it looks good.")
    return " ".join(parts) + DEMO_NOTE


def _demo_learned(user_message: str) -> list[str]:
    """Capture a durable preference offline when the owner clearly states one."""
    msg = user_message.lower()
    if any(w in msg for w in ("hate", "dislike", "allergic", "loves", "prefers")):
        return [user_message.strip()]
    return []


class PawPalAssistant:
    """Wraps the Claude client with retrieval, the agentic loop, and guardrails."""

    def __init__(self, memory_path: str = MEMORY_FILE) -> None:
        self.memory_path = memory_path
        self._client = None  # created lazily so import never fails without a key

    def is_configured(self) -> bool:
        """True if an API key is available to talk to Claude."""
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def demo_mode(self) -> bool:
        """True when offline demo mode is enabled via the PAWPAL_DEMO_MODE env var.

        In demo mode the assistant never calls Claude; it answers with a
        deterministic stand-in so the app is fully usable without API credits.
        """
        return os.environ.get(DEMO_ENV_VAR, "").strip().lower() in (
            "1", "true", "yes", "on",
        )

    def _demo_turn(
        self, owner: Owner, pet: Pet | None, user_message: str,
        guidelines: list[str], prefs: list[str],
    ) -> tuple[AssistantReply, int, list[str]]:
        """Run one turn offline: real validate -> deterministic revise loop.

        Mirrors the live plan->check->revise loop, but the 'plan' and each
        'revise' come from _demo_suggestion/_demo_fix instead of the model.
        Returns (reply, revisions, unresolved_problems).
        """
        suggestions = [_demo_suggestion(pet, user_message, guidelines)]

        revisions = 0
        problems = _validate_suggestions(owner, pet, suggestions)
        while problems and revisions < MAX_REVISIONS:
            revisions += 1
            logger.info(
                "Demo revision %d: adjusting suggestion to satisfy constraints.",
                revisions,
            )
            _demo_fix(owner, suggestions)
            problems = _validate_suggestions(owner, pet, suggestions)

        reply = AssistantReply(
            message=_demo_message(pet, user_message, guidelines, prefs, revisions),
            suggested_tasks=suggestions,
            learned_preferences=_demo_learned(user_message),
        )
        return reply, revisions, problems

    def _get_client(self):
        """Return a cached Anthropic client, importing the SDK lazily."""
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def _complete(self, messages: list[dict]) -> AssistantReply:
        """One validated call to Claude. Returns a parsed AssistantReply."""
        client = self._get_client()
        response = client.messages.parse(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=messages,
            output_format=AssistantReply,
        )
        return response.parsed_output

    def chat(self, owner: Owner, pet: Pet | None, user_message: str) -> ChatResult:
        """Handle one chat turn end to end (retrieve -> plan -> check -> revise).

        On any API failure this returns a ChatResult with ok=False and a clear
        message rather than raising, so the UI never crashes.
        """
        demo = self.demo_mode()

        # Guardrail: no key AND not in demo mode -> explain, don't crash.
        if not demo and not self.is_configured():
            return ChatResult(
                message=(
                    "The AI assistant isn't set up yet. Add your Anthropic API key "
                    "to a `.env` file (see `.env.example`) and restart to enable chat. "
                    "The rest of PawPal+ works without it."
                ),
                ok=False,
            )

        # 1. RETRIEVE context (RAG): knowledge base + this owner's memory.
        #    This runs in both live and demo mode — retrieval is real either way.
        guidelines = retrieve_guidelines(pet, user_message)
        recent, prefs = retrieve_memory(owner)

        # 2 + 3. PLAN -> CHECK -> REVISE.
        if demo:
            # Offline path: deterministic stand-in for the model, same loop shape.
            reply, revisions, problems = self._demo_turn(
                owner, pet, user_message, guidelines, prefs
            )
        else:
            context = (
                f"Owner: {owner.name}. Minutes available today: {owner.minutes_available}.\n"
                f"Pet profile: {_pet_profile(pet)}\n"
                f"Care guidelines (retrieved):\n- "
                + ("\n- ".join(guidelines) if guidelines else "(none matched)")
                + "\nRemembered preferences:\n- "
                + ("\n- ".join(prefs) if prefs else "(none yet)")
                + "\nRecent conversation:\n"
                + ("\n".join(recent) if recent else "(this is the first message)")
            )

            messages = [
                {"role": "user", "content": f"{context}\n\nOwner says: {user_message}"}
            ]

            # 2. PLAN: first attempt.
            try:
                reply = self._complete(messages)
            except Exception as err:  # noqa: BLE001 - any SDK/API error is surfaced safely
                logger.error("AI call failed: %s", err)
                return ChatResult(
                    message=(
                        "Sorry — I couldn't reach the AI service just now. "
                        "Please check your connection/API key and try again. "
                        "(Tip: set PAWPAL_DEMO_MODE=true in .env to run offline "
                        "without API credits.)"
                    ),
                    ok=False,
                )

            # 3. CHECK -> REVISE loop: fix the AI's own plan against real constraints.
            revisions = 0
            problems = _validate_suggestions(owner, pet, reply.suggested_tasks)
            while problems and revisions < MAX_REVISIONS:
                revisions += 1
                logger.info("Revision %d: asking the model to fix its suggestions.", revisions)
                messages.append(
                    {"role": "assistant", "content": reply.model_dump_json()}
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your suggested_tasks failed these checks:\n- "
                            + "\n- ".join(problems)
                            + "\nRevise suggested_tasks so they fit the time budget and "
                            "have no time clashes. Keep your message friendly and brief."
                        ),
                    }
                )
                try:
                    reply = self._complete(messages)
                except Exception as err:  # noqa: BLE001
                    logger.error("AI revision call failed: %s", err)
                    break
                problems = _validate_suggestions(owner, pet, reply.suggested_tasks)

        # 4. REMEMBER: save this turn + any learned preferences, then persist.
        stamp = datetime.now().isoformat(timespec="seconds")
        owner.memory.add_message("user", user_message, stamp)
        owner.memory.add_message("assistant", reply.message, stamp)
        for pref in reply.learned_preferences:
            owner.memory.remember_preference(pref)
        save_memory(owner.memory, self.memory_path)

        return ChatResult(
            message=reply.message,
            suggested_tasks=reply.suggested_tasks,
            warnings=problems,  # any issues still unresolved after MAX_REVISIONS
            revisions=revisions,
            ok=True,
            demo=demo,
        )
