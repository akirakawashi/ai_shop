"""Хранилища событий."""

from people_monitor.storage.base import EventStore
from people_monitor.storage.jsonl import JsonlEventStore

__all__ = ["EventStore", "JsonlEventStore"]
