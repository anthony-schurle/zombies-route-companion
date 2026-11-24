"""Manual observations, route confirmations, and reversible history."""
from dataclasses import dataclass
from datetime import datetime

from .model import Match


@dataclass(frozen=True)
class Event:
    when: datetime
    kind: str
    detail: str
    before: Match
    after: Match
    previous_restrictions: frozenset[str]
    restrictions: frozenset[str]


class Session:
    def __init__(self, profile):
        self.profile = profile
        self.match = profile.initial
        self.prohibited = frozenset()
        self.history = []

    def record(self, kind, detail, match, prohibited=None):
        self.profile.validate_match(match)
        restricted = self.prohibited if prohibited is None else frozenset(prohibited)
        if not restricted <= self.profile.doors.keys():
            raise ValueError("Unknown restricted door")
        if (match, restricted) == (self.match, self.prohibited):
            return
        self.history.append(Event(datetime.now().astimezone(), kind, detail, self.match, match,
                                  self.prohibited, restricted))
        self.match, self.prohibited = match, restricted

    def confirm(self, action):
        match = self.profile.apply(self.match, action, self.prohibited)
        self.record("STEP_CONFIRMED", action.label, match)

    def undo(self):
        if self.history:
            event = self.history.pop()
            self.match, self.prohibited = event.before, event.previous_restrictions

    def reset(self):
        self.record("MATCH_RESET", "Reset match", self.profile.initial, frozenset())
