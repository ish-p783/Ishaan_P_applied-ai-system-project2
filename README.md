# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## ✨ Features

The scheduling algorithms all live in `pawpal_system.py` and are surfaced through both the Streamlit UI (`app.py`) and a CLI demo (`main.py`):

- **Priority sorting** — orders tasks high → medium → low using a numeric `PRIORITY_ORDER` rank, so priorities sort by importance rather than alphabetically.
- **Sorting by time** — parses each `"HH:MM"` start time into an `(hour, minute)` tuple, so `"9:00"` correctly precedes `"10:00"` even when unpadded; unscheduled tasks sort to the end.
- **Filtering** — narrow the task list by pet (`filter_by_pet`) or by completion status (`filter_by_status`).
- **Conflict warnings** — buckets tasks by exact start time and flags any slot holding more than one task, naming the clashing tasks and their pets (works across the same pet *or* different pets).
- **Daily & weekly recurrence** — completing a recurring task auto-spawns a fresh, incomplete copy for the next due date (`due_date + timedelta`, so month/year rollover is handled); `once` tasks don't repeat, and re-completing a done task won't create duplicates.
- **Greedy daily planner** — selects the highest-priority pending tasks that fit within the owner's available minutes, then returns them in clock order so the plan reads as a timeline.
- **Plan explanation** — renders the generated plan as a human-readable summary of what was scheduled and how many minutes it uses.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:
Today's Schedule
========================================
Planned 4 task(s) using 75 of 90 available minutes:
  - Morning walk (Rex) [high, 30 min]
  - Give medication (Mia) [high, 10 min]
  - Play with feather toy (Mia) [medium, 20 min]
  - Brush coat (Rex) [low, 15 min]
```
# e.g.:
# Daily plan for Biscuit (Golden Retriever):
#   08:00 — Morning walk (30 min) [priority: high]
#   09:00 — Feeding (10 min) [priority: high]
#   ...
```

## 🧪 Testing PawPal+

Run the full automated test suite from the project root:

```bash
python -m pytest
```

The suite (`tests/test_pawpal.py`) covers the behaviors most likely to break:

- **Recurrence logic** — completing a daily task spawns a fresh copy due the next day; weekly tasks land 7 days out; `once` tasks don't recur; and re-completing an already-done task is a no-op (no duplicate spawned).
- **Recurrence edge cases** — a recurring task with no attached pet still returns its next occurrence without crashing.
- **Sorting correctness** — `sort_by_time()` returns tasks in chronological order, correctly placing `"9:30"` before `"10:00"` (numeric parse, not string compare).
- **Conflict detection** — the `Scheduler` flags two tasks sharing the same start time with a single warning naming both.
- **Plan generation** — an owner with no tasks yields an empty plan and a clear "No tasks fit" message.
- **Core model** — adding a task increases a pet's task count; `mark_complete()` flips completion status.

Successful test run:

```
============================= test session starts =============================
platform win32 -- Python 3.9.0, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\ishp1\ai110-module2show-pawpal-starter
collected 10 items

tests\test_pawpal.py ..........                                          [100%]

============================= 10 passed in 0.03s ==============================
```

### Confidence Level: ⭐⭐⭐⭐⭐ (5/5)

All 10 tests pass and cover the core scheduling logic — recurrence, sorting, and conflict
detection — including several edge cases (double-completion, unattached recurring tasks,
unpadded times, empty plans). The logic layer is well-exercised and behaves predictably.

## 📐 Smarter Scheduling

