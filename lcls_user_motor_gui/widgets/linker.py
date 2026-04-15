import logging
import time
from pathlib import Path

import epics
from pcdsutils.qt.designer_display import DesignerDisplay
from pydm.widgets.enum_combo_box import PyDMEnumComboBox
from pydm.widgets.label import PyDMLabel
from pydm.widgets.line_edit import PyDMLineEdit
from pydm.widgets.pushbutton import PyDMPushButton
from PyQt5.QtCore import QObject, QThread, pyqtSignal
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

from ..processing.parse_pvs import (
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
from ..utils.dict_tools import (
    find_unique_keys,
    identify_di,
    identify_drv,
    identify_enc,
    strip_axis_id,
    val_to_key,
)


class CaputWorker(QObject):
    result = pyqtSignal(str, bool, object)  # PV name, success, new value
    finished = pyqtSignal()

    def __init__(self, pv_name, value):
        super().__init__()
        self.pv_name = pv_name
        self.value = value

    def do_caput(self):
        # Perform caput operation
        success = epics.caput(self.pv_name, self.value, wait=True, timeout=2)
        # Optionally read back the value
        pv = epics.PV(self.pv_name)
        new_value = pv.get()
        self.result.emit(self.pv_name, success, new_value)
        self.finished.emit()


class SettingsWindow(DesignerDisplay, QWidget):
    filename = "settings_tab.ui"
    ui_dir = Path(__file__).parent / "./../ui"

    settings_duplicate_di_warning: QCheckBox
    settings_duplicate_drv_warning: QCheckBox
    settings_duplicate_enc_warning: QCheckBox

    def __init__(self, main_window, parent=None, logger=None):
        # Properly call the superclass __init__!
        super().__init__(parent)
        self.logger = logger
        self.main_window = main_window


class MappingWindow(DesignerDisplay, QDialog):
    filename = "mapping_window.ui"
    ui_dir = Path(__file__).parent / "./../ui"

    staged_mappings_list: QListWidget


class LinkerWindow(DesignerDisplay, QWidget):
    filename = "linker_tab.ui"
    ui_dir = Path(__file__).parent / "./../ui"

    # Linker Tab
    plc_ioc_list: QComboBox
    plc_ioc_label: PyDMLabel
    axis_list_linker: QListWidget
    digital_input_hardware: QListWidget
    digital_input_main_channels: QListWidget
    digital_input_sub_channels: QListWidget
    digital_input_axis: QListWidget
    drives_list: QListWidget
    drives_channel_list: QListWidget
    encoders_list: QListWidget
    encoders_channel_list: QListWidget
    confirm_mapping: QPushButton
    view_logger: PyDMPushButton
    load_ioc: QPushButton
    stage_mapping: QPushButton
    see_staged_mapping: QPushButton
    clear_mapping: QPushButton

    def __init__(self, main_window, parent=None, logger=None):
        # Properly call the superclass __init__!
        super().__init__(parent)
        self.logger = logger
        self.main_window = main_window
        self.prefixName = ""
        self.axis = []
        # self.drives = []
        self.pvDict = {}
        self.store_di_selection = [[-1, -1], [-1, -1], [-1, -1]]
        self.loaded_unique_di = []
        self.drives_linker = ["None"]
        self.encoders_linker = ["None"]
        self.di_size = 0
        self.digital_inputs_linker = ["None"]
        self.digital_inputs_hardware_linker = ["None"]
        self.loaded_di_channels_linker = []
        # self.staged_mapping = []
        self.staged_mapping = []
        self.staged_channels = []
        self.staged_de = []
        self.duplicate_di_cb_flag = False
        self.duplicate_drv_cb_flag = False
        self.duplicate_enc_cb_flag = False
        self.qCurrAxis = 0

    def isStagedMappingSet(self):
        self.logger.info(f"inStateMapptingSet")
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
        self.logger.debug(f"curr axis index: {self.qCurrAxis}")
        if not self.status_staged_mappings():
            self.logger.debug("There is nothing staged")
            self.select_axis()
        else:
            self.logger.debug("There are some staged values")
            # self.configMappingWarningBox()

            self.main_window.msg.setIcon(QMessageBox.Warning)
            self.main_window.msg.setText(
                "You have unsaved staged changes! Discard changes?"
            )
            self.main_window.msg.setWindowTitle("Warning")
            self.main_window.msg.setStandardButtons(
                QMessageBox.Yes | QMessageBox.No
            )  # Adjusted buttons
            result = self.main_window.msg.exec_()

            self.logger.debug(f"current axis: {self.qCurrAxis}")
            self.logger.debug(f"Message box result: {result}")
            if result == QMessageBox.Yes:
                self.logger.debug("switching to select axis")
                self.clear_stage()
                self.select_axis()
            elif result == QMessageBox.No:
                # QMessageBox.information(self, "Continue", "You can continue")
                temp_flag = True
        if temp_flag:
            self.logger.debug("attempting to reset axis")
            self.logger.debug(f"resetting row to: {self.qCurrAxis}")
            self.axis_list_linker.setEnabled(True)
            self.axis_list_linker.blockSignals(True)
            self.axis_list_linker.setCurrentRow(self.qCurrAxis)
            self.axis_list_linker.blockSignals(False)

    def status_staged_mappings(self):
        self.logger.info(
            f"in status_staged_mapping: checking if there is a staged mapping"
        )
        containsDI = False
        containsDE = False
        for axis in self.staged_mapping:
            if isinstance(axis, list):  # Ensure we're working with a list
                for sublist in axis:
                    self.logger.debug(f"size of staged mapping: {len(sublist)}")
                    self.logger.debug(
                        f"isinstance: {isinstance(sublist, list) and len(sublist) > 1}"
                    )
                    if isinstance(sublist, list) and len(sublist) > 1:
                        self.logger.debug(f"there are stagged di changes")
                        containsDI = True  # Found a non-empty sublist
        for axis in self.staged_de:
            if isinstance(axis, list):  # Ensure we're working with a list
                # [logger.debug(f"items: {item}" for item in axis)]
                [self.logger.debug(f"item: {item}") for item in axis]
                self.logger.debug(
                    f"any: {any([(item != ['None'] and item != [''] and item != []) for item in axis])}"
                )
                if any(
                    [
                        (item != ["None"] and item != [""] and item != [])
                        for item in axis
                    ]
                ):
                    self.logger.debug("drive or encoders staged")
                    containsDE = True
        if containsDE or containsDI:
            return True
        else:
            return False

    def check_duplicate_di_flag(self):
        self.logger.info(f"in check dup di")

        self.duplicate_di_cb_flag = (
            self.settings_window.settings_duplicate_di_warning.isChecked()
        )

        self.logger.debug(f"isDuplicateDIWarning: {self.duplicate_di_cb_flag}")

    def check_duplicate_drv_flag(self):
        self.logger.info(f"in check dup drv")

        self.duplicate_drv_cb_flag = self.duplicate_drv_cb.isChecked()

        self.logger.debug(f"isDuplicateDIWarning: {self.duplicate_drv_cb_flag}")

    def check_duplicate_enc_flag(self):
        self.logger.info(f"in check dup enc")

        self.duplicate_enc_cb_flag = self.duplicate_enc_cb.isChecked()

        self.logger.debug(f"isDuplicateDIWarning: {self.duplicate_enc_cb_flag}")

    def check_duplicate_di(self):
        self.logger.info(f"in check for duplicate di")
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
        self.logger.debug(f"Duplicates in the 2nd index: {duplicates_second}")
        self.logger.debug(f"Duplicates in the 3rd index: {duplicates_third}")

    def check_duplicate_drv(self):
        """
        Check for duplicate first index values in staged_de based on the first element of each inner-most list.
        Ignore duplicates for the value 'None'.

        Returns:
            set: A set of duplicate first index values except 'None'.
        """
        self.logger.info(f"in check for duplicate drv")

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
        self.logger.debug(f"Duplicates: {duplicates}")

    def check_duplicate_enc(self):
        """
        Check for duplicate second index values in staged_de based on the second element of each inner-most list.
        Ignore duplicates for the value 'None'.

        Returns:
            set: A set of duplicate first index values except 'None'.
        """
        self.logger.info(f"in check for duplicate enc")

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
        self.logger.debug(f"Duplicates: {duplicates}")

    def see_stage(self):
        self.logger.info(f"in see_stage")
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
                    self.logger.debug("0 is blank")
                    self.staged_de[stage][0] = [""]
                if len(self.staged_de[stage][1]) < 1:
                    self.staged_de[stage][1] = [""]
                    self.logger.debug("1 is blank")
                self.logger.debug(
                    f"self.staged_de[stage][0]: {self.staged_de[stage][0]}"
                )
                self.logger.debug(
                    f"self.staged_de[stage][1]: {self.staged_de[stage][1]}"
                )

                # Print the row output in groups of three
                mapping_window.staged_mappings_list.addItem(
                    f"Axis {int(self.axis_list_linker.currentRow())+1}: DI: {row_output[0]}, {row_output[1]}, {row_output[2]} DRV: {self.staged_de[stage][0]} ENC:{self.staged_de[stage][1]}"
                )
                # print(row_output)  # Printing as one complete list containing the sublists

            else:
                self.logger.debug(
                    f"Stage {stage} was empty"
                )  # Handling completely empty stages
        # #need to setup a way to push info back to the gui is this is wanted
        # mapping_window.show()
        mapping_window.exec_()

    def save_stage(self):
        self.logger.info(f"in save_stage")

        # setup holder for stagged mapping
        numStages = self.axis_list_linker.count()
        self.logger.debug(f"numStages count: {numStages}")
        # self.staged_mapping= [[] for _ in range(numStages)]

        # saving DI components
        # currAxis = self.axis_list.currentRow()
        self.qCurrAxis = self.axis_list_linker.currentRow()
        currAxis = self.qCurrAxis
        self.logger.debug(f"currAxis: {self.qCurrAxis}")
        currAxisDi = self.digital_input_axis.currentRow() + 1
        self.logger.debug(f"currAxisDi: {currAxisDi}")
        currDiHardwareItem = self.digital_input_hardware.currentItem()
        if currDiHardwareItem is None:
            # No hardware selected, prompt user and exit
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Please select a Digital Input Hardware device!")
            msg.setWindowTitle("Selection Required")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        elif currDiHardwareItem is not None and currDiHardwareItem.text() != "None":
            currDiHardware = currDiHardwareItem.text()
        else:
            currDiHardware = ""
        self.logger.debug(f"currDiHardware: {currDiHardwareItem}")

        currDiHardwareMainChan = self.digital_input_main_channels.currentItem()
        if currDiHardwareMainChan is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Please select a Digital Input Hardware Main Channel!")
            msg.setWindowTitle("Selection Required")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        elif currDiHardwareMainChan is not None:
            currDiHardwareMainChan = str(int(currDiHardwareMainChan.text()))
        else:
            currDiHardwareMainChan = ""
        self.logger.debug(f"currDiHardwareMainChan: {currDiHardwareMainChan}")

        currDiHardwareSubChan = self.digital_input_sub_channels.currentItem()
        if currDiHardwareSubChan is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Please select a Digital Input Hardware Sub Channel!")
            msg.setWindowTitle("Selection Required")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        elif currDiHardwareSubChan is not None:
            currDiHardwareSubChan = str(int(currDiHardwareSubChan.text()))
        else:
            currDiHardwareSubChan = ""
        self.logger.debug(f"currDiHardwareSubChan: {currDiHardwareSubChan}")

        currDrvHardwareChan = self.drives_channel_list.currentItem()
        if currDrvHardwareChan is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Please select a Digital Input Hardware Sub Channel!")
            msg.setWindowTitle("Selection Required")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        elif currDrvHardwareChan is not None:
            currDrvHardwareChan = str(int(currDrvHardwareChan.text()))
        else:
            currDrvHardwareChan = ""
        self.logger.debug(f"currDrvHardwareChan: {currDrvHardwareChan}")

        currEncHardwareChan = self.drives_channel_list.currentItem()
        if currEncHardwareChan is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Please select a Digital Input Hardware Sub Channel!")
            msg.setWindowTitle("Selection Required")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        elif currEncHardwareChan is not None:
            currEncHardwareChan = str(int(currEncHardwareChan.text()))
        else:
            currEncHardwareChan = ""
        self.logger.debug(f"currEncHardwareChan: {currEncHardwareChan}")

        # if (currDiHardware != None and currDiHardware != "None") and (
        #     self.digital_input_channels.currentItem() == None
        # ):
        #     msg = QMessageBox()
        #     msg.setIcon(QMessageBox.Warning)
        #     msg.setText("Please Select DI Hardware Channel")
        #     msg.setInformativeText(f"No DI Hardware Channel Found!")
        #     msg.setWindowTitle("Warning")
        #     msg.setStandardButtons(QMessageBox.Ok)

        #     msg.exec_()

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
            if currDiHardwareMainChan != "":
                self.staged_mapping[0][0].append(currDiHardwareMainChan)
            if currDiHardwareSubChan != "":
                self.staged_mapping[0][0].append(currDiHardwareSubChan)
        elif currAxisDi == 2:
            self.staged_mapping[0][1].append("0" + str(currAxisDi))
            if currDiHardware != "":
                self.staged_mapping[0][1].append(currDiHardware)
            if currDiHardwareMainChan != "":
                self.staged_mapping[0][1].append(currDiHardwareMainChan)
            if currDiHardwareSubChan != "":
                self.staged_mapping[0][1].append(currDiHardwareSubChan)
        elif currAxisDi == 3:
            self.staged_mapping[0][2].append("0" + str(currAxisDi))
            if currDiHardware != "":
                self.staged_mapping[0][2].append(currDiHardware)
            if currDiHardwareMainChan != "":
                self.staged_mapping[0][2].append(currDiHardwareMainChan)
            if currDiHardwareSubChan != "":
                self.staged_mapping[0][2].append(currDiHardwareSubChan)

        if len(self.staged_de[0][0]):
            self.staged_de[0][0].clear()
        if len(self.staged_de[0][1]):
            self.staged_de[0][1].clear()

        # saving drives and encoders
        if self.drives_list.currentItem() == None:
            self.staged_de[0][0] = ["None"]
        elif self.drives_list.currentItem().text() == "None":
            self.staged_de[0][0] = ["None"]
        else:
            self.staged_de[0][0].append(self.drives_list.currentItem().text())
            self.staged_de[0][0].append(self.drives_channel_list.currentItem().text())
        if self.encoders_list.currentItem() == None:
            self.staged_de[0][1] = ["None"]
        elif self.encoders_list.currentItem().text() == "None":
            self.staged_de[0][1] = ["None"]
        else:
            self.staged_de[0][1].append(self.encoders_list.currentItem().text())
            self.staged_de[0][1].append(self.encoders_channel_list.currentItem().text())

        self.check_duplicate_di()
        self.check_duplicate_drv()
        self.check_duplicate_enc()
        # self.staged_mapping[currAxis].append('0'+str(currAxisDi))
        # self.staged_mapping[currAxis].append(currDiHardware)
        # self.staged_mapping[currAxis].append(currDiHardwareChan)

        # show mapping
        self.logger.debug(f"staged mapping: {self.staged_mapping}")
        self.logger.debug(f"staged channels: {self.staged_channels}")
        self.logger.debug(f"staged de: {self.staged_de}")

    def clear_stage(self):
        self.logger.info(f"in clear_stage")
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
        for sublist in self.staged_channels:
            sublist.clear()
        for sublist in self.staged_de:
            for inner_list in sublist:
                inner_list.clear()
        self.staged_mapping = [[["01"], ["02"], ["03"]]]
        self.staged_de = [[["None"], ["None"]]]
        self.logger.debug(f"staged mapping: {self.staged_mapping}")
        self.logger.debug(f"staged channels: {self.staged_channels}")
        self.logger.debug(f"staged de: {self.staged_de}")

    def detect_linked_drv(self):
        self.logger.info(f"in detect_linked_drv")
        currAxis = self.axis_list_linker.currentRow()
        # currAxis = val_to_key(self.axis[currAxisIdx], self.pvDict)
        self.logger.debug(f"currAxis: {currAxis}")

        detectableDRV = (
            self.prefixName + ":AXIS:0" + str(currAxis + 1) + ":SelG:DRV:Id_RBV"
        )

        drvValue = epics.caget(detectableDRV, as_string=True)
        self.logger.debug(f"detDRV: {detectableDRV}")
        self.logger.debug(f"drvValue: {drvValue}")

        found_drv = False
        for i in range(0, self.drives_list.count()):
            if drvValue == self.drives_list.item(i).text():
                self.logger.debug(f"found drv: {self.drives_list.item(i).text()}")
                self.drives_list.setCurrentRow(i)
                found_drv = True
                break

        # load drive channels
        drive_channel = (
            self.prefixName
            + ":AXIS:0"
            + str(self.axis_list_linker.currentRow() + 1)
            + ":SelG:DRV:MAIN_RBV"
        )
        self.logger.debug(f"drive_channel: {drive_channel}")
        drive_channel_val = epics.caget(drive_channel, as_string=True)
        self.logger.debug(f"drive_channel_val: {drive_channel_val}")
        for i in range(0, self.drives_channel_list.count()):
            item = self.drives_channel_list.item(i)
            if item is not None and drive_channel_val == item.text():
                self.logger.debug(f"found drv chan: {item.text()}")
                self.drives_channel_list.setCurrentRow(i)
                break
            else:
                self.logger.debug(f"channel is none, something went wrong")

        if not found_drv:
            self.logger.debug("No link found, defaulting to None")
            self.drives_list.setCurrentRow(0)

    def detect_linked_enc(self):
        self.logger.info(f"in detect_linked_enc")
        currAxis = self.axis_list_linker.currentRow()
        self.logger.debug(f"currAxis: {currAxis}")

        detectableENC = (
            self.prefixName + ":AXIS:0" + str(currAxis + 1) + ":SelG:ENC:Id_RBV"
        )
        encValue = epics.caget(detectableENC, as_string=True)
        self.logger.debug(f"detectableENC: {detectableENC}")
        self.logger.debug(f"encValue: {encValue}")

        found_enc = False
        for i in range(0, self.encoders_list.count()):
            if encValue == self.encoders_list.item(i).text():
                self.logger.debug(f"found enc: {self.encoders_list.item(i).text()}")
                self.encoders_list.setCurrentRow(i)
                found_enc = True
                break

        # load encoder channels
        encoder_channel = (
            self.prefixName
            + ":AXIS:0"
            + str(self.axis_list_linker.currentRow() + 1)
            + ":SelG:ENC:MAIN_RBV"
        )
        self.logger.debug(f"encoder_channel: {encoder_channel}")
        encoder_channel_val = epics.caget(encoder_channel, as_string=True)
        self.logger.debug(f"encoder_channel_val: {encoder_channel_val}")
        for i in range(0, self.encoders_channel_list.count()):
            item = self.encoders_channel_list.item(i)
            if item is not None and encoder_channel_val == item.text():
                self.logger.debug(f"found enc chan: {item.text()}")
                self.encoders_channel_list.setCurrentRow(i)
                break
            else:
                self.logger.debug(f"channel is none, something went wrong")

        if not found_enc:
            self.logger.debug("No link found, defaulting to None")
            self.encoders_channel_list.setCurrentRow(0)

    def load_drives_channel(self):
        self.logger.info(f"in load_drives_channel")
        self.drives_channel_list.clear()
        if "7062" in self.drives_list.currentItem().text():
            for i in range(0, 2):
                self.drives_channel_list.addItem(str(i + 1))

    def load_encoders_channel(self):
        self.logger.info(f"in load_encoders_channel_ui")
        self.encoders_channel_list.clear()
        if "7062" in self.encoders_list.currentItem().text():
            for i in range(0, 2):
                self.encoders_channel_list.addItem(str(i + 1))
        elif "5042" in self.encoders_list.currentItem().text():
            for i in range(0, 2):
                self.encoders_channel_list.addItem(str(i + 1))

    def publish_axis_di(self):
        self.logger.info(f"in publish_axis_di")
        # if self.axis_di_init:
        self.digital_input_axis.clear()
        numDI = 0

        # currAxisIdx = self.axis_list.currentRow()
        # self.logger.debug(f"currAxisIdx: {self.axis[currAxisIdx]}")
        # currAxis = self.val_to_key(self.axis[currAxisIdx])
        # self.logger.debug(f"currAxis: {currAxis}")

        # currAxis = val_to_key(self.axis_list_linker.currentItem().text(), self.pvDict)
        # self.logger.debug(f"currAxis: {currAxis}")
        # for items in self.loaded_unique_di:
        #     if items.startswith(currAxis):
        #         numDI = numDI + 1
        for i in range(0, 3):
            self.digital_input_axis.addItem("0" + str(1 + i))
            # self.axis_di_init = False
        # elif self.axis_di_init is False:
        # self.digital_input_axis.setCurrentRow(self.axis_di_idx)

        self.select_di_channel()

    def select_axis(self):
        self.logger.info(f"in select_axis")
        self.detect_linked_enc()
        self.detect_linked_drv()
        self.publish_axis_di()

    def publish_axis(self):
        """
        Called from load_axis
        ---

        """
        # update enum with axis pulled from .db file
        self.logger.info(f"in populate axis")
        self.axis_list_linker.clear()

        # for item in self.axis:
        #     self.axis_list.addItem(item)

        self.axis_list_linker.addItems(self.axis)

        if not self.axis_list_linker.isEnabled():
            self.axis_list_linker.setEnabled(True)
        # print(self.axis_selection)
        # self.staged_mapping= [[] for _ in range(self.axis_list.count())]

        # self.staged_mapping = [
        #     [[""] for _ in range(3)] for _ in range(self.axis_list.count())
        # ]

        self.staged_mapping = [[["01"], ["02"], ["03"]]]
        self.staged_channels = [["None"], ["None"]]
        self.staged_de = [[["None"], ["None"]]]

    def load_axis_di(self):
        """ """
        self.logger.info(f"in load_axis_di")
        self.digital_input_axis.clear()

        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        delimiter = ":Id_RBV"
        # self.logger.debug(f"di_val: {axis_di}")
        for item in self.axis:
            self.logger.debug(f"axis: {item}")
            # name = self.val_to_key(item)
            # self.logger.debug(f"name: {name}")
            # cleaned_di = name.replace(delimiter, "")
            # self.logger.debug(f"cleaned item: {cleaned_di}")
            # pv = fake_caget(self.pvDict, cleaned_di)
            self.loaded_unique_di.append(self.identify_di(item))

            # self.digital_input_axis.addItem(val)
        self.loaded_unique_di = [
            item for sublist in self.loaded_unique_di for item in sublist
        ]
        self.logger.debug(f"val: {self.loaded_unique_di}")
        # if not self.digital_input_axis.isEnabled():
        #     self.digital_input_hardware.setEnabled(True)
        # self.discover_di_channel()

    def identify_di(self, item):
        val = val_to_key(item, self.pvDict)
        if val is None:
            self.logger.warning(f"identify_di: no axis key for item {item}")
            return []

        things = find_unique_keys(val + ":SelG:DI:", self.pvDict)
        self.logger.debug(f"identify_config: item, {val}, DIs, {things}")

        return things

    def identify_drv(self, item):
        val = val_to_key(item, self.pvDict)
        if val is None:
            self.logger.warning(f"identify_drv: no axis key for item {item}")
            return []

        things = find_unique_keys(val + ":SelG:DRV:", self.pvDict)
        self.logger.debug(f"identify_config: item, {val}, DRVs, {things}")

        return things

    def identify_enc(self, item):
        val = val_to_key(item, self.pvDict)
        if val is None:
            self.logger.warning(f"identify_enc: no axis key for item {item}")
            return []

        things = find_unique_keys(val + ":SelG:ENC:", self.pvDict)
        self.logger.debug(f"identify_config: item, {val}, ENCs, {things}")

        return things

    def load_di(self):
        """
        comes from WCIB
        needs to publish, and call discover_di_channel
        """
        self.logger.info(f"in load_di")
        self.digital_input_hardware.clear()
        self.digital_input_hardware.addItem("None")
        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        replaced_items = []
        for item in self.digital_inputs_linker[1:]:
            replaced_items.append(item.replace("WCIB_RBV", "Id_RBV"))

            # cleaned_di = item.replace(delimiter, ":Id_RBV")
            # self.logger.debug(f"cleaned item: {cleaned_di}")
            # val = fake_caget(self.pvDict, cleaned_di)
            # self.logger.debug(f"val: {val}")
        val = epics.caget_many(replaced_items, as_string=True)
        self.digital_inputs_linker[:] = val[0:]
        self.digital_input_hardware.addItems(self.digital_inputs_linker)
        # self.digital_input_hardware.addItem(val)
        # self.digital_input_hardware.setCurrentRow(0)
        if not self.digital_input_hardware.isEnabled():
            self.digital_input_hardware.setEnabled(True)
        self.discover_di_channel()

    def discover_di_channel(self):
        """
        comes from load_di
        ---
        find out number of DIs
        """
        self.logger.info(f"in load_di channel")
        # self.digital_input_channels.clear()
        # self.logger.debug(f"di text: {self.digital_inputs[self.digital_input_hardware.currentRow()]}")
        # val = self.digital_inputs[self.digital_input_hardware.currentRow()]
        # delimiter = ":WCIB_RBV"
        # cleaned_di = val.replace(delimiter, ":NUMDI_RBV")
        # self.logger.debug(f"cleaned axis: {cleaned_di}")
        # nums = fake_caget(self.pvDict, cleaned_di)
        # self.digital_input_channels = int(nums) + 1

        for pv in self.pvDict:
            if pv.endswith("NUMDI_RBV"):
                self.logger.debug(f"pv: {pv}")
                self.loaded_di_channels_linker.append(pv)

    def select_di_channel(self):
        self.logger.info(f" select_di_channel:")
        # self.check_duplicate_di

        DI_hardware_Channel = 0
        DI_Hardware_Channel_Main = 0
        axis_di_idx = self.digital_input_axis.currentRow()
        self.logger.debug(f"axis_di_idx: {axis_di_idx}")
        if axis_di_idx < 0:
            self.logger.debug("please select a di")
        else:
            currAxisIdx = self.axis_list_linker.currentRow()
            self.logger.debug(f"currAxisIdx: {currAxisIdx}")
            # self.logger.debug(f"axis: {self.axis[currAxisIdx]}")
            # currAxis = val_to_key(self.axis[currAxisIdx], self.pvDict)
            # self.logger.debug(f"currAxis: {currAxis}")
            currAxis = self.prefixName + ":AXIS:0" + str(currAxisIdx + 1)
            detectableDi = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":Id_RBV"
            )
            self.logger.debug(f"link to check: {detectableDi}")
            DI_hardware = epics.caget(detectableDi, as_string=True)
            if DI_hardware == 0:
                DI_hardware = None
            self.logger.debug(f"DI_hardware: {DI_hardware}")
            # returnStatus = self.digital_input_hardware.findItems(value, Qt.MatchCaseSensitive)
            # self.logger.debug(f"returnStatus: {returnStatus.text()}")

            self.logger.debug("searching for DI hardware")
            # detect DI hardware

            for i in range(0, self.digital_input_hardware.count()):
                if DI_hardware == self.digital_input_hardware.item(i).text():
                    # self.logger.debug(f"currItem: {self.digital_input_hardware.item(i).text()}")
                    self.logger.debug(
                        f"found hardware main: {self.digital_input_hardware.item(i).text()}"
                    )
                    self.digital_input_hardware.setCurrentRow(i)
                elif DI_hardware == "0":
                    self.logger.debug("no hardware detected")
                    # self.digital_input_hardware.setCurrentRow(0)
                    self.logger.debug("something went wrong/thinking")
                    self.digital_input_hardware.selectionMode(
                        QAbstractItemView.NoSelection
                    )

            di_chan_slot = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":MAIN_RBV"
            )
            DI_Hardware_Channel_Main = epics.caget(di_chan_slot, as_string=True)
            self.logger.debug(
                f"DI_hardware_Channel Slot: {int(DI_Hardware_Channel_Main)}"
            )
            self.logger.debug("searching for di hardware main channel")

            for i in range(0, self.digital_input_main_channels.count()):
                if (
                    DI_Hardware_Channel_Main
                    == self.digital_input_main_channels.item(i).text()
                ):
                    self.logger.debug(
                        f"found channel main: {self.digital_input_main_channels.item(i).text()}"
                    )
                    self.digital_input_main_channels.setCurrentRow(i)
                elif DI_Hardware_Channel_Main == "0":
                    self.logger.debug("something went wrong, should not be possible")
                    self.digital_input_main_channels.selectionMode(
                        QAbstractItemView.NoSelection
                    )

            self.logger.debug("searching for di hardware sub channel")

            di_chan = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":SUB_RBV"
            )
            DI_hardware_Channel = epics.caget(di_chan, as_string=True)
            self.logger.debug(f"DI_hardware_Channel: {int(DI_hardware_Channel)}")

            for i in range(0, self.digital_input_sub_channels.count()):
                if (
                    DI_hardware_Channel
                    == self.digital_input_sub_channels.item(i).text()
                ):
                    self.logger.debug(
                        f"found channel: {self.digital_input_sub_channels.item(i).text()}"
                    )
                    self.digital_input_sub_channels.setCurrentRow(i)
                elif DI_hardware_Channel == "0":
                    self.logger.debug("something went wrong, should not be possible")
                    self.digital_input_sub_channels.setSelectionMode(
                        QAbstractItemView.NoSelection
                    )

            # if axis_di_idx == 0:
            #     self.store_di_selection[0] = [
            #         self.digital_input_hardware.currentRow(),
            #         self.digital_input_channels.currentRow(),
            #     ]
            # elif axis_di_idx == 1:
            #     self.store_di_selection[1] = [
            #         self.digital_input_hardware.currentRow(),
            #         self.digital_input_channels.currentRow(),
            #     ]
            # elif axis_di_idx == 2:
            #     self.store_di_selection[2] = [
            #         self.digital_input_hardware.currentRow(),
            #         self.digital_input_channels.currentRow(),
            #     ]

    def load_di_channel(self):
        self.logger.debug("load di_channel")
        self.digital_input_main_channels.clear()
        self.digital_input_sub_channels.clear()
        current_item = self.digital_input_hardware.currentItem()
        if current_item is None:
            self.logger.warning("No digital input hardware item selected")
            return

        currDI = current_item.text()
        if currDI == "None":
            self.logger.debug(
                "Selected digital input hardware is None, no hardware selected"
            )
            return

        currDI = currDI.split("_")[0]
        self.logger.debug(f"DI Slice: {currDI}")
        currAxisIdx = self.axis_list_linker.currentRow()
        axis_di_idx = self.digital_input_axis.currentRow()
        currAxis = self.prefixName + ":AXIS:0" + str(currAxisIdx + 1)

        if currDI.startswith("EL7062"):
            # di_chan = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ':SUB_RBV'
            # self.di_size = epics.caget(di_chan)
            for i in range(0, int(2)):
                self.digital_input_main_channels.addItem(str(i + 1))
            for i in range(0, int(2)):
                self.digital_input_sub_channels.addItem(str(i + 1))
        elif currDI.startswith("EL1429"):
            di_chan = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":SUB_RBV"
            )
            self.di_size = epics.caget(di_chan)
            for i in range(0, int(16)):
                self.digital_input_main_channels.addItem(str(i + 1))
            for i in range(0, int(1)):
                self.digital_input_sub_channels.addItem(str(i + 1))
        else:
            self.logger.debug("Slice Unknown")

    def load_drives(self):
        # update enum with drives pulled from .db file
        self.logger.info(f"in load drives")
        self.drives_list.clear()
        # self.drives_list.addItem("None")

        # self.drives = identify_drive(self.pvList, self.axis_list.currentItem().text())

        replaced_items = []
        for item in self.drives_linker[1:]:
            print(f"drives: {item}")
            replaced_items.append(item.replace("WCIB_RBV", "Id_RBV"))

            # publish drive
            # self.drives_list.addItem(val)
            # self.user_input_widget.display_drives_ui.addItem(val)
        val = epics.caget_many(replaced_items, as_string=True)
        self.drives_linker[1:] = val[0:]
        self.drives_list.addItems(self.drives_linker)
        # self.drives_list.setCurrentRow(0)

        if not self.drives_list.isEnabled():
            self.drives_list.setEnabled(True)
        # if not self.user_input_widget.display_drives_ui.isEnabled():
        #     self.user_input_widget.display_drives_ui.setEnabled(True)

        # print(self.drive_selection)

    def load_encoders(self):
        # update enum with drives pulled from .db file
        self.logger.info(f"in load enc")
        self.encoders_list.clear()
        # self.encoders_list.addItem("None")
        # self.user_input_widget.display_encoders_ui.clear()
        # self.user_input_widget.display_encoders_ui.addItem("None")
        # self.enocder_type = identify_enc(self.pvList, self.axis_list.currentItem().text())
        replaced_items = []
        # self.logger.debug(f"encoder list size: {len(self.encoders)}")
        for item in self.encoders_linker[1:]:
            replaced_items.append(item.replace("WCIB_RBV", "Id_RBV"))

            # publish encoders
            # self.encoders_list.addItem(val)
            # self.user_input_widget.display_encoders_ui.addItem(val)
        # self.encoders_list.setCurrentRow(0)

        val = epics.caget_many(replaced_items, as_string=True)
        self.encoders_linker[1:] = val[0:]
        self.encoders_list.addItems(self.encoders_linker)

        if not self.encoders_list.isEnabled():
            self.encoders_list.setEnabled(True)
        # if not self.user_input_widget.display_encoders_ui.isEnabled():
        #     self.user_input_widget.display_encoders_ui.setEnabled(True)
        # print(self.encoder_selection)

    def caput_async(self, pv_name, value):
        worker = CaputWorker(pv_name, value)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.do_caput)
        worker.result.connect(self.handle_caput_result)
        worker.finished.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        worker.finished.connect(worker.deleteLater)
        thread.start()

    # def update_links(self):
    #     self.logger.info(f"in update links")
    #     # caput staged changes to axis

    #     # For each staged_mapping ("DI") entry that has changes
    #     for axis in self.staged_mapping:
    #         for di in axis:
    #             if len(di) > 1:
    #                 try:
    #                     axis_idx = self.axis_list_linker.currentRow() + 1
    #                     prefix = f"{self.prefixName}0{axis_idx}"

    #                     di_idx = di[0]
    #                     # DI hardware (eg "EL7047_2")
    #                     di_hardware = di[1] if len(di) > 1 else None
    #                     di_channel = di[2] if len(di) > 2 else None

    #                     di_hardware_pv = f"{prefix}:SelG:DI:{di_idx}:ID"
    #                     di_channel_pv  = f"{prefix}:SelG:DI:{di_idx}:HardChNum"

    #                     if di_hardware:
    #                         self.caput_async(di_hardware_pv, di_hardware)
    #                     if di_channel:
    #                         self.caput_async(di_channel_pv, di_channel)

    #                 except Exception as e:
    #                     self.logger.error(f"Error processing DI {di}: {e}")

    #     # For each staged_de ("DRV"/"ENC") entry that has changes
    #     for item in self.staged_de:
    #         try:
    #             axis_idx = self.axis_list_linker.currentRow() + 1
    #             prefix = f"{self.prefixName}0{axis_idx}"

    #             drv = item[0][0] if item[0] and item[0][0] != "None" else None
    #             enc = item[1][0] if item[1] and item[1][0] != "None" else None

    #             drv_pv = f"{prefix}:SelG:DRV:Id"
    #             enc_pv = f"{prefix}:SelG:ENC:Id"

    #             if drv:
    #                 self.caput_async(drv_pv, drv)
    #             if enc:
    #                 self.caput_async(enc_pv, enc)
    #         except Exception as e:
    #             self.logger.error(f"Error processing DRV/ENC {item}: {e}")

    # Standard handler for all async results
    def handle_caput_result(self, pv_name, success, new_value):
        if success:
            self.logger.info(f"caput {pv_name} succeeded, new value: {new_value}")
        else:
            self.logger.warning(f"caput {pv_name} failed, attempted set to {new_value}")

    # Optional: display in GUI
    # self.status_label.setText(...)

    def update_links(self):
        self.logger.info(f"in update links")
        """
                # Construct the Process Variable (PV) strings
                # TST:UM:LinkSel:SelG:DI:01:Id
                # TST:UM:LinkSel:SelG:AXIS:Id
                # TST:UM:LinkSel:SelG:DRV:Id
                # TST:UM:LinkSel:SelG:ENC:Id

                # Update link process
                # 1. in link selector caput axis id of interest
                #     - TST:UM:LinkSel:SelG:AXIS:Id
                # 2. view set to true -> gives you all of current config
                #     - TST:UM:LinkSel:View
                # 3. change all link defs you want to change
                #     - TST:UM:LinkSel:DI:[number]:[channel]
                # 4. link selector update command
                #     - TST:UM:LinkSel:Update

                """
        # caput staged changes to axis
        for axis_i, axis in enumerate(self.staged_mapping):
            if len(axis) > 0:
                self.logger.debug(f"found changes in axis: {axis}")

                # step 1
                select_axis_string = f"{self.prefixName}:LinkSel:SelG:AXIS:Id"
                self.logger.debug(f"select_axis_string: {select_axis_string}")
                caReadBackSelectedAxis = epics.caput(
                    select_axis_string,
                    self.axis_list_linker.currentItem().text(),
                    wait=True,
                )
                time.sleep(0.5)
                self.logger.debug(f"caReadBackSelectedAxis: {caReadBackSelectedAxis}")

                # step 2
                view_to_true = f"{self.prefixName}:LinkSel:View"
                caReadBack_view_to_true = epics.caput(view_to_true, True, wait=True)
                time.sleep(0.5)
                self.logger.debug(f"caReadBack_view_to_true: {caReadBack_view_to_true}")

                # step 3
                # for i in range(0,3):
                # digital inputs
                self.logger.debug(f"di_1: {axis[0]}")
                if len(axis[0]) > 2:
                    di_1_id = f"{self.prefixName}:LinkSel:SelG:DI:01:Id"
                    self.logger.debug(f"di_1_id: {di_1_id}")
                    di_1_id_new_value = axis[0][1]
                    self.logger.debug(f"di_1_id_new_value: {di_1_id_new_value}")
                    caReadBack_di_1_id = epics.caput(
                        di_1_id, di_1_id_new_value, wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_1_id: {caReadBack_di_1_id}")

                    di_1_main = f"{self.prefixName}:LinkSel:SelG:DI:01:MAIN"
                    self.logger.debug(f"di_1_main: {di_1_main}")
                    di_1_main_new_value = axis[0][2]
                    self.logger.debug(f"di_1_main_new_value: {di_1_main_new_value}")
                    caReadBack_di_1_main = epics.caput(
                        di_1_main, int(di_1_main_new_value), wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_1_main: {caReadBack_di_1_main}")

                    di_1_sub = f"{self.prefixName}:LinkSel:SelG:DI:01:SUB"
                    self.logger.debug(f"di_1_sub: {di_1_sub}")
                    di_1_sub_new_value = axis[0][3]
                    self.logger.debug(f"di_1_sub_new_value: {di_1_sub_new_value}")
                    caReadBack_di_1_sub = epics.caput(
                        di_1_sub, int(di_1_sub_new_value), wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_1_sub: {caReadBack_di_1_sub}")
                else:
                    self.logger.debug(f"nothing in di1")
                self.logger.debug(f"di_2: {axis[1]}")
                if len(axis[1]) > 2:
                    di_2_id = f"{self.prefixName}:LinkSel:SelG:DI:02:Id"
                    self.logger.debug(f"di_2_id: {di_2_id}")
                    di_2_id_new_value = axis[1][1]
                    self.logger.debug(f"di_2_id_new_value: {di_2_id_new_value}")
                    caReadBack_di_2_id = epics.caput(
                        di_2_id, di_2_id_new_value, wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_2_id: {caReadBack_di_2_id}")

                    di_2_main = f"{self.prefixName}:LinkSel:SelG:DI:02:MAIN"
                    self.logger.debug(f"di_2_main: {di_2_main}")
                    di_2_main_new_value = axis[1][2]
                    self.logger.debug(f"di_2_main_new_value: {di_2_main_new_value}")
                    caReadBack_di_2_main = epics.caput(
                        di_2_main, int(di_2_main_new_value), wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_2_main: {caReadBack_di_2_main}")

                    di_2_sub = f"{self.prefixName}:LinkSel:SelG:DI:02:SUB"
                    self.logger.debug(f"di_1_sub: {di_2_sub}")
                    di_2_sub_new_value = axis[1][3]
                    self.logger.debug(f"di_1_sub_new_value: {di_2_sub_new_value}")
                    caReadBack_di_2_sub = epics.caput(
                        di_2_sub, int(di_2_sub_new_value), wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_2_sub: {caReadBack_di_2_sub}")
                else:
                    self.logger.debug(f"nothing in di2")
                self.logger.debug(f"di_3: {axis[2]}")
                if len(axis[2]) > 2:
                    di_3_id = f"{self.prefixName}:LinkSel:SelG:DI:03:Id"
                    self.logger.debug(f"di_1_id: {di_3_id}")
                    di_3_id_new_value = axis[2][1]
                    self.logger.debug(f"di_1_id_new_value: {di_3_id_new_value}")
                    caReadBack_di_3_id = epics.caput(
                        di_3_id, di_3_id_new_value, wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_3_id: {caReadBack_di_3_id}")

                    di_3_main = f"{self.prefixName}:LinkSel:SelG:DI:03:MAIN"
                    self.logger.debug(f"di_1_main: {di_3_main}")
                    di_3_main_new_value = axis[2][2]
                    self.logger.debug(f"di_1_main_new_value: {di_3_main_new_value}")
                    caReadBack_di_3_main = epics.caput(
                        di_3_main, int(di_3_main_new_value), wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_3_main: {caReadBack_di_3_main}")

                    di_3_sub = f"{self.prefixName}:LinkSel:SelG:DI:03:SUB"
                    self.logger.debug(f"di_3_sub: {di_3_sub}")
                    di_3_sub_new_value = axis[2][3]
                    self.logger.debug(f"di_3_sub_new_value: {di_3_sub_new_value}")
                    caReadBack_di_3_sub = epics.caput(
                        di_3_sub, int(di_3_sub_new_value), wait=True
                    )
                    # time.sleep(2)
                    self.logger.debug(f"caReadBack_di_3_sub: {caReadBack_di_3_sub}")
                else:
                    self.logger.debug(f"nothing in di3")
                time.sleep(0.5)

        #  drives and encoders
        for item in self.staged_de:
            print(f"item: {item}")
            if len(item[0]) > 1:
                # TST:UM:LinkSel:SelG:DRV:Id
                stringDrvHardware = f"{self.prefixName}:LinkSel:SelG:DRV:Id"
                self.logger.debug(f"stringDrvHardware: {stringDrvHardware}")
                stringNewDrvVal = item[0][0]
                self.logger.debug(f"stringNewDrvVal: {stringNewDrvVal}")
                caReadbackNewDriveVal = epics.caput(
                    stringDrvHardware, stringNewDrvVal, wait=True
                )
                time.sleep(0.5)
                self.logger.debug(f"caReadbackNewDriveVal: {caReadbackNewDriveVal}")

                stringDriveMainChan = f"{self.prefixName}:LinkSel:SelG:DRV:MAIN"
                self.logger.debug(f"stringDriveMainChan: {stringDriveMainChan}")
                stringNewMainChanVal = item[0][1]
                self.logger.debug(f"stringNewMainChanVal: {stringNewMainChanVal}")
                caReadbackNewMainChanVal = epics.caput(
                    stringDriveMainChan, stringNewMainChanVal, wait=True
                )
                time.sleep(0.5)
                self.logger.debug(
                    f"caReadbackNewMainChanVal: {caReadbackNewMainChanVal}"
                )

            if len(item[1]) > 1:
                # TST:UM:LinkSel:SelG:ENC:Id
                stringEncHardware = f"{self.prefixName}:LinkSel:SelG:ENC:Id"
                self.logger.debug(f"stringEncHardware: {stringEncHardware}")
                stringNewEncVal = item[1][0]
                self.logger.debug(f"stringNewEncVal: {stringNewEncVal}")
                caReadbackNewEncChanVal = epics.caput(
                    stringEncHardware, stringNewEncVal, wait=True
                )
                time.sleep(0.5)
                self.logger.debug(f"caReadbackNewEncChanVal: {caReadbackNewEncChanVal}")

                stringEncMainChan = f"{self.prefixName}:LinkSel:SelG:ENC:MAIN"
                self.logger.debug(f"stringEncMainChan: {stringEncMainChan}")
                stringNewMainChanVal = item[1][1]
                caReadbackNewMainChanVal = epics.caput(
                    stringEncMainChan, stringNewMainChanVal, wait=True
                )
                time.sleep(0.5)
                self.logger.debug(
                    f"caReadbackNewMainChanVal: {caReadbackNewMainChanVal}"
                )

        # step 4
        update_to_true = f"{self.prefixName}:LinkSel:Update"
        caReadBack_update_to_true = epics.caput(update_to_true, True, wait=True)
        time.sleep(0.5)
        self.logger.debug(f"caReadBack_update_to_true: {caReadBack_update_to_true}")
