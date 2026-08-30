from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import BoundedSemaphore, Lock
from time import monotonic

from .provider_contract import SearchProvider
from .runtime_context import search_context_is_authoritative
from .schemas import ProviderError, SearchContext, SearchFederationResult, SearchHit


@dataclass(frozen=True, slots=True)
class SearchTelemetryEvent:
    provider: str
    latency_bucket: str
    hit_count: int
    zero_result: bool
    partial: bool


TelemetrySink = Callable[[SearchTelemetryEvent], None]


def _latency_bucket(elapsed_ms: int) -> str:
    if elapsed_ms < 100:
        return "LT_100MS"
    if elapsed_ms < 500:
        return "100_499MS"
    if elapsed_ms < 1000:
        return "500_999MS"
    if elapsed_ms < 1500:
        return "1000_1499MS"
    return "GTE_1500MS"


class SearchFederationService:
    """Parallel, partial-safe federation with one total wall-clock budget."""

    def __init__(
        self,
        providers: Iterable[SearchProvider],
        *,
        total_deadline_seconds: float = 1.5,
        max_workers: int = 6,
        telemetry_sink: TelemetrySink | None = None,
    ) -> None:
        self._providers = tuple(providers)
        provider_codes = [str(provider.provider_code or "").strip() for provider in self._providers]
        if any(not code for code in provider_codes) or len(set(provider_codes)) != len(provider_codes):
            raise ValueError("search provider_code values must be non-empty and unique")
        self._deadline = min(max(float(total_deadline_seconds), 0.01), 1.5)
        self._max_workers = min(max(int(max_workers), 1), 8)
        self._telemetry = telemetry_sink
        # These executors belong to the federation service, not to one request.
        # A singleton service therefore has a hard process-local concurrency
        # ceiling even when many searches arrive at once.
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="plat-d-search",
        )
        self._provider_slots = BoundedSemaphore(
            max(len(self._providers), self._max_workers * 4, 1)
        )
        self._telemetry_executor = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="plat-d-search-metrics")
            if telemetry_sink is not None else None
        )
        self._telemetry_slots = BoundedSemaphore(128)
        self._state_lock = Lock()
        self._closed = False

    def search(self, context: SearchContext) -> SearchFederationResult:
        started = monotonic()
        keyword = str(context.keyword or "").strip()
        if len(keyword) < 2:
            return SearchFederationResult(elapsed_ms=0)
        if not search_context_is_authoritative(context):
            return SearchFederationResult(
                provider_errors=[
                    ProviderError(provider=provider.provider_code, code="DENIED")
                    for provider in self._providers
                ],
                partial=False,
                elapsed_ms=int((monotonic() - started) * 1000),
            )
        effective_context = SearchContext(
            tenant_id=int(context.tenant_id),
            actor=dict(context.actor),
            keyword=keyword[:100],
            client=context.client,
            limit=min(max(int(context.limit), 1), 50),
        )

        future_by_provider: dict[str, Future[list[SearchHit]]] = {}
        started_by_provider: dict[str, float] = {}
        capacity_rejected: set[str] = set()
        with self._state_lock:
            if self._closed:
                raise RuntimeError("search federation is closed")
            for provider in self._providers:
                code = provider.provider_code
                started_by_provider[code] = monotonic()
                if not self._provider_slots.acquire(blocking=False):
                    capacity_rejected.add(code)
                    continue
                try:
                    future = self._executor.submit(provider.search, effective_context)
                except Exception:
                    self._provider_slots.release()
                    raise
                future.add_done_callback(lambda _future: self._provider_slots.release())
                future_by_provider[code] = future

        remaining = max(0.0, self._deadline - (monotonic() - started))
        _done, pending = wait(tuple(future_by_provider.values()), timeout=remaining)

        provider_hits: dict[str, list[SearchHit]] = {}
        errors: list[ProviderError] = []
        for provider in self._providers:
            code = provider.provider_code
            if code in capacity_rejected:
                errors.append(ProviderError(provider=code, code="TIMEOUT"))
                continue
            future = future_by_provider[code]
            if future in pending:
                future.cancel()
                errors.append(ProviderError(provider=code, code="TIMEOUT"))
                continue
            try:
                raw_hits = future.result()
                if not isinstance(raw_hits, list):
                    raise TypeError("search providers must return list[SearchHit]")
                bounded_hits = list(raw_hits[:effective_context.limit])
                if any(not isinstance(hit, SearchHit) for hit in bounded_hits):
                    raise TypeError("search provider returned an invalid SearchHit")
                provider_hits[code] = bounded_hits
            except Exception:  # provider errors are intentionally opaque at the API boundary
                provider_hits[code] = []
                errors.append(ProviderError(provider=code, code="FAILED"))

        partial = bool(errors)
        deduped: list[SearchHit] = []
        seen: set[str] = set()
        for provider in self._providers:
            code = provider.provider_code
            hits = provider_hits.get(code, [])
            for hit in hits:
                if hit.dedupe_key in seen:
                    continue
                seen.add(hit.dedupe_key)
                deduped.append(hit)
            self._record_telemetry(
                SearchTelemetryEvent(
                    provider=code,
                    latency_bucket=_latency_bucket(int((monotonic() - started_by_provider[code]) * 1000)),
                    hit_count=len(hits),
                    zero_result=not hits,
                    partial=partial,
                )
            )
        elapsed_ms = int((monotonic() - started) * 1000)
        return SearchFederationResult(
            hits=deduped,
            provider_errors=errors,
            partial=partial,
            elapsed_ms=elapsed_ms,
        )

    def _record_telemetry(self, event: SearchTelemetryEvent) -> None:
        if self._telemetry is None or self._telemetry_executor is None:
            return
        if not self._telemetry_slots.acquire(blocking=False):
            return
        with self._state_lock:
            if self._closed:
                self._telemetry_slots.release()
                return
            try:
                self._telemetry_executor.submit(self._emit_telemetry, event)
            except Exception:
                self._telemetry_slots.release()
                return

    def _emit_telemetry(self, event: SearchTelemetryEvent) -> None:
        try:
            self._telemetry(event)
        except Exception:
            # Observability must not make a safe partial search unavailable.
            return
        finally:
            self._telemetry_slots.release()

    def close(self, *, wait_for_running: bool = False) -> None:
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            provider_executor = self._executor
            telemetry_executor = self._telemetry_executor
        provider_executor.shutdown(
            wait=wait_for_running,
            cancel_futures=True,
        )
        if telemetry_executor is not None:
            telemetry_executor.shutdown(
                wait=wait_for_running,
                cancel_futures=not wait_for_running,
            )
