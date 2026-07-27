"""PawPal+ logic layer.

This module holds all the backend classes for PawPal+:
Task, Pet, Owner, and Scheduler. The Streamlit UI (app.py)
will import and use these classes.

Data ownership (how the pieces relate):
    Owner  has many  Pet
    Pet    has many  Task
    Scheduler reads tasks THROUGH the Owner (owner.get_all_tasks()),
    so it never reaches into a Pet directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# Ranking so priorities sort correctly (higher number = more important).
# Use this instead of sorting priority strings, which would sort alphabetically.
PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}

# How far ahead the next occurrence of a recurring task lands. timedelta does
# the calendar math (month/year rollover) for us. A frequency not in this map
# (e.g. "once") simply doesn't repeat.
FREQUENCY_DELTAS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}


@dataclass
class Task:
    """A single care activity (a walk, a feeding, a dose of meds...)."""

    description: str
    duration_minutes: int = 0
    priority: str = "medium"  # "high", "medium", or "low"
    frequency: str = "daily"  # e.g. "daily", "weekly", "once"
    start_time: str = ""  # clock time in "HH:MM" (24h); "" means unscheduled
    due_date: date = field(default_factory=date.today)  # day this task is due
    completed: bool = False
    pet: "Pet | None" = None  # back-reference, set when added to a Pet

    def is_high_priority(self) -> bool:
        """Return True if this task is high priority."""
        return self.priority == "high"

    def priority_rank(self) -> int:
        """Numeric rank for sorting (unknown priorities rank lowest)."""
        return PRIORITY_ORDER.get(self.priority, 0)

    def is_recurring(self) -> bool:
        """True if this task repeats (daily/weekly), not a one-off."""
        return self.frequency in FREQUENCY_DELTAS

    def next_occurrence(self) -> "Task | None":
        """Build the next instance of this task, or None if it doesn't repeat.

        The copy starts incomplete and its due_date is advanced by the
        frequency's timedelta (daily = +1 day, weekly = +7 days).
        """
        delta = FREQUENCY_DELTAS.get(self.frequency)
        if delta is None:
            return None
        return Task(
            description=self.description,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            frequency=self.frequency,
            start_time=self.start_time,
            due_date=self.due_date + delta,
            completed=False,
        )

    def mark_complete(self) -> "Task | None":
        """Mark this task done and, if it recurs, schedule its next occurrence.

        For a daily/weekly task attached to a pet, a fresh instance is created
        for the next due date and added to the same pet. Returns that new task
        (or None for one-off tasks). Re-completing an already-done task is a
        no-op so it can't spawn duplicates.
        """
        if self.completed:
            return None  # already done — don't spawn a second copy
        self.completed = True

        upcoming = self.next_occurrence()
        if upcoming is not None and self.pet is not None:
            self.pet.add_task(upcoming)
        return upcoming

    def mark_incomplete(self) -> None:
        """Mark this task as not done."""
        self.completed = False


@dataclass
class Pet:
    """Stores a pet's details and the tasks that belong to it."""

    name: str
    breed: str = ""
    gender: str = ""
    weight: float = 0.0
    height: float = 0.0
    age: int = 0
    health_conditions: str = ""
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a care task to this pet."""
        task.pet = self  # so the task knows which pet it belongs to
        self.tasks.append(task)

    def remove_task(self, task: Task) -> None:
        """Remove a task from this pet (safe if it's not present)."""
        if task in self.tasks:
            self.tasks.remove(task)
            task.pet = None

    def pending_tasks(self) -> list[Task]:
        """Return this pet's tasks that aren't completed yet."""
        return [t for t in self.tasks if not t.completed]


@dataclass
class Message:
    """One turn in a chat with the AI assistant.

    role is "user" (the owner) or "assistant" (the AI). timestamp is a plain
    ISO string so the whole thing serialises to JSON without special handling.
    """

    role: str
    text: str
    timestamp: str = ""

    def to_dict(self) -> dict:
        """Plain dict for JSON storage."""
        return {"role": self.role, "text": self.text, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Rebuild a Message from the dict produced by to_dict()."""
        return cls(
            role=data.get("role", ""),
            text=data.get("text", ""),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class Memory:
    """What the AI assistant remembers about an owner across chats.

    This is what makes the bot "personalized": it keeps the running chat
    history plus a short list of durable preferences the owner has stated
    (e.g. "Mochi hates dry food", "prefers morning walks"). Both are fed back
    into future prompts so advice builds on past conversations. The whole
    object round-trips to JSON so memory survives closing the app.
    """

    messages: list[Message] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)

    def add_message(self, role: str, text: str, timestamp: str = "") -> Message:
        """Append a chat turn and return it."""
        message = Message(role=role, text=text, timestamp=timestamp)
        self.messages.append(message)
        return message

    def remember_preference(self, preference: str) -> None:
        """Store a durable preference, skipping exact duplicates."""
        preference = preference.strip()
        if preference and preference not in self.preferences:
            self.preferences.append(preference)

    def recent(self, n: int = 6) -> list[Message]:
        """Return the last n chat turns (all of them if there are fewer)."""
        return self.messages[-n:]

    def to_dict(self) -> dict:
        """Plain dict for JSON storage."""
        return {
            "messages": [m.to_dict() for m in self.messages],
            "preferences": list(self.preferences),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        """Rebuild a Memory from the dict produced by to_dict()."""
        return cls(
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            preferences=list(data.get("preferences", [])),
        )


@dataclass
class Owner:
    """Manages multiple pets and gives access to all their tasks."""

    name: str
    minutes_available: int = 0  # daily care time, same unit as Task.duration_minutes
    preferences: str = ""
    pets: list[Pet] = field(default_factory=list)
    memory: Memory = field(default_factory=Memory)  # the AI assistant's per-owner memory

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet (safe if it's not present)."""
        if pet in self.pets:
            self.pets.remove(pet)

    def get_all_tasks(self) -> list[Task]:
        """Flatten every task across all of this owner's pets."""
        all_tasks: list[Task] = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks

    def get_pending_tasks(self) -> list[Task]:
        """All not-yet-completed tasks across every pet."""
        return [t for t in self.get_all_tasks() if not t.completed]


@dataclass
class Scheduler:
    """The 'brain': retrieves, organizes, and plans tasks across pets."""

    owner: Owner

    def sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return tasks ordered highest priority first."""
        return sorted(tasks, key=lambda t: t.priority_rank(), reverse=True)

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Return tasks ordered earliest start time first.

        Parses each "HH:MM" string into an (hour, minute) tuple so comparison
        is numeric, not lexicographic. That means "9:30" sorts before "10:00"
        even if it isn't zero-padded. Unscheduled tasks ("") sort to the end.
        """

        def time_key(task: Task) -> tuple[int, int]:
            if not task.start_time:
                return (24, 0)  # push unscheduled tasks after any real time
            hour, minute = (int(x) for x in task.start_time.split(":"))
            return (hour, minute)

        return sorted(tasks, key=time_key)

    def filter_by_status(self, completed: bool = False) -> list[Task]:
        """Return the owner's tasks matching the given completion status."""
        return [t for t in self.owner.get_all_tasks() if t.completed == completed]

    def filter_by_pet(self, pet_name: str) -> list[Task]:
        """Return the owner's tasks that belong to the named pet."""
        return [
            t
            for t in self.owner.get_all_tasks()
            if t.pet is not None and t.pet.name == pet_name
        ]

    def detect_conflicts(self, tasks: list[Task] | None = None) -> list[str]:
        """Return warnings for tasks that share the same start time.

        Lightweight strategy: bucket every scheduled task by its exact "HH:MM"
        start time, then flag any slot that holds more than one task — whether
        those tasks belong to the same pet or different ones. Unscheduled tasks
        (blank start_time) are ignored.

        Returns a list of human-readable warning strings (empty when there are
        no clashes). It never raises, so a caller can simply print the results
        and carry on rather than crashing the program.
        """
        if tasks is None:
            tasks = self.owner.get_all_tasks()

        by_time: dict[str, list[Task]] = {}
        for task in tasks:
            if task.start_time:  # skip unscheduled tasks
                by_time.setdefault(task.start_time, []).append(task)

        warnings: list[str] = []
        for start_time, clashing in by_time.items():
            if len(clashing) > 1:
                labels = ", ".join(
                    f"{t.description} ({t.pet.name if t.pet else 'unknown pet'})"
                    for t in clashing
                )
                warnings.append(f"WARNING: {len(clashing)} tasks clash at {start_time}: {labels}")
        return warnings

    def generate_plan(self) -> list[Task]:
        """Build a daily plan of pending tasks that fits the available time.

        Greedy strategy: take the highest-priority pending tasks first and
        keep adding them until the owner's available minutes run out.
        """
        pending = self.owner.get_pending_tasks()
        ordered = self.sort_by_priority(pending)

        plan: list[Task] = []
        minutes_used = 0
        for task in ordered:
            if minutes_used + task.duration_minutes <= self.owner.minutes_available:
                plan.append(task)
                minutes_used += task.duration_minutes

        # Chosen by priority above, but hand back the plan in clock order so
        # the owner reads it as a timeline rather than an importance ranking.
        return self.sort_by_time(plan)

    def explain_plan(self) -> str:
        """Human-readable summary of the generated plan and why."""
        plan = self.generate_plan()
        if not plan:
            return "No tasks fit in the available time."

        total = sum(t.duration_minutes for t in plan)
        lines = [
            f"Planned {len(plan)} task(s) using {total} of "
            f"{self.owner.minutes_available} available minutes:"
        ]
        for task in plan:
            pet_name = task.pet.name if task.pet else "unknown pet"
            lines.append(
                f"  - {task.description} ({pet_name}) "
                f"[{task.priority}, {task.duration_minutes} min]"
            )
        return "\n".join(lines)
