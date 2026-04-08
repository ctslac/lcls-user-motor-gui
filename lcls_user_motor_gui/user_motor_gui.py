import asyncio
import json
import logging
import re
import sys
import time
from enum import Enum
from os import path
from pathlib import Path

import epics
import numpy as np

# import epics
from epics import PV, caget, caput
from pcdsutils.qt.designer_display import DesignerDisplay

# from epics import PV, fake_caget, cainfo, caput
from pydm import Display
from pydm.widgets.enum_combo_box import PyDMEnumComboBox
from pydm.widgets.label import PyDMLabel
from pydm.widgets.line_edit import PyDMLineEdit
from pydm.widgets.pushbutton import PyDMPushButton
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCompleter, QLineEdit, QListView, QVBoxLayout, QWidget
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qtpy.uic import loadUi

from .processing.discover_pvs import discover_pvs
from .processing.parse_pvs import (
    axis_wcib_to_id,
    fake_caget,
    identify_axis,
    identify_coe_drive_params,
    identify_coe_enc_params,
    identify_dg_params,
    identify_drive,
    identify_enc,
    identify_inputs,
    identify_nc_params,
    strip_key,
    what_can_i_be,
)
from .qt_helpers import ThreadWorker
from .utils.dict_tools import (
    find_unique_keys,
    identify_di,
    identify_drv,
    identify_enc,
    strip_axis_id,
    val_to_key,
)
from .widgets.diagnostics import DiagnosticsWindow
from .widgets.expert import ExpertWindow
from .widgets.linker import LinkerWindow
from .widgets.user_input import UserInputWindow

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


class MappingWindow(QDialog):
    def __init__(self, parent=None):
        super(MappingWindow, self).__init__(parent)
        loadUi("mapping-window.ui", self)
        self.staged_mappings_list = self.findChild(QListWidget, "staged_mappings_list")
        # for stages in MainWindow(self.staged_mapping):


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


class SettingsWindow(DesignerDisplay, QWidget):
    filename = "settings_tab.ui"
    ui_dir = Path(__file__).parent / "ui"


