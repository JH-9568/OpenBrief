from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import tomllib
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from threading import Timer

from sqlalchemy.ext.asyncio import create_async_engine

from teampulse.models import Base

HOME_ENV = "TEAMPULSE_HOME"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


@dataclass(frozen=True)
class LocalConfig:
    home: Path
    config_path: Path
    database_url: str
    host: str
    port: int
    open_browser: bool
    log_path: Path
    pid_path: Path
    run_path: Path

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.host}:{self.port}/dashboard"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="teampulse",
        description="TeamPulse local app launcher",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create local TeamPulse config and DB")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    init_parser.add_argument("--home", type=Path, help="Override TeamPulse local app directory")
    init_parser.set_defaults(func=init_command)

    start_parser = subparsers.add_parser("start", help="Start the local TeamPulse web app")
    start_parser.add_argument("--daemon", action="store_true", help="Run in the background")
    start_parser.add_argument("--host", default=None, help="Host to bind")
    start_parser.add_argument("--port", type=int, default=None, help="Port to bind")
    start_parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    start_parser.add_argument("--home", type=Path, help="Override TeamPulse local app directory")
    start_parser.set_defaults(func=start_command)

    stop_parser = subparsers.add_parser("stop", help="Stop a background TeamPulse process")
    stop_parser.add_argument("--home", type=Path, help="Override TeamPulse local app directory")
    stop_parser.set_defaults(func=stop_command)

    status_parser = subparsers.add_parser("status", help="Show local TeamPulse process status")
    status_parser.add_argument("--home", type=Path, help="Override TeamPulse local app directory")
    status_parser.set_defaults(func=status_command)

    serve_parser = subparsers.add_parser("_serve", help=argparse.SUPPRESS)
    serve_parser.add_argument("--home", type=Path, required=True)
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.add_argument("--no-browser", action="store_true")
    serve_parser.set_defaults(func=serve_command)

    return parser


def init_command(args: argparse.Namespace) -> int:
    config = ensure_initialized(home_arg=args.home, force=args.force)
    print(f"TeamPulse local app initialized at {config.home}")
    print(f"Config: {config.config_path}")
    print(f"Dashboard: {config.dashboard_url}")
    return 0


def start_command(args: argparse.Namespace) -> int:
    config = ensure_initialized(home_arg=args.home, force=False)
    config = with_overrides(
        config,
        host=args.host,
        port=args.port,
        open_browser=False if args.no_browser else None,
    )

    if is_running(config.pid_path):
        pid = config.pid_path.read_text(encoding="utf-8").strip()
        print(f"TeamPulse is already running with PID {pid}")
        print(f"Dashboard: {config.dashboard_url}")
        return 0

    if args.daemon:
        return start_daemon(config)

    return run_server(config)


def stop_command(args: argparse.Namespace) -> int:
    config = load_or_default_config(home_arg=args.home)
    if not config.pid_path.exists():
        print("TeamPulse is not running.")
        return 0

    pid_text = config.pid_path.read_text(encoding="utf-8").strip()
    if not pid_text.isdigit():
        config.pid_path.unlink(missing_ok=True)
        print("Removed invalid TeamPulse PID file.")
        return 0

    pid = int(pid_text)
    if not process_exists(pid):
        config.pid_path.unlink(missing_ok=True)
        print("TeamPulse was not running. Removed stale PID file.")
        return 0

    os.kill(pid, signal.SIGTERM)
    config.pid_path.unlink(missing_ok=True)
    config.run_path.unlink(missing_ok=True)
    print(f"Stopped TeamPulse PID {pid}.")
    return 0


def status_command(args: argparse.Namespace) -> int:
    config = load_or_default_config(home_arg=args.home)
    if is_running(config.pid_path):
        pid = config.pid_path.read_text(encoding="utf-8").strip()
        runtime_url = runtime_dashboard_url(config) or config.dashboard_url
        print(f"TeamPulse is running with PID {pid}")
        print(f"Dashboard: {runtime_url}")
        return 0

    print("TeamPulse is not running.")
    print(f"Config: {config.config_path}")
    return 0


def serve_command(args: argparse.Namespace) -> int:
    config = ensure_initialized(home_arg=args.home, force=False)
    config = with_overrides(
        config,
        host=args.host,
        port=args.port,
        open_browser=False if args.no_browser else None,
    )
    return run_server(config)


