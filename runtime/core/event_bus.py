"""Minimal in-process pub/sub."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, DefaultDict, List

_LOG = logging.getLogger("pecunator.core.event_bus")

Subscriber = Callable[[str, Any], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[Subscriber]] = defaultdict(list)

    def subscribe(self, topic: str, callback: Subscriber) -> None:
        if callback not in self._subs[topic]:
            self._subs[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Subscriber) -> None:
        if callback in self._subs[topic]:
            self._subs[topic].remove(callback)

    def publish(self, topic: str, payload: Any) -> None:
        for cb in list(self._subs.get(topic, [])):
            try:
                cb(topic, payload)
            except Exception:
                _LOG.warning("EventBus: subscriber %s crashed on topic '%s'", cb, topic, exc_info=True)

    def publish_prefix(self, prefix: str, payload: Any) -> None:
        for topic, cbs in list(self._subs.items()):
            if topic.startswith(prefix):
                for cb in list(cbs):
                    try:
                        cb(topic, payload)
                    except Exception:
                        _LOG.warning("EventBus: subscriber %s crashed on topic '%s'", cb, topic, exc_info=True)