class MainWindow(DesignerDisplay, QWidget):
    filename = "main_window_new.ui"
    ui_dir = Path(__file__).parent / "ui"

    # Main Window Widgets
    reload_ioc: QPushButton
    load_ioc: QPushButton
    status_logger: QPlainTextEdit
    main_tabs: QTabWidget

    def __init__(
        self,
        parent: QWidget | None = None,
    ):
        # Pass ONLY parent to super().__init__()
        super().__init__(parent)
        # Store macros yourself
        # self.macros = macros

        # user input
        self.user_input_widget = UserInputWindow(self, logger=logger)
        self.main_tabs.addTab(self.user_input_widget, "User Input")

        # linker
        self.linker_widget = LinkerWindow(self, logger=logger)
        self.main_tabs.addTab(self.linker_widget, "Linker")

        # expert
        self.expert_widget = ExpertWindow(self, logger=logger)
        self.main_tabs.addTab(self.expert_widget, "Expert")

        # diagnostic
        self.diagnostic_widget = DiagnosticsWindow(self, logger=logger)
        self.main_tabs.addTab(self.diagnostic_widget, "Diagnostic")

        # setting
        self.setting_widget = SettingsWindow()
        self.main_tabs.addTab(self.setting_widget, "Settings")

        # Mapping message box
        self.msg = QMessageBox()
        self.isMsgActive = False

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
            self.drives = []
            self.digital_inputs = ["None"]
            # self.digital_inputs_ui = ["None"]
            self.digital_inputs_hardware = ["None"]
            self.digital_inputs_hardware_ui = ["None"]
            self.drives_linker = ["None"]
            self.encoders = ["None"]
            self.enocders_list = []
            self.list_WCIB = []
            self.cleaned_di = ""
            self.di_num_channels = 0
            self.loaded_unique_di = []
            # self.loaded_unique_di_ui = []
            # self.loaded_di_channels = []
            # self.loaded_di_channels_ui = []
            self.loaded_di_channel_inputs = []
            self.store_di_selection = [[-1, -1], [-1, -1], [-1, -1]]
            self.axis_di_idx = 0
            self.axis_di_init = True
            self.di_size = 0
            # self.staged_mapping = []
            # self.staged_de = []
            # self.qCurrAxis = 0
            self.ncList = []
            self.coeList = []
            self.wcibList = []

            # self.dg_list = []
            self.ca_nc_list = []
            self.ca_coe_drive_list = []
            self.ca_coe_encoder_list = []
            self.ca_dg_list = []
            self.param_connections = []
            self.ioc_path = "/reg/g/pcds/epics-dev/nlentz/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"

        """
        Load IOC pvs from ioc and update the axis list and identify PVs based on this
        """

        # Load IOC: load axis, Populate DI, DRV, ENC
        # for slot in [self.load_tabs, self.load_ioc_data, self.load_axis, self.populate_options]:
        #     self.load_ioc.clicked.connect(slot)
        for slot in [
            self.load_ioc_data,
            self.setup_tab_signals,
            self.populate_options,
            # self.load_axis,
        ]:
            self.load_ioc.clicked.connect(slot)

        # User Input Tab
        # self.display_axis = self.ui.findChild(QListWidget, "display_axis_ui")
        # self.display_drives = self.ui.findChild(QListxWidget, "display_drives_ui")
        # self.ui_digital_input_axis = self.ui.findChild(
        #     QListWidget, "ui_digital_input_axis"
        # )
        # self.ui_digital_input_hardware = self.ui.findChild(
        #     QListWidget, "ui_digital_input_hardware"
        # )
        # self.ui_digital_input_channels = self.ui.findChild(
        #     QListWidget, "ui_digital_input_channels"
        # )
        # self.display_encoders = self.ui.findChild(QListWidget, "display_encoders_ui")
        # self.stage_settings = self.ui.findChild(QPushButton, "stage_settings")

        # ## Expert Tab
        # self.expert_axis = self.ui.findChild(QComboBox, "expert_axis")
        # self.expert_nc_list = self.ui.findChild(QListWidget, "expert_nc_list")
        # self.expert_drive_list = self.ui.findChild(QListWidget, "expert_drive_list")
        # self.expert_enocder_list = self.ui.findChild(QListWidget, "expert_enocder_list")
        # self.param_list = self.ui.findChild(QListWidget, "expert_param_list")
        # self.expert_drive_param_list = self.ui.findChild(
        #     QListWidget, "expert_coe_drive_list"
        # )
        # self.expert_encoder_param_list = self.ui.findChild(
        #     QListWidget, "expert_coe_encoder_list"
        # )
        # self.nc_groupbox = self.ui.findChild(QGroupBox, "expert_nc_param")
        # self.drive_groupbox = self.ui.findChild(QGroupBox, "expert_drive_param")
        # self.encoder_groupbox = self.ui.findChild(QGroupBox, "expert_encoder_param")

        # # Diagnostic Tab
        # self.diagnostic_axis_selection = self.ui.findChild(
        #     QComboBox, "diagnostic_axis_selection"
        # )
        # self.diagnostic_hardware_selection = self.ui.findChild(
        #     QListWidget, "diagnostic_hardware_selection"
        # )
        # self.diagnostic_groupbox = self.ui.findChild(QGroupBox, "diagnostic_groupbox")

        # self.diagnostic_param_filter = FilteredListWidget(self.diagnostic_groupbox)
        # self.diagnostic_groupbox.layout().addWidget(self.diagnostic_param_filter)

        # self.diagnostic_params_groupbox = self.ui.findChild(
        #     QGroupBox, "diagnostic_params_groupbox"
        # )

        # # Mapping
        # self.stage_mapping = self.ui.findChild(QPushButton, "stage_mapping")
        # self.see_mapping = self.ui.findChild(QPushButton, "see_staged_mapping")
        # self.clear_mapping = self.ui.findChild(QPushButton, "clear_mapping")

        # # Logger

        # if self.status_logger is not None:
        #     handler = QPlainTextEditLoggerHandler(self.status_logger)
        #     formatter = logging.Formatter("%(asctime)s - %(message)s")
        #     handler.setFormatter(formatter)
        #     logging.getLogger().addHandler(handler)
        #     logging.getLogger().setLevel(logging.INFO)
        # else:
        #     logger.warning("status_logger QPlainTextEdit not found in UI.")
        # self.duplicate_di_cb = self.ui.findChild(
        #     QCheckBox, "settings_duplicate_di_warning"
        # )

        # self.duplicate_di_cb.stateChanged.connect(self.check_duplicate_di_flag)

        # self.duplicate_drv_cb = self.ui.findChild(
        #     QCheckBox, "settings_duplicate_drv_warning"
        # )
        # self.duplicate_drv_cb.stateChanged.connect(self.check_duplicate_drv_flag)

        # self.duplicate_enc_cb = self.ui.findChild(
        #     QCheckBox, "settings_duplicate_enc_warning"
        # )
        # self.duplicate_enc_cb.stateChanged.connect(self.check_duplicate_enc_flag)
        # self.status_indicators = self.ui.findChild(QLabel, "status_indicators")

        # """
        # Signals
        # """

        # self.user_input_widget.display_axis_ui.currentRowChanged.connect(self.select_axis_ui)

        # # axis signals
        # self.axis_list.currentRowChanged.connect(self.isStagedMappingSet)
        # self.diagnostic_axis_selection.currentIndexChanged.connect(
        #     self.populate_diagnostic_hardware
        # )
        # self.diagnostic_hardware_selection.currentRowChanged.connect(
        #     self.populate_diagnostic_coe
        # )

        # self.expert_nc_filter.currentIndexChanged.connect(self.highlight_nc_param)
        # self.expert_drive_filter.currentIndexChanged.connect(
        #     self.highlight_coe_drive_param
        # )
        # self.expert_encoder_filter.currentIndexChanged.connect(
        #     self.highlight_coe_encoder_param
        # )
        # self.diagnostic_param_filter.currentIndexChanged.connect(
        #     self.populate_diagnostic_widget
        # )

        # # digitial input handling signals
        # self.digital_input_hardware.currentRowChanged.connect(self.load_di_channel)
        # self.digital_input_axis.currentRowChanged.connect(self.select_di_channel)
        # self.ui_digital_input_axis.currentRowChanged.connect(self.select_di_channel_ui)
        # self.ui_digital_input_hardware.currentRowChanged.connect(
        #     self.load_di_channel_ui
        # )

        # # mapping signals
        # self.stage_mapping.clicked.connect(self.save_stage)
        # self.see_mapping.clicked.connect(self.see_stage)
        # self.clear_mapping.clicked.connect(self.clear_stage)

        # # Misc Buttons
        # self.stage_settings.clicked.connect(self.open_stage_settings)
        # self.confirm_mapping.clicked.connect(self.update_links)

        # for slot in [
        #     self.expert_update_nc,
        #     self.expert_update_drive,
        #     self.expert_update_encoder,
        # ]:
        #     self.expert_axis.currentIndexChanged.connect(slot)

    def setup_tab_signals(self):
        print(f"in setup_tab_signals")
        # self.user_input_widget.display_axis_ui.currentRowChanged.connect(self.select_axis_ui)
        # self.user_input_widget.display_axis_ui.currentRowChanged.connect(self.user_input_widget.select_axis_ui)
        # self.linker_widget.axis_list_linker.currentRowChanged.connect(self.isStagedMappingSet)
        # self.user_input_widget.digital_input_hardware_ui.currentRowChanged.connect(
        #     self.load_di_channel_ui
        # )

        # self.user_input_widget.display_axis_ui.currentRowChanged.connect(self.select_axis_ui)
        # self.diagnostic_axis_selection.currentIndexChanged.connect(
        #     self.populate_diagnostic_hardware
        # )
        # self.diagnostic_hardware_selection.currentRowChanged.connect(
        #     self.populate_diagnostic_coe
        # )

        # self.setting_widget.settings_duplicate_di_warning.stateChanged.connect(
        #     self.check_duplicate_di_flag
        # )
        # self.setting_widget.settings_duplicate_drv_warning.stateChanged.connect(
        #     self.check_duplicate_drv_flag
        # )
        # self.setting_widget.settings_duplicate_enc_warning.stateChanged.connect(
        #     self.check_duplicate_enc_flag
        # )
        # self.status_indicators = self.ui.findChild(QLabel, "status_indicators")

        # SIGNALS
        # # Expert
        # for slot in [
        #     self.expert_widget.expert_update_nc,
        #     self.expert_widget.expert_update_drive,
        #     self.expert_widget.expert_update_encoder,
        # ]:
        #     self.expert_widget.expert_axis.currentIndexChanged.connect(slot)

        # self.expert_widget.expert_nc_widget.currentIndexChanged.connect(
        #     self.expert_widget.highlight_nc_param
        # )
        # self.expert_widget.expert_drive_widget.currentIndexChanged.connect(
        #     self.expert_widget.highlight_coe_drive_param
        # )
        # self.expert_widget.expert_encoder_widget.currentIndexChanged.connect(
        #     self.expert_widget.highlight_coe_encoder_param
        # )

        # User Input
        self.user_input_widget.display_axis_ui.currentRowChanged.connect(
            self.user_input_widget.select_axis_ui
        )
        self.user_input_widget.digital_input_axis_ui.currentRowChanged.connect(
            self.user_input_widget.select_di_channel_ui
        )
        self.user_input_widget.digital_input_hardware_ui.currentRowChanged.connect(
            self.user_input_widget.load_di_channel_ui
        )
        self.user_input_widget.display_drives_ui.currentRowChanged.connect(
            self.user_input_widget.load_drives_channel_ui
        )
        self.user_input_widget.display_encoders_ui.currentRowChanged.connect(
            self.user_input_widget.load_encoders_channel_ui
        )

        # # Diagnostic
        # self.diagnostic_widget.diagnostic_hardware_selection.currentRowChanged.connect(
        #     self.diagnostic_widget.populate_diagnostic_coe
        # )

        # self.diagnostic_widget.diagnostic_param_filter.currentIndexChanged.connect(
        #     self.diagnostic_widget.populate_diagnostic_widget
        # )
        # self.diagnostic_widget.diagnostic_axis_selection.currentIndexChanged.connect(
        #     self.diagnostic_widget.populate_diagnostic_hardware
        # )

        # Linker
        # digitial input handling signals
        self.linker_widget.digital_input_hardware.currentRowChanged.connect(
            self.linker_widget.load_di_channel
        )
        self.linker_widget.digital_input_axis.currentRowChanged.connect(
            self.linker_widget.select_di_channel
        )
        # axis signals
        self.linker_widget.axis_list_linker.currentRowChanged.connect(
            self.linker_widget.isStagedMappingSet
        )

        # mapping signals
        self.linker_widget.stage_mapping.clicked.connect(self.linker_widget.save_stage)
        self.linker_widget.see_staged_mapping.clicked.connect(
            self.linker_widget.see_stage
        )
        self.linker_widget.clear_mapping.clicked.connect(self.linker_widget.clear_stage)

        # Misc Buttons
        self.user_input_widget.stage_settings.clicked.connect(self.open_stage_settings)
        self.linker_widget.confirm_mapping.clicked.connect(
            self.linker_widget.update_links
        )

    # def check_duplicate_di_flag(self):
    #     logger.info(f"in check dup di")

    #     self.duplicate_di_cb_flag = self.setting_widget.settings_duplicate_di_warning.isChecked()

    #     logger.debug(f"isDuplicateDIWarning: {self.duplicate_di_cb_flag}")

    # def check_duplicate_drv_flag(self):
    #     logger.info(f"in check dup drv")

    #     self.duplicate_drv_cb_flag = self.setting_widget.settings_duplicate_drv_warning.isChecked()

    #     logger.debug(f"isDuplicateDIWarning: {self.duplicate_drv_cb_flag}")

    # def check_duplicate_enc_flag(self):
    #     logger.info(f"in check dup enc")

    #     self.duplicate_enc_cb_flag = self.setting_widget.settings_duplicate_enc_warning.isChecked()

    #     logger.debug(f"isDuplicateDIWarning: {self.duplicate_enc_cb_flag}")

    def extract_unique_parts(self, pv_names):
        unique_parts = set()
        for pv in pv_names:
            parts = pv.split(":")
            if len(parts) > 4:
                unique_parts.add(parts[4])
        return sorted(unique_parts)

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
    #     for i in ncs:diagnostic_param_filter
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

    def when_param_changed(self, idx, pv, lineedit):
        print(f"in when_param_changed")
        lineedit = self.param_connections[idx]
        print(f"Value for PV {pv} (index {idx}) is now {lineedit.text()}")

        # Define the function to run in a worker thread
        def caput_check_task(pv):
            pv = self.remove_name_rbv(pv)
            goal_value = epics.caget(pv + ":Goal")
            rbv_value = epics.caget(pv + ":Val_RBV")
            return goal_value == rbv_value, goal_value, rbv_value

        # Define what to do when the worker finishes
        def on_result(result):
            is_match, goal, rbv = result
            if is_match:
                print(f"goal and rbv match: {goal}, {rbv}")
            else:
                print(f"goal and rbv DO NOT match: {goal}, {rbv}")
            print(f"bool: {is_match}")

        # Define what to do on error
        def on_error(exception):
            print(f"Exception in caput_check_task: {exception}")

        # Start the thread worker
        worker = ThreadWorker(caput_check_task, pv)
        worker.returned.connect(on_result)
        worker.error_raised.connect(on_error)
        # Keep a reference alive! Otherwise it might get garbage-collected!
        if not hasattr(self, "_workers"):
            self._workers = []
        self._workers.append(worker)
        worker.start()

    # def check_duplicate_di(self):
    #     logger.info(f"in check for duplicate di")
    #     # To hold values for duplicate checking
    #     second_index_values = set()
    #     third_index_values = set()

    #     # Track duplicates
    #     duplicates_second = set()
    #     duplicates_third = set()

    #     # Loop through each sublist in the main list
    #     for sublist in self.staged_mapping:
    #         for item in sublist:
    #             if len(item) > 1:  # Check if the sublist has at least 2 elements
    #                 # Check the 2nd index value
    #                 second_index_value = item[1]
    #                 if second_index_value in second_index_values:
    #                     duplicates_second.add(second_index_value)
    #                 else:
    #                     second_index_values.add(second_index_value)

    #             if len(item) > 2:  # Check if the sublist has at least 3 elements
    #                 # Check the 3rd index value
    #                 third_index_value = item[2]
    #                 if third_index_value in third_index_values:
    #                     duplicates_third.add(third_index_value)
    #                 else:
    #                     third_index_values.add(third_index_value)
    #     if self.duplicate_di_cb_flag and (duplicates_second or duplicates_third):
    #         # Prepare the message content
    #         second_duplicates = (
    #             ", ".join(duplicates_second) if duplicates_second else "None"
    #         )
    #         third_duplicates = (
    #             ", ".join(duplicates_third) if duplicates_third else "None"
    #         )

    #         msg = QMessageBox()
    #         msg.setIcon(QMessageBox.Warning)
    #         msg.setText("Duplicate DI")
    #         msg.setInformativeText(
    #             f"Duplicate DIs found:\n2nd Index: {second_duplicates}\n3rd Index: {third_duplicates}"
    #         )
    #         msg.setWindowTitle("Warning")
    #         msg.setStandardButtons(QMessageBox.Ok)

    #         msg.exec_()

    #     # Print the results
    #     logger.debug(f"Duplicates in the 2nd index: {duplicates_second}")
    #     logger.debug(f"Duplicates in the 3rd index: {duplicates_third}")

    # def check_duplicate_drv(self):
    #     """
    #     Check for duplicate first index values in staged_de based on the first element of each inner-most list.
    #     Ignore duplicates for the value 'None'.

    #     Returns:
    #         set: A set of duplicate first index values except 'None'.
    #     """
    #     logger.info(f"in check for duplicate drv")

    #     # To hold unique values for duplicate checking
    #     seen_values = []

    #     # Track duplicates
    #     duplicates = []
    #     # Loop through each main list in data
    #     for axis in self.staged_de:
    #         # Loop through each sublist in the main list
    #         # for sublist in axis:
    #         # Ensure the sublist is a list and has at least 1 element
    #         if isinstance(axis, list) and len(axis) > 0:
    #             # Get the first element value
    #             first_element_value = axis[0]

    #             # Ignore None values or empty strings while checking for duplicates
    #             if (
    #                 first_element_value is None
    #                 or first_element_value == "None"
    #                 or first_element_value == ["None"]
    #                 or first_element_value == ""
    #             ):
    #                 continue

    #             # Check for duplicates
    #             if first_element_value in seen_values:
    #                 duplicates.append(first_element_value)
    #             else:
    #                 seen_values.append(first_element_value)

    #     if self.duplicate_di_cb_flag and len(duplicates) > 0:
    #         msg = QMessageBox()
    #         msg.setIcon(QMessageBox.Warning)
    #         msg.setText("Duplicate DRV")
    #         msg.setInformativeText(f"Duplicate DRVs found: {duplicates}")
    #         msg.setWindowTitle("Warning")
    #         msg.setStandardButtons(QMessageBox.Ok)
    #         msg.exec_()

    #     # Print the results
    #     logger.debug(f"Duplicates: {duplicates}")

    # def check_duplicate_enc(self):
    #     """
    #     Check for duplicate second index values in staged_de based on the second element of each inner-most list.
    #     Ignore duplicates for the value 'None'.

    #     Returns:
    #         set: A set of duplicate first index values except 'None'.
    #     """
    #     logger.info(f"in check for duplicate enc")

    #     # To hold unique values for duplicate checking
    #     seen_values = []

    #     # Track duplicates
    #     duplicates = []
    #     # Loop through each main list in data
    #     for axis in self.staged_de:
    #         # Loop through each sublist in the main list
    #         # for sublist in axis:
    #         # Ensure the sublist is a list and has at least 1 element
    #         if isinstance(axis, list) and len(axis) > 0:
    #             # Get the first element value
    #             first_element_value = axis[1]

    #             # Ignore None values or empty strings while checking for duplicates
    #             if (
    #                 first_element_value is None
    #                 or first_element_value == "None"
    #                 or first_element_value == ["None"]
    #                 or first_element_value == ""
    #             ):
    #                 continue

    #             # Check for duplicates
    #             if first_element_value in seen_values:
    #                 duplicates.append(first_element_value)
    #             else:
    #                 seen_values.append(first_element_value)

    #     if self.duplicate_di_cb_flag and len(duplicates) > 0:
    #         msg = QMessageBox()
    #         msg.setIcon(QMessageBox.Warning)
    #         msg.setText("Duplicate ENC")
    #         msg.setInformativeText(f"Duplicate ENCs found: {duplicates}")
    #         msg.setWindowTitle("Warning")
    #         msg.setStandardButtons(QMessageBox.Ok)
    #         msg.exec_()

    #     # Print the results
    #     logger.debug(f"Duplicates: {duplicates}")

    def open_stage_settings(self):
        stageSettings = StageSettings(self)
        stageSettings.exec_()

    # def ui_filename(self):
    #     filename = "traj.ui"
    #     ui_dir = Path(__file__).parent / "ui"
    #     return 'ui/main_window.ui'

    # def ui_filepath(self):
    #     return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def load_ioc_data(self):
        logger.info(f"in load test list")
        configured = "./unit_test_data.json"
        integration_test = "/cds/home/c/ctsoi/epics-dev/ioc/user_motors/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"
        integration_box_test = "/reg/g/pcds/epics-dev/nlentz/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"
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
        iocpath = integration_box_test

        # hard code ioc path
        self.pvList = discover_pvs("", usr_db_path=iocpath, find_makefile=True)

        # finding prefix at element 0
        self.prefixName = self.pvList[0]
        self.user_input_widget.prefixName = self.prefixName
        self.expert_widget.prefixName = self.prefixName
        self.diagnostic_widget.prefixName = self.prefixName
        print(self.prefixName)
        self.pvList = self.pvList[1:-1]

        logger.debug(f"prefixName: {self.prefixName}")

        # caget whole list

        for item in self.pvList:
            if re.search(r"NC", item):
                self.ncList.append(item)
            elif re.search(r"COE", item):
                self.coeList.append(item)
            elif re.search(r"WCIB", item):
                self.wcibList.append(item)
        # pv_caget_list = epics.caget_many(self.pvList, as_string=True)
        ca_wcib_list = epics.caget_many(self.wcibList, as_string=True)
        ca_nc_list = epics.caget_many(self.ncList, as_string=True)
        ca_coe_list = epics.caget_many(self.coeList, as_string=True)
        # put pvs and cagets into a dictionary
        # self.pvDict = dict(zip(self.pvList, pv_caget_list))

        self.ncDict = dict(zip(self.ncList, ca_nc_list))
        self.coeDict = dict(zip(self.coeList, ca_coe_list))
        self.wcibDict = dict(zip(self.wcibList, ca_wcib_list))
        # selfcoevDict = dict(zip(self.pvList, pv_caget_list))
        self.user_input_widget.pvDict = self.pvDict
        self.linker_widget.pvDict = self.pvDict
        self.expert_widget.pvDict = self.pvDict
        self.diagnostic_widget.pvDict = self.pvDict
        # print(self.pvDict)

    def val_to_key(self, val):
        key = [key for key, value in self.pvDict.items() if value == val]
        logger.debug(f"key: {key}")

        """
        there may be more than one key for any given value, i might have to change the logic here
        """
        cleaned_axis = strip_key(key[0])
        # logger.debug(f"val to key, cleaned axis: {cleaned_axis}, key: {key}")
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
        # logger.debug(f"identify_config: item, {val}, DIs, {things}")

        return things

    def identify_drv(self, item):
        val = self.val_to_key(item)
        things = self.find_unique_keys(val + ":SelG:DRV:")
        # logger.debug(f"identify_config: item, {val}, DRVs, {things}")

        return things

    def identify_enc(self, item):
        val = self.val_to_key(item)
        things = self.find_unique_keys(val + ":SelG:ENC:")
        # logger.debug(f"identify_config: item, {val}, ENCs, {things}")

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
        self.clear_items()
        # self.list_WCIB = []

        # for pv in self.pvDict:
        for pv in self.wcibDict:
            logger.debug(f"pv: {pv}")
            if re.search(r".*:WCIB_RBV", pv):
                logger.debug(f"wcib pv: {pv}")
                self.list_WCIB.append(pv)
        for pv in self.list_WCIB:
            # fake_caget output is of type string seperated by comma
            # device_type = epics.caget(pv, as_string=True)
            # device_type = fake_caget(self.pvDict, pv)
            device_type = fake_caget(self.wcibDict, pv)
            print(f"device_type: {device_type}, pv: {pv}")
            if isinstance(device_type, str) and re.search(r"SA", device_type):
                print(f"axis: {pv}")
                self.axis.append(pv)
            if isinstance(device_type, str) and re.search(r"DI", device_type):
                self.linker_widget.digital_inputs_linker.append(pv)
                self.user_input_widget.digital_inputs_ui.append(pv)
            if isinstance(device_type, str) and re.search(r"DRV", device_type):
                self.linker_widget.drives_linker.append(pv)
                self.user_input_widget.drives_ui.append(pv)
            if isinstance(device_type, str) and re.search(r"ENC", device_type):
                self.linker_widget.encoders_linker.append(pv)
                self.user_input_widget.encoders_ui.append(pv)

        # Loading Axis
        # self.axis = axis_wcib_to_id(self.pvDict, self.axis)
        print(f"num of axis: {len(self.axis)}")
        self.axis = axis_wcib_to_id(self.axis)
        self.user_input_widget.axis = self.axis
        self.user_input_widget.publish_axis_ui()
        self.linker_widget.axis = self.axis
        self.linker_widget.publish_axis()
        self.user_input_widget.publish_axis_ui()
        self.expert_widget.axis = self.axis
        self.expert_widget.publish_axis_expert()
        self.diagnostic_widget.axis = self.axis
        self.diagnostic_widget.publish_axis_diagnostic()

        # Loading DIs
        # self.load_di()
        # self.linker_widget.load_axis_di()
        # self.user_input_widget.load_axis_di_ui()
        self.linker_widget.load_di()
        self.user_input_widget.load_di_ui()

        # Loading DRVs
        self.linker_widget.load_drives()
        self.user_input_widget.load_drives_ui()

        # Loading ENCs
        self.linker_widget.load_encoders()
        self.user_input_widget.load_encoders_ui()

    def clear_items(self):
        self.list_WCIB.clear()
        self.digital_inputs.clear()
        self.user_input_widget.digital_inputs_ui.clear()
        self.drives_linker.clear()
        self.encoders.clear()

    # def load_axis(self):
    #     """
    #     Called from load_ioc
    #     ---
    #     Calls publish axis
    #     """
    #     logger.info(f"in load_axis")
    #     # print(self.ioc_name.text())

    #     self.axis = identify_axis(self.pvDict)
    #     self.user_input_widget.axis = self.axis
    #     self.linker_widget.axis = self.axis
    #     self.publish_axis()
    #     self.user_input_widget.publish_axis_ui()
    #     self.expert_widget.axis = self.axis
    #     self.expert_widget.publish_axis_expert()
    #     self.diagnostic_widget.axis = self.axis
    #     self.diagnostic_widget.publish_axis_diagnostic()

    def publish_axis_di(self):
        logger.info(f"in publish_axis_di")
        # if self.axis_di_init:
        self.linker_widget.digital_input_axis.clear()
        numDI = 0

        # currAxisIdx = self.axis_list.currentRow()
        # logger.debug(f"currAxisIdx: {self.axis[currAxisIdx]}")
        # currAxis = self.val_to_key(self.axis[currAxisIdx])
        # logger.debug(f"currAxis: {currAxis}")

        currAxis = self.val_to_key(
            self.linker_widget.axis_list_linker.currentItem().text()
        )
        logger.debug(f"currAxis: {currAxis}")
        # for items in self.loaded_unique_di:
        #     if items.startswith(currAxis):
        #         numDI = numDI + 1
        for i in range(0, 3):
            self.linker_widget.digital_input_axis.addItem("0" + str(1 + i))
            # self.axis_di_init = False
        # elif self.axis_di_init is False:
        # self.digital_input_axis.setCurrentRow(self.axis_di_idx)

        self.select_di_channel()

    def publish_axis(self):
        """
        Called from load_axis
        ---

        """
        # update enum with axis pulled from .db file
        logger.info(f"in populate axis")
        self.linker_widget.axis_list_linker.clear()

        # for item in self.axis:
        #     self.axis_list.addItem(item)

        self.linker_widget.axis_list_linker.addItems(self.axis)

        if not self.linker_widget.axis_list_linker.isEnabled():
            self.linker_widget.axis_list_linker.setEnabled(True)
        # print(self.axis_selection)
        # self.staged_mapping= [[] for _ in range(self.axis_list.count())]

        # self.staged_mapping = [
        #     [[""] for _ in range(3)] for _ in range(self.axis_list.count())
        # ]

        self.linker_widget.staged_mapping = [[["01"], ["02"], ["03"]]]
        self.linker_widget.staged_de = [[["None"], ["None"]]]

    def load_axis_di(self):
        """ """
        logger.info(f"in load_axis_di")
        self.linker_widget.digital_input_axis.clear()

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


# def gather_plc_pvs_from_file(self):
#   pathToPv = ''
#   for pvs in
#   return pvList


if __name__ == "__main__":
    app = QApplication([])
    gui = MainWindow()
    gui.show()
    sys.exit(app.exec_())
