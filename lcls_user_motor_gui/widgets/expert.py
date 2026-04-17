import re
from functools import partial
from os import path
from pathlib import Path

import epics
from pcdsutils.qt.designer_display import DesignerDisplay
from pydm.widgets.label import PyDMLabel
from pydm.widgets.line_edit import PyDMLineEdit
from qtpy import QtCore, uic
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
from .filtered_list import FilteredListWidget


class ExpertWindow(DesignerDisplay, QWidget):
    filename = "expert_tab.ui"
    ui_dir = Path(__file__).parent / "./../ui"

    # Expert Tab
    expert_axis: QComboBox
    param_tab: QTabWidget
    # expert_nc_filter_list_tab: QTabWidget
    expert_nc_filter: QGroupBox
    expert_drive_filter: QGroupBox
    expert_encoder_filter: QGroupBox

    expert_nc_filter_list: QGroupBox
    expert_coe_drive_filter_list: QGroupBox
    expert_coe_encoder_filter_list: QGroupBox
    # nc_groupbox: QGroupBox

    def __init__(self, main_window, parent=None, logger=None):
        super().__init__(parent)
        self.logger = logger
        self.main_window = main_window
        self.axis = []
        self.prefixName = ""
        self.nc_list = []
        self.coe_drive_list = []
        self.coe_encoder_list = []
        self.pvDict = []

        # Expert Tab -> NC Tab
        self.expert_nc_widget = FilteredListWidget(self.expert_nc_filter)
        self.expert_nc_filter.layout().addWidget(self.expert_nc_widget)

        # # Drive Tab -> NC Tab
        self.expert_drive_widget = FilteredListWidget(self.expert_drive_filter)
        self.expert_drive_filter.layout().addWidget(self.expert_drive_widget)

        # # Encoder Tab -> NC Tab
        self.expert_encoder_widget = FilteredListWidget(self.expert_encoder_filter)
        self.expert_encoder_filter.layout().addWidget(self.expert_encoder_widget)

    def filter_expert_nc_filter(self, text):
        self.logger.info("in filter_expert_nc_filter")
        """
        Filter items in expert_nc_filter based on expert_filter text.
        """
        for i in range(self.expert_nc_filter.count()):
            item = self.expert_nc_filter.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def publish_axis_expert(self):
        # update enum with axis pulled from .db file
        self.logger.info(f"in populate axis_expert")
        self.expert_axis.clear()
        axis_list = self.axis
        for item in axis_list:
            self.expert_axis.addItem(item)

        if not self.expert_axis.isEnabled():
            self.expert_axis.setEnabled(True)
        self.logger.debug(f"caput to: self.axis_selection")

    def expert_update_nc(self):
        self.logger.info("in expert_update_nc")

        axis_index = self.expert_axis.currentIndex()
        self.logger.debug(f"axis: {axis_index}")
        axis = f"{self.prefixName}:MMS:{(axis_index+1):02}:NC:"
        c_nc_p = axis + "[^:]+:Name_RBV"
        self.logger.debug(f"nc p regex: {c_nc_p}")
        stripped_nc = []
        for pv in self.nc_list:
            # self.logger.debug(f"nc pv: {pv}")
            if re.search(c_nc_p, pv):
                # self.logger.debug(f"Found nc_param in the list, param: {pv}")
                stripped_nc.append(pv.strip())

        self.logger.debug(f"len of nc param list: {len(stripped_nc)}")
        # Clear previous items
        self.expert_nc_widget.clear_items()
        # self.nc_list.clear()

        self.ca_nc_list = epics.caget_many(stripped_nc, as_string=True)
        self.logger.info(f"items size after caget: {len(self.ca_nc_list)}")

        # Add items (filter out None just in case)
        items = [item for item in self.ca_nc_list if item]
        self.expert_nc_widget.add_items(items)

        # Enable widget if needed
        self.expert_nc_widget.setEnabled(True)

        # Select first item (if exists)
        # if items:
        #     if self.expert_nc_filter.list_widget.count() > 0:
        #         self.expert_nc_filter.list_widget.setCurrentRow(0)
        # self.expert_nc_filter.list_view.setCurrentIndex(first_index)
        # self.expert_nc_filter.line_edit.setText(items[0])

        # Dynamically add param widgets
        self.add_param_widgets(stripped_nc, self.expert_nc_filter_list)

    def expert_update_drive(self, axis):
        self.logger.info(f"in expert_update_drive")

        # Get current axis
        axis_index = self.expert_axis.currentIndex()
        drive_string = f"{self.prefixName}:AXIS:{(axis_index+1):02}:SelG:DRV:Id_RBV"
        self.logger.debug(f"drive_string: {drive_string}")

        # Get hardware slice
        # TST:UM:01:SelG:DRV:Id_RBV
        hardwareID = epics.caget(drive_string, as_string=True)

        self.logger.debug(f"hardwareID before split: {hardwareID}")
        # Remove everything after the first underscore
        if hardwareID:
            if "_" in hardwareID:
                hardwareID = hardwareID.split("_", 1)[0]
        else:
            hardwareID = "None"

        self.logger.debug(f"hardwareID after split: {hardwareID}")

        formatted_drive_string = (
            f"{self.prefixName}:{hardwareID}:{(axis_index+1):02}:COE"
        )
        string_drive_regex = f"{formatted_drive_string}:(?!.*:DG:)[^:]+:Name_RBV"
        self.logger.debug(f"string_drive_regex: {string_drive_regex}")
        stripped_coe = []
        self.logger.debug(f"coe len: {len(self.coe_drive_list)}")
        for pv in self.coe_drive_list:
            # self.logger.debug(f"pv: {pv}")
            if re.search(string_drive_regex, pv):
                # self.logger.debug(f"Found nc_param in the list, param: {pv}")
                stripped_coe.append(pv.strip())

        # Clear previous items
        self.expert_drive_widget.clear_items()
        # self.coe_drive_list.clear()

        self.ca_coe_drive_list = epics.caget_many(stripped_coe, as_string=True)
        self.logger.info(f"items size: {len(self.ca_coe_drive_list)}")

        # Add items (filter out None just in case)
        items = [item for item in self.ca_coe_drive_list if item]
        self.expert_drive_widget.add_items(items)

        # Enable widget if needed
        self.expert_drive_widget.setEnabled(True)

        # Select first item (if exists)
        # if items:
        #     if self.expert_drive_filter.list_widget.count() > 0:
        #         self.expert_drive_filter.list_widget.setCurrentRow(0)
        # self.expert_drive_filter.list_view.setCurrentIndex(first_index)
        # self.expert_drive_filter.line_edit.setText(items[0])

        # # Dynamically add param widgets
        self.add_param_widgets(stripped_coe, self.expert_coe_drive_filter_list)

    def expert_update_encoder(self, axis):
        self.logger.info(f"in expert_update_encoder")

        # Get current axis
        axis_index = self.expert_axis.currentIndex()
        # axis = f"{self.prefixName}:0{axis_index + 1}"
        encoder_string = f"{self.prefixName}:AXIS:{(axis_index+1):02}:SelG:ENC:Id_RBV"
        self.logger.debug(f"encoder_string: {encoder_string}")

        # Get hardware slice
        # TST:UM:01:SelG:DRV:Id_RBV
        hardwareID = epics.caget(encoder_string, as_string=True)

        if hardwareID:
            if "_" in hardwareID:
                hardwareID = hardwareID.split("_", 1)[0]
        else:
            hardwareID = "None"

        self.logger.debug(f"hardwareID after split: {hardwareID}")

        # self.coe_encoder_list = identify_coe_enc_params(
        #     f"{axis}:{hardwareID}", self.pvDict
        # )

        formatted_drive_string = (
            f"{self.prefixName}:{hardwareID}:{(axis_index+1):02}:COE"
        )
        string_enc_regex = f"{formatted_drive_string}:(?!.*:DG:)[^:]+:Name_RBV"
        self.logger.debug(f"string_enc_regex: {string_enc_regex}")
        stripped_coe = []
        # self.logger.debug(f"DEBUG: coe_encoder_list at start = {self.coe_encoder_list}")
        self.logger.debug(f"coe len: {len(self.coe_encoder_list)}")
        for pv in self.coe_encoder_list:
            # self.logger.debug(f"pv: {pv}")
            if re.search(string_enc_regex, pv):
                # self.logger.debug(f"Found nc_param in the list, param: {pv}")
                stripped_coe.append(pv.strip())

        # Clear previous items
        self.expert_encoder_widget.clear_items()
        # self.coe_encoder_list.clear()

        self.ca_coe_encoder_list = epics.caget_many(stripped_coe, as_string=True)
        self.logger.info(f"items size: {len(self.ca_coe_encoder_list)}")

        # Add items (filter out None just in case)
        items = [item for item in self.ca_coe_encoder_list if item]
        self.expert_encoder_widget.add_items(items)

        # Enable widget if needed
        self.expert_encoder_widget.setEnabled(True)

        # Select first item (if exists)
        # if items:
        #     if self.expert_encoder_filter.list_widget.count() > 0:
        #         self.expert_encoder_filter.list_widget.setCurrentRow(0)
        # self.expert_encoder_filter.list_view.setCurrentIndex(first_index)
        # self.expert_encoder_filter.line_edit.setText(items[0])

        # # Dynamically add param widgets
        self.add_param_widgets(stripped_coe, self.expert_coe_encoder_filter_list)

    def configure_param_widgets(self, widget: QWidget, nc_pv):
        """
        Configure all param.ui widgets in self.param_widgets.
        Optionally takes a config_list (list of dicts) to set values for each widget.
        Example config_list: [{"label": "NC1", "lineEdit": "val1", "lineEdit_2": "val2", "label_2": "desc1"}, ...]
        """
        self.logger.info("in configure_param_widgets")
        vals = ["", "", "", ""]
        vals[0] = nc_pv + ":Name_RBV"
        vals[1] = nc_pv + ":Goal"
        vals[2] = nc_pv + ":Val_RBV"
        vals[3] = nc_pv + ":EU_RBV"
        # vals[4] = nc_pv + ":EU_RBV"
        # self.logger.debug("ca://" + vals[1])
        # ca_vals = epics.caget_many(vals, as_string=True)
        # self.logger.debug(ca_vals)
        name = widget.findChild(PyDMLabel, "pv_name")
        name.set_channel("ca:// " + vals[0])
        goal = widget.findChild(PyDMLineEdit, "pv_goal")
        goal.set_channel("ca://" + vals[1])
        rbv = widget.findChild(PyDMLineEdit, "pv_rbv")
        rbv.set_channel("ca://" + vals[2])
        units = widget.findChild(PyDMLabel, "pv_units")
        units.set_channel("ca://" + vals[3])

    def add_param_widgets(self, param, widget: QListWidget):
        """
        Dynamically add instances of the param.ui widget as QListWidgetItems in self.expert_nc_filter_list (QListWidget)
        """
        self.logger.info("in add_param_widgets")
        widget.clear()
        self.param_widgets = []
        self.param_connections = []  # (optional, if you want a new list for every call)
        self.logger.debug(str(Path(__file__).parent))
        for i, pv in enumerate(param):
            param_widget = uic.loadUi(
                str(Path(__file__).parent / "./../ui" / "param.ui")
            )
            item = QListWidgetItem()
            pv_clean = self.remove_name_rbv(pv)
            # self.logger.debug(f"pv: {pv_clean}")
            self.configure_param_widgets(param_widget, pv_clean)

            # --- Find the PyDMLineEdit and connect its signals ---
            pydm_line_edit = param_widget.findChild(PyDMLineEdit, "pv_goal")
            if pydm_line_edit is not None:
                pydm_line_edit.editingFinished.connect(
                    # lambda : self.when_param_changed(i, pv, pydm_line_edit)
                    partial(self.check_caput, pv)
                )
                self.param_connections.append(pydm_line_edit)

            item.setSizeHint(param_widget.sizeHint())
            widget.addItem(item)
            widget.setItemWidget(item, param_widget)

            self.param_widgets.append(param_widget)

    def highlight_nc_param(self):
        self.logger.info("in highlight_nc_param")
        current_text = self.expert_nc_widget.currentText()
        # Defensive check: Make sure current_text is in the list
        if current_text in self.ca_nc_list:
            pv_index = self.ca_nc_list.index(current_text)
            # self.logger.debug(f"current pv: {pv_index} ({current_text})")

            # Clear all highlights
            for i in range(self.expert_nc_filter_list.count()):
                widget = self.expert_nc_filter_list.itemWidget(
                    self.expert_nc_filter_list.item(i)
                )
                if widget is not None:
                    widget.setStyleSheet("")  # Remove highlight

            # Highlight the desired item
            item = self.expert_nc_filter_list.item(pv_index)
            widget = self.expert_nc_filter_list.itemWidget(item)
            if widget is not None:
                widget.setStyleSheet(
                    "border: 2px solid #22AAFF; border-radius: 4px; background: #e8f6fd;"
                )
            # Scroll to this item
            if item is not None:
                self.expert_nc_filter_list.scrollToItem(
                    item, QAbstractItemView.PositionAtCenter
                )

            # (Optional: also select the item in the list view)
            # self.expert_nc_filter_list.setCurrentItem(item)
            else:
                self.logger.debug("Current filter text not found in ca_nc_list!")

    def highlight_coe_drive_param(self):
        self.logger.info("in highlight_coe_drive_param")
        current_text = self.expert_drive_widget.currentText()
        # Defensive check: Make sure current_text is in the list
        if current_text in self.ca_coe_drive_list:
            pv_index = self.ca_coe_drive_list.index(current_text)
            # self.logger.debug(f"current pv: {pv_index} ({current_text})")

            # Clear all highlights
            for i in range(self.expert_coe_drive_filter_list.count()):
                widget = self.expert_coe_drive_filter_list.itemWidget(
                    self.expert_coe_drive_filter_list.item(i)
                )
                if widget is not None:
                    widget.setStyleSheet("")  # Remove highlight

            # Highlight the desired item
            item = self.expert_coe_drive_filter_list.item(pv_index)
            widget = self.expert_coe_drive_filter_list.itemWidget(item)
            if widget is not None:
                widget.setStyleSheet(
                    "border: 2px solid #22AAFF; border-radius: 4px; background: #e8f6fd;"
                )
            # Scroll to this item
            if item is not None:
                self.expert_coe_drive_filter_list.scrollToItem(
                    item, QAbstractItemView.PositionAtCenter
                )

            # (Optional: also select the item in the list view)
            # self.expert_nc_filter_list.setCurrentItem(item)
            else:
                self.logger.debug("Current filter text not found in ca_coe_drive_list!")

    def highlight_coe_encoder_param(self):
        self.logger.info("in highlight_coe_encoder_param")
        current_text = self.expert_encoder_widget.currentText()
        # Defensive check: Make sure current_text is in the list
        if current_text in self.ca_coe_encoder_list:
            pv_index = self.ca_coe_encoder_list.index(current_text)
            # self.logger.debug(f"current pv: {pv_index} ({current_text})")

            # Clear all highlights
            for i in range(self.expert_coe_encoder_filter_list.count()):
                widget = self.expert_coe_encoder_filter_list.itemWidget(
                    self.expert_coe_encoder_filter_list.item(i)
                )
                if widget is not None:
                    widget.setStyleSheet("")  # Remove highlight

            # Highlight the desired item
            item = self.expert_coe_encoder_filter_list.item(pv_index)
            widget = self.expert_coe_encoder_filter_list.itemWidget(item)
            if widget is not None:
                widget.setStyleSheet(
                    "border: 2px solid #22AAFF; border-radius: 4px; background: #e8f6fd;"
                )
            # Scroll to this item
            if item is not None:
                self.expert_coe_encoder_filter_list.scrollToItem(
                    item, QAbstractItemView.PositionAtCenter
                )

            # (Optional: also select the item in the list view)
            # self.expert_nc_filter_list.setCurrentItem(item)
            else:
                self.logger.debug(
                    "Current filter text not found in ca_coe_encoder_list!"
                )

    def remove_name_rbv(self, pv_name):
        suffix = ":Name_RBV"
        if pv_name.endswith(suffix):
            return pv_name[: -len(suffix)]
        return pv_name

    def check_caput(self, pv):
        self.logger.info("in check_caput")

        """
        this function was meant to start an async thread that confirms
        the caput has been successful. in the integration test I was
        relying on the wait=true part of the caput
        """
        pv = self.remove_name_rbv(pv)

        # Run blocking calls in a thread
        goal_value = epics.caget, pv + ":Goal"
        rbv_value = epics.caget, pv + ":Val_RBV"

        if goal_value == rbv_value:
            self.logger.debug(f"goal and rbv match: {goal_value}, {rbv_value}")
            return True
        else:
            self.logger.debug(f"goal and rbv DO NOT match: {goal_value}, {rbv_value}")
            return False

        # units.setText(ca_vals[3])
