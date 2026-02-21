"""Tests for production deployment CLI workflow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from cli.deploy_production import (
    DEFAULT_CADDY_PUBLIC_COMPOSE_FILE,
    DEFAULT_NO_CADDY_COMPOSE_FILE,
    LOCALHOST_BIND_IP,
    PUBLIC_BIND_IP,
    CaddyConfig,
    DeployConfig,
    build_caddy_public_compose_override_content,
    build_caddyfile_content,
    build_direct_compose_content,
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
        host_bind_ip=PUBLIC_BIND_IP,
        caddy_config=None,
        caddy_public=False,
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
    assert f"HOST_BIND_IP={PUBLIC_BIND_IP}" in content
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
        host_bind_ip=LOCALHOST_BIND_IP,
        caddy_config=None,
        caddy_public=False,
    )

    content = build_env_content(config)
    assert 'SECRET_KEY="abc\\"def#ghi"' in content
    assert 'ADMIN_USERNAME="admin user"' in content
    assert 'ADMIN_PASSWORD="pass\\\\word"' in content


def test_build_caddyfile_content_includes_domain_and_optional_email() -> None:
    caddy = CaddyConfig(domain="blog.example.com", email="ops@example.com")
    content = build_caddyfile_content(caddy)
    assert "email ops@example.com" in content
    assert "blog.example.com {" in content
    assert "reverse_proxy agblogger:8000" in content


def test_build_direct_compose_content_uses_host_bind_and_port() -> None:
    content = build_direct_compose_content()
    assert "${HOST_BIND_IP:-127.0.0.1}:${HOST_PORT:-8000}:8000" in content
    assert "caddy:" not in content


def test_build_caddy_public_override_exposes_ports() -> None:
    content = build_caddy_public_compose_override_content()
    assert '"80:80"' in content
    assert '"443:443"' in content


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


def test_deploy_writes_env_file_and_runs_docker_compose_without_caddy(
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
        host_bind_ip=PUBLIC_BIND_IP,
        caddy_config=None,
        caddy_public=False,
    )

    result = deploy(config=config, project_dir=tmp_path)

    assert result.env_path == tmp_path / ".env.production"
    assert (
        result.commands["start"]
        == "docker compose --env-file .env.production -f docker-compose.nocaddy.yml up -d"
    )
    assert (tmp_path / DEFAULT_NO_CADDY_COMPOSE_FILE).exists()
    assert not (tmp_path / "Caddyfile.production").exists()
    assert not (tmp_path / DEFAULT_CADDY_PUBLIC_COMPOSE_FILE).exists()
    assert commands == [
        (
            [
                "/usr/bin/env",
                "docker",
                "compose",
                "--env-file",
                ".env.production",
                "-f",
                "docker-compose.nocaddy.yml",
                "up",
                "-d",
                "--build",
            ],
            tmp_path,
            True,
        )
    ]


def test_deploy_with_public_caddy_writes_override_and_runs_multi_file_compose(
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
        trusted_hosts=["blog.example.com"],
        trusted_proxy_ips=[],
        host_port=8000,
        host_bind_ip=LOCALHOST_BIND_IP,
        caddy_config=CaddyConfig(domain="blog.example.com", email="ops@example.com"),
        caddy_public=True,
    )

    result = deploy(config=config, project_dir=tmp_path)

    assert not (tmp_path / DEFAULT_NO_CADDY_COMPOSE_FILE).exists()
    assert (tmp_path / "Caddyfile.production").exists()
    assert (tmp_path / DEFAULT_CADDY_PUBLIC_COMPOSE_FILE).exists()
    assert (
        result.commands["start"]
        == "docker compose --env-file .env.production -f docker-compose.yml "
        "-f docker-compose.caddy-public.yml up -d"
    )
    assert commands == [
        (
            [
                "/usr/bin/env",
                "docker",
                "compose",
                "--env-file",
                ".env.production",
                "-f",
                "docker-compose.yml",
                "-f",
                "docker-compose.caddy-public.yml",
                "up",
                "-d",
                "--build",
            ],
            tmp_path,
            True,
        )
    ]


def test_deploy_with_local_caddy_runs_base_compose(
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
        trusted_hosts=["blog.example.com"],
        trusted_proxy_ips=[],
        host_port=8000,
        host_bind_ip=LOCALHOST_BIND_IP,
        caddy_config=CaddyConfig(domain="blog.example.com", email=None),
        caddy_public=False,
    )

    result = deploy(config=config, project_dir=tmp_path)

    assert result.commands["start"] == "docker compose --env-file .env.production up -d"
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
        host_bind_ip=PUBLIC_BIND_IP,
        caddy_config=None,
        caddy_public=False,
    )

    with pytest.raises(FileNotFoundError, match=r"docker-compose\.yml"):
        deploy(config=config, project_dir=tmp_path)


def test_build_lifecycle_commands_for_default_caddy() -> None:
    commands = build_lifecycle_commands(use_caddy=True, caddy_public=False)
    assert commands["start"] == "docker compose --env-file .env.production up -d"
    assert commands["stop"] == "docker compose --env-file .env.production down"
    assert commands["status"] == "docker compose --env-file .env.production ps"


def test_build_lifecycle_commands_for_public_caddy_override() -> None:
    commands = build_lifecycle_commands(use_caddy=True, caddy_public=True)
    assert (
        commands["start"] == "docker compose --env-file .env.production -f docker-compose.yml "
        "-f docker-compose.caddy-public.yml up -d"
    )


def test_build_lifecycle_commands_for_no_caddy_file() -> None:
    commands = build_lifecycle_commands(use_caddy=False, caddy_public=False)
    assert (
        commands["start"]
        == "docker compose --env-file .env.production -f docker-compose.nocaddy.yml up -d"
    )
