import argparse
import signal
import sys
import httpx
from app.config import get_settings
from app.db.session import get_engine
from app.services.collector import (CollectionOptions, run_collection, AlreadyRunning,
                                    CollectionInterrupted)
from app.services.quota import DatabaseQuota
from app.sources.adzuna import AdzunaClient


def interrupted(signum, frame):
    raise CollectionInterrupted()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect authorised Adzuna jobs in Victoria, Australia")
    parser.add_argument("--location", default="Melbourne")
    category = parser.add_mutually_exclusive_group()
    category.add_argument("--category", default="it-jobs",
                          help="Adzuna category tag (default: it-jobs)")
    category.add_argument("--all-categories", dest="category", action="store_const", const=None,
                          help="Collect every category")
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--overlap-days", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        options = CollectionOptions(**vars(args))
    except ValueError as exc:
        parser.error(str(exc))
    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        settings, engine = get_settings(), get_engine()
        with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False) as http:
            def client_factory():
                return AdzunaClient(settings.adzuna_app_id.get_secret_value(),
                                    settings.adzuna_app_key.get_secret_value(), DatabaseQuota(engine), http)
            run = run_collection(engine, client_factory, options)
        print(f"Run {run['id']}: {run['status']}; pages {run['pages_completed']}/{run['pages_requested']}; "
              f"observations {run['observations_processed']}; new {run['newly_inserted_jobs']}; "
              f"updated {run['existing_jobs_updated']}")
        if run["error_summary"]:
            print(run["error_summary"], file=sys.stderr)
        # Partial work is visible to systemd and operators; it is not a full success.
        return {"success": 0, "partial": 2, "quota_exhausted": 3, "failed": 1}[run["status"]]
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return 75
    except (Exception, KeyboardInterrupt):
        print("Collector could not complete; check database/configuration. An interrupted running row is recovered on the next run.", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    sys.exit(main())
