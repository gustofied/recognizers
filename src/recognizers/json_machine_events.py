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