PawPal+ goes beyond a flat task list with four pieces of scheduling logic, all in
`pawpal_system.py`:

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_priority()`, `Scheduler.sort_by_time()` | Priority sort ranks high→low via `PRIORITY_ORDER`. Time sort parses `"HH:MM"` into an `(hour, minute)` tuple so `"9:00"` correctly precedes `"10:00"` even when unpadded; unscheduled tasks sort last. |
| Filtering | `Scheduler.filter_by_status()`, `Scheduler.filter_by_pet()` | Return just the completed/pending tasks, or only the tasks belonging to a named pet. |
| Conflict detection | `Scheduler.detect_conflicts()` | Buckets scheduled tasks by exact start time and returns a warning string for any slot holding more than one task (same pet **or** different pets). Never raises — the caller prints the warning and continues. |
| Recurring tasks | `Task.mark_complete()`, `Task.next_occurrence()`, `Task.is_recurring()` | Completing a `daily`/`weekly` task auto-creates a fresh, incomplete copy for the next due date (`due_date + timedelta`, so calendar rollover is handled). `once` tasks don't recur. |

### How the daily plan is built

`Scheduler.generate_plan()` greedily selects the highest-priority pending tasks that fit
inside the owner's `minutes_available`, then returns them ordered by time so the plan reads
as a timeline. `Scheduler.explain_plan()` renders that plan as human-readable text.

## 🎬 Demo Walkthrough

PawPal+ runs two ways: an interactive **Streamlit app** (`streamlit run app.py`) and a scripted **CLI demo** (`python main.py`) that prints every scheduler feature in one pass.

### Main UI features (Streamlit)

From top to bottom, the app lets a pet owner:

- **Set owner details** — name and the number of care minutes available today.
- **Add pets** — name and species; every added pet becomes selectable when creating tasks.
- **Add tasks** — title, duration, priority (low/medium/high), start time, and repeat frequency (once/daily/weekly), each assigned to a specific pet.
- **See conflict warnings first** — any time two tasks share a start time, a highlighted warning appears at the top of the task list naming the clashing tasks and pets, with a tip to reschedule.
- **Sort and filter the task list** — sort by time of day or priority; filter by pet and by status (all/pending/completed), rendered in a clean table.
- **Mark tasks complete** — completing a recurring task automatically schedules its next occurrence and reports the new due date.
- **Generate today's schedule** — builds a timeline that fits the highest-priority tasks into the available minutes and shows how many were used.

### Example workflow

1. Enter the owner's name and set **Time available today** to `90` minutes.
2. **Add a pet** — e.g. `Rex` (dog) — then add a second, `Mia` (cat).
3. **Add tasks** to each pet with start times and priorities (e.g. Rex's *Morning walk* at 09:00 high, Mia's *Feed dinner* at 18:30 high).
4. Watch the **conflict warning** fire if two tasks land on the same time (e.g. Rex's evening walk and Mia's dinner both at 18:30).
5. **Sort by time** to read the day as a timeline, or **filter by pet** to focus on one animal.
6. **Mark** the daily *Morning walk* **complete** and see tomorrow's occurrence appear automatically.
7. Click **Generate schedule** to get the final plan that fits inside 90 minutes.

### Key Scheduler behaviors shown

- **Time sorting** — tasks entered out of order (and with an unpadded `9:00`) print in true chronological order.
- **Filtering** — separates pending vs. completed tasks, and isolates a single pet's tasks.
- **Conflict warnings** — detects the two tasks booked at `18:30` and names both.
- **Daily recurrence** — completing *Morning walk* grows Rex's task count from 3 to 4, with the next occurrence due the following day.
- **Greedy planning** — the schedule packs the highest-priority tasks into exactly the available minutes.

### Sample CLI output (`python main.py`)

```
========================================
All tasks, sorted by time
========================================
  08:00  Give medication (Mia)
   9:00  Morning walk (Rex)
  10:45  Brush coat (Rex)
  12:15  Play with feather toy (Mia)
  18:30  Evening walk (Rex)
  18:30  Feed dinner (Mia)

========================================
Filter: pending vs. completed
========================================
  Pending:
    - Evening walk
    - Morning walk
    - Brush coat
    - Play with feather toy
    - Feed dinner
  Completed:
    - Give medication

========================================
Filter: Rex's tasks only
========================================
  - Evening walk [18:30]
  - Morning walk [9:00]
  - Brush coat [10:45]

