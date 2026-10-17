from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from .provinces import PROVINCES, Province, resolve_province


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = _env(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise SystemExit(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise SystemExit(f"{name} must be <= {maximum}")
    return value


def _float_env(name: str, default: float, minimum: float = 0.0) -> float:
    raw = _env(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be a number, got {raw!r}") from exc
    if value < minimum:
        raise SystemExit(f"{name} must be >= {minimum}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _parse_provinces(raw: str) -> tuple[Province, ...]:
    if not raw or raw.lower() in {"all", "*"}:
        return PROVINCES
    selected: list[Province] = []
    for item in raw.split(","):
        item = item.strip()
        if item:
            selected.append(resolve_province(item))
    if not selected:
        raise SystemExit("PROVINCES is set but contains no province")
    return tuple(dict.fromkeys(selected))


@dataclass(frozen=True)
class Config:
    repo_url: str
    branch: str
    ssh_key: str
    ssh_key_b64: str
    ssh_host: str
    git_user_name: str
    git_user_email: str
    interval_days: int
    hour: int
    minute: int
    run_on_start: bool
    run_once: bool
    timezone: str
    provinces: tuple[Province, ...]
    work_dir: Path
    state_dir: Path
    data_subdir: str
    request_delay: float
    push_retries: int
    dry_run: bool

    @classmethod
    def from_args(cls, argv: list[str] | None = None) -> "Config":
        parser = argparse.ArgumentParser(
            prog="oil-price-collector",
            description="Collect Sinopec retail oil price history and publish it to a Git repository.",
        )
        parser.add_argument("--once", action="store_true", help="Run one collection cycle and exit.")
        parser.add_argument("--repo-dir", help="Override the working copy directory.")
        parser.add_argument("--provinces", help="Comma-separated province codes/names/slugs.")
        parser.add_argument("--dry-run", action="store_true", help="Write files but do not commit or push.")
        args = parser.parse_args(argv)

        default_work = "/repo" if os.name != "nt" else str(Path.cwd())
        default_state = "/state" if os.name != "nt" else str(Path.cwd() / ".state")

        raw_provinces = args.provinces if args.provinces is not None else _env("PROVINCES", "")
        data_subdir = _env("DATA_SUBDIR", "site/data")
        data_path = Path(data_subdir)
        if data_path.is_absolute() or ".." in data_path.parts:
            raise SystemExit("DATA_SUBDIR must be a relative path inside the repository")

        repo_url = _env("GIT_REPO_URL")
        if repo_url and not (repo_url.startswith("git@") or repo_url.startswith("ssh://")):
            raise SystemExit("GIT_REPO_URL must be an SSH URL (git@host:owner/repo.git or ssh://...)")

        return cls(
            repo_url=repo_url,
            branch=_env("GIT_BRANCH", "main"),
            ssh_key=_env("GIT_SSH_PRIVATE_KEY"),
            ssh_key_b64=_env("GIT_SSH_PRIVATE_KEY_B64"),
            ssh_host=_env("GIT_SSH_HOST", "github.com"),
            git_user_name=_env("GIT_USER_NAME", "oil-price-bot"),
            git_user_email=_env("GIT_USER_EMAIL", "oil-price-bot@users.noreply.github.com"),
            interval_days=_int_env("FETCH_INTERVAL_DAYS", 1, minimum=1),
            hour=_int_env("FETCH_HOUR", 6, minimum=0, maximum=23),
            minute=_int_env("FETCH_MINUTE", 0, minimum=0, maximum=59),
            run_on_start=_bool_env("RUN_ON_START", True),
            run_once=args.once or _bool_env("RUN_ONCE", False),
            timezone=_env("TZ", "Asia/Shanghai"),
            provinces=_parse_provinces(raw_provinces),
            work_dir=Path(args.repo_dir or _env("WORK_DIR", default_work)).expanduser().resolve(),
            state_dir=Path(_env("STATE_DIR", default_state)).expanduser().resolve(),
            data_subdir=data_subdir.replace("\\", "/"),
            request_delay=_float_env("REQUEST_DELAY_SECONDS", 0.4),
            push_retries=_int_env("GIT_PUSH_RETRIES", 3, minimum=1),
            dry_run=args.dry_run or _bool_env("DRY_RUN", False),
        )
