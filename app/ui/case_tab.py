"""Onglet 'Cas' : sélection/création de cas, saisie des IP/FQDN, génération et sauvegarde."""
import re
import sqlite3
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

import customtkinter as ctk

import blocker
import db
from db import FIREWALL_LABELS, FIREWALLS
from ui import theme

_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")
_PREFIX_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _default_prefix(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip()).strip("-")
    return f"IOC-case-{slug}" if slug else "IOC-case"


class CaseDialog(ctk.CTkToplevel):
    """Dialogue de création OU de modification d'un cas (case=None -> création)."""

    def __init__(self, master, case: db.Case | None = None):
        super().__init__(master, fg_color=theme.BG)
        self._editing_case = case
        self.title("Modifier le cas" if case else "Nouveau cas")
        self.geometry("440x320")
        self.resizable(False, False)
        self.result: db.Case | None = None
        self._prefix_edited = case is not None  # ne pas écraser un préfixe existant à l'édition
        # ne pas écraser un préfixe de groupe déjà distinct du préfixe des objets à l'édition
        self._group_prefix_edited = case is not None and case.group_prefix != case.prefix

        ctk.CTkLabel(self, text="Nom du cas", text_color=theme.MUTED, font=theme.font_body(12)).pack(
            anchor="w", padx=16, pady=(16, 0)
        )
        self.name_entry = ctk.CTkEntry(self, placeholder_text="ex: iTrust", **theme.entry_style())
        self.name_entry.pack(fill="x", padx=16)
        self.name_entry.bind("<KeyRelease>", self._on_name_changed)
        self.name_entry.bind("<Return>", lambda e: self._submit())

        ctk.CTkLabel(
            self, text="Préfixe des objets", text_color=theme.MUTED, font=theme.font_body(12)
        ).pack(anchor="w", padx=16, pady=(12, 0))
        self.prefix_entry = ctk.CTkEntry(self, placeholder_text="ex: IOC-case-iTrust", **theme.entry_style())
        self.prefix_entry.pack(fill="x", padx=16)
        self.prefix_entry.bind("<KeyRelease>", self._on_prefix_changed)
        self.prefix_entry.bind("<Return>", lambda e: self._submit())

        ctk.CTkLabel(
            self, text="Préfixe du groupe (si différent des objets)", text_color=theme.MUTED,
            font=theme.font_body(12),
        ).pack(anchor="w", padx=16, pady=(12, 0))
        self.group_prefix_entry = ctk.CTkEntry(
            self, placeholder_text="ex: IOC-case-iTrust", **theme.entry_style()
        )
        self.group_prefix_entry.pack(fill="x", padx=16)
        self.group_prefix_entry.bind("<KeyRelease>", lambda e: setattr(self, "_group_prefix_edited", True))
        self.group_prefix_entry.bind("<Return>", lambda e: self._submit())

        if case:
            self.name_entry.insert(0, case.name)
            self.prefix_entry.insert(0, case.prefix)
            self.group_prefix_entry.insert(0, case.group_prefix)

        self.error_label = ctk.CTkLabel(
            self, text="", text_color=theme.DANGER, font=theme.font_body(12), justify="left", wraplength=390
        )
        self.error_label.pack(anchor="w", padx=16, pady=(4, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=16, side="bottom")
        ctk.CTkButton(btn_frame, text="Annuler", command=self.destroy, **theme.btn_secondary()).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(
            btn_frame, text="Enregistrer" if case else "Créer", command=self._submit, **theme.btn_primary()
        ).pack(side="right")

        self.transient(master)
        self.grab_set()
        self.name_entry.focus()

    def _on_name_changed(self, event=None):
        if not self._prefix_edited:
            self.prefix_entry.delete(0, "end")
            self.prefix_entry.insert(0, _default_prefix(self.name_entry.get()))
        if not self._group_prefix_edited:
            self.group_prefix_entry.delete(0, "end")
            self.group_prefix_entry.insert(0, self.prefix_entry.get())

    def _on_prefix_changed(self, event=None):
        self._prefix_edited = True
        if not self._group_prefix_edited:
            self.group_prefix_entry.delete(0, "end")
            self.group_prefix_entry.insert(0, self.prefix_entry.get())

    def _submit(self):
        name = self.name_entry.get().strip()
        prefix = self.prefix_entry.get().strip()
        group_prefix = self.group_prefix_entry.get().strip() or prefix
        if not name or not prefix:
            self.error_label.configure(text="Nom et préfixe requis.")
            return
        if not _PREFIX_RE.match(prefix) or not _PREFIX_RE.match(group_prefix):
            self.error_label.configure(
                text="Préfixe invalide : lettres, chiffres, '_', '.', '-' uniquement (pas d'espace)."
            )
            return
        try:
            if self._editing_case:
                db.update_case(self._editing_case.id, name, prefix, group_prefix)
                self.result = db.Case(
                    id=self._editing_case.id, name=name, prefix=prefix, group_prefix=group_prefix,
                    created_at=self._editing_case.created_at,
                )
            else:
                self.result = db.create_case(name, prefix, group_prefix)
        except sqlite3.IntegrityError:
            self.error_label.configure(text="Un cas avec ce nom existe déjà.")
            return
        self.destroy()


class FirewallResultPanel(ctk.CTkFrame):
    def __init__(self, master, case: db.Case, result: blocker.FirewallResult, on_saved):
        super().__init__(master, **theme.card())
        self.case = case
        self.result = result
        self.on_saved = on_saved

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            header, text=FIREWALL_LABELS[result.firewall], text_color=theme.TEXT, font=theme.font_heading(14),
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=self._summary(result), text_color=theme.MUTED, font=theme.font_body(12),
        ).pack(side="left", padx=(10, 0))

        # Anomalies affichées EN PREMIER, avant les commandes, pour ne pas passer inaperçues.
        if result.duplicates_in_case:
            ctk.CTkLabel(
                self,
                text="⚠ Déjà présentes dans ce cas (ignorées) : " + ", ".join(result.duplicates_in_case),
                text_color=theme.WARNING,
                font=theme.font_body(12, "bold"),
                justify="left",
                wraplength=560,
            ).pack(anchor="w", padx=14, pady=(8, 0))

        if result.cross_case_warnings:
            warn_text = "\n".join(f"⚠ {v} déjà bloquée sous le cas « {c} »" for v, c in result.cross_case_warnings)
            ctk.CTkLabel(
                self, text=warn_text, text_color=theme.WARNING, font=theme.font_body(12), justify="left"
            ).pack(anchor="w", padx=14, pady=(8, 0))

        if result.invalid:
            ctk.CTkLabel(
                self,
                text="✕ Invalides (ignorées) : " + ", ".join(result.invalid),
                text_color=theme.DANGER,
                font=theme.font_body(12, "bold"),
                justify="left",
                wraplength=560,
            ).pack(anchor="w", padx=14, pady=(8, 0))

        if result.new_values:
            self.textbox = ctk.CTkTextbox(
                self, height=150, wrap="none", fg_color=theme.CODE_BG, text_color=theme.CODE_TEXT,
                font=theme.font_mono(12), corner_radius=theme.RADIUS_CONTROL,
            )
            self.textbox.pack(fill="both", expand=True, padx=14, pady=10)
            self.textbox.insert("1.0", result.commands)
            self.textbox.configure(state="disabled")

            action_frame = ctk.CTkFrame(self, fg_color="transparent")
            action_frame.pack(fill="x", padx=14, pady=(0, 12))
            ctk.CTkButton(action_frame, text="Copier", width=90, command=self._copy, **theme.btn_secondary()).pack(
                side="left"
            )
            ctk.CTkButton(
                action_frame, text="Exporter .txt", width=112, command=self._export, **theme.btn_secondary()
            ).pack(side="left", padx=8)
            self.save_btn = ctk.CTkButton(
                action_frame, text=f"Enregistrer ({len(result.new_values)})", command=self._save,
                **theme.btn_primary(),
            )
            self.save_btn.pack(side="right")
        else:
            ctk.CTkLabel(
                self, text="Aucune nouvelle valeur à générer.", text_color=theme.MUTED, font=theme.font_body(12)
            ).pack(anchor="w", padx=14, pady=(10, 12))
            self.save_btn = None

    @staticmethod
    def _summary(result: blocker.FirewallResult) -> str:
        parts = [f"{len(result.new_values)} nouvelle(s)"]
        if result.duplicates_in_case:
            parts.append(f"{len(result.duplicates_in_case)} doublon(s)")
        if result.cross_case_warnings:
            parts.append(f"{len(result.cross_case_warnings)} déjà bloquée(s) ailleurs")
        if result.invalid:
            parts.append(f"{len(result.invalid)} invalide(s)")
        return " · ".join(parts)

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.result.commands)

    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"Commandes_{self.case.name}_{self.result.firewall}.txt",
            filetypes=[("Fichier texte", "*.txt")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.result.commands)

    def _save(self):
        blocker.save(self.case, self.result.firewall, self.result.new_values)
        if self.save_btn:
            self.save_btn.configure(
                text="Enregistré ✓", state="disabled",
                fg_color=theme.SUCCESS_BG, text_color=theme.SUCCESS, border_width=0,
            )
        self.on_saved()


