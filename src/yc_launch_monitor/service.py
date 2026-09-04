from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid

from .classification import classify_social_signal, normalize_company
from .domain import RunResult, SignalStatus, Source, utc_now


class MonitorService:
    def __init__(
        self,
        store,
        collectors,
        notifier,
        *,
        bootstrap_notify: bool = True,
        notify_needs_review: bool = False,
        record_deliveries: bool = True,
    ):
        self.store = store
        self.collectors = collectors
        self.notifier = notifier
        self.bootstrap_notify = bootstrap_notify
        self.notify_needs_review = notify_needs_review
        self.record_deliveries = record_deliveries

    def run_once(self) -> RunResult:
        run_id = str(uuid.uuid4())
        started_at = utc_now()
        self.store.start_run(run_id, started_at)
        with ThreadPoolExecutor(max_workers=max(1, len(self.collectors))) as executor:
            results = list(executor.map(lambda collector: collector.collect(), self.collectors))
        for result in results:
            self.store.record_source(run_id, result)

        yc_names = {
            normalize_company(item.company_name)
            for result in results if result.source == Source.YC_DIRECTORY for item in result.signals
        }
        speedrun_names = {
            normalize_company(item.company_name)
            for result in results if result.source == Source.SPEEDRUN for item in result.signals
        }

        collected = 0
        changed_count = 0
        delivered = 0
        failed = 0
        for result in results:
            source_was_empty = not self.store.has_signals(result.source)
            for item in result.signals:
                collected += 1
                if item.source in {Source.X, Source.LINKEDIN}:
                    item = classify_social_signal(
                        item,
                        yc_company_names=yc_names,
                        speedrun_company_names=speedrun_names,
                    )
                changed = self.store.upsert_signal(item)
                changed_count += int(changed)
                eligible = item.status != SignalStatus.NEEDS_REVIEW or self.notify_needs_review
                bootstrap_allowed = self.bootstrap_notify or not source_was_empty
                if eligible and bootstrap_allowed and self.store.should_deliver(item):
                    try:
                        self.notifier.send(item)
                    except Exception:
                        failed += 1
                    else:
                        if self.record_deliveries:
                            self.store.mark_delivered(item)
                            delivered += 1
                elif eligible and not bootstrap_allowed and self.store.should_deliver(item):
                    if self.record_deliveries:
                        self.store.mark_suppressed(item)

        completed_at = utc_now()
        self.store.finish_run(
            run_id,
            completed_at,
            collected,
            changed_count,
            delivered,
            failed,
        )
        return RunResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            collected=collected,
            new_or_changed=changed_count,
            delivered=delivered,
            failed_deliveries=failed,
            source_health={result.source.value: result.health.value for result in results},
        )
