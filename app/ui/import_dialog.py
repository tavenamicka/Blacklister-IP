"""Dialogue d'import/ajout manuel dans l'historique — mêmes contrôles de dédup que l'onglet Cas,
mais sans génération de commandes CLI (sert à enregistrer des blocages déjà en place sur le pare-feu)."""
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

import customtkinter as ctk

import blocker
import db
from db import FIREWALL_LABELS, FIREWALLS
from ui import theme


class ImportDialog(ctk.CTkToplevel):
    def __init__(self, master, on_imported):
        super().__init__(master, fg_color=theme.BG)
        self.on_imported = on_imported
        self.title("Importer / ajouter dans l'historique")
        self.geometry("540x540")
        self.minsize(480, 440)
        self._result: blocker.FirewallResult | None = None
        self._case: db.Case | None = None
        self._firewall: str | None = None

        cases = db.list_cases()
        self._cases_by_name = {c.name: c for c in cases}

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(top, text="Cas :", text_color=theme.MUTED, font=theme.font_body(13)).pack(side="left")
        self.case_menu = ctk.CTkOptionMenu(
            top, values=list(self._cases_by_name) or ["—"], width=200, **theme.option_menu_style()
        )
        self.case_menu.pack(side="left", padx=8)
        ctk.CTkLabel(top, text="Pare-feu :", text_color=theme.MUTED, font=theme.font_body(13)).pack(
            side="left", padx=(12, 0)
        )
        self.fw_menu = ctk.CTkOptionMenu(
            top, values=[FIREWALL_LABELS[fw] for fw in FIREWALLS], width=140, **theme.option_menu_style()
        )
        self.fw_menu.pack(side="left", padx=8)

        ctk.CTkLabel(
            self, text="IP / CIDR / FQDN déjà bloquées à enregistrer (une par ligne)",
            text_color=theme.MUTED, font=theme.font_body(12),
        ).pack(anchor="w", padx=16, pady=(8, 0))
        self.input_box = ctk.CTkTextbox(
            self, height=140, fg_color=theme.SURFACE, text_color=theme.TEXT, font=theme.font_mono(12),
            border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_CONTROL,
        )
        self.input_box.pack(fill="both", expand=True, padx=16, pady=(4, 8))

        file_frame = ctk.CTkFrame(self, fg_color="transparent")
        file_frame.pack(fill="x", padx=16)
        ctk.CTkButton(
            file_frame, text="Charger un fichier...", width=140, command=self._load_file, **theme.btn_secondary()
        ).pack(side="left")

        self.check_btn = ctk.CTkButton(self, text="Vérifier", command=self._check, **theme.btn_secondary())
        self.check_btn.pack(anchor="w", padx=16, pady=(8, 0))

        self.summary_label = ctk.CTkLabel(
            self, text="", justify="left", wraplength=490, text_color=theme.TEXT, font=theme.font_body(12)
        )
        self.summary_label.pack(anchor="w", padx=16, pady=(8, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=16, side="bottom")
        ctk.CTkButton(btn_frame, text="Fermer", command=self.destroy, **theme.btn_secondary()).pack(
            side="right", padx=(8, 0)
        )
        self.confirm_btn = ctk.CTkButton(
            btn_frame, text="Ajouter à l'historique", command=self._confirm, state="disabled",
            **theme.btn_primary(),
        )
        self.confirm_btn.pack(side="right")

        self.transient(master)
        self.grab_set()

    def _load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Texte / CSV", "*.txt *.csv"), ("Tous les fichiers", "*.*")])
        if not path:
            return
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", content)

    def _check(self):
        case_name = self.case_menu.get()
        case = self._cases_by_name.get(case_name)
        if not case:
            messagebox.showwarning("Blacklister IP", "Sélectionnez ou créez d'abord un cas dans l'onglet Cas.")
            return
        firewall = _firewall_from_label(self.fw_menu.get())
        raw_text = self.input_box.get("1.0", "end")
        if not raw_text.strip():
            messagebox.showwarning("Blacklister IP", "Collez au moins une IP/FQDN.")
            return

        result = blocker.process(case, firewall, raw_text)
        self._case = case
        self._firewall = firewall
        self._result = result

        parts = [f"{len(result.new_values)} nouvelle(s) à ajouter"]
        if result.duplicates_in_case:
            parts.append(f"{len(result.duplicates_in_case)} déjà présente(s) dans ce cas (ignorées)")
        if result.cross_case_warnings:
            parts.append(f"{len(result.cross_case_warnings)} déjà bloquée(s) sous un autre cas")
        if result.invalid:
            parts.append(f"{len(result.invalid)} invalide(s) (ignorées) : " + ", ".join(result.invalid))
        self.summary_label.configure(text="\n".join(parts))

        self.confirm_btn.configure(state="normal" if result.new_values else "disabled")

    def _confirm(self):
        if not self._result or not self._result.new_values:
            return
        blocker.save(self._case, self._firewall, self._result.new_values)
        messagebox.showinfo(
            "Blacklister IP", f"{len(self._result.new_values)} entrée(s) ajoutée(s) à l'historique."
        )
        if self.on_imported:
            self.on_imported()
        self.destroy()


def _firewall_from_label(label: str) -> str:
    for fw, fw_label in FIREWALL_LABELS.items():
        if fw_label == label:
            return fw
    raise ValueError(label)
