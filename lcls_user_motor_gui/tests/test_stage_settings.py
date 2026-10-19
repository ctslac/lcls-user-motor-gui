from types import SimpleNamespace
from unittest.mock import MagicMock

from lcls_user_motor_gui.save_and_restore import PVConfig, ValueConfig
from lcls_user_motor_gui.widgets.stage_settings import StageSettings


class StageSettingsHarness:
    ui_dir = StageSettings.ui_dir
    template_prefix_macro = StageSettings.template_prefix_macro
    template_ioc_prefix_macro = StageSettings.template_ioc_prefix_macro
    template_axis_macro = StageSettings.template_axis_macro
    template_drive_coe_prefix_macro = StageSettings.template_drive_coe_prefix_macro
    template_encoder_coe_prefix_macro = StageSettings.template_encoder_coe_prefix_macro

    configure_template_macros = StageSettings.configure_template_macros
    get_axis_coe_channel_prefix = StageSettings.get_axis_coe_channel_prefix
    get_axis_coe_prefix = StageSettings.get_axis_coe_prefix
    get_ioc_template_prefix = StageSettings.get_ioc_template_prefix
    get_nc_prefix = StageSettings.get_nc_prefix
    get_template_macros = StageSettings.get_template_macros
    get_template_prefix = StageSettings.get_template_prefix
    normalize_coe_prefix_metadata = StageSettings.normalize_coe_prefix_metadata
    normalize_template_coe_suffix = StageSettings.normalize_template_coe_suffix
    drop_unreadable_config_values = StageSettings.drop_unreadable_config_values
    resolve_template_coe_pvs = StageSettings.resolve_template_coe_pvs
    convert_axis_to_template = StageSettings.convert_axis_to_template


def make_stage_settings(prefix="UED:UM1"):
    stage_settings = StageSettingsHarness()
    stage_settings.user_input_widget = SimpleNamespace(prefixName=prefix)
    stage_settings.logger = MagicMock()
    return stage_settings


def test_configure_template_macros_uses_nc_and_coe_prefixes():
    stage_settings = make_stage_settings()
    config = ValueConfig(
        name="Axis 1",
        desc="Test config",
        schema_ver=0,
        metadata={
            "axis": "Axis 1",
            "axis_index": 1,
            "ioc_prefix": "UED:UM1",
            "nc_prefix": "UED:UM1:MMS:01",
            "drive_coe_prefix": "UED:UM1:EL7062:01:COE:02",
            "encoder_coe_prefix": "UED:UM1:EL5102:01:COE:01",
        },
        data=[
            (
                "UED:UM1:MMS:01:NC:Vel:Goal",
                "UED:UM1:MMS:01:NC:Vel:Val_RBV",
                1.0,
            ),
            (
                "UED:UM1:EL7062:01:COE:02:MaxCurrent:Goal",
                "UED:UM1:EL7062:01:COE:02:MaxCurrent:Val_RBV",
                1000,
            ),
            (
                "UED:UM1:EL5102:01:COE:01:Scale:Goal",
                "UED:UM1:EL5102:01:COE:01:Scale:Val_RBV",
                1.0,
            ),
        ],
    )

    result = stage_settings.configure_template_macros(config, axis_index=0)

    assert result.data == [
        (
            "${NC_PREFIX}:NC:Vel:Goal",
            "${NC_PREFIX}:NC:Vel:Val_RBV",
            1.0,
        ),
        (
            "${DRIVE_COE_PREFIX}:MaxCurrent:Goal",
            "${DRIVE_COE_PREFIX}:MaxCurrent:Val_RBV",
            1000,
        ),
        (
            "${ENCODER_COE_PREFIX}:Scale:Goal",
            "${ENCODER_COE_PREFIX}:Scale:Val_RBV",
            1.0,
        ),
    ]


def test_drop_unreadable_config_values_drops_missing_and_malformed_rows(monkeypatch):
    stage_settings = make_stage_settings()
    config = ValueConfig(
        name="Axis 1",
        desc="Test config",
        schema_ver=0,
        metadata={},
        data=[
            ("short", "row"),
            ("missing", "readback", None),
            ("readable", "readback", 1.0),
            ("extra", "fields", 2.0, "unexpected"),
        ],
    )
    warning = MagicMock()
    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.QMessageBox.warning", warning
    )

    result = stage_settings.drop_unreadable_config_values(config)

    assert result.data == [("readable", "readback", 1.0)]
    warning.assert_called_once()


def test_resolve_template_coe_pvs_skips_hardware_lookup_without_coe_rows():
    stage_settings = make_stage_settings()
    stage_settings.get_axis_coe_channel_prefix = MagicMock()
    config = ValueConfig(
        name="Axis 1",
        desc="Test config",
        schema_ver=0,
        metadata={},
        data=[("UED:UM1:MMS:01:NC:Vel:Goal", "UED:UM1:MMS:01:NC:Vel:Val_RBV", 1.0)],
    )

    result = stage_settings.resolve_template_coe_pvs(config, axis_index=0)

    assert result is config
    stage_settings.get_axis_coe_channel_prefix.assert_not_called()


def test_resolve_template_coe_pvs_aborts_when_coe_hardware_is_missing(monkeypatch):
    stage_settings = make_stage_settings()
    stage_settings.get_axis_coe_channel_prefix = MagicMock(return_value=None)
    config = ValueConfig(
        name="Axis 1",
        desc="Test config",
        schema_ver=0,
        metadata={},
        data=[
            (
                "UED:UM1:MMS:01:COE:02:Scale:Goal",
                "UED:UM1:MMS:01:COE:02:Scale:Val_RBV",
                1.0,
            )
        ],
    )
    warning = MagicMock()
    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.QMessageBox.warning", warning
    )

    result = stage_settings.resolve_template_coe_pvs(config, axis_index=0)

    assert result is None
    warning.assert_called_once()


