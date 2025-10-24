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
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
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
            self.di_num_channels = 0
            self.loaded_unique_di = []
            self.loaded_di_channels = []
            self.loaded_di_channel_inputs = []
            self.store_di_selection = [[-1, -1], [-1, -1], [-1, -1]]
            self.axis_di_idx = 0
            self.axis_di_init = True
            self.di_size = 0

        # finding children
        # Linker Tab
        self.plc_ioc_list = self.ui.findChild(QComboBox, "plc_ioc_list")
        self.plc_ioc_label = self.ui.findChild(PyDMLabel, "ioc_label")
        self.axis_list = self.ui.findChild(QListWidget, "axis_list_view")
        self.digital_inputs_list = self.ui.findChild(
            QListWidget, "digital_input_list_view"
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
        self.display_di = self.ui.findChild(QListWidget, "display_di_ui")
        self.display_di_c = self.ui.findChild(QListWidget, "display_di_c_ui")
        self.display_encoders = self.ui.findChild(QListWidget, "display_encoders_ui")
        self.stage_settings = self.ui.findChild(QPushButton, "stage_settings")

        # Expert Tab
        self.expert_axis = self.ui.findChild(QListWidget, "expert_axis")
        self.expert_nc_list = self.ui.findChild(QListWidget, "expert_nc_list")
        self.expert_drive_list = self.ui.findChild(QListWidget, "expert_drive_list")
        self.expert_enocder_list = self.ui.findChild(QListWidget, "expert_enocder_list")

        """
        Signals
        """

        for slot in [self.update_nc]:
            self.expert_axis.currentRowChanged.connect(slot)
        # self.expert_axis.currentRowChanged.connect(self.update_nc(self.expert_axis.currentRow()))

        # digitial input handling signals
        # self.digital_inputs_list.currentRowChanged.connect(self.discover_di_channel)
        # self.digital_inputs_list.currentRowChanged.connect(self.load_axis_di)
        self.axis_list.currentRowChanged.connect(self.select_axis)
        self.digital_inputs_list.currentRowChanged.connect(self.load_di_channel)
        self.digital_input_axis.currentRowChanged.connect(self.select_di_channel)

        self.stage_settings.clicked.connect(self.open_stage_settings)
        self.confirm_mapping.clicked.connect(self.update_links)

    def update_links(self):
        print("in update links")
        self.publish_axis_ui()
        self.load_di_ui()
        self.load_di_c_ui()
        self.load_drives_ui()
        self.load_encoders_ui()
        self.publish_axis_expert()
        # self.update_nc(self.axis[self.expert_axis.currentRow()])

    def open_stage_settings(self):
        stageSettings = StageSettings(self)
        stageSettings.exec_()

    def ui_filename(self):
        return "user-motor-gui.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def load_test_list(self):
        print("in load test list")
        configured = "./unit_test_data.json"
        unconfigured = "./unit_test_config.json"
        filepath2 = "./expert_unit_test.json"
        filepath1 = configured
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

    def val_to_key(self, val):
        key = [key for key, value in self.pvDict.items() if value == val]
        cleaned_axis = strip_key(key)
        return str(cleaned_axis)

    def find_unique_keys(self, prefix):
        print("find unique di values")
        # assume Id_RBV
        unique_keys = set()  # Use a set to store unique values
        print(f"prefix: {prefix}")
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
        print(f"identify_config: item, {val}, DIs, {things}")

        return things

    def identify_drv(self, item):
        val = self.val_to_key(item)
        things = self.find_unique_keys(val + ":SelG:DRV:")
        print(f"identify_config: item, {val}, DRVs, {things}")

        return things

    def identify_enc(self, item):
        val = self.val_to_key(item)
        things = self.find_unique_keys(val + ":SelG:ENC:")
        print(f"identify_config: item, {val}, ENCs, {things}")

        return things

    def populate_options(self):
        print("in populate options")

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

        # # find all axis dis
        # for item in self.axis:
        #     DIs.append(self.identify_di(item))
        #     DRVs = self.identify_drv(item)
        #     ENCs = self.identify_enc(item)
        # print(f"DIs: {DIs}")
        # flat_di_list = [item for sublist in DIs for item in sublist]
        # for items in flat_di_list:
        #     print(f"items: {items}")
        #     val = fake_caget(self.pvDict, items)
        #     print(f"di val caget: {val}")

        # self.identify_WCIB

    def identify_WCIB(self):
        """
        there are three possible options:
        1. if the caget is an empty string, dont highlight anything
        2. if the there is a value and it matches something, then highlight
        3. there is a string but it doesnt match anything, something went wrong
        """
        print("in identify_WCIB'")
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

        # Calling other methods
        # self.load_di()
        self.load_axis_di()
        self.load_di()
        self.load_drives()
        self.load_encoders()

    def load_axis(self):
        """
        Called from load_ioc
        ---
        Calls publish axis
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

        self.axis = identify_axis(self.pvDict)
        self.publish_axis()

    def detect_linked_hardware_di(self):
        print("in detect_linked_hardware_di")
        axis_di_idx = self.digital_input_axis.currentRow()
        currAxisIdx = self.axis_list.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableDi = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1))
        print(f"link to check: {detectableDi}")
        DI_hardware = fake_caget(self.pvDict, detectableDi + ":ID_RBV")
        print(f"DI_hardware: {DI_hardware}")
        DI_hardware_Channel = fake_caget(self.pvDict, detectableDi + ":HardChNum_RBV")
        print(f"DI_hardware_channel: {DI_hardware_Channel}")

    def detect_linked_drv(self):
        print("in detect_linked_drv")
        currAxisIdx = self.axis_list.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableDRV = currAxis + ":SelG:DRV:Id_RBV"
        drvValue = fake_caget(self.pvDict, detectableDRV)
        print(f"drvValue: {drvValue}")

        for i in range(0, self.drives_list.count()):
            if drvValue == self.drives_list.item(i).text():
                print(f"found drv: {self.drives_list.item(i).text()}")
                self.drives_list.setCurrentRow(i)

    def detect_linked_enc(self):
        print("in detect_linked_enc")
        currAxisIdx = self.axis_list.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableENC = currAxis + ":SelG:ENC:Id_RBV"
        encValue = fake_caget(self.pvDict, detectableENC)
        print(f"emcValue: {encValue}")

        for i in range(0, self.enocders_list.count()):
            if encValue == self.enocders_list.item(i).text():
                print(f"found drv: {self.enocders_list.item(i).text()}")
                self.enocders_list.setCurrentRow(i)

    def select_axis(self):
        print("in select_axis")
        self.detect_linked_enc()
        self.detect_linked_drv()
        self.publish_axis_di()

    def publish_axis_di(self):
        print("in publish_axis_di")
        # if self.axis_di_init:
        self.digital_input_axis.clear()
        numDI = 0
        currAxisIdx = self.axis_list.currentRow()
        print(f"currAxisIdx: {self.axis[currAxisIdx]}")
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        print(f"currAxis: {currAxis}")
        for items in self.loaded_unique_di:
            if items.startswith(currAxis):
                numDI = numDI + 1
        for i in range(0, numDI):
            self.digital_input_axis.addItem("0" + str(1 + i))
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
        print("in populate axis")
        self.axis_list.clear()

        for item in self.axis:
            self.axis_list.addItem(item)
        # self.axis_list.setCurrentRow(0)
        if not self.axis_list.isEnabled():
            self.axis_list.setEnabled(True)
        # print(self.axis_selection)

    def load_axis_di(self):
        """ """
        print("in load_axis_di")
        self.digital_input_axis.clear()
        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        delimiter = ":Id_RBV"
        # print(f"di_val: {axis_di}")
        for item in self.axis:
            print(f"axis: {item}")
            # name = self.val_to_key(item)
            # print(f"name: {name}")
            # cleaned_di = name.replace(delimiter, "")
            # print(f"cleaned item: {cleaned_di}")
            # pv = fake_caget(self.pvDict, cleaned_di)
            self.loaded_unique_di.append(self.identify_di(item))

            # self.digital_input_axis.addItem(val)
        self.loaded_unique_di = [
            item for sublist in self.loaded_unique_di for item in sublist
        ]
        print(f"val: {self.loaded_unique_di}")
        # if not self.digital_input_axis.isEnabled():
        #     self.digital_inputs_list.setEnabled(True)
        # self.discover_di_channel()

    def load_di(self):
        """
        comes from WCIB
        needs to publish, and call discover_di_channel
        """
        print("in load_di")
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
        # self.digital_inputs_list.setCurrentRow(0)
        if not self.digital_inputs_list.isEnabled():
            self.digital_inputs_list.setEnabled(True)
        self.discover_di_channel()

    def discover_di_channel(self):
        """
        comes from load_di
        ---
        find out number of DIs
        """
        print("in load_di channel")
        # self.digital_input_channels.clear()
        # print(f"di text: {self.digital_inputs[self.digital_inputs_list.currentRow()]}")
        # val = self.digital_inputs[self.digital_inputs_list.currentRow()]
        # delimiter = ":WCIB_RBV"
        # cleaned_di = val.replace(delimiter, ":NUMDI_RBV")
        # print(f"cleaned axis: {cleaned_di}")
        # nums = fake_caget(self.pvDict, cleaned_di)
        # self.digital_input_channels = int(nums) + 1

        for pv in self.pvDict:
            if pv.endswith("NUMDI_RBV"):
                print(f"pv: {pv}")
                self.loaded_di_channels.append(pv)

        # for i in range(1, int(nums) + 1):
        #     self.digital_input_channels.addItem(str(i))
        # # self.digital_input_channels.setCurrentRow(0)
        # if not self.digital_input_channels.isEnabled():
        #     self.digital_input_channels.setEnabled(True)

    # def publish_di_channel(self):
    #     self.digital_input_channels.clear()

    def select_di_channel(self):
        print(f"in select_di_channel:")

        axis_di_idx = self.digital_input_axis.currentRow()
        print(f"axis_di_idx: {axis_di_idx}")
        currAxisIdx = self.axis_list.currentRow()
        currAxis = self.val_to_key(self.axis[currAxisIdx])
        detectableDi = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1))
        print(f"link to check: {detectableDi}")
        DI_hardware = fake_caget(self.pvDict, detectableDi + ":ID_RBV")
        print(f"DI_hardware: {DI_hardware}")
        DI_hardware_Channel = fake_caget(self.pvDict, detectableDi + ":HardChNum_RBV")
        print(f"DI_hardware_channel: {DI_hardware_Channel}")
        # returnStatus = self.digital_inputs_list.findItems(value, Qt.MatchCaseSensitive)
        # print(f"returnStatus: {returnStatus.text()}")

        # discovering DI hardware
        for i in range(0, self.digital_inputs_list.count()):
            if DI_hardware == self.digital_inputs_list.item(i).text():
                # print(f"currItem: {self.digital_inputs_list.item(i).text()}")
                print(f"found hardware: {self.digital_inputs_list.item(i).text()}")
                self.digital_inputs_list.setCurrentRow(i)
        for i in range(0, self.digital_input_channels.count()):
            if DI_hardware_Channel == self.digital_input_channels.item(i).text():
                print(f"found channel: {self.digital_input_channels.item(i).text()}")
                self.digital_input_channels.setCurrentRow(i)

        if axis_di_idx == 0:
            self.store_di_selection[0] = [
                self.digital_inputs_list.currentRow(),
                self.digital_input_channels.currentRow(),
            ]
        elif axis_di_idx == 1:
            self.store_di_selection[1] = [
                self.digital_inputs_list.currentRow(),
                self.digital_input_channels.currentRow(),
            ]
        elif axis_di_idx == 2:
            self.store_di_selection[2] = [
                self.digital_inputs_list.currentRow(),
                self.digital_input_channels.currentRow(),
            ]
        print(f"stored_di_selection: {self.store_di_selection[0][0]}, {self.store_di_selection[0][1]}\n \
        {self.store_di_selection[1][0]}, {self.store_di_selection[1][1]}\n \
        {self.store_di_selection[2][0]}, {self.store_di_selection[2][1]}\n     ")

        # currDI = self.loaded_di_channels[currDiIdx]
        # print(f"currDI: {currDI}")
        # currDiChanIdx = self.digital_input_channels.currentRow()

        # for di in self.digital_input_channels:
        #     """
        #     finish code here need to implement
        #     when a di slot is selected save the selected mapping
        #     in self.store_di_selection = {}
        #     """
        #     pass

    def load_di_channel(self):
        self.digital_input_channels.clear()
        currDiIdx = self.digital_inputs_list.currentRow()
        currDI = self.digital_inputs[currDiIdx]
        print(f"DI idx: {currDI}")
        delimiter = ":WCIB_RBV"
        cleaned_di = currDI.replace(delimiter, ":NUMDI_RBV")
        print(f"cleaned axis: {cleaned_di}")
        self.di_size = fake_caget(self.pvDict, cleaned_di)
        for i in range(0, int(self.di_size)):
            self.digital_input_channels.addItem(str(i + 1))

    def load_di_slot(self):
        """
        this kinda works, it needs to be modified to detect all axis DIS
        """
        id_list = []
        id_nums = []
        print("in load_di_slot")
        self.digital_input_axis.clear()
        currentAxisIndx = self.axis_list.currentRow()
        print(f"currentAxisIndx: {currentAxisIndx}")
        print(f"currentAxis: {self.axis[currentAxisIndx]}")
        axisKey = self.axis[currentAxisIndx]
        keys_with_value = [
            key for key, value in self.pvDict.items() if value == axisKey
        ]
        axis = strip_key(keys_with_value)
        print(f"axis: {axis}")
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
        print("in load drives")
        self.drives_list.clear()
        # self.drives = identify_drive(self.pvList, self.axis_list.currentItem().text())

        delimiter = ":WCIB_RBV"
        for item in self.drives:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            print(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)

            # publish drive
            self.drives_list.addItem(val)
        # self.drives_list.setCurrentRow(0)

        if not self.drives_list.isEnabled():
            self.drives_list.setEnabled(True)

        # print(self.drive_selection)

    def load_encoders(self):
        # update enum with drives pulled from .db file
        print("in load enc")
        self.enocders_list.clear()
        # self.enocder_type = identify_enc(self.pvList, self.axis_list.currentItem().text())
        delimiter = ":WCIB_RBV"
        # print(f"encoder list size: {len(self.encoders)}")
        for item in self.encoders:
            cleaned_item = item.replace(delimiter, ":Id_RBV")
            print(f"cleaned item: {cleaned_item}")
            val = fake_caget(self.pvDict, cleaned_item)

            # publish encoders
            self.enocders_list.addItem(val)
        # self.enocders_list.setCurrentRow(0)

        if not self.enocders_list.isEnabled():
            self.enocders_list.setEnabled(True)
        # print(self.encoder_selection)

    def publish_axis_ui(self):
        # update enum with axis pulled from .db file
        print("in populate axis_ui")
        self.display_axis.clear()
        axis_list = self.axis
        for item in axis_list:
            self.display_axis.addItem(item)
        # idx = self.axis_list
        self.display_axis.setCurrentRow(self.axis_list.currentRow())
        self.display_axis.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_axis.isEnabled():
            self.display_axis.setEnabled(True)
        print(f"caput to: self.axis_selection")

    def load_di_ui(self):
        print("in load_di_ui")
        self.display_di.clear()
        di_list = self.digital_inputs
        delimiter = ":WCIB_RBV"
        for item in di_list:
            cleaned_di = item.replace(delimiter, ":Id_RBV")
            val = fake_caget(self.pvDict, cleaned_di)
            self.display_di.addItem(val)
        self.display_di.setCurrentRow(self.digital_inputs_list.currentRow())
        self.display_di.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_di.isEnabled():
            self.display_di.setEnabled(True)
        # self.discover_di_channel()

    def load_di_c_ui(self):
        print("in load_di_c_ui")
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
        self.display_di_c.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_di_c.isEnabled():
            self.display_di_c.setEnabled(True)

    def load_drives_ui(self):
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
        self.display_drives.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_drives.isEnabled():
            self.display_drives.setEnabled(True)

    def load_encoders_ui(self):
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
        self.display_encoders.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_encoders.isEnabled():
            self.display_encoders.setEnabled(True)
        # print(self.encoder_selection)

    def publish_axis_expert(self):
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

    def update_nc(self):
        """
        if axis selection current index is changed grab index and axis reference to populate NC dropdown
        get currently selected axis
        identify all NC params based on selected axis
        clear previous list
        add items
        """
        print("in update_nc")
        axis = self.axis[self.expert_axis.currentRow()]
        print(f"axis: {self.expert_axis.currentRow()}")
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
        self.expert_drive_list.clear()
        axis = self.axis[self.expert_axis.currentRow()]
        print(f"axis: {self.expert_axis.currentRow()}")
        keys_with_value = [key for key, value in self.pvDict.items() if value == axis]
        cleaned_axis = strip_key(keys_with_value)
        print(f"cleaned axis: {cleaned_axis}")
        """Need to coordinate with Nick on how to structure PVs"""

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
