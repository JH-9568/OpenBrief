import json
import os
from pathlib import Path

from teampulse import cli


def test_init_creates_local_config_and_sqlite_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(cli.HOME_ENV, str(tmp_path))

    exit_code = cli.main(["init"])

    assert exit_code == 0
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "teampulse.db").exists()
    assert "TeamPulse local app initialized" in capsys.readouterr().out


def test_status_reports_not_running_for_fresh_local_home(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(cli.HOME_ENV, str(tmp_path))

    exit_code = cli.main(["status"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "TeamPulse is not running." in output
    assert str(Path(tmp_path) / "config.toml") in output


def test_default_config_uses_sqlite_database_in_local_home(tmp_path):
    config = cli.default_config(tmp_path)

    assert config.database_url.startswith("sqlite+aiosqlite:///")
    assert config.database_url.endswith("/teampulse.db")
    assert config.dashboard_url == "http://127.0.0.1:8000/dashboard"


def test_status_uses_runtime_dashboard_url(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(cli.HOME_ENV, str(tmp_path))
    config = cli.default_config(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    cli.write_config(config)
    config.pid_path.write_text(str(os.getpid()), encoding="utf-8")
    config.run_path.write_text(
        json.dumps({"dashboard_url": "http://127.0.0.1:8010/dashboard"}),
        encoding="utf-8",
    )

    exit_code = cli.main(["status"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "TeamPulse is running" in output
    assert "http://127.0.0.1:8010/dashboard" in output