========================================
Conflict detection
========================================
  WARNING: 2 tasks clash at 18:30: Evening walk (Rex), Feed dinner (Mia)

========================================
Recurring task rollover
========================================
  Before: Rex has 3 tasks. 'Morning walk' due 2026-07-02.
  Completed 'Morning walk'.
  After:  Rex has 4 tasks. Next occurrence due 2026-07-03 (completed=False).

========================================
Today's Schedule
========================================
Planned 4 task(s) using 90 of 90 available minutes:
  - Morning walk (Rex) [high, 30 min]
  - Play with feather toy (Mia) [medium, 20 min]
  - Evening walk (Rex) [high, 30 min]
  - Feed dinner (Mia) [high, 10 min]
```

<br/>

---
---

<br/>

# 🐾 PawPal+ — AI Edition (current project)

> **Everything above** documents the original rule-based PawPal+ (Modules 1–3).
> **Everything below** documents the new **AI-integrated edition** built on top of
> it.

## 📦 Original Project (Modules 1–3)

Original project: PawPal+
An app built to help pet owners manage and track tasks for their pets' wellbeing. It was able to generate a schedule for owners based on the tasks and time constraints the owner inputted as well as any additional information regarding the pet such as medical history or allergies. The app also allows owners to add or remove tasks.


## 📌 Title and Summary

My project will use the original pet care app and implement an AI Care chatbot that allows owners to ask questions and get advice tailored specifically for their situation. It will retrieve helpful guidance, recommend tasks that can be added or remove, and offers ways to improve schedule if asked. It matters because most people cannot find the best advice from the internet that fits their current situation, even from forums such as reddit. However, with an AI Care chatbot, users can receive correct advice for general decision making.
The AI uses Retrieval-Augmented Generation (RAG) as it uses previous conversations to keep in mind any information you may have said previously and give advice adjusted in real-time with the help of the Agentic workflow to make sure the plan is valid. The program also had run test cases to verify guardrails and memory of previous chats.


## 🏗️ Architecture Overview

Diagrams (Mermaid source; open at <https://mermaid.live> or any Mermaid viewer):

- [`diagrams/ai_architecture.mmd`](diagrams/ai_architecture.mmd) — the **AI data flow**.
- [`diagrams/uml_final.mmd`](diagrams/uml_final.mmd) — the **class model**, synced with the code.
- [`diagrams/architecture.mmd`](diagrams/architecture.mmd) — the original layered architecture.

**Data flow (input → process → output):**

1. **Input.** Owner types a message and picks a pet (`app.py`).
2. **Retriever (RAG).** `retrieve_guidelines()` pulls matching snippets from
   `care_guidelines.md`; `retrieve_memory()` pulls the owner's past chat and
   preferences. Both go into the prompt so answers are grounded and personalized.
3. **Agent (plan → check → revise).** `PawPalAssistant.chat()` asks Claude for a
   reply plus tasks as validated JSON; `_validate_suggestions()` checks them
   against the time budget and reuses the existing `Scheduler.detect_conflicts()`.
   Failures are handed back to the model to fix (up to 3 times).
4. **Output.** A reply plus validated task suggestions.
5. **Human-in-the-loop.** Nothing is scheduled automatically — the owner clicks
   **Add** to accept a suggestion.
6. **Memory.** The turn and learned preferences are saved to `pawpal_memory.json`.
7. **Verification.** `tests/test_ai_assistant.py` and `ai_demo.py` exercise the
   retriever, guardrail, and memory with no API key.

## ⚙️ Setup Instructions

**Prerequisites:** Python 3.9+ and an [Anthropic API key](https://console.anthropic.com/)
(the AI chat needs it; everything else runs without it).

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API key (enables the AI chat)
cp .env.example .env               # Windows: copy .env.example .env
#    then open .env and paste your key after ANTHROPIC_API_KEY=

# 4. Run the app
streamlit run app.py

# Optional — reproducible evidence (no API key needed):
python ai_demo.py                  # RAG + guardrail + degradation demo
python -m pytest                   # full test suite
python main.py                     # scheduler CLI demo
```

