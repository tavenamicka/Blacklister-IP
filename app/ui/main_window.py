"""Fenêtre principale : onglets Cas / Historique."""
import app_info
import customtkinter as ctk

from ui import theme
from ui.about_dialog import AboutDialog
from ui.case_tab import CaseTab
from ui.devices_tab import DevicesTab
from ui.history_tab import HistoryTab


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Blacklister IP")
        self.geometry("840x740")
        self.minsize(700, 580)
        self.configure(fg_color=theme.BG)

        status_bar = ctk.CTkFrame(self, fg_color="transparent", height=24)
        status_bar.pack(fill="x", side="bottom", padx=16, pady=(0, 8))
        self.version_label = ctk.CTkLabel(
            status_bar, text=app_info.get_version(), text_color=theme.MUTED, font=theme.font_body(11),
            cursor="hand2",
        )
        self.version_label.pack(side="right")
        self.version_label.bind("<Button-1>", lambda e: self._open_about())

        tabview = ctk.CTkTabview(
            self,
            command=self._on_tab_changed,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
            corner_radius=theme.RADIUS_CARD,
            segmented_button_fg_color=theme.SURFACE,
            segmented_button_selected_color=theme.SURFACE_2,
            segmented_button_selected_hover_color=theme.SURFACE_2,
            segmented_button_unselected_color=theme.SURFACE,
            segmented_button_unselected_hover_color=theme.SURFACE_2,
            segmented_button_font=theme.font_heading(13),
            text_color=theme.TEXT,
            text_color_disabled=theme.MUTED,
        )
        self.tabview = tabview
        tabview.pack(fill="both", expand=True, padx=16, pady=16)
        tab_cas = tabview.add("Cas")
        tab_historique = tabview.add("Historique")
        tab_parefeu = tabview.add("Pare-feu")
        tab_cas.configure(fg_color=theme.BG)
        tab_historique.configure(fg_color=theme.BG)
        tab_parefeu.configure(fg_color=theme.BG)

        self.history_tab = HistoryTab(tab_historique)
        self.history_tab.pack(fill="both", expand=True)

        self.case_tab = CaseTab(tab_cas, on_data_changed=self.history_tab.refresh)
        self.case_tab.pack(fill="both", expand=True)

        self.devices_tab = DevicesTab(tab_parefeu)
        self.devices_tab.pack(fill="both", expand=True)

    def _on_tab_changed(self):
        """Rafraîchit l'onglet qu'on vient d'afficher : le registre 'Pare-feu' peut avoir changé
        depuis le dernier passage sur 'Cas' ou 'Historique'."""
        current = self.tabview.get()
        if current == "Cas":
            self.case_tab.refresh_devices()
        elif current == "Historique":
            self.history_tab.refresh()

    def _open_about(self):
        AboutDialog(self)
