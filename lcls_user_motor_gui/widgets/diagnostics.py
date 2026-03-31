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


class DiagnosticsWindow(DesignerDisplay, QWidget):
    filename = "diagnostic_tab.ui"
    ui_dir = Path(__file__).parent / "./../ui"

    # Diagnostic Tab
    diagnostic_axis_selection: QComboBox
    diagnostic_hardware_selection: QListWidget
    diagnostic_groupbox: QGroupBox
    diagnostic_params_groupbox: QGroupBox

    def __init__(self, main_window, parent=None, logger=None):
        super().__init__(parent)
        self.logger = logger
        self.main_window = main_window
        self.prefixName = ""
        self.pvDict = {}
        self.axis = []
        self.dg_list = []

        self.diagnostic_param_filter = FilteredListWidget(self.diagnostic_groupbox)
        self.diagnostic_groupbox.layout().addWidget(self.diagnostic_param_filter)

    def publish_axis_diagnostic(self):
        # update enum with axis pulled from .db file
        self.logger.info(f"in publish_axis_diagnostic")
        self.diagnostic_axis_selection.clear()
        self.diagnostic_axis_selection.addItems(self.axis)
        # idx = self.axis_list
        # self.expert_axis.setCurrentRow(0)
        if not self.diagnostic_axis_selection.isEnabled():
            self.diagnostic_axis_selection.setEnabled(True)
        self.logger.debug(f"caput to: self.axis_selection")

    def populate_diagnostic_hardware(self):
        self.logger.info(f"in populate_diagnostic_hardware")
        # Get current axis
        self.diagnostic_hardware_selection.clear()
        axis_index = self.diagnostic_axis_selection.currentIndex()
        axis = f"{self.prefixName}:0{axis_index + 1}"
        print(f"axis: {axis}")
        print(f'caget: {axis + ":SelG:ENC:Id_RBV"}')
        hardwareDrvId = epics.caget(axis + ":SelG:DRV:Id_RBV", as_string=True)
        hardwareEncId = epics.caget(axis + ":SelG:ENC:Id_RBV", as_string=True)
        print(f"drv id: {hardwareDrvId}, enc id: {hardwareEncId}")
        if hardwareDrvId:
            if "_" in hardwareDrvId:
                hardwareDrvId = hardwareDrvId.split("_", 1)[0]
        else:
            hardwareDrvId = "None"

        if hardwareEncId:
            if "_" in hardwareEncId:
                hardwareEncId = hardwareEncId.split("_", 1)[0]
        else:
            hardwareEncId = "None"

        axis_w_drv = f"{axis}:{hardwareDrvId}"
        axis_w_enc = f"{axis}:{hardwareEncId}"
        self.diagnostic_hardware_selection.addItems([axis_w_drv, axis_w_enc])

    def populate_diagnostic_coe(self):
        self.logger.info(f"in populate_diagnostic_coe")
        currHardware = self.diagnostic_hardware_selection.currentItem().text()
        dgPrefix = currHardware + ":COE:DG:"

        # Clear previous items
        self.diagnostic_param_filter.clear_items()
        self.dg_list.clear()

        self.dg_list = identify_dg_params(dgPrefix, self.pvDict)

        print(f"dg list size: {len(self.dg_list)}")

        self.ca_dg_list = epics.caget_many(self.dg_list, as_string=True)

        # Add items (filter out None just in case)
        items = [item for item in self.ca_dg_list if item]
        self.diagnostic_param_filter.add_items(items)

        # Enable widget if needed
        self.diagnostic_param_filter.setEnabled(True)

        # Select first item (if exists)
        # if self.diagnostic_param_filter.list_widget.count() > 0:
        #     self.diagnostic_param_filter.list_widget.setCurrentRow(0)

        # # Dynamically add param widgets
        # self.add_param_widgets(self.dg_list, self.expert_encoder_param_list)

    def populate_diagnostic_widget(self):
        """
        Docstring for populate_diagnostic_widget

        :param self: recieves one axis ID
        """
        print(f"in populate_diagnostic_widget!!!!!!!!!!")
        print(f"current Item: {self.diagnostic_param_filter.currentText()}")
        current_text = self.diagnostic_param_filter.currentText()

        if current_text in self.ca_dg_list:
            pv_index = self.ca_dg_list.index(current_text)
            print(f"current pv: {pv_index} ({current_text})")
            # item = self.param_list.item(pv_index)
            thing = self.dg_list[pv_index]
            print(f"item: {thing}")
            name = self.remove_name_rbv(thing)
            param_widget = uic.loadUi(
                str(Path(__file__).parent / "./../ui" / "diagnostics.ui")
            )
            self.configure_diagnostic_widgets(param_widget, name)
            self.diagnostic_params_groupbox.layout().addWidget(param_widget)

    def configure_diagnostic_widgets(self, widget: QWidget, nc_pv):
        """
        Configure all param.ui widgets in self.param_widgets.
        Optionally takes a config_list (list of dicts) to set values for each widget.
        Example config_list: [{"label": "NC1", "lineEdit": "val1", "lineEdit_2": "val2", "label_2": "desc1"}, ...]
        """
        vals = [
            nc_pv + ":Goal_RBV",
            nc_pv + ":Goal",
            nc_pv + ":Acc_RBV",
            nc_pv + ":Desc_RBV",
            nc_pv + ":TLastUp_RBV",
            nc_pv + ":EU_RBV",
        ]
        # vals[0] = nc_pv + ":Goal_RBV"
        # vals[1] = nc_pv + ":Val_RBV"
        # vals[2] = nc_pv + ":Acc_RBV"
        # vals[3] = nc_pv + ":Desc_RBV"
        # vals[4] = nc_pv + ":TLastUp_RBV"
        # vals[5] = nc_pv + ":EU_RBV"
        # print("ca://" + vals[1])
        ca_vals = epics.caget_many(vals, as_string=True)
        # print(ca_vals)
        goal = widget.findChild(PyDMLabel, "goal")
        goal.setText(ca_vals[0])
        value = widget.findChild(PyDMLabel, "value")
        value.setText(ca_vals[1])
        access = widget.findChild(PyDMLabel, "access")
        access.setText(ca_vals[2])
        description = widget.findChild(PyDMLabel, "description")
        description.setText(ca_vals[3])
        tlastup = widget.findChild(PyDMLabel, "tlastup")
        tlastup.setText(ca_vals[4])
        eu = widget.findChild(PyDMLabel, "eu")
        eu.setText(ca_vals[5])

    def remove_name_rbv(self, pv_name):
        suffix = ":Name_RBV"
        if pv_name.endswith(suffix):
            return pv_name[: -len(suffix)]
        return pv_name