The `.env` file is git-ignored, so your key is never committed. Skip step 3 and
the app still runs — the chat section just explains how to enable itself.

## 💬 Sample Interactions

Representative chats with the AI Care Assistant (dog **Rex**, 90 minutes/day

### Example 1 — Task suggestion with self-correction
You: Rex seems really hyper lately, what should I do?
>
> **🤖 PawPal+:** High-energy dogs like Rex usually need 60–90 minutes of active
> exercise a day, split into a couple of sessions. Here are two walks and a play
> session that fit your 90 minutes.
>
> *Suggested tasks* (revised 1 time to fit your time budget):
> - **Morning walk** — 08:00 · high · 35 min · daily
> - **Evening walk** — 18:00 · high · 35 min · daily
> - **Fetch in the yard** — 12:30 · medium · 20 min · daily → **[Add]**

*(The model first proposed 120 min of walks; the guardrail flagged it exceeded
the 90-minute budget and the model shortened them to fit.)*

### Example 2 — Personalization (it remembers)
> **You:** Just so you know, Rex hates dry kibble.
>
> **🤖 PawPal+:** Got it — I'll remember Rex doesn't like dry kibble. *(saved to
> "🧠 What I remember")*
>
> **You (later):** Any feeding ideas for him?
>
> **🤖 PawPal+:** Since Rex isn't a fan of dry kibble, I'd stick with two measured
> wet-food or fresh meals a day, morning and evening...

### Example 3 — Unwell pet, with the vet guardrail
> **You:** Rex threw up twice today and won't eat.
>
> **🤖 PawPal+:** I'm sorry to hear that. You can try a smaller, lighter meal and
> plenty of water and keep activity gentle for now — but vomiting plus not eating
> for a day is worth a call to your vet, and I'd recommend reaching out if it
> continues. I'm not a substitute for a veterinarian for anything serious.

## 🧠 Design Decisions

I built the AI agent to have RAG, agentic loop, and testing to ensure the responses are adjusting according to context and preserve memory. The AI also has access to methods and commands within the program to ensure any advice given fits the constraints already stated by owner. The Trade offs are that while it's simple to set up, the AI needs more specific wording as it relies on key words. There is also the issue of an extra click needed for owner review before any changes are made.


## 🧪 Testing Output and Summary



### A. AI feature demo — `python ai_demo.py`

Shows the example **input**, the retrieval/guardrail **processing**, and the
**output**. The leading `[INFO]` lines are the assistant's own logging (a
reliability feature).

```text
$ python ai_demo.py
2026-07-26 15:26:05 [INFO] Retrieved 1 guideline snippet(s) for query.
2026-07-26 15:26:05 [INFO] Loaded 1 memory message(s) and 1 preference(s).
2026-07-26 15:26:05 [INFO] Validation found 1 problem(s) in suggestions.

============================================================
1 | RETRIEVAL (RAG): grounding advice in care_guidelines.md
============================================================
Input query : Rex seems really hyper lately, what should I do?
Pet profile : Rex, labrador
Retrieved knowledge snippets:
  - Daily exercise for high-energy dogs: High-energy dogs generally need 60-90
    minutes of active exercise per day, split across two or more sessions...

============================================================
2 | MEMORY: personalization from what the owner told us
============================================================
Remembered preferences : ['Rex hates dry kibble']
Recent conversation    : ['user: Rex hates dry kibble']

============================================================
3 | GUARDRAIL: validating the AI's proposed tasks
============================================================
Proposed tasks: two 40-min walks, both at 08:00 (owner has 90 min).
Guardrail found these problems:
  ! 2 tasks clash at 08:00: Walk A (Rex), Walk B (Rex)

Revised tasks: 35-min walks at 08:00 and 18:00 (total 70 min).
Guardrail result: PASS - no problems

============================================================
4 | GUARDRAIL: graceful degradation with no API key
============================================================
API key configured? False
chat() ok flag    : False
chat() message    : The AI assistant isn't set up yet. Add your Anthropic API
                    key to a `.env` file (see `.env.example`) and restart...
```

