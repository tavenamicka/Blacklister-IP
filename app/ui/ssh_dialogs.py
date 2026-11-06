"""Dialogues SSH partagés par l'onglet Pare-feu (lancement terminal seul) et l'onglet Cas
(lancement terminal + envoi des commandes générées) — cf. ssh_client.py."""
import re
import tkinter.messagebox as messagebox

import customtkinter as ctk
import db
import ssh_client

from ui import theme

_LOGIN_RE = re.compile(r"^\S+$")


class LoginPromptDialog(ctk.CTkToplevel):
    """Demande juste l'utilisateur SSH avant de lancer un terminal — le mot de passe est saisi
    par l'opérateur dans ce terminal, l'appli ne le voit jamais."""

    def __init__(self, master, device: db.Device):
        super().__init__(master, fg_color=theme.BG)
        self.title("Terminal SSH")
        self.geometry("360x190")
        self.resizable(False, False)
        self.result: str | None = None

        ctk.CTkLabel(
            self, text=f"{device.name} ({device.site}) — {device.host}:{device.ssh_port}",
            text_color=theme.TEXT, font=theme.font_heading(13), wraplength=330, justify="left",
        ).pack(anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(self, text="Utilisateur SSH", text_color=theme.MUTED, font=theme.font_body(12)).pack(
            anchor="w", padx=16, pady=(12, 0)
        )
        self.login_entry = ctk.CTkEntry(self, placeholder_text="ex: jdupont", **theme.entry_style())
        self.login_entry.pack(fill="x", padx=16)
        remembered = ssh_client.get_remembered_login()
        if remembered:
            self.login_entry.insert(0, remembered)
        self.login_entry.bind("<Return>", lambda e: self._submit())

        self.error_label = ctk.CTkLabel(self, text="", text_color=theme.DANGER, font=theme.font_body(12))
        self.error_label.pack(anchor="w", padx=16, pady=(4, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=16, side="bottom")
        ctk.CTkButton(btn_frame, text="Annuler", command=self.destroy, **theme.btn_secondary()).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(
            btn_frame, text="Ouvrir le terminal", command=self._submit, **theme.btn_primary()
        ).pack(side="right")

        self.transient(master)
        self.grab_set()
        self.login_entry.focus()

    def _submit(self):
        login = self.login_entry.get().strip()
        if not login or not _LOGIN_RE.match(login):
            self.error_label.configure(text="Utilisateur requis (pas d'espace).")
            return
        self.result = login
        self.destroy()


def open_terminal_flow(master, device: db.Device) -> None:
    """Demande l'utilisateur SSH puis lance le terminal — à appeler depuis un bouton 'Terminal
    SSH', que ce soit l'onglet Pare-feu (consultation libre) ou l'onglet Cas (depuis un résultat
    généré pour ce device)."""
    dialog = LoginPromptDialog(master, device)
    master.wait_window(dialog)
    if not dialog.result:
        return
    ssh_client.remember_login(dialog.result)
    try:
        ssh_client.open_terminal(device.host, device.ssh_port, dialog.result)
    except RuntimeError as exc:
        messagebox.showerror("Blacklister IP", str(exc))


class SSHPushDialog(ctk.CTkToplevel):
    """Écran de confirmation + envoi : montre le device cible et les commandes exactes avant de
    rien envoyer, demande utilisateur/mot de passe (jamais stockés), puis affiche la sortie brute
    du pare-feu pour que l'opérateur vérifie lui-même le résultat."""

    def __init__(self, master, device: db.Device, commands: str):
        super().__init__(master, fg_color=theme.BG)
        self.device = device
        self.commands = commands
        self.title("Envoyer via SSH")
        self.geometry("560x560")
        self.resizable(False, False)

        ctk.CTkLabel(
            self, text=f"{device.name} ({device.site}) — {device.host}:{device.ssh_port}",
            text_color=theme.TEXT, font=theme.font_heading(14),
        ).pack(anchor="w", padx=16, pady=(16, 0))
        n_lines = len(commands.splitlines())
        ctk.CTkLabel(
            self, text=f"{n_lines} ligne(s) de commande à envoyer, exactement comme ci-dessous :",
            text_color=theme.MUTED, font=theme.font_body(12),
        ).pack(anchor="w", padx=16, pady=(8, 0))

        preview = ctk.CTkTextbox(
            self, height=140, wrap="none", fg_color=theme.CODE_BG, text_color=theme.CODE_TEXT,
            font=theme.font_mono(11), corner_radius=theme.RADIUS_CONTROL,
        )
        preview.pack(fill="x", padx=16, pady=(4, 8))
        preview.insert("1.0", commands)
        preview.configure(state="disabled")

        creds = ctk.CTkFrame(self, fg_color="transparent")
        creds.pack(fill="x", padx=16)
        login_col = ctk.CTkFrame(creds, fg_color="transparent")
        login_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(login_col, text="Utilisateur", text_color=theme.MUTED, font=theme.font_body(12)).pack(
            anchor="w"
        )
        self.login_entry = ctk.CTkEntry(login_col, **theme.entry_style())
        self.login_entry.pack(fill="x")
        remembered = ssh_client.get_remembered_login()
        if remembered:
            self.login_entry.insert(0, remembered)
        pwd_col = ctk.CTkFrame(creds, fg_color="transparent")
        pwd_col.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ctk.CTkLabel(pwd_col, text="Mot de passe", text_color=theme.MUTED, font=theme.font_body(12)).pack(
            anchor="w"
        )
        self.password_entry = ctk.CTkEntry(pwd_col, show="•", **theme.entry_style())
        self.password_entry.pack(fill="x")
        self.password_entry.bind("<Return>", lambda e: self._send())

        self.status_label = ctk.CTkLabel(
            self, text="", text_color=theme.DANGER, font=theme.font_body(12), wraplength=520, justify="left",
        )
        self.status_label.pack(anchor="w", padx=16, pady=(8, 0))

        self.output_box = ctk.CTkTextbox(
            self, height=130, wrap="word", fg_color=theme.SURFACE_2, text_color=theme.TEXT,
            font=theme.font_mono(11), corner_radius=theme.RADIUS_CONTROL,
        )

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=16, side="bottom")
        ctk.CTkButton(btn_frame, text="Fermer", command=self.destroy, **theme.btn_secondary()).pack(
            side="right", padx=(8, 0)
        )
        self.send_btn = ctk.CTkButton(btn_frame, text="Envoyer", command=self._send, **theme.btn_primary())
        self.send_btn.pack(side="right")

        self.transient(master)
        self.grab_set()
        self.login_entry.focus()

    def _send(self):
        login = self.login_entry.get().strip()
        password = self.password_entry.get()
        if not login or not password:
            self.status_label.configure(text="Utilisateur et mot de passe requis.", text_color=theme.DANGER)
            return

        self.send_btn.configure(state="disabled", text="Envoi en cours...")
        self.status_label.configure(text="")
        self.update()
        try:
            output = ssh_client.push_commands(self.device.host, self.device.ssh_port, login, password, self.commands)
        except ssh_client.SSHPushError as exc:
            self.status_label.configure(text=str(exc), text_color=theme.DANGER)
            self.send_btn.configure(state="normal", text="Envoyer")
            return

        ssh_client.remember_login(login)
        self.status_label.configure(
            text="Commandes envoyées — vérifie la sortie ci-dessous avant de considérer le blocage effectif.",
            text_color=theme.SUCCESS,
        )
        self.output_box.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        self.output_box.insert("1.0", output.strip() or "(aucune sortie reçue)")
        self.output_box.configure(state="disabled")
        self.send_btn.configure(state="disabled", text="Envoyé ✓")
