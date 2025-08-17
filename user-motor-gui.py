import json
import re
import sys
import time
from enum import Enum
from os import path

import epics

# from epics import PV, fake_caget, cainfo, caput
from pydm import Display
from pydm.widgets.enum_combo_box import PyDMEnumComboBox
from pydm.widgets.label import PyDMLabel
from pydm.widgets.line_edit import PyDMLineEdit
from pydm.widgets.pushbutton import PyDMPushButton
from qtpy import QtCore, uic
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
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


class StageSettings(QDialog):
    def __init__(self, parent=None):
        super(StageSettings, self).__init__(parent)
        loadUi("stage-config.ui", self)  # Load the UI from the .ui file


class MyDisplay(Display):
    ui: QWidget

    def __init__(self, parent=None, args=None, macros=None):
        print("In init")
        super().__init__(parent=parent, args=args, macros=macros)

        # initialize vars
        init = True
        if init:
            init = False
            self.pvDict = {}
            self.expertDict = {}
            self.plc_ioc_list = []
            self.plc_ioc_label = ""
            self.axis = []
            self.digital_inputs = []
            self.drives = []
            self.encoders = []
            self.enocders_list = []
            self.list_WCIB = []
            self.cleaned_di = ""

        # finding children
        # Linker Tab
        self.plc_ioc_list = self.ui.findChild(QComboBox, "plc_ioc_list")
        self.plc_ioc_label = self.ui.findChild(PyDMLabel, "ioc_label")
        self.axis_list = self.ui.findChild(QListWidget, "axis_list_view")
        self.digital_inputs_list = self.ui.findChild(
            QListWidget, "digital_inputs_list_view"
        )
        self.digital_input_channels = self.ui.findChild(
            QListWidget, "digital_input_comp"
        )
        self.drives_list = self.ui.findChild(QListWidget, "drives_list_view")
        self.enocders_list = self.ui.findChild(QListWidget, "encoders_list_view")
        self.confirm_mapping = self.ui.findChild(QPushButton, "confirm_mapping")
        self.view_logger = self.ui.findChild(PyDMPushButton, "view_logger_button")
        self.load_ioc = self.ui.findChild(QPushButton, "load_ioc_pushButton")

        """
        Load IOC pvs from ioc and update the axis list and identify PVs based on this
        """
        for slot in [self.load_test_list, self.load_axis, self.identify_WCIB]:
            self.load_ioc.clicked.connect(slot)

        # User Input Tab
        self.display_axis = self.ui.findChild(QListWidget, "display_axis_ui")
        self.display_drives = self.ui.findChild(QListWidget, "display_drives_ui")
        self.display_di = self.ui.findChild(QListWidget, "display_di_ui")
        self.display_di_c = self.ui.findChild(QListWidget, "display_di_c_ui")
        self.display_encoders = self.ui.findChild(QListWidget, "display_encoders_ui")
        self.stage_settings = self.ui.findChild(QPushButton, "stage_settings")

        # Expert Tab
        self.expert_axis = self.ui.findChild(QListWidget, "expert_axis")
        self.expert_nc_list = self.ui.findChild(QListWidget, "expert_nc_list")
        self.expert_drive_list = self.ui.findChild(QListWidget, "expert_drive_list")
        self.expert_enocder_list = self.ui.findChild(QListWidget, "expert_enocder_list")

        # Signals
        # for slot in [self.update_nc(self.expert_axis.currentRow())]:
        #     self.expert_axis.currentRowChanged.connect(slot)
        # self.expert_axis.currentRowChanged.connect(self.update_nc(self.expert_axis.currentRow()))

        self.digital_inputs_list.currentRowChanged.connect(self.populate_di_channel)
        self.stage_settings.clicked.connect(self.open_stage_settings)
        self.confirm_mapping.clicked.connect(self.update_links)

    def update_links(self):
        print("in update links")
        self.populate_axis_ui()
        self.populate_di_ui()
        self.populate_di_c_ui()
        self.populate_drives_ui()
        self.populate_encoders_ui()
        self.populate_axis_expert()
        self.update_nc(self.axis[self.expert_axis.currentRow()])

    def open_stage_settings(self):
        stageSettings = StageSettings(self)
        stageSettings.exec_()

    def ui_filename(self):
        return "user-motor-gui.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def load_test_list(self):
        filepath1 = "./unit_test_data.json"
        filepath2 = "./expert_unit_test.json"
        pv_list = []
        try:
            # with open(f"{filepath}", "r") as f:
            #     for pvs in f:
            #         pv_list.append(pvs)

            with open(filepath1, "r") as file:
                self.pvDict = json.load(file)
        except Exception as e:
            print(f"Failed to read {filepath1}: {e}")
        try:
            # with open(f"{filepath}", "r") as f:
            #     for pvs in f:
            #         pv_list.append(pvs)

            with open(filepath2, "r") as file:
                self.expertDict = json.load(file)
        except Exception as e:
            print(f"Failed to read {filepath2}: {e}")
        # for pvs in pv_list:
        #     print(pvs)
        # pv_list = json.loads(pv_list)
        print(f"type: {type(self.pvDict)}")

    def identify_WCIB(self):
        self.list_WCIB = []
        for pv in self.pvDict:
            if re.search(r".*:WCIB_RBV", pv):
                self.list_WCIB.append(pv)
        for pv in self.list_WCIB:
            # fake_caget output is of type string seperated by comma
            comp_type = fake_caget(self.pvDict, pv)
            if re.search(r"DI", comp_type):
                self.digital_inputs.append(pv)
            if re.search(r"DRV", comp_type):
                self.drives.append(pv)
            if re.search(r"ENC", comp_type):
                self.encoders.append(pv)
        self.populate_di()
        self.populate_drives()
        self.populate_encoders()

    def load_axis(self):
        """
        Once the ioc has been identified, find the available axis and load them.
        """
        print("in get pvs from input")
        # print(self.ioc_name.text())

        # use this to pull db from ioc
        # iocpath, dbpath = grep_ioc(
        #     self.ioc_name.text(), "/cds/group/pcds/pyps/config/mec/iocmanager.cfg", "-p"
        # )
        # print(iocpath, dbpath)
        # iocpath = '/reg/g/pcds/epics-dev/ctsoi/ioc/tst/lcls-plc-hxr-polycap/iocBoot/ioc-lcls-plc-hxr-polycap/lcls_plc_hxr_polycap.db'

        # self.pvList = discover_pvs('', usr_db_path=iocpath)
        # self.pvList = self.load_test_list()

        self.axis_list.clear()
        self.populate_axis()

    def populate_axis(self):
        # update enum with axis pulled from .db file
        print("in populate axis")
        self.axis = identify_axis(self.pvDict)

        for item in self.axis:
            self.axis_list.addItem(item)
        self.axis_list.setCurrentRow(0)
        if not self.axis_list.isEnabled():
            self.axis_list.setEnabled(True)
        # print(self.axis_selection)

    def populate_di(self):
        print("in populate_di")
        self.digital_inputs_list.clear()
        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        delimiter = ":WCIB_RBV"
        for item in self.digital_inputs:
            cleaned_di = item.replace(delimiter, ":Id_RBV")
            print(f"cleaned item: {cleaned_di}")
            val = fake_caget(self.pvDict, cleaned_di)
            self.digital_inputs_list.addItem(val)
        self.digital_inputs_list.setCurrentRow(0)
        if not self.digital_inputs_list.isEnabled():
            self.digital_inputs_list.setEnabled(True)
        self.populate_di_channel()

    def populate_di_channel(self):
        print("in populate_di channel")
        self.digital_input_channels.clear()
        print(f"di text: {self.digital_inputs[self.digital_inputs_list.currentRow()]}")
        val = self.digital_inputs[self.digital_inputs_list.currentRow()]
        delimiter = ":WCIB_RBV"
        cleaned_di = val.replace(delimiter, ":NUMDI_RBV")
        print(f"cleaned axis: {cleaned_di}")
        nums = fake_caget(self.pvDict, cleaned_di)
        for i in range(1, int(nums) + 1):
            self.digital_input_channels.addItem(str(i))
        self.digital_input_channels.setCurrentRow(0)
        if not self.digital_input_channels.isEnabled():
            self.digital_input_channels.setEnabled(True)

    def populate_drives(self):
        # update enum with drives pulled from .db file
        print("in populate drives")
        self.drives_list.clear()
        # self.drives = identify_drive(self.pvList, self.axis_list.currentItem().text())

        delimiter = ":WCIB_RBV"
        for item in self.drives:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            print(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)
            self.drives_list.addItem(val)
        self.drives_list.setCurrentRow(0)

        if not self.drives_list.isEnabled():
            self.drives_list.setEnabled(True)

        # print(self.drive_selection)

    def populate_encoders(self):
        # update enum with drives pulled from .db file
        print("in populate enc")
        self.enocders_list.clear()
        # self.enocder_type = identify_enc(self.pvList, self.axis_list.currentItem().text())
        delimiter = ":WCIB_RBV"
        # print(f"encoder list size: {len(self.encoders)}")
        for item in self.encoders:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            print(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)
            self.enocders_list.addItem(val)
        self.enocders_list.setCurrentRow(0)

        if not self.enocders_list.isEnabled():
            self.enocders_list.setEnabled(True)
        # print(self.encoder_selection)

    def populate_axis_ui(self):
        # update enum with axis pulled from .db file
        print("in populate axis_ui")
        self.display_axis.clear()
        axis_list = self.axis
        for item in axis_list:
            self.display_axis.addItem(item)
        # idx = self.axis_list
        self.display_axis.setCurrentRow(self.axis_list.currentRow())
        if not self.display_axis.isEnabled():
            self.display_axis.setEnabled(True)
        print(f"caput to: self.axis_selection")

    def populate_di_ui(self):
        print("in populate_di_ui")
        self.display_di.clear()
        di_list = self.digital_inputs
        delimiter = ":WCIB_RBV"
        for item in di_list:
            cleaned_di = item.replace(delimiter, ":Id_RBV")
            val = fake_caget(self.pvDict, cleaned_di)
            self.display_di.addItem(val)
        self.display_di.setCurrentRow(self.digital_inputs_list.currentRow())
        if not self.display_di.isEnabled():
            self.display_di.setEnabled(True)
        # self.populate_di_channel()

    def populate_di_c_ui(self):
        print("in populate_di_c_ui")
        self.display_di_c.clear()
        print(f"di text: {self.digital_inputs[self.digital_inputs_list.currentRow()]}")
        val = self.digital_inputs[self.digital_inputs_list.currentRow()]
        delimiter = ":WCIB_RBV"
        cleaned_di = val.replace(delimiter, ":NUMDI_RBV")
        print(f"cleaned axis: {cleaned_di}")
        nums = fake_caget(self.pvDict, cleaned_di)
        for i in range(1, int(nums) + 1):
            self.display_di_c.addItem(str(i))
        self.display_di_c.setCurrentRow(self.digital_input_channels.currentRow())
        if not self.display_di_c.isEnabled():
            self.display_di_c.setEnabled(True)

    def populate_drives_ui(self):
        # update enum with drives pulled from .db file
        print("in populate drives_ui")
        self.display_drives.clear()
        # self.drives = identify_drive(self.pvList, self.axis_list.currentItem().text())

        delimiter = ":WCIB_RBV"
        drives = self.drives
        for item in drives:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            # print(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)
            self.display_drives.addItem(val)
        self.display_drives.setCurrentRow(self.drives_list.currentRow())

        if not self.display_drives.isEnabled():
            self.display_drives.setEnabled(True)

    def populate_encoders_ui(self):
        # update enum with drives pulled from .db file
        print("in populate enc_ui")
        self.display_encoders.clear()
        # self.enocder_type = identify_enc(self.pvList, self.axis_list.currentItem().text())
        delimiter = ":WCIB_RBV"
        # print(f"encoder list size: {len(self.encoders)}")
        encoders = self.encoders
        for item in encoders:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            print(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)
            self.display_encoders.addItem(val)
        self.display_encoders.setCurrentRow(self.enocders_list.currentRow())

        if not self.display_encoders.isEnabled():
            self.display_encoders.setEnabled(True)
        # print(self.encoder_selection)

    def populate_axis_expert(self):
        # update enum with axis pulled from .db file
        print("in populate axis_expert")
        self.expert_axis.clear()
        axis_list = self.axis
        for item in axis_list:
            self.expert_axis.addItem(item)
        # idx = self.axis_list
        self.expert_axis.setCurrentRow(0)
        if not self.expert_axis.isEnabled():
            self.expert_axis.setEnabled(True)
        print(f"caput to: self.axis_selection")

    def update_nc(self, axis):
        """
        if axis selection current index is changed grab index and axis reference to populate NC dropdown
        get currently selected axis
        identify all NC params based on selected axis
        clear previous list
        add items
        """
        print("in update_nc")
        print(f"axis: {axis}")
        self.expert_nc_list.clear()
        keys_with_value = [key for key, value in self.pvDict.items() if value == axis]
        print(f"Key: {keys_with_value}")
        cleaned_axis = strip_key(keys_with_value)
        print(f"cleaned axis: {cleaned_axis}")
        items = identify_nc_params(cleaned_axis, self.expertDict)
        for item in items:
            self.expert_nc_list.addItem(item)
        self.expert_nc_list.setCurrentRow(0)
        if not self.expert_nc_list.isEnabled():
            self.expert_nc_list.setEnabled(True)

    def update_coe_drive(self, axis):
        print("in update coe drive")
        self.coe_drive_list.clear()

        """Need to coordinate with Nick on how to structure PVs"""

        keys_with_value = [key for key, value in self.pvDict.items() if value == axis]
        if self.drive_selection.currentText() == "EL7047":
            self.coe_drive_list = identify_coe_drive_params(
                self.axis_selection.currentText(),
                "EL7047",
                self.pvList,
            )
        elif self.drive_selection.currentText() == "EL7062":
            self.coe_drive_list = identify_coe_drive_params(
                self.axis_selection.currentText(),
                "EL7062",
                self.pvList,
            )
        self.drive_coe_dropdown.addItems(self.coe_drive_list)
        self.drive_coe_dropdown.setCurrentIndex(0)
        self.drive_coe_dropdown.show()
        if not self.drive_coe_dropdown.isEnabled():
            self.drive_coe_dropdown.setEnabled(True)

    def update_coe_enc(self):
        print("in update enc coe")
        self.coe_enc_list.clear()
        self.encoder_coe_dropdown.clear()
        if self.encoder_selection.currentText() == "EL5102":
            self.coe_enc_list = identify_coe_enc_params(
                self.axis_selection.currentText(),
                "EL5102",
                self.pvList,
            )
        elif self.encoder_selection.currentText() == "EL5042":
            self.coe_enc_list = identify_coe_enc_params(
                self.axis_selection.currentText(),
                "EL5042",
                self.pvList,
            )
        self.encoder_coe_dropdown.addItems(self.coe_enc_list)
        self.encoder_coe_dropdown.setCurrentIndex(0)
        self.encoder_coe_dropdown.show()
        if not self.encoder_coe_dropdown.isEnabled():
            self.encoder_coe_dropdown.setEnabled(True)

    def update_nc_io(self, index):
        print("in update_nc_io")
        self.nc_list_indx = self.nc_param_dropdown.currentIndex()
        nc_pv = self.nc_param_dropdown.currentText()
        # print(f"nc_pv: {nc_pv}")
        # self.nc_param_io.channel = "ca://" + nc_pv
        self.nc_param_io.setText("ca://" + nc_pv)
        if not self.nc_param_io.isEnabled():
            self.nc_param_io.setEnabled(True)
        self.nc_param_io.show()

    def update_drive_coe_io(self, index):
        print("in update_drive_coe_io")
        self.coe_drive_indx = self.drive_coe_dropdown.currentIndex()
        coe_pv = self.drive_coe_dropdown.currentText()
        print(f"UDIO: coe_pv: {coe_pv}")
        # self.drive_coe_io.channel = "ca://" + coe_pv
        self.drive_coe_io.setText("ca://" + coe_pv)
        if not self.drive_coe_io.isEnabled():
            self.drive_coe_io.setEnabled(True)
        self.drive_coe_io.show()

    def update_enc_coe_io(self, index):
        print("in update_enc_coe_io")
        self.coe_enc_indx = self.encoder_coe_dropdown.currentIndex()
        coe_pv = self.encoder_coe_dropdown.currentText()
        print(f"UEIO: coe_pv: {coe_pv}")
        # self.encoder_coe_io.channel = "ca://" + coe_pv
        self.encoder_coe_io.setText("ca://" + coe_pv)
        if not self.encoder_coe_io.isEnabled():
            self.encoder_coe_io.setEnabled(True)
        self.encoder_coe_io.show()

    def update_nc_index(self):
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
