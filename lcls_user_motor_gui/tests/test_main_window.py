from unittest.mock import MagicMock, patch

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


def test_load_ioc_data_assigns_prefix_and_pvDict(qtbot, monkeypatch):
    """
    Test to make sure that
    """
    mw = MainWindow()
    qtbot.addWidget(mw)

    mw.user_input_widget = DummyWidget()
    mw.linker_widget = DummyWidget()
    mw.expert_widget = DummyWidget()
    mw.diagnostic_widget = DummyWidget()

    fake_pvs = ["TST:UM:", "PV1", "PV2", "PV3", "LASTPV"]
    fake_cagets = ["value1", "value2", "value3"]

    monkeypatch.setattr(
        "lcls_user_motor_gui.user_motor_gui.discover_pvs", lambda *a, **k: fake_pvs
    )
    monkeypatch.setattr(
        "lcls_user_motor_gui.user_motor_gui.epics.caget_many",
        lambda *a, **k: fake_cagets,
    )

    mw.load_ioc_data()

    assert mw.prefixName == "TST:UM:"
    assert mw.pvList == ["PV1", "PV2", "PV3"]
    assert mw.pvDict == {"PV1": "value1", "PV2": "value2", "PV3": "value3"}

    for widget in [
        mw.user_input_widget,
        mw.linker_widget,
        mw.expert_widget,
        mw.diagnostic_widget,
    ]:
        assert widget.prefixName == "TST:UM:"
        assert widget.pvDict == mw.pvDict