def start_daemon(config: LocalConfig) -> int:
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = config.log_path.open("ab")
    command = [
        sys.executable,
        "-m",
        "teampulse.cli",
        "_serve",
        "--home",
        str(config.home),
        "--host",
        config.host,
        "--port",
        str(config.port),
    ]
    if not config.open_browser:
        command.append("--no-browser")

    process = subprocess.Popen(  # noqa: S603
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    time.sleep(0.5)
    if process.poll() is not None:
        print(f"TeamPulse failed to start. Check log: {config.log_path}")
        return process.returncode or 1

    print(f"Started TeamPulse in the background with PID {process.pid}")
    print(f"Dashboard: {config.dashboard_url}")
    print(f"Log: {config.log_path}")
    return 0


def run_server(config: LocalConfig) -> int:
    apply_runtime_env(config)
    config.pid_path.parent.mkdir(parents=True, exist_ok=True)
    config.pid_path.write_text(str(os.getpid()), encoding="utf-8")
    write_runtime(config)

    if config.open_browser:
        Timer(1.0, webbrowser.open, args=(config.dashboard_url,)).start()

    try:
        import uvicorn

        uvicorn.run("teampulse.main:app", host=config.host, port=config.port)
    finally:
        if config.pid_path.exists() and config.pid_path.read_text(encoding="utf-8") == str(
            os.getpid()
        ):
            config.pid_path.unlink(missing_ok=True)
            config.run_path.unlink(missing_ok=True)
    return 0


def ensure_initialized(home_arg: Path | None, force: bool) -> LocalConfig:
    config = load_or_default_config(home_arg=home_arg)
    config.home.mkdir(parents=True, exist_ok=True)
    config.log_path.parent.mkdir(parents=True, exist_ok=True)

    if force or not config.config_path.exists():
        write_config(config)
    asyncio.run(create_database(config.database_url))
    return config


async def create_database(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def load_or_default_config(home_arg: Path | None) -> LocalConfig:
    home = local_home(home_arg)
    config_path = home / "config.toml"
    default = default_config(home)
    if not config_path.exists():
        return default

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    server = data.get("server", {})
    database = data.get("database", {})
    app = data.get("app", {})
    return LocalConfig(
        home=home,
        config_path=config_path,
        database_url=str(database.get("url", default.database_url)),
        host=str(server.get("host", default.host)),
        port=int(server.get("port", default.port)),
        open_browser=bool(app.get("open_browser", default.open_browser)),
        log_path=Path(app.get("log_path", default.log_path)).expanduser(),
        pid_path=Path(app.get("pid_path", default.pid_path)).expanduser(),
        run_path=Path(app.get("run_path", default.run_path)).expanduser(),
    )


def default_config(home: Path) -> LocalConfig:
    database_path = home / "teampulse.db"
    return LocalConfig(
        home=home,
        config_path=home / "config.toml",
        database_url=sqlite_url(database_path),
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        open_browser=True,
        log_path=home / "logs" / "teampulse.log",
        pid_path=home / "teampulse.pid",
        run_path=home / "run.json",
    )


def with_overrides(
    config: LocalConfig,
    *,
    host: str | None,
    port: int | None,
    open_browser: bool | None,
) -> LocalConfig:
    return LocalConfig(
        home=config.home,
        config_path=config.config_path,
        database_url=config.database_url,
        host=host or config.host,
        port=port or config.port,
        open_browser=config.open_browser if open_browser is None else open_browser,
        log_path=config.log_path,
        pid_path=config.pid_path,
        run_path=config.run_path,
    )


def write_config(config: LocalConfig) -> None:
    config.config_path.write_text(
        f"""# TeamPulse local app config

[server]
host = "{config.host}"
port = {config.port}

[database]
url = "{config.database_url}"

[app]
open_browser = {str(config.open_browser).lower()}
log_path = "{config.log_path}"
pid_path = "{config.pid_path}"
run_path = "{config.run_path}"
""",
        encoding="utf-8",
    )


def apply_runtime_env(config: LocalConfig) -> None:
    os.environ.setdefault("DATABASE_URL", config.database_url)
    os.environ.setdefault("ENVIRONMENT", "local")


def local_home(home_arg: Path | None = None) -> Path:
    if home_arg is not None:
        return home_arg.expanduser().resolve()
    if env_home := os.environ.get(HOME_ENV):
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".teampulse").resolve()


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.expanduser().resolve()}"


def write_runtime(config: LocalConfig) -> None:
    config.run_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "host": config.host,
                "port": config.port,
                "dashboard_url": config.dashboard_url,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def runtime_dashboard_url(config: LocalConfig) -> str | None:
    if not config.run_path.exists():
        return None
    try:
        data = json.loads(config.run_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data.get("dashboard_url")


def is_running(pid_path: Path) -> bool:
    if not pid_path.exists():
        return False
    pid_text = pid_path.read_text(encoding="utf-8").strip()
    return pid_text.isdigit() and process_exists(int(pid_text))


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


if __name__ == "__main__":
    raise SystemExit(main())
