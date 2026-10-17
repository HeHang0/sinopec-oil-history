from __future__ import annotations

import json
import logging
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .client import BASE_URL, OilPriceClient
from .config import Config
from .git_sync import commit_and_push, ensure_repository, ensure_site_template, prepare_git_environment
from .normalize import parse_payload
from .scheduler import next_run_at, sleep_until
from .storage import build_index, merge_rows, read_rows, write_json


LOG = logging.getLogger("oil-price")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _state_path(config: Config) -> Path:
    return config.state_dir / "fetch_state.json"


def load_last_run(config: Config, timezone: ZoneInfo) -> datetime | None:
    path = _state_path(config)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return datetime.fromisoformat(value["last_run"]).astimezone(timezone)
    except Exception:  # noqa: BLE001
        LOG.warning("ignoring unreadable state file %s", path)
        return None


def save_last_run(config: Config, last_run: datetime) -> None:
    write_json(_state_path(config), {"last_run": last_run.isoformat(timespec="seconds")})


def run_cycle(config: Config, client: OilPriceClient, env: dict[str, str]) -> tuple[int, int, bool]:
    data_dir = config.work_dir / config.data_subdir
    data_dir.mkdir(parents=True, exist_ok=True)
    successes = 0
    failures = 0
    publish_failed = False

    for index, province in enumerate(config.provinces, start=1):
        label = f"[{index}/{len(config.provinces)}] {province.name}({province.code})"
        try:
            payload = client.fetch_history(province)
            upstream_name, rows = parse_payload(payload)
            if not rows:
                LOG.warning("%s returned no price rows", label)
                failures += 1
            else:
                path = data_dir / f"{province.slug}.json"
                existing = read_rows(path)
                merged = merge_rows(existing, rows)
                write_json(path, merged)
                added = len(merged) - len(existing)
                LOG.info(
                    "%s ok: upstream=%s rows=%s added=%s total=%s zones=%s",
                    label,
                    upstream_name or "?",
                    len(rows),
                    added,
                    len(merged),
                    len({row.get("zone") for row in merged if row.get("zone")}),
                )
                successes += 1
        except Exception as exc:  # noqa: BLE001 - continue with other provinces
            failures += 1
            LOG.error("%s failed: %s", label, exc, exc_info=LOG.isEnabledFor(logging.DEBUG))
        if index < len(config.provinces) and config.request_delay > 0:
            time.sleep(config.request_delay)

    if successes:
        index_data = build_index(data_dir, f"{BASE_URL}/yjkqiantai/core/toHistoryOilPrice")
        LOG.info(
            "index built: %s provinces, %s records",
            len(index_data["provinces"]),
            index_data["total_records"],
        )
        message = f"data: update oil prices {datetime.now().date().isoformat()}"
        try:
            commit_and_push(config, env, data_dir, message)
        except Exception as exc:  # noqa: BLE001
            LOG.error("git publish failed: %s", exc)
            failures += 1
            publish_failed = True
    else:
        LOG.error("no province succeeded; data was not published")

    return successes, failures, publish_failed


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    config = Config.from_args(argv)
    timezone = ZoneInfo(config.timezone)
    LOG.info(
        "collector starting: provinces=%s interval=%sd time=%02d:%02d tz=%s repo=%s",
        len(config.provinces),
        config.interval_days,
        config.hour,
        config.minute,
        config.timezone,
        "local" if not config.repo_url else config.repo_url,
    )

    env = prepare_git_environment(config)
    ensure_repository(config, env)
    ensure_site_template(config)

    client = OilPriceClient()

    if config.run_once:
        successes, _, publish_failed = run_cycle(config, client, env)
        return 0 if successes and not publish_failed else 1

    stop_event = threading.Event()

    def handle_stop(signum: int, _frame: object) -> None:
        LOG.info("received signal %s; stopping after the current wait", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    last_run = load_last_run(config, timezone)
    if config.run_on_start or last_run is None:
        started = datetime.now(timezone)
        LOG.info("running initial collection")
        run_cycle(config, client, env)
        last_run = started
        save_last_run(config, last_run)

    while not stop_event.is_set():
        next_run = next_run_at(
            datetime.now(timezone),
            last_run,
            config.interval_days,
            config.hour,
            config.minute,
        )
        LOG.info("next collection at %s", next_run.isoformat(timespec="minutes"))
        if not sleep_until(next_run, stop_event):
            break
        started = datetime.now(timezone)
        run_cycle(config, client, env)
        last_run = started
        save_last_run(config, last_run)

    LOG.info("collector stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
