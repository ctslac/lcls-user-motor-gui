import logging
from pathlib import Path

import epics
from pcdsutils.qt.designer_display import DesignerDisplay
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
    keep_prefix,
    strip_axis_id,
    val_to_key,
)


class UserInputWindow(DesignerDisplay, QWidget):
    filename = "user_input_tab.ui"
    ui_dir = Path(__file__).parent / "./../ui"

    # User Input Tab
    display_axis_ui: QListWidget
    display_drives_ui: QListWidget
    display_drives_channel_ui: QListWidget
    display_encoders_ui: QListWidget
    display_encoders_channel_ui: QListWidget
    digital_input_axis_ui: QListWidget
    digital_input_hardware_ui: QListWidget
    digital_input_channels_ui: QListWidget
    digital_input_channel_slot_ui: QListWidget
    stage_settings: QPushButton

    def __init__(self, main_window, parent=None, logger=None):
        # Properly call the superclass __init__!
        super().__init__(parent)
        self.logger = logger
        self.main_window = main_window
        self.prefixName = ""
        self.axis = []
        # self.drives = []
        # self.encoders = []
        self.pvDict = {}
        self.store_di_selection = [[-1, -1], [-1, -1], [-1, -1]]
        self.loaded_unique_di = []
        self.drives_ui = ["None"]
        self.encoders_ui = ["None"]
        self.di_size = 0
        self.digital_inputs_ui = ["None"]
        self.digital_inputs_hardware_ui = ["None"]
        self.loaded_di_channels_ui = []

    def select_axis_ui(self):
        self.logger.info(f"in select_axis_ui")
        # self.populate_di()
        self.detect_linked_enc_ui()
        self.detect_linked_drv_ui()
        self.publish_axis_di_ui()

    def detect_linked_enc_ui(self):
        self.logger.info(f"in detect_linked_enc_ui")
        # currAxisIdx = self.display_axis_ui.currentRow()
        # currAxis = val_to_key(self.axis[currAxisIdx], self.pvDict)
        currAxis = self.display_axis_ui.currentRow()
        self.logger.debug(f"currAxis: {currAxis}")
        # currAxis = strip_axis_id(currAxis)
        detectableENC = (
            self.prefixName + ":AXIS:0" + str(currAxis + 1) + ":SelG:ENC:Id_RBV"
        )
        encValue = epics.caget(detectableENC, as_string=True)
        self.logger.debug(f"detectableENC: {detectableENC}")
        self.logger.debug(f"encValue: {encValue}")

        found_enc = False
        for i in range(0, self.display_encoders_ui.count()):
            if encValue == self.display_encoders_ui.item(i).text():
                self.logger.debug(
                    f"found enc: {self.display_encoders_ui.item(i).text()}"
                )
                self.display_encoders_ui.setCurrentRow(i)
                found_enc = True
                break

        # load encoder channels
        encoder_channel = (
            self.prefixName
            + ":AXIS:0"
            + str(self.display_axis_ui.currentRow() + 1)
            + ":SelG:ENC:MAIN_RBV"
        )
        self.logger.debug(f"encoder_channel: {encoder_channel}")
        encoder_channel_val = epics.caget(encoder_channel, as_string=True)
        self.logger.debug(f"encoder_channel_val: {encoder_channel_val}")
        for i in range(0, self.display_encoders_channel_ui.count()):
            item = self.display_encoders_channel_ui.item(i)
            if item is not None and encoder_channel_val == item.text():
                self.logger.debug(f"found enc chan: {item.text()}")
                self.display_encoders_channel_ui.setCurrentRow(i)
                break
            else:
                self.logger.debug(f"channel is none, something went wrong")

        if not found_enc:
            self.logger.debug("No link found, defaulting to None")
            self.display_drives_ui.setCurrentRow(0)

    def detect_linked_drv_ui(self):
        self.logger.info(f"in detect_linked_drv_ui")
        currAxis = self.display_axis_ui.currentRow()
        # currAxis = val_to_key(self.axis[currAxisIdx], self.pvDict)
        self.logger.debug(f"currAxis: {currAxis}")
        # currAxis = strip_axis_id(currAxis)
        detectableDRV = (
            self.prefixName + ":AXIS:0" + str(currAxis + 1) + ":SelG:DRV:Id_RBV"
        )

        drvValue = epics.caget(detectableDRV, as_string=True)
        self.logger.debug(f"detDRV: {detectableDRV}")
        self.logger.debug(f"drvValue: {drvValue}")

        found_drv = False
        for i in range(0, self.display_drives_ui.count()):
            if drvValue == self.display_drives_ui.item(i).text():
                self.logger.debug(f"found drv: {self.display_drives_ui.item(i).text()}")
                self.display_drives_ui.setCurrentRow(i)
                found_drv = True
                break

        # load drive channels
        drive_channel = (
            self.prefixName
            + ":AXIS:0"
            + str(self.display_axis_ui.currentRow() + 1)
            + ":SelG:DRV:MAIN_RBV"
        )
        self.logger.debug(f"drive_channel: {drive_channel}")
        drive_channel_val = epics.caget(drive_channel, as_string=True)
        self.logger.debug(f"drive_channel_val: {drive_channel_val}")
        for i in range(0, self.display_drives_channel_ui.count()):
            item = self.display_drives_channel_ui.item(i)
            if item is not None and drive_channel_val == item.text():
                self.logger.debug(f"found drv chan: {item.text()}")
                self.display_drives_channel_ui.setCurrentRow(i)
                break
            else:
                self.logger.debug(f"channel is none, something went wrong")

        if not found_drv:
            self.logger.debug("No link found, defaulting to None")
            self.display_drives_ui.setCurrentRow(0)

    def load_axis_di_ui(self):
        """ """
        self.logger.info(f"in load_axis_di_ui")
        self.digital_input_axis_ui.clear()

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
            self.loaded_unique_di_ui.append(self.identify_di(item))

            # self.digital_input_axis.addItem(val)
        self.loaded_unique_di_ui = [
            item for sublist in self.loaded_unique_di_ui for item in sublist
        ]
        self.logger.debug(f"val: {self.loaded_unique_di_ui}")
        # if not self.digital_input_axis.isEnabled():
        #     self.digital_input_hardware.setEnabled(True)
        # self.discover_di_channel()

    def publish_axis_di_ui(self):
        self.logger.info(f"in publish_axis_di_ui")
        # if self.axis_di_init:
        self.digital_input_axis_ui.clear()
        numDI = 0

        # currAxisIdx = self.axis_list.currentRow()
        # self.logger.debug(f"currAxisIdx: {self.axis[currAxisIdx]}")
        # currAxis = self.val_to_key(self.axis[currAxisIdx])
        # self.logger.debug(f"currAxis: {currAxis}")

        currAxis = val_to_key(self.display_axis_ui.currentItem().text(), self.pvDict)
        self.logger.debug(f"currAxis: {currAxis}")
        # for items in self.loaded_unique_di:
        #     if items.startswith(currAxis):
        #         numDI = numDI + 1
        for i in range(0, 3):
            self.logger.debug("adding di item")
            self.digital_input_axis_ui.addItem("0" + str(1 + i))
            # self.axis_di_init = False
        # elif self.axis_di_init is False:
        # self.digital_input_axis.setCurrentRow(self.axis_di_idx)

        self.select_di_channel_ui()

    def select_di_channel_ui(self):
        self.logger.info(f" select_di_channel_ui:")
        # self.digital_input_channel_slot_ui.clear()
        # self.check_duplicate_di
        DI_hardware_Channel = 0
        DI_hardware_Channel_Slots = 0
        axis_di_idx = self.digital_input_axis_ui.currentRow()
        self.logger.debug(f"axis_di_idx: {axis_di_idx}")
        if axis_di_idx < 0:
            self.logger.debug("please select a di")
        else:
            currAxisIdx = self.display_axis_ui.currentRow()
            self.logger.debug(f"currAxisIdx: {currAxisIdx}")
            self.logger.debug(f"axis: {self.axis[currAxisIdx]}")
            # currAxis = val_to_key(self.axis[currAxisIdx], self.pvDict)
            # self.logger.debug(f"currAxis: {currAxis}")
            # currAxis = strip_axis_id(currAxis)
            currAxis = self.prefixName + ":AXIS:0" + str(currAxisIdx + 1)
            detectableDi = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":Id_RBV"
            )
            self.logger.debug(f"link to check: {detectableDi}")
            # DI_hardware = fake_caget(self.pvDict, detectableDi + ":ID_RBV")
            DI_hardware = epics.caget(detectableDi, as_string=True)
            if DI_hardware == 0:
                DI_hardware = None
            self.logger.debug(f"DI_hardware: {DI_hardware}")

            # self.logger.debug(f"DI_hardware_channel: {DI_hardware_Channel}")
            # returnStatus = self.digital_input_hardware.findItems(value, Qt.MatchCaseSensitive)
            # self.logger.debug(f"returnStatus: {returnStatus.text()}")

            self.logger.debug("searching for DI hardware channel")
            """
            detect DI hardware, here this is any slice
            the next thing that needs to happen is parse by slice type and check mains and sub-mains
            ie.
            ID = 1429 -> 1 main -> 1 submain
            ID = 7062 -> 2 mains -> 2 submains per main
            ID = 7047 -> 1 main -> 1 submain
            """
            for i in range(0, self.digital_input_hardware_ui.count()):
                if DI_hardware == self.digital_input_hardware_ui.item(i).text():
                    # self.logger.debug(f"currItem: {self.digital_input_hardware.item(i).text()}")
                    print(
                        f"found hardware: {self.digital_input_hardware_ui.item(i).text()}"
                    )
                    self.digital_input_hardware_ui.setCurrentRow(i)
                    break
                elif DI_hardware == None:
                    self.logger.debug("no hardware detected")
                    self.digital_input_hardware_ui.setCurrentRow(0)
                else:
                    self.logger.debug("something went wrong/thinking")

            ### START HERE ###
            """
            I need to implement ways for checking what the slice type is
            if the slice type is something that contains more than 1 main then I need to check the submain
            """
            # di_s = currAxis + ":NUMDI_RBV"
            # DI_hardware_Channel = epics.caget(num_di, )
            # if "7062" in DI_hardware:
            #     self.logger.debug("di slice is 7062")
            #     di_chan = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ':SUB_RBV'
            #     di_chan_slot = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ':MAIN_RBV'
            #     DI_hardware_Channel_Slots = epics.caget(di_chan_slot, as_string=True)
            #     DI_hardware_Channel = epics.caget(di_chan, as_string=True)
            #     self.logger.debug(f"DI_hardware_Channel: {int(DI_hardware_Channel)}")
            #     self.logger.debug(f"DI_hardware_Channel Slot: {int(DI_hardware_Channel_Slots)}")
            #     # for i in range(0, DI_hardware_Channel_Slots):
            #     #     self.digital_input_channel_slot_ui.addItem(str(i+1))
            # elif "1429" in DI_hardware:
            #     self.logger.debug("di slice is 1429")
            #     di_chan = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ':SUB_RBV'
            #     di_chan_slot = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ':MAIN_RBV'
            #     DI_hardware_Channel_Slots = epics.caget(di_chan_slot, as_string=True)
            #     DI_hardware_Channel = epics.caget(di_chan, as_string=True)
            #     self.logger.debug(f"DI_hardware_Channel: {int(DI_hardware_Channel)}")
            #     self.logger.debug(f"DI_hardware_Channel Slot: {int(DI_hardware_Channel_Slots)}")
            #     # for i in range(0, int(DI_hardware_Channel_Slots)):
            #     #     self.digital_input_channel_slot_ui.addItem(str(i+1))

            self.logger.debug("searching for DI hardware channel slot")
            di_chan_slot = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":MAIN_RBV"
            )
            DI_hardware_Channel_Slots = epics.caget(di_chan_slot, as_string=True)
            self.logger.debug(
                f"DI_hardware_Channel Slot: {int(DI_hardware_Channel_Slots)}"
            )

            for i in range(0, self.digital_input_channel_slot_ui.count()):
                if (
                    DI_hardware_Channel_Slots
                    == self.digital_input_channel_slot_ui.item(i).text()
                ):
                    self.logger.debug(
                        f"found channel main: {self.digital_input_channel_slot_ui.item(i).text()}"
                    )
                    self.digital_input_channel_slot_ui.setCurrentRow(i)
                elif DI_hardware_Channel_Slots == "0":
                    self.logger.debug("something went wrong, should not be possible")
                    self.digital_input_channel_slot_ui.selectionMode(
                        QAbstractItemView.NoSelection
                    )

            self.logger.debug("searching for DI hardware channel")
            di_chan = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":SUB_RBV"
            )
            DI_hardware_Channel = epics.caget(di_chan, as_string=True)
            self.logger.debug(f"DI_hardware_Channel: {int(DI_hardware_Channel)}")

            for i in range(0, self.digital_input_channels_ui.count()):
                if DI_hardware_Channel == self.digital_input_channels_ui.item(i).text():
                    self.logger.debug(
                        f"found channel sub: {self.digital_input_channels_ui.item(i).text()}"
                    )
                    self.digital_input_channels_ui.setCurrentRow(i)
                elif DI_hardware_Channel == "0":
                    self.logger.debug("something went wrong, should not be possible")
                    self.digital_input_channels_ui.selectionMode(
                        QAbstractItemView.NoSelection
                    )

            if axis_di_idx == 0:
                self.store_di_selection[0] = [
                    self.digital_input_hardware_ui.currentRow(),
                    self.digital_input_channels_ui.currentRow(),
                ]
            elif axis_di_idx == 1:
                self.store_di_selection[1] = [
                    self.digital_input_hardware_ui.currentRow(),
                    self.digital_input_channels_ui.currentRow(),
                ]
            elif axis_di_idx == 2:
                self.store_di_selection[2] = [
                    self.digital_input_hardware_ui.currentRow(),
                    self.digital_input_channels_ui.currentRow(),
                ]

        # currDI = self.loaded_di_channels[currDiIdx]
        # self.logger.debug(f"currDI: {currDI}")
        # currDiChanIdx = self.digital_input_channels.currentRow()

        # for di in self.digital_input_channels:
        #     """
        #     finish code here need to implement
        #     when a di slot is selected save the selected mapping
        #     in self.store_di_selection = {}
        #     """
        #     pass

    def load_di_ui(self):
        """
        comes from WCIB
        needs to publish, and call discover_di_channel
        """
        self.logger.info(f"in load_di_ui")
        self.digital_input_hardware_ui.clear()
        self.digital_input_hardware_ui.addItem("None")
        # self.digital_inputs = identify_inputs(
        #     self.pvList, self.axis_list.currentItem().text()
        # )

        replaced_items = []
        for item in self.digital_inputs_ui:
            print(f"item: {item}")
            replaced_items.append(item.replace("WCIB_RBV", "Id_RBV"))

            # cleaned_di = item.replace(delimiter, ":Id_RBV")
            # cleaned_di = keep_prefix(item, 4)
            # cleaned_di = cleaned_di + ":Id_RBV"
            # self.logger.debug(f"cleaned item: {cleaned_di}")
            # val = fake_caget(self.pvDict, cleaned_di)
            # self.logger.debug(f"val: {val}")
            # self.digital_input_hardware_ui.addItem(val)
        # self.digital_input_hardware.setCurrentRow(0)
        val = epics.caget_many(replaced_items, as_string=True)
        self.digital_inputs_ui[:] = val[0:]
        self.digital_input_hardware_ui.addItems(self.digital_inputs_ui)
        if not self.digital_input_hardware_ui.isEnabled():
            self.digital_input_hardware_ui.setEnabled(True)
        # self.discover_di_channel_ui()
        # self.load_di_channel_ui

    def load_di_channel_ui(self):
        self.logger.info(f"in load di_channel_ui")
        self.digital_input_channels_ui.clear()
        self.digital_input_channel_slot_ui.clear()
        current_item = self.digital_input_hardware_ui.currentItem()
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
        currAxisIdx = self.display_axis_ui.currentRow()
        axis_di_idx = self.digital_input_axis_ui.currentRow()
        currAxis = self.prefixName + ":AXIS:0" + str(currAxisIdx + 1)
        if currDI.startswith("EL7062"):
            # di_chan = currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ':SUB_RBV'
            # self.di_size = epics.caget(di_chan)
            for i in range(0, int(2)):
                self.digital_input_channel_slot_ui.addItem(str(i + 1))
            for i in range(0, int(2)):
                self.digital_input_channels_ui.addItem(str(i + 1))
        elif currDI.startswith("EL1429"):
            di_chan = (
                currAxis + ":SelG:DI:" + ("0" + str(int(axis_di_idx) + 1)) + ":SUB_RBV"
            )
            self.di_size = epics.caget(di_chan)
            for i in range(0, int(16)):
                self.digital_input_channel_slot_ui.addItem(str(i + 1))
            for i in range(0, int(1)):
                self.digital_input_channels_ui.addItem(str(i + 1))
        else:
            self.logger.debug("Slice Unknown")
        # cleaned_di = self.prefixName + ':0' + str(self.display_axis_ui.currentRow()+1) +':'+ currDI +  ":NUMDI_RBV"
        # cleaned_di = self.prefixName + ':0' + str(self.display_axis_ui.currentRow()+1) + ':0' + str(self.digital_input_axis_ui.currentRow()) + ":NUMDI_RBV"
        # self.logger.debug(f"cleaned axis: {cleaned_di}")

        # self.di_size = fake_caget(self.pvDict, cleaned_di)
        # if self.di_size is None:
        #     self.logger.warning(f"NUMDI_RBV value for {cleaned_di} is None")
        #     return

        # try:
        #     di_size_int = int(self.di_size)
        # except (TypeError, ValueError):
        #     self.logger.error(f"Invalid NUMDI_RBV value for {cleaned_di}: {self.di_size}")
        #     return

        # if self.di_size > 0:
        #     for i in range(self.di_size):
        #         self.digital_input_channel_slot_ui.addItem(str(i + 1))
        # else:
        #     self.digital_input_channel_slot_ui.clear()

    def load_drives_ui(self):
        # update enum with drives pulled from .db file
        self.logger.info(f"in populate drives_ui")
        self.display_drives_ui.clear()
        # self.user_input_widget.display_drives_ui.clear()
        # self.display_drives_ui.addItem("None")
        # self.drives = identify_drive(self.pvList, self.axis_list.currentItem().text())
        replaced_items = []
        # drives = self.drives_ui
        for item in self.drives_ui[1:]:
            print(f"drives: {item}")
            replaced_items.append(item.replace("WCIB_RBV", "Id_RBV"))
            # self.logger.debug(f"cleaned item: {cleaned_item}")
        # self.drives_ui[1:-1] = replaced_items
        val = epics.caget_many(replaced_items, as_string=True)
        self.drives_ui[1:] = val[0:]
        self.display_drives_ui.addItems(self.drives_ui)

        # self.display_drives_ui.setCurrentRow(self.drives_list.currentRow())
        # self.display_drives_ui.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_drives_ui.isEnabled():
            self.display_drives_ui.setEnabled(True)

    def load_drives_channel_ui(self):
        self.logger.info(f"in load_drives_channel_ui")
        self.display_drives_channel_ui.clear()
        if "7062" in self.display_drives_ui.currentItem().text():
            for i in range(0, 2):
                self.display_drives_channel_ui.addItem(str(i + 1))

    def load_encoders_channel_ui(self):
        self.logger.info(f"in load_encoders_channel_ui")
        self.display_encoders_channel_ui.clear()
        if "7062" in self.display_encoders_ui.currentItem().text():
            for i in range(0, 2):
                self.display_encoders_channel_ui.addItem(str(i + 1))
        elif "5042" in self.display_encoders_ui.currentItem().text():
            for i in range(0, 2):
                self.display_encoders_channel_ui.addItem(str(i + 1))

    def discover_di_channel_ui(self):
        """
        comes from load_di
        ---
        find out number of DIs
        """
        self.logger.info(f"in load_di channel_ui")
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
                self.loaded_di_channels_ui.append(pv)

        # for i in range(1, int(nums) + 1):
        #     self.digital_input_channels.addItem(str(i))
        # # self.digital_input_channels.setCurrentRow(0)
        # if not self.digital_input_channels.isEnabled():
        #     self.digital_input_channels.setEnabled(True)

    def load_axis_di_ui(self):
        """ """
        self.logger.info(f"in load_axis_di_ui")
        self.digital_input_axis_ui.clear()

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
            self.loaded_unique_di.append(identify_di(item, self.pvDict))

            # self.digital_input_axis.addItem(val)
        self.loaded_unique_di = [
            item for sublist in self.loaded_unique_di for item in sublist
        ]
        self.logger.debug(f"val: {self.loaded_unique_di}")
        # if not self.digital_input_axis.isEnabled():
        #     self.digital_input_hardware.setEnabled(True)
        # self.discover_di_channel()

    def publish_axis_ui(self):
        # update enum with axis pulled from .db file
        self.logger.info(f"in populate axis_ui")
        self.display_axis_ui.clear()
        # display_items = []
        # for item in self.axis:
        #     item = fake_caget(self.pvDict, item)
        for item in self.axis:
            print(f"axis: {item}")
        self.display_axis_ui.addItems(self.axis)
        # idx = self.axis_list
        # self.display_axis.setCurrentRow(self.axis_list.currentRow())
        # self.display_axis.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_axis_ui.isEnabled():
            self.display_axis_ui.setEnabled(True)
        # self.logger.debug(f"caput to: self.axis_selection")

    def load_encoders_ui(self):
        # update enum with drives pulled from .db file
        self.logger.info(f"in populate enc_ui")
        self.display_encoders_ui.clear()
        # self.display_encoders_ui.addItem("None")
        # self.enocder_type = identify_enc(self.pvList, self.axis_list.currentItem().text())
        # self.logger.debug(f"encoder list size: {len(self.encoders)}")
        replaced_items = []
        # drives = self.drives_ui
        for item in self.encoders_ui[1:]:
            print(f"drives: {item}")
            replaced_items.append(item.replace("WCIB_RBV", "Id_RBV"))
            # self.logger.debug(f"cleaned item: {cleaned_item}")
        # self.drives_ui[1:-1] = replaced_items
        val = epics.caget_many(replaced_items, as_string=True)
        self.encoders_ui[1:] = val[0:]
        self.display_encoders_ui.addItems(self.encoders_ui)
        # self.display_encoders_ui.setCurrentRow(self.enocders_list.currentRow())
        # self.display_encoders_ui.setSelectionMode(QAbstractItemView.NoSelection)
        if not self.display_encoders_ui.isEnabled():
            self.display_encoders_ui.setEnabled(True)
        # print(self.encoder_selection)
