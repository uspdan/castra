"""Phase 9 — refusal layer for sandbox-breaking docker-py kwargs."""

from __future__ import annotations

import pytest

from app.services.orchestration.forbidden import (
    ForbiddenContainerOption,
    enforce_no_forbidden,
)


_BASE = {
    "image": "siege/test@sha256:" + "0" * 64,
    "name": "siege-1-test",
    "detach": True,
    "read_only": True,
    "tmpfs": {"/tmp": "size=64M"},
    "mem_limit": "256m",
    "pids_limit": 128,
    "cap_drop": ["ALL"],
    "cap_add": [],
    "security_opt": ["no-new-privileges:true"],
    "network": "siege-ch-1-x",
    "ports": {"8080/tcp": 12345},
}


def test_baseline_kwargs_pass() -> None:
    enforce_no_forbidden(_BASE)


def test_privileged_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="privileged"):
        enforce_no_forbidden({**_BASE, "privileged": True})


def test_network_mode_host_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="network_mode"):
        enforce_no_forbidden({**_BASE, "network_mode": "host"})


def test_pid_mode_host_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="pid_mode"):
        enforce_no_forbidden({**_BASE, "pid_mode": "host"})


def test_ipc_mode_host_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="ipc_mode"):
        enforce_no_forbidden({**_BASE, "ipc_mode": "host"})


def test_userns_mode_host_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="userns_mode"):
        enforce_no_forbidden({**_BASE, "userns_mode": "host"})


def test_cap_add_sys_admin_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="SYS_ADMIN"):
        enforce_no_forbidden({**_BASE, "cap_add": ["SYS_ADMIN"]})


def test_cap_add_net_admin_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="NET_ADMIN"):
        enforce_no_forbidden({**_BASE, "cap_add": ["NET_ADMIN"]})


def test_volume_mount_docker_socket_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="docker.sock"):
        enforce_no_forbidden(
            {**_BASE, "volumes": {"/var/run/docker.sock": {"bind": "/sock"}}}
        )


def test_volume_mount_proc_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="/proc"):
        enforce_no_forbidden(
            {**_BASE, "volumes": {"/proc/sys": {"bind": "/p"}}}
        )


def test_binds_kwarg_refused() -> None:
    with pytest.raises(ForbiddenContainerOption, match="binds"):
        enforce_no_forbidden({**_BASE, "binds": ["/etc:/etc"]})
