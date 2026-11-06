"""Tests de ssh_client.py — paramiko et subprocess sont mockés : pas de vraie connexion réseau,
pas de vrai terminal lancé."""
import paramiko
import pytest
import ssh_client


@pytest.fixture(autouse=True)
def _reset_session_login(monkeypatch):
    """La mémorisation du login est un global module (en mémoire pour la session, cf. docstring
    de ssh_client.py) — on l'isole entre les tests pour ne pas polluer l'ordre d'exécution."""
    monkeypatch.setattr(ssh_client, "_session_login", None)


def test_login_not_remembered_by_default():
    assert ssh_client.get_remembered_login() is None


def test_remember_login_roundtrip():
    ssh_client.remember_login("jdupont")
    assert ssh_client.get_remembered_login() == "jdupont"


def test_open_terminal_raises_if_ssh_missing(monkeypatch):
    monkeypatch.setattr(ssh_client.shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError):
        ssh_client.open_terminal("10.1.0.1", 22, "jdupont")


def test_open_terminal_prefers_windows_terminal(monkeypatch):
    monkeypatch.setattr(
        ssh_client.shutil, "which", lambda name: f"C:/fake/{name}.exe" if name in ("ssh", "wt") else None
    )
    calls = []
    monkeypatch.setattr(ssh_client.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))

    ssh_client.open_terminal("10.1.0.1", 2222, "jdupont")

    assert len(calls) == 1
    assert calls[0][0].endswith("wt.exe")
    assert "jdupont@10.1.0.1" in calls[0]
    assert "2222" in calls[0]


def test_open_terminal_falls_back_to_cmd_without_windows_terminal(monkeypatch):
    monkeypatch.setattr(ssh_client.shutil, "which", lambda name: "C:/fake/ssh.exe" if name == "ssh" else None)
    calls = []
    monkeypatch.setattr(ssh_client.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))

    ssh_client.open_terminal("10.1.0.1", 22, "jdupont")

    assert len(calls) == 1
    assert calls[0][0] == "cmd.exe"
    assert "jdupont@10.1.0.1" in calls[0]


class _FakeChannel:
    def __init__(self, replies: dict[str, str]):
        self._replies = replies
        self._pending = ""

    def send(self, data: str):
        self._pending += self._replies.get(data.strip(), "")

    def recv_ready(self) -> bool:
        return bool(self._pending)

    def recv(self, _n: int) -> bytes:
        data, self._pending = self._pending, ""
        return data.encode()


class _FakeSSHClient:
    connections: list[dict] = []

    def __init__(self):
        self.closed = False

    def set_missing_host_key_policy(self, _policy):
        pass

    def connect(self, host, port, username, password, timeout, banner_timeout, auth_timeout):
        _FakeSSHClient.connections.append(
            {"host": host, "port": port, "username": username, "password": password}
        )

    def invoke_shell(self):
        return _FakeChannel({"set address obj1 ip-netmask 1.2.3.4/32": "ok\n"})

    def close(self):
        self.closed = True


def test_push_commands_sends_lines_and_returns_output(monkeypatch):
    _FakeSSHClient.connections = []
    monkeypatch.setattr(ssh_client.paramiko, "SSHClient", _FakeSSHClient)

    output = ssh_client.push_commands(
        "10.1.0.1", 22, "jdupont", "secret", "set address obj1 ip-netmask 1.2.3.4/32",
    )

    assert "ok" in output
    assert _FakeSSHClient.connections == [
        {"host": "10.1.0.1", "port": 22, "username": "jdupont", "password": "secret"}
    ]


def test_push_commands_wraps_authentication_failure(monkeypatch):
    class _FailingAuthClient(_FakeSSHClient):
        def connect(self, *args, **kwargs):
            raise paramiko.AuthenticationException()

    monkeypatch.setattr(ssh_client.paramiko, "SSHClient", _FailingAuthClient)

    with pytest.raises(ssh_client.SSHPushError):
        ssh_client.push_commands("10.1.0.1", 22, "jdupont", "wrong", "set address obj1")


def test_push_commands_wraps_connection_failure(monkeypatch):
    class _UnreachableClient(_FakeSSHClient):
        def connect(self, *args, **kwargs):
            raise OSError("no route to host")

    monkeypatch.setattr(ssh_client.paramiko, "SSHClient", _UnreachableClient)

    with pytest.raises(ssh_client.SSHPushError):
        ssh_client.push_commands("10.1.0.1", 22, "jdupont", "secret", "set address obj1")
