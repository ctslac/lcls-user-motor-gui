from unittest.mock import MagicMock, mock_open, patch

import pytest

from lcls_user_motor_gui.user_motor_gui import MainWindow

# def test_publish_axis_di_list(linking_axis):
#     test_dict = linking_axis()

#     # need to write function
#     # need to parse test_dic for a test axis ID
#     test_avail_axis_di_1 = publish_axis_di_list(test_dict, axis_id_1)
#     test_avail_axis_di_2 = publish_axis_di_list(test_dict, axis_id_2)
#     test_avail_axis_di_3 = publish_axis_di_list(test_dict, axis_id_3)
#     test_avail_axis_di_4 = publish_axis_di_list(test_dict, axis_id_4)
#     assert test_avail_axis_di_1 == ["1", "2", "3"]
#     assert test_avail_axis_di_2 == ["1", "2", "3"]
#     assert test_avail_axis_di_3 == ["1", "2"]
#     assert test_avail_axis_di_4 == ["1"]


# def test_publish_axis_di_list(linking_axis):
#     test_dict = linking_axis()

#     """
#     To do in for function:
#     | Digital Inputs |
#     | Virtual Axis DI Num (01, 02, 03) | Device ID (EL7047_1) | Hardware Channel Number (0,1,2) |
#     # treat "0" as invalid
#     # given axis ID and DI slot num expect correct DI device and hardware channel number
#     # need to parse test_dic for a test axis ID


#     to do for gui:
#     have nothing show for a fresh install
#     if configuration/mapping exists, populate/highlight connections
#     """
#     selcted_di_vals_1 = publish_axis_di_selection_list(axis_id_1, axis_di_num_1)
#     selcted_di_vals_2 = publish_axis_di_selection_list(axis_id_2, axis_di_num_2)
#     selcted_di_vals_3 = publish_axis_di_selection_list(axis_id_3, axis_di_num_3)
#     selcted_di_vals_4 = publish_axis_di_selection_list(axis_id_4, axis_di_num_4)
#     assert test_avail_axis_di_1 == {"EL7062_1_Ch1": "2"}  # Axis 1, 01
#     assert test_avail_axis_di_2 == dict()  # has virtual axis DI but no link; axis 1, 03
#     assert (
#         test_avail_axis_di_3 == dict()
#     )  # does not have virtual axis di num; axis 4, 02/03
#     assert test_avail_axis_di_4 == {"EL1429_1": "15"}  # axis 2, 3


class DummyWidget:
    def __init__(self):
        self.prefixName = None
        self.pvDict = None


@pytest.fixture
def main_window(qtbot):
    """Create a MainWindow instance with mocked widgets"""
    mw = MainWindow()
    qtbot.addWidget(mw)

    # Replace child widgets with dummy widgets to avoid UI initialization
    mw.user_input_widget = DummyWidget()
    mw.linker_widget = DummyWidget()
    mw.expert_widget = DummyWidget()
    mw.diagnostic_widget = DummyWidget()

    return mw


# def test_load_ioc_data(main_window, monkeypatch):
#     """Test that load_ioc_data correctly sets prefixName and pvList"""
#     fake_pvs = ["TST:UM:", "PV1", "PV2", "PV3", "LASTPV"]
#     fake_ioc_path = "/reg/g/pcds/epics-dev/nlentz/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"

#     monkeypatch.setattr(
#         "lcls_user_motor_gui.user_motor_gui.discover_pvs",
#         lambda *a, **k: fake_ioc_path
#     )
#     monkeypatch.setattr(
#         "lcls_user_motor_gui.user_motor_gui.epics.caget_many",
#         lambda pv_list, **k: ["value1", "value2", "value3"]
#     )
#     monkeypatch.setattr("builtins.open", mock_open())

#     main_window.load_ioc_data()

#     assert main_window.prefixName == "TST:UM:"
#     assert main_window.pvList == ["PV1", "PV2", "PV3"]


def test_discover_pvs_with_usr_db_path(monkeypatch):
    """Test discover_pvs with a user-provided database path"""
    from lcls_user_motor_gui.processing.discover_pvs import discover_pvs

    # Mock file content
    mock_db_content = """
    record(motor, "TST:UM:01:Axis:Name")
    record(motor, "TST:UM:02:Axis:Name")
    record(ai, "TST:UM:01:EL7047:Stat")
    """

    # Mock the open function to return our fake db file
    monkeypatch.setattr("builtins.open", mock_open(read_data=mock_db_content))

    # Mock os.path.isfile to return True for our path
    monkeypatch.setattr(
        "lcls_user_motor_gui.processing.discover_pvs.os.path.isfile", lambda x: True
    )

    # Call discover_pvs with a user-provided path
    result = discover_pvs("", usr_db_path="/path/to/test.db")

    # Verify PVs were extracted
    assert "TST:UM:01:Axis:Name" in result
    assert "TST:UM:02:Axis:Name" in result
    assert "TST:UM:01:EL7047:Stat" in result


def test_discover_pvs_with_makefile_prefix(monkeypatch):
    """Test discover_pvs with find_makefile flag to extract prefix"""
    from lcls_user_motor_gui.processing.discover_pvs import discover_pvs

    mock_makefile_content = "PREFIX := TST:UM:"
    mock_db_content = """
    record(motor, "TST:UM:01:Axis:Name")
    record(motor, "TST:UM:02:Axis:Name")
    """

    # Track which file is being opened
    def mock_file_open(filepath, mode="r"):
        if "Makefile" in filepath:
            return mock_open(read_data=mock_makefile_content)()
        else:
            return mock_open(read_data=mock_db_content)()

    monkeypatch.setattr("builtins.open", mock_file_open)
    monkeypatch.setattr(
        "lcls_user_motor_gui.processing.discover_pvs.os.path.isfile", lambda x: True
    )
    monkeypatch.setattr(
        "lcls_user_motor_gui.processing.discover_pvs.os.path.exists", lambda x: True
    )

    result = discover_pvs("", usr_db_path="/path/to/test.db", find_makefile=True)

    # When find_makefile is True, prefix should be first element
    assert result[0] == "TST:UM:"
    assert "TST:UM:01:Axis:Name" in result
    assert "TST:UM:02:Axis:Name" in result


def test_discover_pvs_invalid_hutch():
    """Test discover_pvs raises error for invalid hutch"""
    from lcls_user_motor_gui.processing.discover_pvs import discover_pvs

    with pytest.raises(ValueError) as exc_info:
        discover_pvs("ioc_name", hutch="invalid_hutch")

    assert "Invalid hutch" in str(exc_info.value)


def test_discover_pvs_invalid_db_path():
    """Test discover_pvs raises error for non-existent db path"""
    from lcls_user_motor_gui.processing.discover_pvs import discover_pvs

    with pytest.raises(FileExistsError) as exc_info:
        discover_pvs("", usr_db_path="/nonexistent/path.db")

    assert "Invalid db path" in str(exc_info.value)
