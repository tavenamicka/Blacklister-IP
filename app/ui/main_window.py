"""Fenêtre principale : onglets Cas / Historique."""
import customtkinter as ctk

from ui import theme
from ui.case_tab import CaseTab
from ui.history_tab import HistoryTab


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Blacklister IP")
        self.geometry("840x740")
        self.minsize(700, 580)
        self.configure(fg_color=theme.BG)

        tabview = ctk.CTkTabview(
            self,
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
        tabview.pack(fill="both", expand=True, padx=16, pady=16)
        tab_cas = tabview.add("Cas")
        tab_historique = tabview.add("Historique")
        tab_cas.configure(fg_color=theme.BG)
        tab_historique.configure(fg_color=theme.BG)

        self.history_tab = HistoryTab(tab_historique)
        self.history_tab.pack(fill="both", expand=True)

        self.case_tab = CaseTab(tab_cas, on_data_changed=self.history_tab.refresh)
        self.case_tab.pack(fill="both", expand=True)
