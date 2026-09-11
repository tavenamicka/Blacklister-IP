"""Palette, typographie et styles de boutons du thème 'Tech Dashboard' (SaaS pro, cartes + tableaux).

Verrouille l'appli en mode clair : ce style est pensé pour un fond clair (comme la quasi-totalité
des dashboards SaaS) et n'a pas d'équivalent sombre défini.
"""
import customtkinter as ctk

BG = "#f6f7fb"
SURFACE = "#ffffff"
SURFACE_2 = "#eef0f7"
BORDER = "#e3e5ee"
TEXT = "#191c26"
MUTED = "#6a7086"

ACCENT = "#3452eb"
ACCENT_HOVER = "#2b45cc"
ACCENT_2 = "#12b3a6"  # teal secondaire — réservé aux accents ponctuels (chiffres clés), pas aux boutons

SUCCESS = "#16a34a"
SUCCESS_BG = "#dcfce7"
WARNING = "#b45309"
WARNING_BG = "#fef3c7"
DANGER = "#dc2626"
DANGER_BG = "#fef2f2"
DANGER_BORDER = "#fecaca"

CODE_BG = "#11131a"
CODE_TEXT = "#d7e0f5"

RADIUS_CARD = 12
RADIUS_CONTROL = 8

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"


def apply() -> None:
    """A appeler une seule fois, avant la création de la fenêtre principale."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


def font_heading(size: int = 15, weight: str = "bold") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def font_body(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def font_mono(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FAMILY, size=size, weight=weight)


def btn_primary(**overrides) -> dict:
    kwargs = dict(
        fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#ffffff",
        corner_radius=RADIUS_CONTROL, font=font_body(13, "bold"),
    )
    kwargs.update(overrides)
    return kwargs


def btn_secondary(**overrides) -> dict:
    kwargs = dict(
        fg_color=SURFACE, hover_color=SURFACE_2, text_color=TEXT,
        border_width=1, border_color=BORDER, corner_radius=RADIUS_CONTROL,
        font=font_body(13, "normal"),
    )
    kwargs.update(overrides)
    return kwargs


def btn_danger(**overrides) -> dict:
    kwargs = dict(
        fg_color=DANGER_BG, hover_color="#fde2e2", text_color=DANGER,
        border_width=1, border_color=DANGER_BORDER, corner_radius=RADIUS_CONTROL,
        font=font_body(13, "bold"),
    )
    kwargs.update(overrides)
    return kwargs


def entry_style(**overrides) -> dict:
    kwargs = dict(
        fg_color=SURFACE, border_width=1, border_color=BORDER, text_color=TEXT,
        placeholder_text_color=MUTED, corner_radius=RADIUS_CONTROL,
        font=font_body(13),
    )
    kwargs.update(overrides)
    return kwargs


def option_menu_style(**overrides) -> dict:
    kwargs = dict(
        fg_color=SURFACE, button_color=SURFACE_2, button_hover_color=BORDER,
        text_color=TEXT, dropdown_fg_color=SURFACE, dropdown_text_color=TEXT,
        dropdown_hover_color=SURFACE_2, corner_radius=RADIUS_CONTROL,
        font=font_body(13),
    )
    kwargs.update(overrides)
    return kwargs


def checkbox_style(**overrides) -> dict:
    kwargs = dict(
        fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=BORDER,
        checkmark_color="#ffffff", text_color=TEXT, font=font_body(13),
    )
    kwargs.update(overrides)
    return kwargs


def card(**overrides) -> dict:
    kwargs = dict(
        fg_color=SURFACE, corner_radius=RADIUS_CARD, border_width=1, border_color=BORDER,
    )
    kwargs.update(overrides)
    return kwargs
