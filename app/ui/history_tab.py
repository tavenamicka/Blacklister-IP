"""Onglet 'Historique' : liste des entrées bloquées, import/ajout manuel, recherche, archivage,
suppression, export CSV, sauvegarde de la base."""
import csv
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

import db
from db import FIREWALL_LABELS
from ui import theme
from ui.import_dialog import ImportDialog

COLUMNS = ("case", "firewall", "value", "type", "status", "created_at")
HEADERS = {
    "case": "Cas",
    "firewall": "Pare-feu",
    "value": "Valeur",
    "type": "Type",
    "status": "Statut",
    "created_at": "Ajouté le",
}

SEARCH_DEBOUNCE_MS = 300
STATUS_FILTERS = {"Toutes": "all", "Actives": "active", "Débloquées": "archived"}

_TREE_STYLE_INSTALLED = False


def _install_tree_style() -> None:
    """Style ttk 'Tech Dashboard' : fond clair, en-tête discret, pas de relief 3D."""
    global _TREE_STYLE_INSTALLED
    if _TREE_STYLE_INSTALLED:
        return
    style = ttk.Style()
    style.theme_use("default")
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure(
        "Treeview", background=theme.SURFACE, fieldbackground=theme.SURFACE, foreground=theme.TEXT,
        rowheight=30, font=(theme.FONT_FAMILY, 10), borderwidth=0,
    )
    style.configure(
        "Treeview.Heading", background=theme.SURFACE_2, foreground=theme.MUTED,
        font=(theme.FONT_FAMILY, 9, "bold"), relief="flat", borderwidth=0,
    )
    style.map(
        "Treeview.Heading", background=[("active", theme.SURFACE_2)],
    )
    style.map(
        "Treeview",
        background=[("selected", "#e9edfd")],
        foreground=[("selected", theme.TEXT)],
    )
    _TREE_STYLE_INSTALLED = True


def _status_text(row) -> str:
    return f"Débloquée le {row['unblocked_at']}" if row["unblocked_at"] else "Active"


class StatTile(ctk.CTkFrame):
    def __init__(self, master, label: str, accent: bool = False):
        super().__init__(master, **theme.card(corner_radius=theme.RADIUS_CONTROL))
        ctk.CTkLabel(self, text=label.upper(), text_color=theme.MUTED, font=theme.font_body(10, "bold")).pack(
            anchor="w", padx=13, pady=(10, 0)
        )
        self.value_label = ctk.CTkLabel(
            self, text="—", text_color=theme.ACCENT_2 if accent else theme.TEXT, font=theme.font_mono(20, "bold"),
        )
        self.value_label.pack(anchor="w", padx=13, pady=(0, 11))

    def set_value(self, value) -> None:
        self.value_label.configure(text=str(value))


class HistoryTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        _install_tree_style()
        self._search_after_id = None

        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", padx=16, pady=(16, 8))
        for i in range(3):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")
        self.stat_total = StatTile(stats, "Total entrées")
        self.stat_total.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.stat_active = StatTile(stats, "Actives", accent=True)
        self.stat_active.grid(row=0, column=1, sticky="ew", padx=6)
        self.stat_archived = StatTile(stats, "Débloquées")
        self.stat_archived.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(0, 8))
        self.search_entry = ctk.CTkEntry(
            top, placeholder_text="Rechercher un cas ou une valeur...", **theme.entry_style()
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)
        self.status_menu = ctk.CTkOptionMenu(
            top, values=list(STATUS_FILTERS), command=lambda _v: self.refresh(), width=120,
            **theme.option_menu_style(),
        )
        self.status_menu.set("Toutes")
        self.status_menu.pack(side="left", padx=8)
        ctk.CTkButton(top, text="Importer...", width=100, command=self._open_import_dialog, **theme.btn_secondary()).pack(
            side="left"
        )

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkButton(
            actions, text="Marquer comme débloquée(s)", width=190, command=self._archive_selected,
            **theme.btn_secondary(),
        ).pack(side="left")
        ctk.CTkButton(
            actions, text="Restaurer", width=90, command=self._unarchive_selected, **theme.btn_secondary()
        ).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="Supprimer", width=90, command=self._delete_selected, **theme.btn_danger()).pack(
            side="left"
        )
        ctk.CTkButton(actions, text="Exporter CSV", width=110, command=self._export_csv, **theme.btn_secondary()).pack(
            side="right"
        )
        ctk.CTkButton(
            actions, text="Sauvegarder la base", width=150, command=self._backup_db, **theme.btn_secondary()
        ).pack(side="right", padx=8)

        table_card = ctk.CTkFrame(self, **theme.card(corner_radius=theme.RADIUS_CONTROL))
        table_card.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.tree = ttk.Treeview(table_card, columns=COLUMNS, show="headings", selectmode="extended")
        for col in COLUMNS:
            self.tree.heading(col, text=HEADERS[col])
            self.tree.column(col, width=140, anchor="w")
        self.tree.tag_configure("even", background=theme.SURFACE)
        self.tree.tag_configure("odd", background=theme.SURFACE_2)
        self.tree.pack(fill="both", expand=True, padx=1, pady=1)

        self.refresh()

    def _on_search_changed(self, event=None):
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(SEARCH_DEBOUNCE_MS, self.refresh)

    def refresh(self):
        self._search_after_id = None
        search = self.search_entry.get().strip()
        status = STATUS_FILTERS.get(self.status_menu.get(), "all")
        rows = db.list_history(search, status)
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            type_label = "FQDN" if row["is_fqdn"] else "IP"
            self.tree.insert(
                "",
                "end",
                iid=str(row["entry_id"]),
                tags=("even" if i % 2 == 0 else "odd",),
                values=(
                    row["case_name"],
                    FIREWALL_LABELS.get(row["firewall"], row["firewall"]),
                    row["value"],
                    type_label,
                    _status_text(row),
                    row["created_at"],
                ),
            )

        counts = db.count_history()
        self.stat_total.set_value(counts["total"])
        self.stat_active.set_value(counts["active"])
        self.stat_archived.set_value(counts["archived"])

    def _selected_ids(self) -> list[int]:
        return [int(iid) for iid in self.tree.selection()]

    def _open_import_dialog(self):
        if not db.list_cases():
            messagebox.showwarning("Blacklister IP", "Créez d'abord un cas dans l'onglet Cas.")
            return
        ImportDialog(self, on_imported=self.refresh)

    def _archive_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning("Blacklister IP", "Sélectionnez une ou plusieurs lignes.")
            return
        for entry_id in ids:
            db.archive_entry(entry_id)
        self.refresh()

    def _unarchive_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning("Blacklister IP", "Sélectionnez une ou plusieurs lignes.")
            return
        for entry_id in ids:
            db.unarchive_entry(entry_id)
        self.refresh()

    def _delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning("Blacklister IP", "Sélectionnez une ou plusieurs lignes.")
            return
        if not messagebox.askyesno(
            "Blacklister IP", f"Supprimer définitivement {len(ids)} entrée(s) de l'historique ?", icon="warning"
        ):
            return
        for entry_id in ids:
            db.delete_entry(entry_id)
        self.refresh()

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="historique_blacklister.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        status = STATUS_FILTERS.get(self.status_menu.get(), "all")
        rows = db.list_history(self.search_entry.get().strip(), status)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Cas", "Pare-feu", "Valeur", "Type", "Statut", "Ajouté le"])
            for row in rows:
                type_label = "FQDN" if row["is_fqdn"] else "IP"
                writer.writerow(
                    [
                        row["case_name"],
                        FIREWALL_LABELS.get(row["firewall"], row["firewall"]),
                        row["value"],
                        type_label,
                        _status_text(row),
                        row["created_at"],
                    ]
                )

    def _backup_db(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            initialfile="blacklister_backup.db",
            filetypes=[("Base SQLite", "*.db")],
        )
        if not path:
            return
        db.backup_to(Path(path))
        messagebox.showinfo("Blacklister IP", f"Base sauvegardée :\n{path}")
