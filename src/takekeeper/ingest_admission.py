from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Callable


class IngestOverloaded(RuntimeError):
    """Authenticated ingest work was rejected by the local admission boundary."""


@dataclass(frozen=True, slots=True)
class IngestAdmissionSnapshot:
    active_requests: int
    admitted_total: int
    rejected_concurrency_total: int
    rejected_rate_total: int
    rejected_capacity_total: int


@dataclass(slots=True)
class _ActorState:
    active: int
    recent: deque[float]


class _AdmissionLease:
    def __init__(self, guard: "ActorIngestAdmissionGuard", actor_id: str) -> None:
        self._guard = guard
        self._actor_id = actor_id
        self._released = False

    def __enter__(self) -> "_AdmissionLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._guard._release(self._actor_id)


class ActorIngestAdmissionGuard:
    """Thread-safe, process-local admission control keyed only by trusted actor identity.

    The guard combines a per-actor concurrent-work cap with a sliding-window request cap.
    It intentionally never accepts tenant, production, scene, take, media URI, or other
    caller-controlled metadata as a key. Metrics are aggregate-only to keep cardinality and
    identity disclosure bounded.

    This protects one application process. Multi-instance deployments should pair it with
    upstream Cloud Run/IAP/API-gateway quotas or another distributed rate-control layer.
    """

    def __init__(
        self,
        *,
        max_concurrent_per_actor: int = 2,
        max_requests_per_window: int = 30,
        window_seconds: float = 60.0,
        max_tracked_actors: int = 512,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if type(max_concurrent_per_actor) is not int or not 1 <= max_concurrent_per_actor <= 64:
            raise ValueError("invalid concurrent ingest limit")
        if type(max_requests_per_window) is not int or not 1 <= max_requests_per_window <= 10_000:
            raise ValueError("invalid ingest rate limit")
        if not isinstance(window_seconds, (int, float)) or not 1 <= float(window_seconds) <= 3_600:
            raise ValueError("invalid ingest rate window")
        if type(max_tracked_actors) is not int or not 1 <= max_tracked_actors <= 4_096:
            raise ValueError("invalid actor tracking limit")

        self.max_concurrent_per_actor = max_concurrent_per_actor
        self.max_requests_per_window = max_requests_per_window
        self.window_seconds = float(window_seconds)
        self.max_tracked_actors = max_tracked_actors
        self._clock = clock
        self._lock = Lock()
        self._actors: dict[str, _ActorState] = {}
        self._active_requests = 0
        self._admitted_total = 0
        self._rejected_concurrency_total = 0
        self._rejected_rate_total = 0
        self._rejected_capacity_total = 0

    def acquire(self, actor_id: str) -> _AdmissionLease:
        actor = actor_id.strip() if isinstance(actor_id, str) else ""
        if not actor or len(actor) > 512 or any(ord(ch) < 32 for ch in actor):
            raise PermissionError("invalid authenticated actor")

        now = float(self._clock())
        cutoff = now - self.window_seconds
        with self._lock:
            state = self._actors.get(actor)
            if state is None:
                self._prune_idle_locked(cutoff)
                if len(self._actors) >= self.max_tracked_actors:
                    self._rejected_capacity_total += 1
                    raise IngestOverloaded("ingest capacity exceeded")
                state = _ActorState(active=0, recent=deque())
                self._actors[actor] = state

            while state.recent and state.recent[0] <= cutoff:
                state.recent.popleft()

            if state.active >= self.max_concurrent_per_actor:
                self._rejected_concurrency_total += 1
                raise IngestOverloaded("concurrent ingest limit exceeded")
            if len(state.recent) >= self.max_requests_per_window:
                self._rejected_rate_total += 1
                raise IngestOverloaded("ingest rate exceeded")

            state.active += 1
            state.recent.append(now)
            self._active_requests += 1
            self._admitted_total += 1
        return _AdmissionLease(self, actor)

    def snapshot(self) -> IngestAdmissionSnapshot:
        with self._lock:
            return IngestAdmissionSnapshot(
                active_requests=self._active_requests,
                admitted_total=self._admitted_total,
                rejected_concurrency_total=self._rejected_concurrency_total,
                rejected_rate_total=self._rejected_rate_total,
                rejected_capacity_total=self._rejected_capacity_total,
            )

    def _release(self, actor_id: str) -> None:
        with self._lock:
            state = self._actors.get(actor_id)
            if state is None or state.active <= 0:
                return
            state.active -= 1
            self._active_requests -= 1

    def _prune_idle_locked(self, cutoff: float) -> None:
        removable: list[str] = []
        for actor, state in self._actors.items():
            while state.recent and state.recent[0] <= cutoff:
                state.recent.popleft()
            if state.active == 0 and not state.recent:
                removable.append(actor)
        for actor in removable:
            del self._actors[actor]