**What this proves:** (1) RAG retrieves the *right* guideline for the pet, (2) the
guardrail catches an invalid AI plan (a time clash) and confirms a fixed plan
passes, and (3) with no key the system degrades gracefully instead of crashing.

### B. Automated test suite — `python -m pytest -v`

```text
$ python -m pytest -v
============================= test session starts =============================
platform win32 -- Python 3.9.0, pytest-8.4.2, pluggy-1.6.0
collected 22 items

tests/test_ai_assistant.py::test_retrieval_matches_pet_by_tag PASSED     [  4%]
tests/test_ai_assistant.py::test_retrieval_respects_k_limit PASSED       [  9%]
tests/test_ai_assistant.py::test_retrieval_handles_missing_file PASSED   [ 13%]
tests/test_ai_assistant.py::test_memory_dedupes_preferences PASSED       [ 18%]
tests/test_ai_assistant.py::test_memory_recent_returns_last_n PASSED     [ 22%]
tests/test_ai_assistant.py::test_memory_round_trips_to_dict PASSED       [ 27%]
tests/test_ai_assistant.py::test_memory_persists_to_disk PASSED          [ 31%]
tests/test_ai_assistant.py::test_load_memory_missing_file_returns_empty PASSED [ 36%]
tests/test_ai_assistant.py::test_validation_flags_over_budget PASSED     [ 40%]
tests/test_ai_assistant.py::test_validation_flags_conflict_with_existing_task PASSED [ 45%]
tests/test_ai_assistant.py::test_validation_passes_clean_suggestions PASSED [ 50%]
tests/test_ai_assistant.py::test_chat_without_api_key_degrades_gracefully PASSED [ 54%]
tests/test_pawpal.py::test_mark_complete_changes_status PASSED           [ 59%]
tests/test_pawpal.py::test_completing_daily_task_spawns_next_day PASSED  [ 63%]
tests/test_pawpal.py::test_completing_weekly_task_spawns_next_week PASSED [ 68%]
tests/test_pawpal.py::test_once_task_does_not_recur PASSED               [ 72%]
tests/test_pawpal.py::test_adding_task_increases_pet_task_count PASSED   [ 77%]
tests/test_pawpal.py::test_double_complete_does_not_spawn_duplicate PASSED [ 81%]
tests/test_pawpal.py::test_recurring_task_with_no_pet_does_not_crash PASSED [ 86%]
tests/test_pawpal.py::test_sort_by_time_handles_non_zero_padded_times PASSED [ 90%]
tests/test_pawpal.py::test_detect_conflicts_flags_same_time_tasks PASSED [ 95%]
tests/test_pawpal.py::test_empty_owner_generates_empty_plan PASSED       [100%]

============================= 22 passed in 0.45s ==============================
```

### Reliability summary

**22 of 22 tests passed.** They cover RAG retrieval, the guardrail validator
(over-budget and time-clash detection), memory persistence, and graceful no-key
fallback.
What worked: The AI was able to properly adjust to any conflicting suggestions and stay within constraints. 
What didn't work: The model is keyword-based so it misses certain guidelines with different wording.
I learned that AI chatbots need validation testing to make sure that advice is not only just right but also fits the constraints given.


## 📝 Reflection

Building an AI Care chatbot taught me that creating a well functioning model also includes making sure the AI has authentic responses that adjust in real time to fit the user's situation. 

Building PawPal+'s AI layer taught me that the interesting engineering is around
the model, not inside it: retrieval to ground it, a validation loop to keep it
honest, and guardrails so it fails safely. The full graded responsible-AI
reflection — how I collaborated with AI, one helpful and one flawed AI
suggestion, and the system's limitations — is in [`model_card.md`](model_card.md).

