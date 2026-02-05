import json
import logging
import re
import sys
import time
from enum import Enum
from os import path

import epics
import numpy as np

# import epics
from epics import PV, caget, caput

# from epics import PV, fake_caget, cainfo, caput
from pydm import Display
from pydm.widgets.enum_combo_box import PyDMEnumComboBox
from pydm.widgets.label import PyDMLabel
from pydm.widgets.line_edit import PyDMLineEdit
from pydm.widgets.pushbutton import PyDMPushButton
from qtpy import QtCore, uic
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qtpy.uic import loadUi

from discover_pvs import discover_pvs
from parse_pvs import (
    fake_caget,
    identify_axis,
    identify_coe_drive_params,
    identify_coe_enc_params,
    identify_drive,
    identify_enc,
    identify_inputs,
    identify_nc_params,
    strip_key,
    what_can_i_be,
)

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class QPlainTextEditLoggerHandler(logging.Handler):
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit

    def emit(self, record):
        if record.levelno == logging.INFO:
            msg = self.format(record)
            self.text_edit.appendPlainText(msg)


from PyQt5 import QtCore
from PyQt5.QtWidgets import QCompleter, QLineEdit, QListView, QVBoxLayout, QWidget


class FilteredListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # Line edit for filtering
        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Type to filter...")
        layout.addWidget(self.line_edit)

        # Source model
        self.source_model = QtCore.QStringListModel(self)

        # Proxy model for filtering
        self.filter_model = QtCore.QSortFilterProxyModel(self)
        self.filter_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.filter_model.setSourceModel(self.source_model)

        # List view
        self.list_view = QListView(self)
        self.list_view.setModel(self.filter_model)
        layout.addWidget(self.list_view)

        # Completer
        self.completer = QCompleter(self.filter_model, self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.line_edit.setCompleter(self.completer)

        # Connections
        self.line_edit.textEdited.connect(self.filter_model.setFilterFixedString)
        self.completer.activated.connect(self.on_completer_activated)

    def add_items(self, items):
        current = self.source_model.stringList()
        self.source_model.setStringList(current + list(items))

    def on_completer_activated(self, text):
        matches = self.filter_model.match(
            self.filter_model.index(0, 0),
            QtCore.Qt.DisplayRole,
            text,
            hits=1,
            flags=QtCore.Qt.MatchExactly,
        )
        if matches:
            self.list_view.setCurrentIndex(matches[0])


class MappingWindow(QDialog):
    def __init__(self, parent=None):
        super(MappingWindow, self).__init__(parent)
        loadUi("mapping-window.ui", self)
        self.staged_mappings_list = self.findChild(QListWidget, "staged_mappings_list")
        # for stages in MyDisplay(self.staged_mapping):


class StageSettings(QDialog):
    def __init__(self, parent=None):
        super(StageSettings, self).__init__(parent)
        loadUi("stage-config.ui", self)  # Load the UI from the .ui file
        self.egu_rev = self.findChild(PyDMLineEdit, "egu_rev")
        self.step_rev = self.findChild(PyDMLineEdit, "step_rev")
        self.run_current = self.findChild(PyDMLineEdit, "run_current")
        self.encoder_scaling = self.findChild(PyDMLineEdit, "encoder_scaling")
        self.backlash = self.findChild(PyDMLineEdit, "backlash")
        self.generate_params = self.findChild(QPushButton, "generate_params")

        self.generate_params.clicked.connect(self.calculate_params)

    def calculate_params(self):
        egu_rev = self.egu_rev.text()
        step_rev = self.step_rev.text()
        run_current = self.run_current.text()
        encoder_scaling = self.encoder_scaling.text()
        backlash = self.backlash.text()
        generate_params = self.generate_params.text()

        print(
            egu_rev, step_rev, run_current, encoder_scaling, backlash, generate_params
        )


class MyDisplay(Display):
    ui: QWidget

    def __init__(self, parent=None, args=None, macros=None):
        logger.info("In init")
        super().__init__(parent=parent, args=args, macros=macros)

        # initialize vars
        init = True
        if init:
            init = False
            self.prefixName = ""
            self.testList = []
            self.loadedList = []
            self.pvDict = {}
            self.pvDict_table = {}
            self.expertDict = {}
            self.plc_ioc_list = []
            self.plc_ioc_label = ""
            self.axis = []
            self.digital_inputs = ["None"]
            self.digital_inputs_ui = ["None"]
            self.digital_inputs_hardware = ["None"]
            self.digital_inputs_hardware_ui = ["None"]
            self.drives = ["None"]
            self.encoders = ["None"]
            self.enocders_list = []
            self.list_WCIB = []
            self.cleaned_di = ""
            self.di_num_channels = 0
            self.loaded_unique_di = []
            self.loaded_unique_di_ui = []
            self.loaded_di_channels = []
            self.loaded_di_channels_ui = []
            self.loaded_di_channel_inputs = []
            self.store_di_selection = [[-1, -1], [-1, -1], [-1, -1]]
            self.axis_di_idx = 0
            self.axis_di_init = True
            self.di_size = 0
            self.staged_mapping = []
            self.staged_de = []
            self.duplicate_di_cb_flag = False
            self.duplicate_drv_cb_flag = False
            self.duplicate_enc_cb_flag = False
            self.qCurrAxis = 0
            self.nc_list = []
            self.coe_drive_list = []
            self.coe_encoder_list = []

            # Mapping message box
            self.msg = QMessageBox()
            self.isMsgActive = False

        # finding children
        # Linker Tab
        self.plc_ioc_list = self.ui.findChild(QComboBox, "plc_ioc_list")
        self.plc_ioc_label = self.ui.findChild(PyDMLabel, "ioc_label")
        self.axis_list = self.ui.findChild(QListWidget, "axis_list_view")
        self.digital_input_hardware = self.ui.findChild(
            QListWidget, "digital_input_hardware"
        )
        self.digital_input_channels = self.ui.findChild(
            QListWidget, "digital_input_channel"
        )
        self.digital_input_axis = self.ui.findChild(QListWidget, "digital_input_axis")
        self.drives_list = self.ui.findChild(QListWidget, "drives_list_view")
        self.enocders_list = self.ui.findChild(QListWidget, "encoders_list_view")
        self.confirm_mapping = self.ui.findChild(QPushButton, "confirm_mapping")
        self.view_logger = self.ui.findChild(PyDMPushButton, "view_logger_button")
        self.load_ioc = self.ui.findChild(QPushButton, "load_ioc_pushButton")

        """
        Load IOC pvs from ioc and update the axis list and identify PVs based on this
        """

        # Load IOC: load axis, Populate DI, DRV, ENC
        for slot in [self.load_test_list, self.load_axis, self.populate_options]:
            self.load_ioc.clicked.connect(slot)

        # User Input Tab
        self.display_axis = self.ui.findChild(QListWidget, "display_axis_ui")
        self.display_drives = self.ui.findChild(QListWidget, "display_drives_ui")
        self.ui_digital_input_axis = self.ui.findChild(
            QListWidget, "ui_digital_input_axis"
        )
        self.ui_digital_input_hardware = self.ui.findChild(
            QListWidget, "ui_digital_input_hardware"
        )
        self.ui_digital_input_channels = self.ui.findChild(
            QListWidget, "ui_digital_input_channels"
        )
        self.display_encoders = self.ui.findChild(QListWidget, "display_encoders_ui")
        self.stage_settings = self.ui.findChild(QPushButton, "stage_settings")

        ## Expert Tab
        self.expert_axis = self.ui.findChild(QComboBox, "expert_axis")
        self.expert_nc_list = self.ui.findChild(QListWidget, "expert_nc_list")
        self.expert_drive_list = self.ui.findChild(QListWidget, "expert_drive_list")
        self.expert_enocder_list = self.ui.findChild(QListWidget, "expert_enocder_list")
        self.param_list = self.ui.findChild(QListWidget, "expert_param_list")
        self.expert_drive_param_list = self.ui.findChild(
            QListWidget, "expert_coe_drive_list"
        )
        self.expert_encoder_param_list = self.ui.findChild(
            QListWidget, "expert_coe_encoder_list"
        )
        self.nc_groupbox = self.ui.findChild(QGroupBox, "expert_nc_param")
        self.drive_groupbox = self.ui.findChild(QGroupBox, "expert_drive_param")
        self.encoder_groupbox = self.ui.findChild(QGroupBox, "expert_encoder_param")

        # NC Tab
        self.expert_nc_filter = FilteredListWidget(self.nc_groupbox)
        self.nc_groupbox.layout().addWidget(self.expert_nc_filter)

        # Drive Tab
        self.expert_drive_filter = FilteredListWidget(self.drive_groupbox)
        self.drive_groupbox.layout().addWidget(self.expert_drive_filter)

        # Encoder Tab
        self.expert_encoder_filter = FilteredListWidget(self.encoder_groupbox)
        self.encoder_groupbox.layout().addWidget(self.expert_encoder_filter)

        # Mapping
        self.stage_mapping = self.ui.findChild(QPushButton, "stage_mapping")
        self.see_mapping = self.ui.findChild(QPushButton, "see_staged_mapping")
        self.clear_mapping = self.ui.findChild(QPushButton, "clear_mapping")

        # Logger
        self.status_logger = self.ui.findChild(QPlainTextEdit, "status_logger")
        if self.status_logger is not None:
            handler = QPlainTextEditLoggerHandler(self.status_logger)
            formatter = logging.Formatter("%(asctime)s - %(message)s")
            handler.setFormatter(formatter)
            logging.getLogger().addHandler(handler)
            logging.getLogger().setLevel(logging.INFO)
        else:
            logger.warning("status_logger QPlainTextEdit not found in UI.")

        """
        Signals
        """
        for slot in [
            self.expert_update_nc,
            self.expert_update_drive,
            self.expert_update_encoder,
        ]:
            self.expert_axis.currentIndexChanged.connect(slot)

        self.display_axis.currentRowChanged.connect(self.select_axis_ui)

        # axis signals
        self.axis_list.currentRowChanged.connect(self.isStagedMappingSet)

        # digitial input handling signals
        self.digital_input_hardware.currentRowChanged.connect(self.load_di_channel)
        self.digital_input_axis.currentRowChanged.connect(self.select_di_channel)
        self.ui_digital_input_axis.currentRowChanged.connect(self.select_di_channel_ui)
        self.ui_digital_input_hardware.currentRowChanged.connect(
            self.load_di_channel_ui
        )

        # mapping signals
        self.stage_mapping.clicked.connect(self.save_stage)
        self.see_mapping.clicked.connect(self.see_stage)
        self.clear_mapping.clicked.connect(self.clear_stage)

        # Misc Buttons
        self.stage_settings.clicked.connect(self.open_stage_settings)
        self.confirm_mapping.clicked.connect(self.update_links)

        self.duplicate_di_cb = self.ui.findChild(
            QCheckBox, "settings_duplicate_di_warning"
        )
        self.duplicate_di_cb.stateChanged.connect(self.check_duplicate_di_flag)

        self.duplicate_drv_cb = self.ui.findChild(
            QCheckBox, "settings_duplicate_drv_warning"
        )
        self.duplicate_drv_cb.stateChanged.connect(self.check_duplicate_drv_flag)

        self.duplicate_enc_cb = self.ui.findChild(
            QCheckBox, "settings_duplicate_enc_warning"
        )
        self.duplicate_enc_cb.stateChanged.connect(self.check_duplicate_enc_flag)
        self.status_indicators = self.ui.findChild(QLabel, "status_indicators")

    def filter_expert_nc_list(self, text):
        """
        Filter items in expert_nc_list based on expert_filter text.
        """
        for i in range(self.expert_nc_list.count()):
            item = self.expert_nc_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def update_links(self):
        logger.info(f"in update links")
        di_hardware_pv = ""
        di_channel_pv = ""
        drv_pv = ""
        enc_pv = ""
        # caput staged changes to axis
        for axis in self.staged_mapping:
            for di in axis:
                print(f"di: {di}")
                if len(di) > 1:
                    print(f"Found changes in di: {di}")

                    try:
                        # Construct the Process Variable (PV) strings
                        # TST:UM:03:SelG:DI:01:ID
                        di_hardware_pv = (
                            self.prefixName
                            + "0"
                            + str(self.axis_list.currentRow() + 1)
                            + ":SelG:DI:"
                            + di[0]
                            + ":ID"
                        )
                        di_channel_pv = (
                            self.prefixName
                            + "0"
                            + str(self.axis_list.currentRow() + 1)
                            + ":SelG:DI:"
                            + di[0]
                            + ":HardChNum"
                        )

                        # Set di_hardware to the second element of di
                        if len(di) > 1:
                            di_hardware = di[1]  # This is expected to be 'EL7047_2'
                        else:
                            raise ValueError(
                                "di does not have enough elements to retrieve di_hardware."
                            )

                        # Set di_channel to the element after di_hardware ('EL7047_2')
                        if len(di) > 2:
                            # Find the index of 'EL7047_2' and get the next element
                            if di_hardware in di:
                                index = di.index(di_hardware)
                                if index + 1 < len(di):
                                    di_channel = di[index + 1]  # Get the next element
                                else:
                                    raise ValueError(
                                        f"No element found after {di_hardware} in {di}."
                                    )
                            else:
                                raise ValueError(f"{di_hardware} not found in di.")
                        else:
                            raise ValueError(
                                "di does not have enough elements to retrieve di_channel."
                            )

                        print(
                            f"di_hardware_pv: {di_hardware_pv}, di hardware: {di_hardware}"
                        )
                        print(
                            f"di_channel_pv: {di_channel_pv}, di channel: {di_channel}"
                        )

                        # Example operation that may raise an exception
                        try:
                            print("trying to caput di hardware")
                            status_di_hardware = epics.caput(
                                di_hardware_pv, di_hardware
                            )
                            if status_di_hardware == 0:
                                print("di hardware caput succeded")
                            elif status_di_hardware < 0:
                                raise ValueError(
                                    f"DI Hardware caput failed: {status_di_hardware}"
                                )
                        except ValueError as e:
                            print(f"Value error for di: {di}")

                        try:
                            print("trying to caput di channel")
                            status_di_channel = epics.caput(di_channel_pv, di_channel)
                            if status_di_channel == 0:
                                print("di channel caput succeded")
                            elif status_di_channel < 0:
                                raise ValueError(
                                    f"DI Hardware caput failed: {status_di_channel}"
                                )
                        except ValueError as e:
                            print(f"Value error for di: {di}")

                    except IndexError as e:
                        print(
                            f"IndexError for di {di}: {e}. Ensure di has enough elements."
                        )
                    except ValueError as e:
                        print(f"ValueError for di {di}: {e}")
                    except Exception as e:
                        print(f"An unexpected error occurred for di {di}: {e}")
                else:
                    print(f"no changes in di: {di}")
        # for sublist in self.staged_de:
        for item in self.staged_de:
            print(f"item: {item}")
            if len(item) > 1:
                # TST:UM:03:SelG:ENC:Id
                drv_pv = (
                    self.prefixName
                    + "0"
                    + str(self.axis_list.currentRow() + 1)
                    + ":SelG:DRV:Id"
                )
                enc_pv = (
                    self.prefixName
                    + "0"
                    + str(self.axis_list.currentRow() + 1)
                    + ":SelG:ENC:Id"
                )
                print(f"drv_pv: {drv_pv}, drv: {item[0][0]}, enc: {item[1][0]}")
                try:
                    status_drv = epics.caput(drv_pv, item[0][0])
                    if status_drv == 1:
                        print("drv caput succeded")
                    elif status_drv < 0:
                        raise ValueError(f"Drv caput failed: {status_drv}")
                except ValueError as e:
                    print(f"Value error for drv: {item[0][0]}")
                try:
                    status_enc = epics.caput(enc_pv, item[1][0])
                    if status_enc == 1:
                        print("enc caput succeded")
                    elif status_enc < 0:
                        raise ValueError(f"Enc caput failed: {status_enc}")
                except ValueError as e:
                    print(f"Value error for enc: {item[1][0]}")

    def check_duplicate_di_flag(self):
        logger.info(f"in check dup di")

        self.duplicate_di_cb_flag = self.duplicate_di_cb.isChecked()

        logger.debug(f"isDuplicateDIWarning: {self.duplicate_di_cb_flag}")

    def check_duplicate_drv_flag(self):
        logger.info(f"in check dup drv")

        self.duplicate_drv_cb_flag = self.duplicate_drv_cb.isChecked()

        logger.debug(f"isDuplicateDIWarning: {self.duplicate_drv_cb_flag}")

    def check_duplicate_enc_flag(self):
        logger.info(f"in check dup enc")

        self.duplicate_enc_cb_flag = self.duplicate_enc_cb.isChecked()

        logger.debug(f"isDuplicateDIWarning: {self.duplicate_enc_cb_flag}")

    def isStagedMappingSet(self):
        logger.info(f"inStateMapptingSet")
        for stage in range(len(self.staged_mapping)):
            for di in range(len(self.staged_mapping[stage])):
                print(f"di: {self.staged_mapping[stage][di]}")
        for stage in range(len(self.staged_de)):
            for item in range(len(self.staged_de[stage])):
                print(f"item: {self.staged_de[stage][item]}")
        # if there is nothing staged
        # Check if there are any staged mappings
        temp_flag = False
        self.isMsgActive = True
        # self.axis_list.isEnabled(False)
        # temp = self.axis_list.currentRow()
        logger.debug(f"curr axis index: {self.qCurrAxis}")
        if not self.status_staged_mappings():
            logger.debug("There is nothing staged")
            self.select_axis()
        else:
            logger.debug("There are some staged values")
            # self.configMappingWarningBox()

            self.msg.setIcon(QMessageBox.Warning)
            self.msg.setText("You have unsaved staged changes! Discard changes?")
            self.msg.setWindowTitle("Warning")
            self.msg.setStandardButtons(
                QMessageBox.Yes | QMessageBox.No
            )  # Adjusted buttons
            result = self.msg.exec_()

            logger.debug(f"current axis: {self.qCurrAxis}")
            logger.debug(f"Message box result: {result}")
            if result == QMessageBox.Yes:
                logger.debug("switching to select axis")
                self.clear_stage()
                self.select_axis()
            elif result == QMessageBox.No:
                # QMessageBox.information(self, "Continue", "You can continue")
                temp_flag = True
        if temp_flag:
            logger.debug("attempting to reset axis")
            logger.debug(f"resetting row to: {self.qCurrAxis}")
            self.axis_list.setEnabled(True)
            self.axis_list.blockSignals(True)
            self.axis_list.setCurrentRow(self.qCurrAxis)
            self.axis_list.blockSignals(False)

    def extract_unique_parts(self, pv_names):
        unique_parts = set()
        for pv in pv_names:
            parts = pv.split(":")
            if len(parts) > 4:
                unique_parts.add(parts[4])
        return sorted(unique_parts)

    def remove_name_rbv(self, pv_name):
        suffix = ":Name_RBV"
        if pv_name.endswith(suffix):
            return pv_name[: -len(suffix)]
        return pv_name

    def configure_param_widgets(self, widget: QWidget, nc_pv):
        """
        Configure all param.ui widgets in self.param_widgets.
        Optionally takes a config_list (list of dicts) to set values for each widget.
        Example config_list: [{"label": "NC1", "lineEdit": "val1", "lineEdit_2": "val2", "label_2": "desc1"}, ...]
        """
        vals = ["", "", "", ""]
        vals[0] = nc_pv + ":Name_RBV"
        vals[1] = nc_pv + ":Goal"
        vals[2] = nc_pv + ":Val_RBV"
        vals[3] = nc_pv + ":EU_RBV"
        # print("ca://" + vals[1])
        ca_vals = epics.caget_many(vals, as_string=True)
        # print(ca_vals)
        name = widget.findChild(PyDMLabel, "pv_name")
        name.setText(ca_vals[0])
        goal = widget.findChild(PyDMLineEdit, "pv_goal")
        goal.set_channel("ca://" + vals[1])
        rbv = widget.findChild(PyDMLineEdit, "pv_rbv")
        rbv.set_channel("ca://" + vals[2])
        units = widget.findChild(PyDMLabel, "pv_units")
        units.setText(ca_vals[3])

    # def add_param_widgets(self, param, widget : QListWidget):
    #     """
    #     Dynamically add instances of the param.ui widget as QListWidgetItems in self.param_list (QListWidget)
    #     """

    #     # Remove all items from the QListWidget
    #     widget.clear()
    #     self.param_widgets = []
    #     pv = ""
    #     # ncs = identify_nc_params(
    #     #     self.prefixName + "0" + str(self.expert_axis.currentIndex() + 1),
    #     #     self.pvDict,
    #     # )
    #     ncs = param

    #     # Add new widgets based on expert_nc_list
    #     for i in ncs:
    #         param_widget = uic.loadUi(
    #             path.join(path.dirname(path.realpath(__file__)), "param.ui")
    #         )
    #         item = QListWidgetItem()
    #         pv = self.remove_name_rbv(i)
    #         print(f"pv: {pv}")
    #         self.configure_param_widgets(param_widget, pv)
    #         item.setSizeHint(param_widget.sizeHint())
    #         self.widget.addItem(item)
    #         self.widget.setItemWidget(item, param_widget)

    #         self.param_widgets.append(param_widget)

    def add_param_widgets(self, param, widget: QListWidget):
        """
        Dynamically add instances of the param.ui widget as QListWidgetItems in self.param_list (QListWidget)
        """
        # Remove all items from the QListWidget
        widget.clear()
        self.param_widgets = []
        # ... other code ...
        for i in param:
            param_widget = uic.loadUi(
                path.join(path.dirname(path.realpath(__file__)), "param.ui")
            )
            item = QListWidgetItem()
            pv = self.remove_name_rbv(i)
            print(f"pv: {pv}")
            self.configure_param_widgets(param_widget, pv)
            item.setSizeHint(param_widget.sizeHint())
            widget.addItem(item)
            widget.setItemWidget(item, param_widget)

            self.param_widgets.append(param_widget)

    def status_staged_mappings(self):
        logger.info(f"in status_staged_mapping: checking if there is a staged mapping")
        containsDI = False
        containsDE = False
        for axis in self.staged_mapping:
            if isinstance(axis, list):  # Ensure we're working with a list
                for sublist in axis:
                    logger.debug(f"size of staged mapping: {len(sublist)}")
                    logger.debug(
                        f"isinstance: {isinstance(sublist, list) and len(sublist) > 1}"
                    )
                    if isinstance(sublist, list) and len(sublist) > 1:
                        logger.debug(f"there are stagged di changes")
                        containsDI = True  # Found a non-empty sublist
        for axis in self.staged_de:
            if isinstance(axis, list):  # Ensure we're working with a list
                # [logger.debug(f"items: {item}" for item in axis)]
                [logger.debug(f"item: {item}") for item in axis]
                logger.debug(
                    f"any: {any([(item != ['None'] and item != [''] and item != []) for item in axis])}"
                )
                if any(
                    [
                        (item != ["None"] and item != [""] and item != [])
                        for item in axis
                    ]
                ):
                    logger.debug("drive or encoders staged")
                    containsDE = True
        if containsDE or containsDI:
            return True
        else:
            return False

    def check_duplicate_di(self):
        logger.info(f"in check for duplicate di")
        # To hold values for duplicate checking
        second_index_values = set()
        third_index_values = set()

        # Track duplicates
        duplicates_second = set()
        duplicates_third = set()

        # Loop through each sublist in the main list
        for sublist in self.staged_mapping:
            for item in sublist:
                if len(item) > 1:  # Check if the sublist has at least 2 elements
                    # Check the 2nd index value
                    second_index_value = item[1]
                    if second_index_value in second_index_values:
                        duplicates_second.add(second_index_value)
                    else:
                        second_index_values.add(second_index_value)

                if len(item) > 2:  # Check if the sublist has at least 3 elements
                    # Check the 3rd index value
                    third_index_value = item[2]
                    if third_index_value in third_index_values:
                        duplicates_third.add(third_index_value)
                    else:
                        third_index_values.add(third_index_value)
        if self.duplicate_di_cb_flag and (duplicates_second or duplicates_third):
            # Prepare the message content
            second_duplicates = (
                ", ".join(duplicates_second) if duplicates_second else "None"
            )
            third_duplicates = (
                ", ".join(duplicates_third) if duplicates_third else "None"
            )

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Duplicate DI")
            msg.setInformativeText(
                f"Duplicate DIs found:\n2nd Index: {second_duplicates}\n3rd Index: {third_duplicates}"
            )
            msg.setWindowTitle("Warning")
            msg.setStandardButtons(QMessageBox.Ok)

            msg.exec_()

        # Print the results
        logger.debug(f"Duplicates in the 2nd index: {duplicates_second}")
        logger.debug(f"Duplicates in the 3rd index: {duplicates_third}")

    def check_duplicate_drv(self):
        """
        Check for duplicate first index values in staged_de based on the first element of each inner-most list.
        Ignore duplicates for the value 'None'.

        Returns:
            set: A set of duplicate first index values except 'None'.
        """
        logger.info(f"in check for duplicate drv")

        # To hold unique values for duplicate checking
        seen_values = []

        # Track duplicates
        duplicates = []
        # Loop through each main list in data
        for axis in self.staged_de:
            # Loop through each sublist in the main list
            # for sublist in axis:
            # Ensure the sublist is a list and has at least 1 element
            if isinstance(axis, list) and len(axis) > 0:
                # Get the first element value
                first_element_value = axis[0]

                # Ignore None values or empty strings while checking for duplicates
                if (
                    first_element_value is None
                    or first_element_value == "None"
                    or first_element_value == ["None"]
                    or first_element_value == ""
                ):
                    continue

                # Check for duplicates
                if first_element_value in seen_values:
                    duplicates.append(first_element_value)
                else:
                    seen_values.append(first_element_value)

        if self.duplicate_di_cb_flag and len(duplicates) > 0:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Duplicate DRV")
            msg.setInformativeText(f"Duplicate DRVs found: {duplicates}")
            msg.setWindowTitle("Warning")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

        # Print the results
        logger.debug(f"Duplicates: {duplicates}")

    def check_duplicate_enc(self):
        """
        Check for duplicate second index values in staged_de based on the second element of each inner-most list.
        Ignore duplicates for the value 'None'.

        Returns:
            set: A set of duplicate first index values except 'None'.
        """
        logger.info(f"in check for duplicate enc")

        # To hold unique values for duplicate checking
        seen_values = []

        # Track duplicates
        duplicates = []
        # Loop through each main list in data
        for axis in self.staged_de:
            # Loop through each sublist in the main list
            # for sublist in axis:
            # Ensure the sublist is a list and has at least 1 element
            if isinstance(axis, list) and len(axis) > 0:
                # Get the first element value
                first_element_value = axis[1]

                # Ignore None values or empty strings while checking for duplicates
                if (
                    first_element_value is None
                    or first_element_value == "None"
                    or first_element_value == ["None"]
                    or first_element_value == ""
                ):
                    continue

                # Check for duplicates
                if first_element_value in seen_values:
                    duplicates.append(first_element_value)
                else:
                    seen_values.append(first_element_value)

        if self.duplicate_di_cb_flag and len(duplicates) > 0:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Duplicate ENC")
            msg.setInformativeText(f"Duplicate ENCs found: {duplicates}")
            msg.setWindowTitle("Warning")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()

        # Print the results
        logger.debug(f"Duplicates: {duplicates}")

    def see_stage(self):
        logger.info(f"in see_stage")
        mapping_window = MappingWindow(self)
        mapping_window.staged_mappings_list.clear()
        # for stage in range(0,len(self.staged_mapping)):
        #     if self.staged_mapping[stage]:
        #         for di in range(0,len(self.staged_mapping[stage])):
        #             logger.debug(f"axis num: {stage}, di: {di}, di array: {len(self.staged_mapping[stage][di])}")
        #             for item in range(0, len(self.staged_mapping[stage][di])):
        #                 mapping_window.staged_mappings_list.addItem(f"{self.staged_mapping[stage][di][item]}, {self.staged_mapping[stage][di][item]}, {self.staged_mapping[stage][di][item]}")
        #     else:
        #         logger.debug(f"stage was empty")

        for stage in range(len(self.staged_mapping)):
            if self.staged_mapping[stage]:  # Check if stage is not empty
                row_output = []  # To gather items in rows of three
                for di in range(len(self.staged_mapping[stage])):
                    # Gather each item's corresponding list output
                    if self.staged_mapping[stage][di]:
                        # Append the item to the row output
                        row_output.append(self.staged_mapping[stage][di])
                    else:
                        # Append an empty list for empty entries
                        row_output.append([""])
                if len(self.staged_de[stage][0]) < 1:
                    logger.debug("0 is blank")
                    self.staged_de[stage][0] = [""]
                if len(self.staged_de[stage][1]) < 1:
                    self.staged_de[stage][1] = [""]
                    logger.debug("1 is blank")
                logger.debug(f"self.staged_de[stage][0]: {self.staged_de[stage][0]}")
                logger.debug(f"self.staged_de[stage][1]: {self.staged_de[stage][1]}")

                # Print the row output in groups of three
                mapping_window.staged_mappings_list.addItem(
                    f"Axis {int(self.axis_list.currentRow())+1}: DI: {row_output[0]}, {row_output[1]}, {row_output[2]} DRV: {self.staged_de[stage][0]} ENC:{self.staged_de[stage][1]}"
                )
                # print(row_output)  # Printing as one complete list containing the sublists

            else:
                logger.debug(
                    f"Stage {stage} was empty"
                )  # Handling completely empty stages
        # #need to setup a way to push info back to the gui is this is wanted
        # mapping_window.show()
        mapping_window.exec_()

    def open_stage_settings(self):
        stageSettings = StageSettings(self)
        stageSettings.exec_()

    def ui_filename(self):
        return "user-motor-gui.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def load_test_list(self):
        logger.info(f"in load test list")
        configured = "./unit_test_data.json"
        integration_test = "/cds/home/c/ctsoi/epics-dev/ioc/user_motors/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"
        unconfigured = "./unit_test_config.json"
        filepath2 = "./expert_unit_test.json"
        filepath1 = configured
        pv_caget_list = []

        # ## test with configuration
        # iocpath = configured

        # try:
        #     # with open(f"{filepath}", "r") as f:
        #     #     for pvs in f:
        #     #         pv_caget_list.append(pvs)

        #     with open(iocpath, "r") as file:
        #         self.pvDict = json.load(file)
        # except Exception as e:
        #     logger.debug(f"Failed to read {filepath1}: {e}")

        # self.prefixName = list(self.pvDict.keys())[0]
        # pattern = r"(TST:UM:)(?=\S)"

        # match = re.search(pattern, self.prefixName)
        # if match:
        #     print(match.group(1))  # Output: TST:UM:
        # self.prefixName = match.group(1)

        ## integration test
        iocpath = integration_test

        # hard code ioc path
        self.pvList = discover_pvs("", usr_db_path=iocpath, find_makefile=True)

        # finding prefix at element 0
        self.prefixName = self.pvList[0]
        print(self.prefixName)
        self.pvList = self.pvList[1:-1]

        logger.debug(f"prefixName: {self.prefixName}")

        # caget whole list
        pv_caget_list = epics.caget_many(self.pvList, as_string=True)

        # put pvs and cagets into a dictionary
        self.pvDict = dict(zip(self.pvList, pv_caget_list))

    def val_to_key(self, val):
        key = [key for key, value in self.pvDict.items() if value == val]
        logger.debug(f"key: {key}")

        """
        there may be more than one key for any given value, i might have to change the logic here
        """
        cleaned_axis = strip_key(key[0])
        logger.debug(f"val to key, cleaned axis: {cleaned_axis}, key: {key}")
        return str(cleaned_axis)

    def find_unique_keys(self, prefix):
        logger.debug("find unique di values")
        # assume Id_RBV
        unique_keys = set()  # Use a set to store unique values
        logger.debug(f"prefix: {prefix}")
        # Loop through the dictionary items
        for key, value in self.pvDict.items():
            # Check if the key starts with the given prefix
            if key.startswith(prefix) and (
                key.endswith("ID_RBV") or key.endswith("Id_RBV")
            ):
                # Add the value to the set of unique values
                unique_keys.add(key)

        # Return the unique values as a list
        return list(unique_keys)

    def identify_di(self, item):
        val = self.val_to_key(item)
        things = self.find_unique_keys(val + ":SelG:DI:")
        logger.debug(f"identify_config: item, {val}, DIs, {things}")

        return things

    def identify_drv(self, item):
        val = self.val_to_key(item)
        things = self.find_unique_keys(val + ":SelG:DRV:")
        logger.debug(f"identify_config: item, {val}, DRVs, {things}")

        return things

    def identify_enc(self, item):
        val = self.val_to_key(item)
        things = self.find_unique_keys(val + ":SelG:ENC:")
        logger.debug(f"identify_config: item, {val}, ENCs, {things}")

        return things

    def populate_options(self):
        logger.info(f"in populate options")

        """
        Called from load_ioc
        ---
        Calls populate di, populate drv, populate enc
        Check to see if there is an existing config for each comp type DI. DRV, ENV
        SelG:DI:*:ID_RBV
        SelG:DRV:*:ID_RBV
        SelG:ENC
        """
        # identify WCIB PVs
        self.identify_WCIB()

    def identify_WCIB(self):
        """
        there are three possible options:
        1. if the caget is an empty string, dont highlight anything
        2. if the there is a value and it matches something, then highlight
        3. there is a string but it doesnt match anything, something went wrong
        """
        logger.info(f"in identify_WCIB'")
        self.list_WCIB = []
        for pv in self.pvDict:
            if re.search(r".*:WCIB_RBV", pv):
                self.list_WCIB.append(pv)
        for pv in self.list_WCIB:
            # fake_caget output is of type string seperated by comma
            # device_type = epics.caget(pv, as_string=True)
            device_type = fake_caget(self.pvDict, pv)
            logger.debug(f"device_type: {device_type}")
            if re.search(r"DI", device_type):
                self.digital_inputs.append(pv)
                self.digital_inputs_ui.append(pv)
            if re.search(r"DRV", device_type):
                self.drives.append(pv)
                # self.display_drives.append(pv)
            if re.search(r"ENC", device_type):
                self.encoders.append(pv)
                # self.display_encoders.append(pv)

        # Calling other methods
        # self.load_di()
        self.load_axis_di()
        self.load_axis_di_ui()
        self.load_di()
        self.load_di_ui()
        self.load_drives()
        self.load_encoders()

    def load_axis(self):
        """
        Called from load_ioc
        ---
        Calls publish axis
        """
        logger.info(f"in get pvs from input")
        # print(self.ioc_name.text())

        self.axis = identify_axis(self.pvDict)
        self.publish_axis()
        self.publish_axis_ui()
        self.publish_axis_expert()

    def save_stage(self):
        logger.info(f"in save_stage")

        # setup holder for stagged mapping
        numStages = self.axis_list.count()
        logger.debug(f"numStages count: {numStages}")
        # self.staged_mapping= [[] for _ in range(numStages)]

        # saving DI components
        # currAxis = self.axis_list.currentRow()
        self.qCurrAxis = self.axis_list.currentRow()
        currAxis = self.qCurrAxis
        logger.debug(f"currAxis: {self.qCurrAxis}")
        currAxisDi = self.digital_input_axis.currentRow() + 1
        logger.debug(f"currAxisDi: {currAxisDi}")
        if self.digital_input_hardware.currentItem().text() != "None":
            currDiHardware = self.digital_input_hardware.currentItem().text()
        else:
            currDiHardware = ""
        logger.debug(f"currDiHardware: {currDiHardware}")
        if self.digital_input_channels.currentItem() != None:
            currDiHardwareChan = str(
                int(self.digital_input_channels.currentItem().text())
            )
        else:
            currDiHardwareChan = ""
        logger.debug(f"currDiHardwareChan: {currDiHardwareChan}")

        if (currDiHardware != None and currDiHardware != "None") and (
            self.digital_input_channels.currentItem() == None
        ):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Please Select DI Hardware Channel")
            msg.setInformativeText(f"No DI Hardware Channel Found!")
            msg.setWindowTitle("Warning")
            msg.setStandardButtons(QMessageBox.Ok)

            msg.exec_()

        if len(self.staged_mapping[0]) and currAxisDi == 1:
            self.staged_mapping[0][0].clear()
        elif len(self.staged_mapping[0]) and currAxisDi == 2:
            self.staged_mapping[0][1].clear()
        elif len(self.staged_mapping[0]) and currAxisDi == 3:
            self.staged_mapping[0][2].clear()

        if currAxisDi == 1:
            self.staged_mapping[0][0].append("0" + str(currAxisDi))
            if currDiHardware != "":
                self.staged_mapping[0][0].append(currDiHardware)
            if currDiHardwareChan != "":
                self.staged_mapping[0][0].append(currDiHardwareChan)
        elif currAxisDi == 2:
            self.staged_mapping[0][1].append("0" + str(currAxisDi))
            if currDiHardware != "":
                self.staged_mapping[0][1].append(currDiHardware)
            if currDiHardwareChan != "":
                self.staged_mapping[0][1].append(currDiHardwareChan)
        elif currAxisDi == 3:
            self.staged_mapping[0][2].append("0" + str(currAxisDi))
            if currDiHardware != "":
                self.staged_mapping[0][2].append(currDiHardware)
            if currDiHardwareChan != "":
                self.staged_mapping[0][2].append(currDiHardwareChan)

        # saving drive
        if self.drives_list.currentItem() == None:
            self.staged_de[0][0] = ["None"]
        elif self.drives_list.currentItem().text() == "None":
            self.staged_de[0][0] = ["None"]
        else:
            self.staged_de[0][0] = [self.drives_list.currentItem().text()]
        if self.enocders_list.currentItem() == None:
            self.staged_de[0][1] = ["None"]
        elif self.enocders_list.currentItem().text() == "None":
            self.staged_de[0][1] = ["None"]
        else:
            self.staged_de[0][1] = [self.enocders_list.currentItem().text()]

        self.check_duplicate_di()
        self.check_duplicate_drv()
        self.check_duplicate_enc()
        # self.staged_mapping[currAxis].append('0'+str(currAxisDi))
        # self.staged_mapping[currAxis].append(currDiHardware)
        # self.staged_mapping[currAxis].append(currDiHardwareChan)

        # show mapping
        logger.debug(f"staged mapping: {self.staged_mapping}")
        logger.debug(f"staged de: {self.staged_de}")

    def clear_stage(self):
        logger.info(f"in clear_stage")
        # try:
        # for sublist in self.staged_mapping:
        #     # Loop through and remove the element if it exists in any of the inner lists
        #     for inner_list in range(1,sublist):
        #         # if element in inner_list:
        #             inner_list.remove(1)
        #             inner_list.remove(2)

        for sublist in self.staged_mapping:
            for inner_list in sublist:
                inner_list.clear()
        for sublist in self.staged_de:
            for inner_list in sublist:
                inner_list.clear()
        logger.debug(f"staged mapping: {self.staged_mapping}")
        logger.debug(f"staged de: {self.staged_de}")

    # def detect_linked_hardware_di(self):
    #     logger.info(f"in detect_linked_hardware_di")
    #     axis_di_idx = self.digital_input_axis.currentRow()
    #     currAxisIdx = self.axis_list.currentRow()
    #     currAxis = self.val_to_key(self.axis[currAxisIdx])
    #     detectableDi = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1))
    #     logger.debug(f"link to check: {detectableDi}")
    #     DI_hardware = fake_caget(self.pvDict, detectableDi + ":ID_RBV")

    #     logger.debug(f"DI_hardware: {DI_hardware}")
    #     DI_hardware_Channel = fake_caget(self.pvDict, detectableDi + ":HardChNum_RBV")
    #     logger.debug(f"DI_hardware_channel: {DI_hardware_Channel}")

    def detect_linked_drv(self):
        logger.info(f"in detect_linked_drv")
        currAxisIdx = self.axis_list.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableDRV = currAxis + ":SelG:DRV:Id_RBV"
        drvValue = fake_caget(self.pvDict, detectableDRV)
        logger.debug(f"drvValue: {drvValue}")

        for i in range(0, self.drives_list.count()):
            if drvValue == self.drives_list.item(i).text():
                logger.debug(f"found drv: {self.drives_list.item(i).text()}")
                self.drives_list.setCurrentRow(i)
                break
            else:
                logger.debug("No link found, defaulting to None")
                self.drives_list.setCurrentRow(0)

    def detect_linked_drv_ui(self):
        logger.info(f"in detect_linked_drv_ui")
        currAxisIdx = self.display_axis.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableDRV = currAxis + ":SelG:DRV:Id_RBV"
        logger.debug(f"detDRV: {detectableDRV}")
        drvValue = fake_caget(self.pvDict, detectableDRV)
        logger.debug(f"drvValue: {drvValue}")

        for i in range(0, self.display_drives.count()):
            if drvValue == self.display_drives.item(i).text():
                logger.debug(f"found drv: {self.display_drives.item(i).text()}")
                self.display_drives.setCurrentRow(i)
                break
            else:
                logger.debug("No link found, defaulting to None")
                self.display_drives.setCurrentRow(0)

    def detect_linked_enc(self):
        logger.info(f"in detect_linked_enc")
        currAxisIdx = self.axis_list.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableENC = currAxis + ":SelG:ENC:Id_RBV"
        encValue = fake_caget(self.pvDict, detectableENC)
        logger.debug(f"encValue: {encValue}")

        for i in range(0, self.enocders_list.count()):
            currEnc = self.enocders_list.item(i).text()
            logger.debug(f"currEnc: {currEnc}, sizeEnc: {len(self.enocders_list)}")
            if encValue == currEnc:
                logger.debug(f"found enc: {self.enocders_list.item(i).text()}")
                self.enocders_list.setCurrentRow(i)
                break
            else:
                logger.debug("No link found, defaulting to None")
                self.enocders_list.setCurrentRow(0)

    def detect_linked_enc_ui(self):
        logger.info(f"in detect_linked_enc_ui")
        currAxisIdx = self.display_axis.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableENC = currAxis + ":SelG:ENC:Id_RBV"
        encValue = fake_caget(self.pvDict, detectableENC)
        logger.debug(f"encValue: {encValue}")

        for i in range(0, self.display_encoders.count()):
            if encValue == self.display_encoders.item(i).text():
                logger.debug(f"found drv: {self.display_encoders.item(i).text()}")
                self.display_encoders.setCurrentRow(i)
                break
            else:
                logger.debug("No link found, defaulting to None")
                self.display_encoders.setCurrentRow(0)

    def select_axis(self):
        logger.info(f"in select_axis")
        self.detect_linked_enc()
        self.detect_linked_drv()
        self.publish_axis_di()

    def select_axis_ui(self):
        logger.info(f"in select_axis_ui")
        self.detect_linked_enc_ui()
        self.detect_linked_drv_ui()
        self.publish_axis_di_ui()

    def publish_axis_di(self):
        logger.info(f"in publish_axis_di")
        # if self.axis_di_init:
        self.digital_input_axis.clear()
        numDI = 0

        # currAxisIdx = self.axis_list.currentRow()
        # logger.debug(f"currAxisIdx: {self.axis[currAxisIdx]}")
        # currAxis = self.val_to_key(self.axis[currAxisIdx])
        # logger.debug(f"currAxis: {currAxis}")

        currAxis = self.val_to_key(self.axis_list.currentItem().text())

        for items in self.loaded_unique_di:
            if items.startswith(currAxis):
                numDI = numDI + 1
        for i in range(0, numDI):
            self.digital_input_axis.addItem("0" + str(1 + i))
            # self.axis_di_init = False
        # elif self.axis_di_init is False:
        # self.digital_input_axis.setCurrentRow(self.axis_di_idx)

        self.select_di_channel()

    def publish_axis_di_ui(self):
        logger.info(f"in publish_axis_di_ui")
        # if self.axis_di_init:
        self.ui_digital_input_axis.clear()
        numDI = 0

        # currAxisIdx = self.axis_list.currentRow()
        # logger.debug(f"currAxisIdx: {self.axis[currAxisIdx]}")
        # currAxis = self.val_to_key(self.axis[currAxisIdx])
        # logger.debug(f"currAxis: {currAxis}")

        currAxis = self.val_to_key(self.display_axis.currentItem().text())
        logger.debug(f"currAxis: {currAxis}")
        for items in self.loaded_unique_di_ui:
            if items.startswith(currAxis):
                numDI = numDI + 1
        for i in range(0, numDI):
            self.ui_digital_input_axis.addItem("0" + str(1 + i))
            # self.axis_di_init = False
        # elif self.axis_di_init is False:
        # self.digital_input_axis.setCurrentRow(self.axis_di_idx)

        self.select_di_channel_ui()

    def publish_axis(self):
        """
        Called from load_axis
        ---

        """
        # update enum with axis pulled from .db file
        logger.info(f"in populate axis")
        self.axis_list.clear()

        # for item in self.axis:
        #     self.axis_list.addItem(item)

        self.axis_list.addItems(self.axis)

        if not self.axis_list.isEnabled():
            self.axis_list.setEnabled(True)
        # print(self.axis_selection)
        # self.staged_mapping= [[] for _ in range(self.axis_list.count())]

        # self.staged_mapping = [
        #     [[""] for _ in range(3)] for _ in range(self.axis_list.count())
        # ]

        self.staged_mapping = [[["01"], ["02"], ["03"]]]
        self.staged_de = [[["None"], ["None"]]]

    def load_axis_di(self):
        """ """
        logger.info(f"in load_axis_di")
        self.digital_input_axis.clear()

        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        delimiter = ":Id_RBV"
        # logger.debug(f"di_val: {axis_di}")
        for item in self.axis:
            logger.debug(f"axis: {item}")
            # name = self.val_to_key(item)
            # logger.debug(f"name: {name}")
            # cleaned_di = name.replace(delimiter, "")
            # logger.debug(f"cleaned item: {cleaned_di}")
            # pv = fake_caget(self.pvDict, cleaned_di)
            self.loaded_unique_di.append(self.identify_di(item))

            # self.digital_input_axis.addItem(val)
        self.loaded_unique_di = [
            item for sublist in self.loaded_unique_di for item in sublist
        ]
        logger.debug(f"val: {self.loaded_unique_di}")
        # if not self.digital_input_axis.isEnabled():
        #     self.digital_input_hardware.setEnabled(True)
        # self.discover_di_channel()

    def load_axis_di_ui(self):
        """ """
        logger.info(f"in load_axis_di_ui")
        self.ui_digital_input_axis.clear()

        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        delimiter = ":Id_RBV"
        # logger.debug(f"di_val: {axis_di}")
        for item in self.axis:
            logger.debug(f"axis: {item}")
            # name = self.val_to_key(item)
            # logger.debug(f"name: {name}")
            # cleaned_di = name.replace(delimiter, "")
            # logger.debug(f"cleaned item: {cleaned_di}")
            # pv = fake_caget(self.pvDict, cleaned_di)
            self.loaded_unique_di_ui.append(self.identify_di(item))

            # self.digital_input_axis.addItem(val)
        self.loaded_unique_di_ui = [
            item for sublist in self.loaded_unique_di_ui for item in sublist
        ]
        logger.debug(f"val: {self.loaded_unique_di_ui}")
        # if not self.digital_input_axis.isEnabled():
        #     self.digital_input_hardware.setEnabled(True)
        # self.discover_di_channel()

    def load_di(self):
        """
        comes from WCIB
        needs to publish, and call discover_di_channel
        """
        logger.info(f"in load_di")
        self.digital_input_hardware.clear()
        self.digital_input_hardware.addItem("None")
        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        delimiter = ":WCIB_RBV"
        for item in self.digital_inputs:
            cleaned_di = item.replace(delimiter, ":Id_RBV")
            logger.debug(f"cleaned item: {cleaned_di}")
            val = fake_caget(self.pvDict, cleaned_di)
            self.digital_input_hardware.addItem(val)
        # self.digital_input_hardware.setCurrentRow(0)
        if not self.digital_input_hardware.isEnabled():
            self.digital_input_hardware.setEnabled(True)
        self.discover_di_channel()

    def load_di_ui(self):
        """
        comes from WCIB
        needs to publish, and call discover_di_channel
        """
        logger.info(f"in load_di_ui")
        self.ui_digital_input_hardware.clear()
        self.ui_digital_input_hardware.addItem("None")
        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        delimiter = ":WCIB_RBV"
        for item in self.digital_inputs_ui:
            cleaned_di = item.replace(delimiter, ":Id_RBV")
            logger.debug(f"cleaned item: {cleaned_di}")
            val = fake_caget(self.pvDict, cleaned_di)
            self.ui_digital_input_hardware.addItem(val)
        # self.digital_input_hardware.setCurrentRow(0)
        if not self.ui_digital_input_hardware.isEnabled():
            self.ui_digital_input_hardware.setEnabled(True)
        self.discover_di_channel_ui()

    def discover_di_channel(self):
        """
        comes from load_di
        ---
        find out number of DIs
        """
        logger.info(f"in load_di channel")
        # self.digital_input_channels.clear()
        # logger.debug(f"di text: {self.digital_inputs[self.digital_input_hardware.currentRow()]}")
        # val = self.digital_inputs[self.digital_input_hardware.currentRow()]
        # delimiter = ":WCIB_RBV"
        # cleaned_di = val.replace(delimiter, ":NUMDI_RBV")
        # logger.debug(f"cleaned axis: {cleaned_di}")
        # nums = fake_caget(self.pvDict, cleaned_di)
        # self.digital_input_channels = int(nums) + 1

        for pv in self.pvDict:
            if pv.endswith("NUMDI_RBV"):
                logger.debug(f"pv: {pv}")
                self.loaded_di_channels.append(pv)

    def discover_di_channel_ui(self):
        """
        comes from load_di
        ---
        find out number of DIs
        """
        logger.info(f"in load_di channel_ui")
        # self.digital_input_channels.clear()
        # logger.debug(f"di text: {self.digital_inputs[self.digital_input_hardware.currentRow()]}")
        # val = self.digital_inputs[self.digital_input_hardware.currentRow()]
        # delimiter = ":WCIB_RBV"
        # cleaned_di = val.replace(delimiter, ":NUMDI_RBV")
        # logger.debug(f"cleaned axis: {cleaned_di}")
        # nums = fake_caget(self.pvDict, cleaned_di)
        # self.digital_input_channels = int(nums) + 1

        for pv in self.pvDict:
            if pv.endswith("NUMDI_RBV"):
                logger.debug(f"pv: {pv}")
                self.loaded_di_channels_ui.append(pv)

        # for i in range(1, int(nums) + 1):
        #     self.digital_input_channels.addItem(str(i))
        # # self.digital_input_channels.setCurrentRow(0)
        # if not self.digital_input_channels.isEnabled():
        #     self.digital_input_channels.setEnabled(True)

    # def publish_di_channel(self):
    #     self.digital_input_channels.clear()

    def select_di_channel(self):
        logger.info(f" select_di_channel:")
        # self.check_duplicate_di
        axis_di_idx = self.digital_input_axis.currentRow()
        logger.debug(f"axis_di_idx: {axis_di_idx}")
        currAxisIdx = self.axis_list.currentRow()
        logger.debug(f"currAxisIdx: {currAxisIdx}")
        logger.debug(f"axis: {self.axis[currAxisIdx]}")
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        logger.debug(f"currAxis: {currAxis}")
        detectableDi = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1))
        logger.debug(f"link to check: {detectableDi}")
        DI_hardware = fake_caget(self.pvDict, detectableDi + ":ID_RBV")
        if DI_hardware == "":
            DI_hardware = None
        logger.debug(f"DI_hardware: {DI_hardware}")
        DI_hardware_Channel = fake_caget(self.pvDict, detectableDi + ":HardChNum_RBV")
        logger.debug(f"DI_hardware_channel: {DI_hardware_Channel}")
        # returnStatus = self.digital_input_hardware.findItems(value, Qt.MatchCaseSensitive)
        # logger.debug(f"returnStatus: {returnStatus.text()}")

        logger.debug("searching for DI hardware")
        # detect DI hardware
        for i in range(0, self.digital_input_hardware.count()):
            if DI_hardware == self.digital_input_hardware.item(i).text():
                # logger.debug(f"currItem: {self.digital_input_hardware.item(i).text()}")
                logger.debug(
                    f"found hardware: {self.digital_input_hardware.item(i).text()}"
                )
                self.digital_input_hardware.setCurrentRow(i)
            elif DI_hardware == None:
                logger.debug("no hardware detected")
                self.digital_input_hardware.setCurrentRow(0)
            else:
                logger.debug("something went wrong/thinking")

        logger.debug("searching for di hardware channel")
        for i in range(0, self.digital_input_channels.count()):
            if DI_hardware_Channel == self.digital_input_channels.item(i).text():
                logger.debug(
                    f"found channel: {self.digital_input_channels.item(i).text()}"
                )
                self.digital_input_channels.setCurrentRow(i)
            elif DI_hardware_Channel == "0":
                logger.debug("something went wrong, should not be possible")
                self.digital_input_channels.selectionMode(QAbstractItemView.NoSelection)

        if axis_di_idx == 0:
            self.store_di_selection[0] = [
                self.digital_input_hardware.currentRow(),
                self.digital_input_channels.currentRow(),
            ]
        elif axis_di_idx == 1:
            self.store_di_selection[1] = [
                self.digital_input_hardware.currentRow(),
                self.digital_input_channels.currentRow(),
            ]
        elif axis_di_idx == 2:
            self.store_di_selection[2] = [
                self.digital_input_hardware.currentRow(),
                self.digital_input_channels.currentRow(),
            ]

    def select_di_channel_ui(self):
        logger.info(f" select_di_channel_ui:")
        # self.check_duplicate_di
        axis_di_idx = self.ui_digital_input_axis.currentRow()
        logger.debug(f"axis_di_idx: {axis_di_idx}")
        currAxisIdx = self.display_axis.currentRow()
        logger.debug(f"currAxisIdx: {currAxisIdx}")
        logger.debug(f"axis: {self.axis[currAxisIdx]}")
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        logger.debug(f"currAxis: {currAxis}")
        detectableDi = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1))
        logger.debug(f"link to check: {detectableDi}")
        DI_hardware = fake_caget(self.pvDict, detectableDi + ":ID_RBV")
        if DI_hardware == "":
            DI_hardware = None
        logger.debug(f"DI_hardware: {DI_hardware}")
        DI_hardware_Channel = fake_caget(self.pvDict, detectableDi + ":HardChNum_RBV")
        logger.debug(f"DI_hardware_channel: {DI_hardware_Channel}")
        # returnStatus = self.digital_input_hardware.findItems(value, Qt.MatchCaseSensitive)
        # logger.debug(f"returnStatus: {returnStatus.text()}")

        logger.debug("searching for DI hardware")
        # detect DI hardware
        for i in range(0, self.ui_digital_input_hardware.count()):
            if DI_hardware == self.ui_digital_input_hardware.item(i).text():
                # logger.debug(f"currItem: {self.digital_input_hardware.item(i).text()}")
                print(
                    f"found hardware: {self.ui_digital_input_hardware.item(i).text()}"
                )
                self.ui_digital_input_hardware.setCurrentRow(i)
                break
            elif DI_hardware == None:
                logger.debug("no hardware detected")
                self.ui_digital_input_hardware.setCurrentRow(0)
            else:
                logger.debug("something went wrong/thinking")

        logger.debug("searching for di hardware channel")
        for i in range(0, self.ui_digital_input_channels.count()):
            if DI_hardware_Channel == self.ui_digital_input_channels.item(i).text():
                logger.debug(
                    f"found channel: {self.ui_digital_input_channels.item(i).text()}"
                )
                self.ui_digital_input_channels.setCurrentRow(i)
            elif DI_hardware_Channel == "0":
                logger.debug("something went wrong, should not be possible")
                self.ui_digital_input_channels.selectionMode(
                    QAbstractItemView.NoSelection
                )

        if axis_di_idx == 0:
            self.store_di_selection[0] = [
                self.digital_input_hardware.currentRow(),
                self.ui_digital_input_channels.currentRow(),
            ]
        elif axis_di_idx == 1:
            self.store_di_selection[1] = [
                self.digital_input_hardware.currentRow(),
                self.ui_digital_input_channels.currentRow(),
            ]
        elif axis_di_idx == 2:
            self.store_di_selection[2] = [
                self.digital_input_hardware.currentRow(),
                self.ui_digital_input_channels.currentRow(),
            ]

        # currDI = self.loaded_di_channels[currDiIdx]
        # logger.debug(f"currDI: {currDI}")
        # currDiChanIdx = self.digital_input_channels.currentRow()

        # for di in self.digital_input_channels:
        #     """
        #     finish code here need to implement
        #     when a di slot is selected save the selected mapping
        #     in self.store_di_selection = {}
        #     """
        #     pass

    def load_di_channel(self):
        logger.debug("load di_channel")
        self.digital_input_channels.clear()
        currDiIdx = self.digital_input_hardware.currentRow()
        currDI = self.digital_inputs[currDiIdx]
        logger.debug(f"DI idx: {currDI}")
        delimiter = ":WCIB_RBV"
        cleaned_di = currDI.replace(delimiter, ":NUMDI_RBV")
        logger.debug(f"cleaned axis: {cleaned_di}")
        self.di_size = fake_caget(self.pvDict, cleaned_di)
        logger.debug(f"di size: {self.di_size}")
        if self.di_size is not None and self.di_size != 0:
            for i in range(0, int(self.di_size)):
                self.digital_input_channels.addItem(str(i + 1))
        else:
            self.digital_input_channels.clear()

    def load_di_channel_ui(self):
        logger.info(f"in load di_channel_ui")
        self.ui_digital_input_channels.clear()
        currDiIdx = self.ui_digital_input_hardware.currentRow()
        logger.debug(f"currDiIdx: {currDiIdx}")
        currDI = self.digital_inputs_ui[currDiIdx]
        logger.debug(f"DI idx: {currDI}")
        delimiter = ":WCIB_RBV"
        cleaned_di = currDI.replace(delimiter, ":NUMDI_RBV")
        logger.debug(f"cleaned axis: {cleaned_di}")
        self.di_size = fake_caget(self.pvDict, cleaned_di)
        if self.di_size != 0 or self.di_size != None:
            for i in range(0, int(self.di_size)):
                self.ui_digital_input_channels.addItem(str(i + 1))
        else:
            self.ui_digital_input_channels.clear()

    def load_di_slot(self):
        """
        this kinda works, it needs to be modified to detect all axis DIS
        """
        id_list = []
        id_nums = []
        logger.info(f"in load_di_slot")
        self.digital_input_axis.clear()
        currentAxisIndx = self.axis_list.currentRow()
        logger.debug(f"currentAxisIndx: {currentAxisIndx}")
        logger.debug(f"currentAxis: {self.axis[currentAxisIndx]}")
        axisKey = self.axis[currentAxisIndx]
        keys_with_value = [
            key for key, value in self.pvDict.items() if value == axisKey
        ]
        axis = strip_key(keys_with_value)
        logger.debug(f"axis: {axis}")
        for pv in self.pvDict.keys():
            if re.search(rf"{axis}:SelG:DI:*", pv):
                id_list.append(re.sub(r":\w+RBV", "", pv))
        # a = [1, 2, 1, 1, 3, 4, 3, 3, 5]
        res = list(dict.fromkeys(id_list))
        # print(res)
        for j in res:
            re.sub(r"")

    def load_drives(self):
        # update enum with drives pulled from .db file
        logger.info(f"in load drives")
        self.drives_list.clear()
        self.drives_list.addItem("None")
        self.display_drives.clear()
        self.display_drives.addItem("None")
        # self.drives = identify_drive(self.pvList, self.axis_list.currentItem().text())

        delimiter = ":WCIB_RBV"
        for item in self.drives:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            logger.debug(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)

            # publish drive
            self.drives_list.addItem(val)
            self.display_drives.addItem(val)
        # self.drives_list.setCurrentRow(0)

        if not self.drives_list.isEnabled():
            self.drives_list.setEnabled(True)
        if not self.display_drives.isEnabled():
            self.display_drives.setEnabled(True)

        # print(self.drive_selection)

    def load_encoders(self):
        # update enum with drives pulled from .db file
        logger.info(f"in load enc")
        self.enocders_list.clear()
        self.enocders_list.addItem("None")
        self.display_encoders.clear()
        self.display_encoders.addItem("None")
        # self.enocder_type = identify_enc(self.pvList, self.axis_list.currentItem().text())
        delimiter = ":WCIB_RBV"
        # logger.debug(f"encoder list size: {len(self.encoders)}")
        for item in self.encoders:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            logger.debug(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)

            # publish encoders
            self.enocders_list.addItem(val)
            self.display_encoders.addItem(val)
        # self.enocders_list.setCurrentRow(0)

        if not self.enocders_list.isEnabled():
            self.enocders_list.setEnabled(True)
        if not self.display_encoders.isEnabled():
            self.display_encoders.setEnabled(True)
        # print(self.encoder_selection)

    def publish_axis_ui(self):
        # update enum with axis pulled from .db file
        logger.info(f"in populate axis_ui")
        self.display_axis.clear()
        self.display_axis.addItems(self.axis)
        # idx = self.axis_list
        # self.display_axis.setCurrentRow(self.axis_list.currentRow())
        # self.display_axis.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_axis.isEnabled():
            self.display_axis.setEnabled(True)
        logger.debug(f"caput to: self.axis_selection")

    # def load_di_ui(self):
    #     logger.info(f"in load_di_ui")
    #     self.ui_digital_input_hardware.clear()
    #     di_list = self.digital_inputs
    #     delimiter = ":WCIB_RBV"
    #     for item in di_list:
    #         cleaned_di = item.replace(delimiter, ":Id_RBV")
    #         val = fake_caget(self.pvDict, cleaned_di)
    #         self.ui_digital_input_hardware.addItem(val)
    #     self.ui_digital_input_hardware.setCurrentRow(self.digital_input_hardware.currentRow())
    #     self.ui_digital_input_hardware.setSelectionMode(QAbstractItemView.NoSelection)
    #     if not self.ui_digital_input_hardware.isEnabled():
    #         self.ui_digital_input_hardware.setEnabled(True)
    # self.discover_di_channel()

    def load_di_c_ui(self):
        logger.info(f"in load_di_c_ui")
        self.ui_digital_input_channels.clear()
        print(
            f"di text: {self.digital_inputs[self.digital_input_hardware.currentRow()]}"
        )
        val = self.digital_inputs[self.digital_input_hardware.currentRow()]
        delimiter = ":WCIB_RBV"
        cleaned_di = val.replace(delimiter, ":NUMDI_RBV")
        logger.debug(f"cleaned axis: {cleaned_di}")
        nums = fake_caget(self.pvDict, cleaned_di)
        for i in range(1, int(nums) + 1):
            self.ui_digital_input_channels.addItem(str(i))
        self.ui_digital_input_channels.setCurrentRow(
            self.digital_input_channels.currentRow()
        )
        self.ui_digital_input_channels.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.ui_digital_input_channels.isEnabled():
            self.ui_digital_input_channels.setEnabled(True)

    def load_drives_ui(self):
        # update enum with drives pulled from .db file
        logger.info(f"in populate drives_ui")
        self.display_drives.clear()
        # self.drives = identify_drive(self.pvList, self.axis_list.currentItem().text())

        delimiter = ":WCIB_RBV"
        drives = self.drives
        for item in drives:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            # logger.debug(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)
            self.display_drives.addItem(val)
        self.display_drives.setCurrentRow(self.drives_list.currentRow())
        self.display_drives.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_drives.isEnabled():
            self.display_drives.setEnabled(True)

    def load_encoders_ui(self):
        # update enum with drives pulled from .db file
        logger.info(f"in populate enc_ui")
        self.display_encoders.clear()
        # self.enocder_type = identify_enc(self.pvList, self.axis_list.currentItem().text())
        delimiter = ":WCIB_RBV"
        # logger.debug(f"encoder list size: {len(self.encoders)}")
        encoders = self.encoders
        for item in encoders:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            logger.debug(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)
            self.display_encoders.addItem(val)
        self.display_encoders.setCurrentRow(self.enocders_list.currentRow())
        self.display_encoders.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_encoders.isEnabled():
            self.display_encoders.setEnabled(True)
        # print(self.encoder_selection)

    def publish_axis_expert(self):
        # update enum with axis pulled from .db file
        logger.info(f"in populate axis_expert")
        self.expert_axis.clear()
        axis_list = self.axis
        for item in axis_list:
            self.expert_axis.addItem(item)
        # idx = self.axis_list
        # self.expert_axis.setCurrentRow(0)
        if not self.expert_axis.isEnabled():
            self.expert_axis.setEnabled(True)
        logger.debug(f"caput to: self.axis_selection")

    def expert_update_nc(self):
        logger.info("in expert_update_nc")

        axis_index = self.expert_axis.currentIndex()
        axis = f"{self.prefixName}0{axis_index + 1}"

        # Clear previous items
        self.expert_nc_filter.source_model.setStringList([])
        self.nc_list.clear()

        # Identify NC params
        self.nc_list = identify_nc_params(axis, self.pvDict)

        temp = epics.caget_many(self.nc_list, as_string=True)
        logger.info(f"items size: {len(temp)}")

        # Add items (filter out None just in case)
        items = [item for item in temp if item]
        self.expert_nc_filter.add_items(items)

        # Enable widget if needed
        self.expert_nc_filter.setEnabled(True)

        # Select first item (if exists)
        if items:
            first_index = self.expert_nc_filter.filter_model.index(0, 0)
            self.expert_nc_filter.list_view.setCurrentIndex(first_index)
            # self.expert_nc_filter.line_edit.setText(items[0])

        # Dynamically add param widgets
        self.add_param_widgets(self.nc_list, self.param_list)

    def expert_update_drive(self, axis):
        logger.info(f"\nin expert_update_drive")

        # Get current axis
        axis_index = self.expert_axis.currentIndex()
        axis = f"{self.prefixName}0{axis_index + 1}"
        print(f"axis: {axis}")
        print(f'caget: {axis + ":SelG:DRV:Id_RBV"}')

        # Clear previous items
        self.expert_drive_filter.source_model.setStringList([])
        self.coe_drive_list.clear()

        # Get hardware slice
        # TST:UM:01:SelG:DRV:Id_RBV
        hardwareID = epics.caget(axis + ":SelG:DRV:Id_RBV", as_string=True)

        print(f"hardwareID after split: {hardwareID}")
        # Remove everything after the first underscore
        if hardwareID and "_" in hardwareID:
            hardwareID = hardwareID.split("_", 1)[0]
        print(f"hardwareID after split: {hardwareID}")

        self.coe_drive_list = identify_coe_drive_params(
            axis + ":" + hardwareID, self.pvDict
        )

        temp = epics.caget_many(self.coe_drive_list, as_string=True)
        logger.info(f"items size: {len(temp)}")

        # Add items (filter out None just in case)
        items = [item for item in temp if item]
        self.expert_drive_filter.add_items(items)

        # Enable widget if needed
        self.expert_drive_filter.setEnabled(True)

        # Select first item (if exists)
        if items:
            first_index = self.expert_drive_filter.filter_model.index(0, 0)
            self.expert_drive_filter.list_view.setCurrentIndex(first_index)
            # self.expert_drive_filter.line_edit.setText(items[0])

        # # Dynamically add param widgets
        self.add_param_widgets(self.coe_drive_list, self.expert_drive_param_list)

    def expert_update_encoder(self, axis):
        logger.info(f"in expert_update_encoder")

        # Get current axis
        axis_index = self.expert_axis.currentIndex()
        axis = f"{self.prefixName}0{axis_index + 1}"
        print(f"axis: {axis}")
        print(f'caget: {axis + ":SelG:ENC:Id_RBV"}')

        # Clear previous items
        self.expert_encoder_filter.source_model.setStringList([])
        self.coe_encoder_list.clear()

        # Get hardware slice
        # TST:UM:01:SelG:DRV:Id_RBV
        hardwareID = epics.caget(axis + ":SelG:ENC:Id_RBV", as_string=True)

        print(f"hardwareID after split: {hardwareID}")
        # Remove everything after the first underscore
        if hardwareID and "_" in hardwareID:
            hardwareID = hardwareID.split("_", 1)[0]
        print(f"hardwareID after split: {hardwareID}")

        self.coe_encoder_list = identify_coe_enc_params(
            axis + ":" + hardwareID, self.pvDict
        )

        temp = epics.caget_many(self.coe_encoder_list, as_string=True)
        logger.info(f"items size: {len(temp)}")

        # Add items (filter out None just in case)
        items = [item for item in temp if item]
        self.expert_encoder_filter.add_items(items)

        # Enable widget if needed
        self.expert_encoder_filter.setEnabled(True)

        # Select first item (if exists)
        if items:
            first_index = self.expert_encoder_filter.filter_model.index(0, 0)
            self.expert_encoder_filter.list_view.setCurrentIndex(first_index)
            # self.expert_encoder_filter.line_edit.setText(items[0])

        # # Dynamically add param widgets
        self.add_param_widgets(self.coe_encoder_list, self.expert_encoder_param_list)

    def expert_update_nc_io(self, index):
        logger.info(f"in expert_update_nc_io")
        self.nc_list_indx = self.nc_param_dropdown.currentIndex()
        nc_pv = self.nc_param_dropdown.currentText()
        # logger.debug(f"nc_pv: {nc_pv}")
        # self.nc_param_io.channel = "ca://" + nc_pv
        self.nc_param_io.setText("ca://" + nc_pv)
        if not self.nc_param_io.isEnabled():
            self.nc_param_io.setEnabled(True)
        self.nc_param_io.show()

    def update_drive_coe_io(self, index):
        logger.info(f"in update_drive_coe_io")
        self.coe_drive_indx = self.drive_coe_dropdown.currentIndex()
        coe_pv = self.drive_coe_dropdown.currentText()
        logger.debug(f"UDIO: coe_pv: {coe_pv}")
        # self.drive_coe_io.channel = "ca://" + coe_pv
        self.drive_coe_io.setText("ca://" + coe_pv)
        if not self.drive_coe_io.isEnabled():
            self.drive_coe_io.setEnabled(True)
        self.drive_coe_io.show()

    def update_enc_coe_io(self, index):
        logger.info(f"in update_enc_coe_io")
        self.coe_enc_indx = self.encoder_coe_dropdown.currentIndex()
        coe_pv = self.encoder_coe_dropdown.currentText()
        logger.debug(f"UEIO: coe_pv: {coe_pv}")
        # self.encoder_coe_io.channel = "ca://" + coe_pv
        self.encoder_coe_io.setText("ca://" + coe_pv)
        if not self.encoder_coe_io.isEnabled():
            self.encoder_coe_io.setEnabled(True)
        self.encoder_coe_io.show()

    def expert_update_nc_index(self):
        self.nc_list_indx = self.nc_param_dropdown.currentIndex()


# def gather_plc_pvs_from_file(self):
#   pathToPv = ''
#   for pvs in
#   return pvList
if __name__ == "__main__":
    app = QApplication([])
    gui = MyDisplay()
    gui.show()
    sys.exit(app.exec_())
