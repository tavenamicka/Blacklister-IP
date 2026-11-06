"""Bascule 'Multi-vsys' Palo Alto (checkbox + menu shared/vsys nommé + champ nom) — widget
partagé par l'onglet Cas (mode générique, sans device précis) et l'onglet Pare-feu (par device),
pour éviter que les deux dérivent l'un de l'autre à force de copier-coller (cf. SUIVI.md)."""
import re

import customtkinter as ctk

from ui import theme

_VSYS_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class VsysSelector(ctk.CTkFrame):
    """L'appelant décide quand afficher/activer ce sélecteur (`set_available`) selon son propre
    contexte (ex. marque Palo Alto sélectionnée, aucun device précis coché...) — ce widget ne
    connaît que son état interne (case cochée, mode shared/nommé, nom saisi)."""

    def __init__(self, master, checkbox_padx=(8, 8)):
        super().__init__(master, fg_color="transparent")
        self._available = False

        self.enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self, text="Multi-vsys", variable=self.enabled_var,
            command=self.refresh, **theme.checkbox_style(),
        ).pack(side="left", padx=checkbox_padx)
        self.mode_menu = ctk.CTkOptionMenu(
            self, values=["shared", "vsys nommé"], command=self.refresh,
            width=130, **theme.option_menu_style(),
        )
        self.mode_menu.pack(side="left")
        self.name_entry = ctk.CTkEntry(
            self, placeholder_text="ex: vsys1", width=100, **theme.entry_style()
        )
        self.refresh()

    def set_available(self, available: bool, **pack_kwargs) -> None:
        """available=False : masque tout le sélecteur et réinitialise la case (le contexte qui le
        rendait pertinent a disparu). available=True : l'affiche avec `pack_kwargs` (propre à
        l'écran appelant : ordre, marges)."""
        self._available = available
        if available:
            self.pack(**pack_kwargs)
        else:
            self.enabled_var.set(False)
            self.pack_forget()
        self.refresh()

    def refresh(self, _value=None) -> None:
        """Met à jour menu/champ nom selon l'état courant. `_value` : ignoré, seulement pour être
        directement utilisable comme callback `command=` d'un CTkOptionMenu."""
        enabled = self._available and self.enabled_var.get()
        self.mode_menu.configure(state="normal" if enabled else "disabled")
        mode = self.mode_menu.get() if enabled else "shared"
        if enabled and mode == "vsys nommé":
            self.name_entry.pack(side="left", padx=(8, 0))
            self.name_entry.configure(state="normal")
        else:
            self.name_entry.pack_forget()

    def get_value(self) -> str | None:
        """Scope PAN-OS à utiliser : None (pas de préfixe, mono-vsys), 'shared' ou le nom saisi.
        Lève ValueError si le nom de vsys contient un caractère non supporté."""
        if not self.enabled_var.get():
            return None
        if self.mode_menu.get() == "shared":
            return "shared"
        name = self.name_entry.get().strip() or "vsys1"
        if not _VSYS_NAME_RE.match(name):
            raise ValueError(
                "Nom de vsys invalide : lettres, chiffres, '_', '.', '-' uniquement (pas d'espace)."
            )
        return name

    def set_value(self, vsys: str | None) -> None:
        """Pré-remplit l'état à partir d'une valeur déjà stockée (édition d'un device existant).
        Sans effet sur l'affichage : l'appelant doit ensuite rafraîchir via `set_available`."""
        if not vsys:
            return
        self.enabled_var.set(True)
        self.mode_menu.set("shared" if vsys == "shared" else "vsys nommé")
        if vsys != "shared":
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, vsys)
