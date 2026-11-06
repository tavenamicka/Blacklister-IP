"""Tests de la bascule 'Multi-vsys' (Palo Alto) dans l'onglet Cas — instancie de vrais widgets
CustomTkinter/Tk (pas de mock), cf. ui/case_tab.py. Nécessite un display (Xvfb en CI, cf. ci.yml).

Réutilise la fenêtre Tk racine partagée de conftest.py (`root`, scope session) : CustomTkinter ne
supporte correctement qu'une seule fenêtre Tk par processus — on recrée seulement le `CaseTab`
entre les tests, jamais la racine."""
import pytest
from ui.case_tab import CaseTab


@pytest.fixture
def case_tab(isolated_db, root):
    tab = CaseTab(root)
    root.update()
    yield tab
    tab.destroy()


def test_vsys_frame_hidden_when_palo_alto_unchecked(case_tab):
    case_tab.fw_vars["palo_alto"].set(False)
    case_tab._update_palo_vsys_visibility()

    # winfo_manager() : nom du gestionnaire de géométrie courant ("pack" si affiché, "" sinon) —
    # contrairement à winfo_ismapped(), ne dépend pas de la visibilité réelle de la fenêtre.
    assert case_tab.palo_vsys_frame.winfo_manager() == ""
    assert case_tab._palo_alto_vsys_value() is None


def test_vsys_frame_shown_when_palo_alto_checked(case_tab):
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab._update_palo_vsys_visibility()

    assert case_tab.palo_vsys_frame.winfo_manager() == "pack"


def test_vsys_value_defaults_to_none_when_multi_vsys_unchecked(case_tab):
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab.palo_vsys_enabled_var.set(False)
    case_tab._update_palo_vsys_visibility()

    assert case_tab._palo_alto_vsys_value() is None


def test_vsys_value_is_shared_by_default_when_multi_vsys_checked(case_tab):
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab.palo_vsys_enabled_var.set(True)
    case_tab._update_palo_vsys_visibility()

    assert case_tab._palo_alto_vsys_value() == "shared"


def test_vsys_value_uses_named_vsys_with_default_name(case_tab):
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab.palo_vsys_enabled_var.set(True)
    case_tab.palo_vsys_mode_menu.set("vsys nommé")
    case_tab._on_palo_vsys_mode_changed("vsys nommé")

    assert case_tab._palo_alto_vsys_value() == "vsys1"


def test_vsys_value_uses_custom_vsys_name(case_tab):
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab.palo_vsys_enabled_var.set(True)
    case_tab.palo_vsys_mode_menu.set("vsys nommé")
    case_tab._on_palo_vsys_mode_changed("vsys nommé")
    case_tab.palo_vsys_name_entry.insert(0, "vsys2")

    assert case_tab._palo_alto_vsys_value() == "vsys2"


def test_vsys_value_rejects_invalid_vsys_name(case_tab):
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab.palo_vsys_enabled_var.set(True)
    case_tab.palo_vsys_mode_menu.set("vsys nommé")
    case_tab._on_palo_vsys_mode_changed("vsys nommé")
    case_tab.palo_vsys_name_entry.insert(0, "vsys 2 !")

    with pytest.raises(ValueError):
        case_tab._palo_alto_vsys_value()


def test_unchecking_palo_alto_resets_multi_vsys_flag(case_tab):
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab.palo_vsys_enabled_var.set(True)
    case_tab._update_palo_vsys_visibility()

    case_tab.fw_vars["palo_alto"].set(False)
    case_tab._update_palo_vsys_visibility()

    assert case_tab.palo_vsys_enabled_var.get() is False
