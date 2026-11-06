"""Tests de la sélection par device dans l'onglet Cas — instancie de vrais widgets CustomTkinter
(pas de mock), cf. ui/case_tab.py. Réutilise la fenêtre Tk racine partagée de conftest.py (`root`,
scope session) — voir test_case_tab_vsys.py pour pourquoi il ne faut jamais en recréer une par
module."""
import pytest
from ui.case_tab import CaseTab


@pytest.fixture
def case_tab(isolated_db, root):
    tab = CaseTab(root)
    root.update()
    yield tab
    tab.destroy()


def test_no_device_checkboxes_when_registry_empty(case_tab):
    assert case_tab.device_vars == {}


def test_device_checkbox_appears_for_checked_firewall(isolated_db, case_tab):
    device = isolated_db.create_device("Paris", "FW-PAR", "palo_alto", "10.1.0.1")
    case_tab.refresh_devices()

    assert device.id in case_tab.device_vars
    assert case_tab.device_vars[device.id].get() is False


def test_device_checkbox_disappears_when_firewall_unchecked(isolated_db, case_tab):
    isolated_db.create_device("Paris", "FW-PAR", "fortinet", "10.1.0.1")
    case_tab.fw_vars["fortinet"].set(False)
    case_tab.refresh_devices()

    assert case_tab.device_vars == {}


def test_selecting_palo_device_hides_generic_vsys_controls(isolated_db, case_tab):
    device = isolated_db.create_device("Paris", "FW-PAR", "palo_alto", "10.1.0.1")
    case_tab.refresh_devices()
    case_tab.fw_vars["palo_alto"].set(True)
    case_tab._update_palo_vsys_visibility()
    assert case_tab.palo_vsys_frame.winfo_manager() == "pack"

    case_tab.device_vars[device.id].set(True)
    case_tab._update_palo_vsys_visibility()

    assert case_tab.palo_vsys_frame.winfo_manager() == ""


def test_generate_uses_device_prefix_and_saves_device_id(isolated_db, case_tab):
    case = isolated_db.create_case("Test", "IOC-case-Test")
    device = isolated_db.create_device("Paris", "FW-PAR", "palo_alto", "10.1.0.1", object_prefix="IOC-PAR")
    case_tab.current_case = case
    case_tab.case_menu.set(case.name)
    for fw in ("fortinet", "cisco_asa"):
        case_tab.fw_vars[fw].set(False)
    case_tab.refresh_devices()
    case_tab.device_vars[device.id].set(True)
    case_tab.input_box.insert("1.0", "1.2.3.4")

    case_tab._generate()

    assert len(case_tab.result_panels) == 1
    result = case_tab.result_panels[0].result
    assert result.device == device
    assert "IOC-PAR_1.2.3.4" in result.commands
