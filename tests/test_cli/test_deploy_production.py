"""Tests for production deployment CLI workflow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from cli.deploy_production import (
    DeployConfig,
    build_env_content,
    build_lifecycle_commands,
    check_prerequisites,
    deploy,
    parse_csv_list,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_csv_list_trims_and_deduplicates() -> None:
    values = parse_csv_list("example.com, blog.example.com ,example.com,,")
    assert values == ["example.com", "blog.example.com"]


def test_build_env_content_includes_required_production_values() -> None:
    config = DeployConfig(
        secret_key="x" * 64,
        admin_username="admin",
        admin_password="very-strong-password",
        trusted_hosts=["example.com", "www.example.com"],
        trusted_proxy_ips=["172.16.0.1"],
        host_port=8000,
    )

    content = build_env_content(config)

    assert (
        'SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"' in content
    )
    assert 'ADMIN_USERNAME="admin"' in content
    assert 'ADMIN_PASSWORD="very-strong-password"' in content
    assert "DEBUG=false" in content
    assert "HOST=0.0.0.0" in content
    assert "PORT=8000" in content
    assert 'TRUSTED_HOSTS=["example.com","www.example.com"]' in content
    assert 'TRUSTED_PROXY_IPS=["172.16.0.1"]' in content


def test_build_env_content_quotes_special_characters() -> None:
    config = DeployConfig(
        secret_key='abc"def#ghi',
        admin_username="admin user",
        admin_password="pass\\word",
        trusted_hosts=["example.com"],
        trusted_proxy_ips=[],
        host_port=8000,
    )

    content = build_env_content(config)
    assert 'SECRET_KEY="abc\\"def#ghi"' in content
    assert 'ADMIN_USERNAME="admin user"' in content
    assert 'ADMIN_PASSWORD="pass\\\\word"' in content


def test_check_prerequisites_checks_docker_and_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr("cli.deploy_production.shutil.which", lambda _name: "/usr/bin/docker")
    commands: list[tuple[list[str], Path, bool]] = []

    def fake_run(command: list[str], cwd: Path, check: bool) -> SimpleNamespace:
        commands.append((command, cwd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("cli.deploy_production.subprocess.run", fake_run)

    check_prerequisites(tmp_path)

    assert commands == [
        (["/usr/bin/env", "docker", "--version"], tmp_path, True),
        (["/usr/bin/env", "docker", "compose", "version"], tmp_path, True),
    ]


def test_deploy_writes_env_file_and_runs_docker_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    commands: list[tuple[list[str], Path, bool]] = []

    def fake_run(command: list[str], cwd: Path, check: bool) -> SimpleNamespace:
        commands.append((command, cwd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("cli.deploy_production.subprocess.run", fake_run)

    config = DeployConfig(
        secret_key="x" * 64,
        admin_username="admin",
        admin_password="very-strong-password",
        trusted_hosts=["example.com"],
        trusted_proxy_ips=[],
        host_port=8000,
    )

    result = deploy(
        config=config,
        project_dir=tmp_path,
    )

    assert result.env_path == tmp_path / ".env.production"
    assert result.commands["start"] == "docker compose --env-file .env.production up -d"
    assert result.commands["stop"] == "docker compose --env-file .env.production down"
    assert result.commands["status"] == "docker compose --env-file .env.production ps"
    assert commands == [
        (
            [
                "/usr/bin/env",
                "docker",
                "compose",
                "--env-file",
                ".env.production",
                "up",
                "-d",
                "--build",
            ],
            tmp_path,
            True,
        )
    ]


def test_deploy_requires_docker_compose_file(tmp_path: Path) -> None:
    config = DeployConfig(
        secret_key="x" * 64,
        admin_username="admin",
        admin_password="very-strong-password",
        trusted_hosts=["example.com"],
        trusted_proxy_ips=[],
        host_port=8000,
    )

    with pytest.raises(FileNotFoundError, match=r"docker-compose\.yml"):
        deploy(config=config, project_dir=tmp_path)


def test_build_lifecycle_commands_uses_default_env_filename() -> None:
    commands = build_lifecycle_commands()
    assert commands["start"] == "docker compose --env-file .env.production up -d"
    assert commands["stop"] == "docker compose --env-file .env.production down"
    assert commands["status"] == "docker compose --env-file .env.production ps"
