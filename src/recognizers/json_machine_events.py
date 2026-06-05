from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum, auto


class EventType(StrEnum):
    KEY_SEEN = auto()
    FIELD_COMPLETE = auto()
    OBJECT_COMPLETE = auto()
    ARRAY_ELEMENT_COMPLETE = auto()
    VALID_COMPLETE = auto()
    ERROR = auto()


@dataclass(frozen=True)
class Event:
    event_type: EventType
    message: str
    value: object = None
    reward: float = 0.0


def total_reward(events: Iterable[Event]) -> float:
    return sum(event.reward for event in events)
