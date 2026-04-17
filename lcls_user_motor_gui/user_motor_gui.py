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
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
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

        logger.debug(
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
            self.wcibDict = {}

            # self.dg_list = []
            self.ca_nc_list = []
            self.ca_coe_drive_list = []
            self.ca_coe_encoder_list = []
            self.ca_dg_list = []
            self.param_connections = []
            self.ioc_path = "/reg/g/pcds/epics-dev/nlentz/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"

        """
        Load IOC pvs from ioc db, setup the tab signals and populate data from loaded db
        """

        for slot in [
            self.load_ioc_data,
            self.setup_tab_signals,
            self.populate_options,
            # self.load_axis,
        ]:
            self.load_ioc.clicked.connect(slot)

    def setup_tab_signals(self):
        logger.debug(f"in setup_tab_signals")
        """
        Setup all of the signals for each of the tab widgets.
        """

        """
        Settings tab
        """
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

        """
        SIGNALS
        """
        """
        Expert
        """
        for slot in [
            self.expert_widget.expert_update_nc,
            self.expert_widget.expert_update_drive,
            self.expert_widget.expert_update_encoder,
        ]:
            self.expert_widget.expert_axis.currentIndexChanged.connect(slot)

        self.expert_widget.expert_nc_widget.currentIndexChanged.connect(
            self.expert_widget.highlight_nc_param
        )
        self.expert_widget.expert_drive_widget.currentIndexChanged.connect(
            self.expert_widget.highlight_coe_drive_param
        )
        self.expert_widget.expert_encoder_widget.currentIndexChanged.connect(
            self.expert_widget.highlight_coe_encoder_param
        )

        """
        User Input
        """
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

        """
        Diagnostic
        """
        self.diagnostic_widget.diagnostic_hardware_selection.currentRowChanged.connect(
            self.diagnostic_widget.populate_diagnostic_coe
        )

        self.diagnostic_widget.diagnostic_param_filter.currentIndexChanged.connect(
            self.diagnostic_widget.populate_diagnostic_widget
        )
        self.diagnostic_widget.diagnostic_axis_selection.currentIndexChanged.connect(
            self.diagnostic_widget.populate_diagnostic_hardware
        )

        """
        Linker
        """
        # digitial input handling signals
        self.linker_widget.digital_input_hardware.currentRowChanged.connect(
            self.linker_widget.load_di_channel
        )
        self.linker_widget.digital_input_axis.currentRowChanged.connect(
            self.linker_widget.select_di_channel
        )
        self.linker_widget.drives_list.currentRowChanged.connect(
            self.linker_widget.load_drives_channel
        )
        self.linker_widget.encoders_list.currentRowChanged.connect(
            self.linker_widget.load_encoders_channel
        )
        """
        axis signals
        """
        self.linker_widget.axis_list_linker.currentRowChanged.connect(
            self.linker_widget.isStagedMappingSet
        )

        """
        mapping signals
        """
        self.linker_widget.stage_mapping.clicked.connect(self.linker_widget.save_stage)
        self.linker_widget.see_staged_mapping.clicked.connect(
            self.linker_widget.see_stage
        )
        self.linker_widget.clear_mapping.clicked.connect(self.linker_widget.clear_stage)

        """
        Linking Buttons
        """
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

    # Currently not used
    def when_param_changed(self, idx, pv, lineedit):
        logger.debug(f"in when_param_changed")
        lineedit = self.param_connections[idx]
        logger.debug(f"Value for PV {pv} (index {idx}) is now {lineedit.text()}")

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
                logger.debug(f"goal and rbv match: {goal}, {rbv}")
            else:
                logger.debug(f"goal and rbv DO NOT match: {goal}, {rbv}")
            logger.debug(f"bool: {is_match}")

        # Define what to do on error
        def on_error(exception):
            logger.debug(f"Exception in caput_check_task: {exception}")

        # Start the thread worker
        worker = ThreadWorker(caput_check_task, pv)
        worker.returned.connect(on_result)
        worker.error_raised.connect(on_error)
        # Keep a reference alive! Otherwise it might get garbage-collected!
        if not hasattr(self, "_workers"):
            self._workers = []
        self._workers.append(worker)
        worker.start()

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
        """
        load pvs from a db file, find the prefix, sort pvs by type and make a dictionaries or lists from the cagets
        """

        logger.info(f"in load test list")
        configured = "./unit_test_data.json"
        integration_test = "/cds/home/c/ctsoi/epics-dev/ioc/user_motors/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"
        integration_box_test = "/reg/g/pcds/epics-dev/nlentz/lcls-plc-template-user-motors/iocBoot/ioc-lcls-plc-template-user-motors/lcls_plc_template_user_motors.db"

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
        #     logger.debug(match.group(1))  # Output: TST:UM:
        # self.prefixName = match.group(1)

        ## integration test
        iocpath = integration_box_test

        # hard code ioc path
        self.pvList = discover_pvs("", usr_db_path=iocpath, find_makefile=True)

        # for testing only
        # Save self.pvList to a file
        # with open("pvlist.txt", "w") as f:
        #     for pv in self.pvList:
        #         f.write(pv + "\n")

        # finding prefix at element 0
        self.prefixName = self.pvList[0]
        self.user_input_widget.prefixName = self.prefixName
        self.linker_widget.prefixName = self.prefixName
        self.expert_widget.prefixName = self.prefixName
        self.diagnostic_widget.prefixName = self.prefixName
        logger.debug(self.prefixName)
        self.pvList = self.pvList[1:-1]

        logger.debug(f"prefixName: {self.prefixName}")

        # caget whole list

        for item in self.pvList:
            if re.search(r"NC", item):
                self.ncList.append(item)
            elif re.search(r"COE", item):
                # logger.debug(f'item: {item}')
                self.coeList.append(item)
            elif re.search(r"WCIB", item):
                self.wcibList.append(item)
        # pv_caget_list = epics.caget_many(self.pvList, as_string=True)
        ca_wcib_list = epics.caget_many(self.wcibList, as_string=True)
        ca_nc_list = epics.caget_many(self.ncList, as_string=True)
        logger.debug(f"len self.coeList: {len(self.coeList)}")
        ca_coe_list = epics.caget_many(self.coeList, as_string=True)
        # put pvs and cagets into a dictionary
        # self.pvDict = dict(zip(self.pvList, pv_caget_list))

        self.ncDict = dict(zip(self.ncList, ca_nc_list))
        self.coeDict = dict(zip(self.coeList, ca_coe_list))
        self.wcibDict = dict(zip(self.wcibList, ca_wcib_list))
        # selfcoevDict = dict(zip(self.pvList, pv_caget_list))
        self.expert_widget.nc_list = self.ncList.copy()
        self.expert_widget.coe_drive_list = self.coeList.copy()
        self.expert_widget.coe_encoder_list = self.coeList.copy()
        self.user_input_widget.pvDict = self.pvDict
        self.linker_widget.pvDict = self.pvDict
        self.expert_widget.pvDict = self.pvDict
        self.diagnostic_widget.dg_list = self.coeList.copy()
        self.diagnostic_widget.ca_coe_list = self.coeDict.copy()
        # logger.debug(self.pvDict)

    def populate_options(self):
        logger.info(f"in populate options")

        """
        Called from load_ioc
        ---
        Calls WCIB
        """
        # identify WCIB PVs
        self.identify_WCIB()

    def identify_WCIB(self):
        """
        Given a a dictionary of WCIB PVs we move this into a list then sort by the type:
        SA - Software Axis
        DI - Digital Input
        DRV - Drive
        ENC - Encoder

        Once sorted, copy to each of the seperate widgets
        """
        logger.info(f"in identify_WCIB'")
        self.clear_items()
        # self.list_WCIB = []

        # for pv in self.pvDict:
        for pv in self.wcibDict:
            # logger.debug(f"pv: {pv}")
            if re.search(r".*:WCIB_RBV", pv):
                # logger.debug(f"wcib pv: {pv}")
                self.list_WCIB.append(pv)
        for pv in self.list_WCIB:
            # fake_caget output is of type string seperated by comma
            # device_type = epics.caget(pv, as_string=True)
            # device_type = fake_caget(self.pvDict, pv)
            device_type = fake_caget(self.wcibDict, pv)
            logger.debug(f"device_type: {device_type}, pv: {pv}")
            if isinstance(device_type, str) and re.search(r"SA", device_type):
                # logger.debug(f"axis: {pv}")
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
        logger.debug(f"num of axis: {len(self.axis)}")
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

    def publish_axis_di(self):
        logger.info(f"in publish_axis_di")
        # if self.axis_di_init:
        self.linker_widget.digital_input_axis.clear()
        numDI = 0

        currAxis = self.val_to_key(
            self.linker_widget.axis_list_linker.currentItem().text()
        )
        logger.debug(f"currAxis: {currAxis}")

        # need to change this to number of DIs
        for i in range(0, 3):
            self.linker_widget.digital_input_axis.addItem("0" + str(1 + i))

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

        self.linker_widget.staged_mapping = [[["01"], ["02"], ["03"]]]
        self.linker_widget.staged_de = [[["None"], ["None"]]]

    def load_axis_di(self):
        """ """
        logger.info(f"in load_axis_di")
        self.linker_widget.digital_input_axis.clear()

        # logger.debug(f"di_val: {axis_di}")
        for item in self.axis:
            logger.debug(f"axis: {item}")
            self.loaded_unique_di.append(self.identify_di(item))

            # self.digital_input_axis.addItem(val)
        self.loaded_unique_di = [
            item for sublist in self.loaded_unique_di for item in sublist
        ]
        logger.debug(f"val: {self.loaded_unique_di}")
        # if not self.digital_input_axis.isEnabled():
        #     self.digital_input_hardware.setEnabled(True)
        # self.discover_di_channel()


if __name__ == "__main__":
    app = QApplication([])
    gui = MainWindow()
    gui.show()
    sys.exit(app.exec_())