def test_resolve_template_coe_pvs_aborts_on_unresolved_coe_macro(monkeypatch):
    stage_settings = make_stage_settings()
    stage_settings.get_axis_coe_channel_prefix = MagicMock(
        side_effect=lambda axis_index, selector: (
            "UED:UM1:EL5102:01:COE:01:" if selector == "ENC" else None
        )
    )
    stage_settings.get_coe_list = MagicMock(return_value=[])
    config = ValueConfig(
        name="Axis 1",
        desc="Test config",
        schema_ver=0,
        metadata={},
        data=[
            (
                "${DRIVE_COE_PREFIX}:Scale:Goal",
                "${DRIVE_COE_PREFIX}:Scale:Val_RBV",
                1.0,
            )
        ],
    )
    warning = MagicMock()
    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.QMessageBox.warning", warning
    )

    result = stage_settings.resolve_template_coe_pvs(config, axis_index=0)

    assert result is None
    warning.assert_called_once()


def test_axis_coe_channel_prefix_uses_linked_hardware_formula(monkeypatch):
    stage_settings = make_stage_settings()
    stage_settings.get_coe_list = MagicMock(
        return_value=["UED:UM1:EL7062:01:COE:02:MaxCurrent:Name_RBV"]
    )

    def fake_caget(pv, as_string=False):
        if pv.endswith(":Id_RBV"):
            return "EL7062_1"
        if pv.endswith(":MAIN_RBV"):
            return "02"
        return None

    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.epics.caget", fake_caget
    )

    assert (
        stage_settings.get_axis_coe_channel_prefix(axis_index=0, selector="DRV")
        == "UED:UM1:EL7062:01:COE:02:"
    )


class FakeComboBox:
    def __init__(self, index, text):
        self.index = index
        self.text = text

    def currentIndex(self):
        return self.index

    def currentText(self):
        return self.text


class FakeLineEdit:
    def __init__(self):
        self.value = ""

    def setText(self, value):
        self.value = value

    def text(self):
        return self.value


class FakeDialog:
    Accepted = 1

    def __init__(self, parent=None):
        self.parent = parent

    def exec_(self):
        self.lineEdit_template_name.setText("My Template")
        self.lineEdit_template_desc.setText("Template description")
        self.lineEdit_template_file.setText("/tmp/my_template.toml")
        return self.Accepted


def fake_load_ui(filename, dialog):
    dialog.label_axis_value = FakeLineEdit()
    dialog.lineEdit_template_name = FakeLineEdit()
    dialog.lineEdit_template_desc = FakeLineEdit()
    dialog.lineEdit_template_file = FakeLineEdit()
    dialog.pushButton_browse_template_file = MagicMock()


def test_convert_axis_to_template(monkeypatch):
    pv_config = PVConfig(
        name="Axis 1",
        desc="Writable NC parameters for Axis 1",
        schema_ver=0,
        metadata={"axis": "Axis 1", "axis_index": 1},
        data=[("${axis_prefix}Param:Goal", "${axis_prefix}Param:Val_RBV")],
    )
    template_config = ValueConfig(
        name="Axis 1",
        desc="Writable NC parameters for Axis 1",
        schema_ver=0,
        metadata={"existing": "metadata"},
        data=[("${axis_prefix}Param:Goal", "${axis_prefix}Param:Val_RBV", 5)],
    )

    mock_get_live_config = MagicMock(return_value=template_config)
    mock_config_to_file = MagicMock()
    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.QDialog", FakeDialog
    )
    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.loadUi", fake_load_ui
    )
    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.get_live_config",
        mock_get_live_config,
    )
    monkeypatch.setattr(
        "lcls_user_motor_gui.widgets.stage_settings.config_to_file",
        mock_config_to_file,
    )

    user_input_widget = MagicMock()
    user_input_widget.prefixName = "TST:UM"
    user_input_widget.loaded_config_path = "/tmp"

    stage_settings = make_stage_settings()
    stage_settings.user_input_widget = user_input_widget
    stage_settings.get_axis_coe_channel_prefix = MagicMock(return_value=None)
    stage_settings.comboBox_convert_to_template = FakeComboBox(0, "Axis 1")
    stage_settings.checkBox_use_existing_config = MagicMock()
    stage_settings.checkBox_use_existing_config.isChecked.return_value = False
    stage_settings.get_axis_pv_config = MagicMock(return_value=pv_config)
    stage_settings.load_configs_from_user_input = MagicMock()

    stage_settings.convert_axis_to_template()

    stage_settings.get_axis_pv_config.assert_called_once_with(
        0, "Axis 1", "TST:UM:MMS:01:NC:"
    )
    mock_get_live_config.assert_called_once_with(
        pv_config,
        macros=stage_settings.get_template_macros(0),
    )
    mock_config_to_file.assert_called_once()
    filename, saved_config = mock_config_to_file.call_args.args
    assert filename == "/tmp/my_template.toml"
    user_input_widget.load_configs.assert_called_once_with()
    stage_settings.load_configs_from_user_input.assert_called_once_with()

    assert saved_config.name == "My Template"
    assert saved_config.desc == "Template description"
    assert saved_config.metadata == {
        "existing": "metadata",
        "axis": "Axis 1",
        "axis_index": 1,
    }
    assert saved_config.data == [
        ("${NC_PREFIX}:NC:Param:Goal", "${NC_PREFIX}:NC:Param:Val_RBV", 5)
    ]