class CaseTab(ctk.CTkFrame):
    def __init__(self, master, on_data_changed=None):
        super().__init__(master, fg_color="transparent")
        self.on_data_changed = on_data_changed
        self.current_case: db.Case | None = None
        self.fw_vars: dict[str, ctk.BooleanVar] = {}
        self.result_panels: list[FirewallResultPanel] = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(top, text="Cas :", text_color=theme.MUTED, font=theme.font_body(13)).pack(side="left")
        self.case_menu = ctk.CTkOptionMenu(
            top, values=["—"], command=self._on_case_selected, width=220, **theme.option_menu_style()
        )
        self.case_menu.pack(side="left", padx=8)
        ctk.CTkButton(top, text="Nouveau cas", width=104, command=self._new_case, **theme.btn_secondary()).pack(
            side="left"
        )
        ctk.CTkButton(top, text="Modifier", width=90, command=self._edit_case, **theme.btn_secondary()).pack(
            side="left", padx=8
        )
        ctk.CTkButton(top, text="Supprimer", width=90, command=self._delete_case, **theme.btn_danger()).pack(
            side="left"
        )

        fw_frame = ctk.CTkFrame(self, fg_color="transparent")
        fw_frame.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(fw_frame, text="Pare-feu :", text_color=theme.MUTED, font=theme.font_body(13)).pack(
            side="left"
        )
        for fw in FIREWALLS:
            var = ctk.BooleanVar(value=True)
            self.fw_vars[fw] = var
            ctk.CTkCheckBox(fw_frame, text=FIREWALL_LABELS[fw], variable=var, **theme.checkbox_style()).pack(
                side="left", padx=8
            )

        ctk.CTkLabel(
            self, text="IP / CIDR / FQDN à bloquer (une par ligne)", text_color=theme.MUTED, font=theme.font_body(12)
        ).pack(anchor="w", padx=16, pady=(8, 0))
        self.input_box = ctk.CTkTextbox(
            self, height=120, fg_color=theme.SURFACE, text_color=theme.TEXT, font=theme.font_mono(12),
            border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_CONTROL,
        )
        self.input_box.pack(fill="x", padx=16, pady=(4, 8))

        self.generate_btn = ctk.CTkButton(
            self, text="Générer", command=self._generate, width=120, **theme.btn_primary()
        )
        self.generate_btn.pack(padx=16, anchor="w")

        self.results_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.results_scroll.pack(fill="both", expand=True, padx=16, pady=12)

        self.refresh_cases()

    def refresh_cases(self):
        cases = db.list_cases()
        self._cases_by_name = {c.name: c for c in cases}
        names = list(self._cases_by_name.keys()) or ["—"]
        self.case_menu.configure(values=names)
        if self.current_case and self.current_case.name in self._cases_by_name:
            self.case_menu.set(self.current_case.name)
        elif names != ["—"]:
            self.case_menu.set(names[0])
            self.current_case = self._cases_by_name[names[0]]
        else:
            self.case_menu.set("—")
            self.current_case = None

    def _on_case_selected(self, value: str):
        self.current_case = self._cases_by_name.get(value)

    def _new_case(self):
        dialog = CaseDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self.refresh_cases()
            self.current_case = dialog.result
            self.case_menu.set(dialog.result.name)

    def _edit_case(self):
        if not self.current_case:
            messagebox.showwarning("Blacklister IP", "Sélectionnez un cas à modifier.")
            return
        dialog = CaseDialog(self, case=self.current_case)
        self.wait_window(dialog)
        if dialog.result:
            self.current_case = dialog.result
            self.refresh_cases()
            self.case_menu.set(dialog.result.name)
            if self.on_data_changed:
                self.on_data_changed()

    def _delete_case(self):
        if not self.current_case:
            messagebox.showwarning("Blacklister IP", "Sélectionnez un cas à supprimer.")
            return
        case = self.current_case
        count = db.count_entries_for_case(case.id)
        message = f"Supprimer le cas « {case.name} » ?"
        if count:
            message += f"\n\nCela supprimera aussi les {count} entrée(s) de son historique. Action irréversible."
        else:
            message += "\n\nAction irréversible."
        if not messagebox.askyesno("Blacklister IP", message, icon="warning"):
            return
        db.delete_case(case.id)
        self.current_case = None
        for panel in self.result_panels:
            panel.destroy()
        self.result_panels.clear()
        self.refresh_cases()
        if self.on_data_changed:
            self.on_data_changed()

    def _generate(self):
        if not self.current_case:
            messagebox.showwarning("Blacklister IP", "Sélectionnez ou créez un cas d'abord.")
            return
        selected_fw = [fw for fw, var in self.fw_vars.items() if var.get()]
        if not selected_fw:
            messagebox.showwarning("Blacklister IP", "Sélectionnez au moins un pare-feu.")
            return
        raw_text = self.input_box.get("1.0", "end")
        if not raw_text.strip():
            messagebox.showwarning("Blacklister IP", "Collez au moins une IP/FQDN.")
            return

        for panel in self.result_panels:
            panel.destroy()
        self.result_panels.clear()

        for fw in selected_fw:
            result = blocker.process(self.current_case, fw, raw_text)
            panel = FirewallResultPanel(self.results_scroll, self.current_case, result, on_saved=self._on_saved)
            panel.pack(fill="x", pady=(0, 10))
            self.result_panels.append(panel)

    def _on_saved(self):
        if self.on_data_changed:
            self.on_data_changed()
