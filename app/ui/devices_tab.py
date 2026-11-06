"""Onglet 'Pare-feu' : registre des pare-feu physiques (site/pôle, host SSH, préfixes propres),
pour voir d'un coup d'œil quel device appartient à quel pôle avant de s'y connecter."""
import json
import re
import sqlite3
import tkinter.messagebox as messagebox
from tkinter import ttk

import customtkinter as ctk
import db
from db import FIREWALL_LABELS, FIREWALLS

from ui import theme
from ui.ssh_dialogs import open_terminal_flow

COLUMNS = ("site", "name", "firewall", "host", "port", "object_prefix", "group_prefix")
HEADERS = {
    "site": "Pôle / Site",
    "name": "Nom",
    "firewall": "Marque",
    "host": "Host",
    "port": "Port SSH",
    "object_prefix": "Préfixe objets",
    "group_prefix": "Préfixe groupe",
}

_HOST_RE = re.compile(r"^\S+$")  # pas d'espace ; IP, FQDN ou nom court tous acceptés
_VSYS_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class DeviceDialog(ctk.CTkToplevel):
    """Dialogue de création OU de modification d'un pare-feu physique (device=None -> création)."""

    def __init__(self, master, device: db.Device | None = None):
        super().__init__(master, fg_color=theme.BG)
        self._editing_device = device
        self.title("Modifier le pare-feu" if device else "Nouveau pare-feu")
        self.geometry("440x620")
        self.resizable(False, False)
        self.result: db.Device | None = None

        def label(text):
            ctk.CTkLabel(self, text=text, text_color=theme.MUTED, font=theme.font_body(12)).pack(
                anchor="w", padx=16, pady=(12, 0)
            )

        label("Pôle / Site")
        self.site_entry = ctk.CTkEntry(self, placeholder_text="ex: Paris", **theme.entry_style())
        self.site_entry.pack(fill="x", padx=16)

        label("Nom du pare-feu")
        self.name_entry = ctk.CTkEntry(self, placeholder_text="ex: FW-PAR-EDGE1", **theme.entry_style())
        self.name_entry.pack(fill="x", padx=16)

        label("Marque")
        self.firewall_menu = ctk.CTkOptionMenu(
            self, values=[FIREWALL_LABELS[fw] for fw in FIREWALLS], width=200,
            command=lambda _v: self._update_vsys_visibility(), **theme.option_menu_style(),
        )
        self.firewall_menu.pack(anchor="w", padx=16)

        # Options vsys : uniquement pertinentes pour Palo Alto (contexte PAN-OS), cf.
        # generators/palo_alto.generate(). Stockées dans devices.extra_options (JSON).
        self.vsys_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.vsys_enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self.vsys_frame, text="Multi-vsys", variable=self.vsys_enabled_var,
            command=self._update_vsys_visibility, **theme.checkbox_style(),
        ).pack(side="left", padx=(16, 8))
        self.vsys_mode_menu = ctk.CTkOptionMenu(
            self.vsys_frame, values=["shared", "vsys nommé"], command=self._on_vsys_mode_changed,
            width=130, **theme.option_menu_style(),
        )
        self.vsys_mode_menu.pack(side="left")
        self.vsys_name_entry = ctk.CTkEntry(
            self.vsys_frame, placeholder_text="ex: vsys1", width=100, **theme.entry_style()
        )

        host_row = ctk.CTkFrame(self, fg_color="transparent")
        host_row.pack(fill="x", padx=16, pady=(12, 0))
        host_col = ctk.CTkFrame(host_row, fg_color="transparent")
        host_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(host_col, text="Host (IP ou nom)", text_color=theme.MUTED, font=theme.font_body(12)).pack(
            anchor="w"
        )
        self.host_entry = ctk.CTkEntry(host_col, placeholder_text="ex: 10.1.2.3", **theme.entry_style())
        self.host_entry.pack(fill="x")
        port_col = ctk.CTkFrame(host_row, fg_color="transparent")
        port_col.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(port_col, text="Port SSH", text_color=theme.MUTED, font=theme.font_body(12)).pack(anchor="w")
        self.port_entry = ctk.CTkEntry(port_col, width=80, **theme.entry_style())
        self.port_entry.insert(0, "22")
        self.port_entry.pack()

        label("Préfixe objets (optionnel — sinon celui du cas)")
        self.object_prefix_entry = ctk.CTkEntry(self, placeholder_text="ex: IOC-PAR", **theme.entry_style())
        self.object_prefix_entry.pack(fill="x", padx=16)

        label("Préfixe groupe (optionnel — sinon celui du cas)")
        self.group_prefix_entry = ctk.CTkEntry(self, placeholder_text="ex: IOC-PAR", **theme.entry_style())
        self.group_prefix_entry.pack(fill="x", padx=16)

        if device:
            self.site_entry.insert(0, device.site)
            self.name_entry.insert(0, device.name)
            self.firewall_menu.set(FIREWALL_LABELS[device.firewall])
            self.host_entry.insert(0, device.host)
            self.port_entry.delete(0, "end")
            self.port_entry.insert(0, str(device.ssh_port))
            self.object_prefix_entry.insert(0, device.object_prefix)
            self.group_prefix_entry.insert(0, device.group_prefix)
            vsys = _device_vsys(device)
            if vsys:
                self.vsys_enabled_var.set(True)
                if vsys == "shared":
                    self.vsys_mode_menu.set("shared")
                else:
                    self.vsys_mode_menu.set("vsys nommé")
        self._update_vsys_visibility()
        if device and _device_vsys(device) not in (None, "shared"):
            self.vsys_name_entry.insert(0, _device_vsys(device))

        self.error_label = ctk.CTkLabel(
            self, text="", text_color=theme.DANGER, font=theme.font_body(12), justify="left", wraplength=390
        )
        self.error_label.pack(anchor="w", padx=16, pady=(8, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=16, side="bottom")
        ctk.CTkButton(btn_frame, text="Annuler", command=self.destroy, **theme.btn_secondary()).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(
            btn_frame, text="Enregistrer" if device else "Créer", command=self._submit, **theme.btn_primary()
        ).pack(side="right")

        self.transient(master)
        self.grab_set()
        self.site_entry.focus()

    def _firewall_key(self) -> str:
        label = self.firewall_menu.get()
        return next(fw for fw, lbl in FIREWALL_LABELS.items() if lbl == label)

    def _update_vsys_visibility(self):
        is_palo = self._firewall_key() == "palo_alto"
        if is_palo:
            self.vsys_frame.pack(fill="x", pady=(4, 0), after=self.firewall_menu)
        else:
            self.vsys_enabled_var.set(False)
            self.vsys_frame.pack_forget()
        enabled = is_palo and self.vsys_enabled_var.get()
        self.vsys_mode_menu.configure(state="normal" if enabled else "disabled")
        self._on_vsys_mode_changed(self.vsys_mode_menu.get() if enabled else "shared")

    def _on_vsys_mode_changed(self, mode: str):
        enabled = self._firewall_key() == "palo_alto" and self.vsys_enabled_var.get()
        if enabled and mode == "vsys nommé":
            self.vsys_name_entry.pack(side="left", padx=(8, 0))
            self.vsys_name_entry.configure(state="normal")
        else:
            self.vsys_name_entry.pack_forget()

    def _vsys_value(self) -> str | None:
        """Scope PAN-OS à stocker pour ce device (None = pas de préfixe, mono-vsys)."""
        if self._firewall_key() != "palo_alto" or not self.vsys_enabled_var.get():
            return None
        if self.vsys_mode_menu.get() == "shared":
            return "shared"
        name = self.vsys_name_entry.get().strip() or "vsys1"
        if not _VSYS_NAME_RE.match(name):
            raise ValueError("Nom de vsys invalide : lettres, chiffres, '_', '.', '-' uniquement (pas d'espace).")
        return name

    def _submit(self):
        site = self.site_entry.get().strip()
        name = self.name_entry.get().strip()
        host = self.host_entry.get().strip()
        port_text = self.port_entry.get().strip()
        object_prefix = self.object_prefix_entry.get().strip()
        group_prefix = self.group_prefix_entry.get().strip()

        if not site or not name or not host:
            self.error_label.configure(text="Pôle/site, nom et host sont requis.")
            return
        if not _HOST_RE.match(host):
            self.error_label.configure(text="Host invalide (pas d'espace).")
            return
        if not port_text.isdigit() or not (1 <= int(port_text) <= 65535):
            self.error_label.configure(text="Port SSH invalide (1-65535).")
            return
        port = int(port_text)
        firewall = self._firewall_key()
        try:
            vsys = self._vsys_value()
        except ValueError as exc:
            self.error_label.configure(text=str(exc))
            return
        extra_options = json.dumps({"vsys": vsys}) if vsys else "{}"

        try:
            if self._editing_device:
                db.update_device(
                    self._editing_device.id, site, name, firewall, host, port, object_prefix, group_prefix,
                    extra_options,
                )
                self.result = db.Device(
                    id=self._editing_device.id, site=site, name=name, firewall=firewall, host=host,
                    ssh_port=port, object_prefix=object_prefix, group_prefix=group_prefix,
                    extra_options=extra_options, created_at=self._editing_device.created_at,
                )
            else:
                self.result = db.create_device(
                    site, name, firewall, host, port, object_prefix, group_prefix, extra_options,
                )
        except sqlite3.IntegrityError:
            self.error_label.configure(text="Un pare-feu avec ce nom existe déjà pour ce pôle/site.")
            return
        self.destroy()


def _device_vsys(device: db.Device) -> str | None:
    try:
        return json.loads(device.extra_options).get("vsys")
    except (json.JSONDecodeError, AttributeError):
        return None


class DevicesTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        theme.install_tree_style()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            top, text="Registre des pare-feu physiques, par pôle/site.", text_color=theme.MUTED,
            font=theme.font_body(13),
        ).pack(side="left")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(
            actions, text="Nouveau pare-feu", width=130, command=self._new_device, **theme.btn_primary()
        ).pack(side="left")
        ctk.CTkButton(actions, text="Modifier", width=90, command=self._edit_device, **theme.btn_secondary()).pack(
            side="left", padx=8
        )
        ctk.CTkButton(actions, text="Supprimer", width=90, command=self._delete_device, **theme.btn_danger()).pack(
            side="left"
        )
        ctk.CTkButton(
            actions, text="Terminal SSH", width=110, command=self._open_terminal, **theme.btn_secondary()
        ).pack(side="left", padx=8)

        table_card = ctk.CTkFrame(self, **theme.card(corner_radius=theme.RADIUS_CONTROL))
        table_card.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.tree = ttk.Treeview(table_card, columns=COLUMNS, show="headings", selectmode="browse")
        for col in COLUMNS:
            self.tree.heading(col, text=HEADERS[col])
            self.tree.column(col, width=110, anchor="w")
        self.tree.tag_configure("even", background=theme.SURFACE)
        self.tree.tag_configure("odd", background=theme.SURFACE_2)
        self.tree.pack(fill="both", expand=True, padx=1, pady=1)

        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, dev in enumerate(db.list_devices()):
            self.tree.insert(
                "",
                "end",
                iid=str(dev.id),
                tags=("even" if i % 2 == 0 else "odd",),
                values=(
                    dev.site,
                    dev.name,
                    FIREWALL_LABELS.get(dev.firewall, dev.firewall),
                    dev.host,
                    dev.ssh_port,
                    dev.object_prefix,
                    dev.group_prefix,
                ),
            )

    def _selected_device(self) -> db.Device | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return db.get_device(int(selection[0]))

    def _new_device(self):
        dialog = DeviceDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self.refresh()

    def _edit_device(self):
        device = self._selected_device()
        if not device:
            messagebox.showwarning("Blacklister IP", "Sélectionnez un pare-feu à modifier.")
            return
        dialog = DeviceDialog(self, device=device)
        self.wait_window(dialog)
        if dialog.result:
            self.refresh()

    def _delete_device(self):
        device = self._selected_device()
        if not device:
            messagebox.showwarning("Blacklister IP", "Sélectionnez un pare-feu à supprimer.")
            return
        if not messagebox.askyesno(
            "Blacklister IP", f"Supprimer le pare-feu « {device.name} » ({device.site}) ?", icon="warning"
        ):
            return
        db.delete_device(device.id)
        self.refresh()

    def _open_terminal(self):
        device = self._selected_device()
        if not device:
            messagebox.showwarning("Blacklister IP", "Sélectionnez un pare-feu.")
            return
        open_terminal_flow(self, device)
