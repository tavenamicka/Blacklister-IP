"""Fenêtre 'À propos' : nom, version, date de build, auteur, contact, copyright (cf. app_info.py)."""
import app_info
import customtkinter as ctk

from ui import theme


class AboutDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master, fg_color=theme.BG)
        self.title("À propos")
        self.geometry("360x280")
        self.resizable(False, False)

        ctk.CTkLabel(self, text=app_info.APP_NAME, text_color=theme.TEXT, font=theme.font_heading(18)).pack(
            anchor="w", padx=20, pady=(20, 0)
        )

        def row(label: str, value: str):
            r = ctk.CTkFrame(self, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=(10, 0))
            ctk.CTkLabel(r, text=label, text_color=theme.MUTED, font=theme.font_body(12), width=100).pack(
                side="left", anchor="w"
            )
            ctk.CTkLabel(r, text=value, text_color=theme.TEXT, font=theme.font_body(12)).pack(
                side="left", anchor="w"
            )

        row("Version", app_info.get_version())
        row("Build", app_info.get_build_date())
        row("Auteur", app_info.AUTHOR)
        row("Contact", app_info.CONTACT)

        ctk.CTkLabel(
            self, text=app_info.COPYRIGHT, text_color=theme.MUTED, font=theme.font_body(11),
        ).pack(anchor="w", padx=20, pady=(16, 0))

        ctk.CTkButton(self, text="Fermer", command=self.destroy, **theme.btn_secondary()).pack(
            padx=20, pady=20, side="bottom", anchor="e"
        )

        self.transient(master)
        self.grab_set()
