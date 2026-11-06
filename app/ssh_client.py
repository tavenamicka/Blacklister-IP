"""SSH vers les pare-feu du registre `devices` — pas d'API possible sur ces équipements.

Deux usages, cf. SUIVI.md :
- `open_terminal` : lance un terminal local déjà pointé sur le device (host/port/login), le mot
  de passe est tapé par l'opérateur dans ce terminal, l'appli ne le voit jamais.
- `push_commands` : envoie les commandes générées via un canal shell SSH interactif (paramiko) et
  retourne la sortie brute, affichée à l'opérateur pour qu'il vérifie lui-même le résultat.

Rien n'est jamais persisté sur disque : seul le dernier login saisi est gardé en mémoire pour la
durée de la session (cf. `remember_login`/`get_remembered_login`), le mot de passe jamais."""
import shutil
import subprocess
import time

import paramiko

_session_login: str | None = None


def get_remembered_login() -> str | None:
    return _session_login


def remember_login(login: str) -> None:
    global _session_login
    _session_login = login


class SSHPushError(Exception):
    """Connexion/authentification SSH échouée — message déjà prêt pour affichage à l'opérateur."""


def open_terminal(host: str, port: int, login: str) -> None:
    """Ouvre un terminal local avec une commande `ssh` déjà prête (host/port/login) ; le mot de
    passe est saisi par l'opérateur dans ce terminal, jamais vu par l'appli."""
    if not shutil.which("ssh"):
        raise RuntimeError(
            "Client SSH introuvable (ssh.exe absent du PATH) — installez le client OpenSSH de Windows."
        )
    ssh_cmd = ["ssh", f"{login}@{host}", "-p", str(port)]
    wt = shutil.which("wt") or shutil.which("wt.exe")
    if wt:
        subprocess.Popen([wt, *ssh_cmd])
    else:
        subprocess.Popen(["cmd.exe", "/c", "start", "cmd", "/k", *ssh_cmd])


def push_commands(host: str, port: int, login: str, password: str, commands: str, timeout: float = 10.0) -> str:
    """Envoie `commands` (bloc multi-lignes déjà généré par un `generators/*`) dans un canal shell
    SSH interactif — nécessaire pour les blocs multi-commandes avec état (config .../end chez
    Fortinet, conf t chez Cisco ASA...), un `exec_command` par ligne ouvrirait une session neuve
    à chaque fois et perdrait ce contexte. Retourne la sortie brute capturée (pas d'interprétation
    des erreurs : à l'opérateur de la relire)."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            host, port=port, username=login, password=password,
            timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
        )
    except paramiko.AuthenticationException as exc:
        raise SSHPushError("Authentification refusée (utilisateur/mot de passe).") from exc
    except (paramiko.SSHException, OSError) as exc:
        raise SSHPushError(f"Connexion impossible : {exc}") from exc

    try:
        shell = client.invoke_shell()
        time.sleep(0.5)
        output: list[str] = []
        if shell.recv_ready():
            output.append(shell.recv(65535).decode(errors="replace"))  # bannière de connexion
        for line in commands.splitlines():
            shell.send(line + "\n")
            time.sleep(0.15)
            while shell.recv_ready():
                output.append(shell.recv(65535).decode(errors="replace"))
        time.sleep(0.5)
        while shell.recv_ready():
            output.append(shell.recv(65535).decode(errors="replace"))
        return "".join(output)
    finally:
        client.close()
