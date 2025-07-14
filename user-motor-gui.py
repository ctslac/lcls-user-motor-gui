import sys
import time
from enum import Enum
from os import path

from epics import PV, caget, cainfo, caput
from pydm import Display
from pydm.widgets.enum_combo_box import PyDMEnumComboBox
from pydm.widgets.line_edit import (
    PyDMLineEdit,
)
from qtpy import QtCore
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from discover_pvs import discover_pvs
from parse_pvs import identify_axis, identify_nc_params


class MyDisplay(Display):
    def __init__(self, parent=None, args=None, macros=None):
        print("In init")
        super().__init__(parent=parent, args=args, macros=macros)

        # initialize vars
        init = True
        if init:
            init = False
            self.axis_list = []
            self.nc_list_indx = 0
            self.nc_list = []
            self.pvList = []

        # finding children
        self.ioc_name = self.ui.findChild(QLineEdit, "input_ioc")
        self.axis_selection = self.ui.findChild(PyDMEnumComboBox, "axis_selection")
        self.nc_param_dropdown = self.ui.findChild(
            PyDMEnumComboBox, "nc_param_dropdown"
        )
        self.nc_param_io = self.ui.findChild(PyDMLineEdit, "nc_param_io")

        # SIGNALS
        # want to update axis every time the ioc is being changed
        self.ioc_name.returnPressed.connect(self.get_pvs_from_input)

        # update NC params if axis selection is changed
        self.axis_selection.currentIndexChanged.connect(self.update_nc_dropdown)

        # update nc param index if its changed
        self.nc_param_dropdown.currentIndexChanged.connect(self.update_nc_index)

    def ui_filename(self):
        return "user-motor-gui.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def load_test_list(self):
        filepath = "./test_output.txt"
        pv_list = []
        try:
            with open(f"{filepath}", "r") as f:
                for pvs in f:
                    pv_list.append(pvs)
        except Exception as e:
            print(f"Failed to read {filepath}: {e}")

        return pv_list

    def get_pvs_from_input(self):
        print("in get pvs from input")
        print(self.ioc_name.text())
        # iocpath, dbpath = grep_ioc(
        #     self.ioc_name.text(), "/cds/group/pcds/pyps/config/mec/iocmanager.cfg", "-p"
        # )
        # print(iocpath, dbpath)
        # iocpath = '/reg/g/pcds/epics-dev/ctsoi/ioc/tst/lcls-plc-hxr-polycap/iocBoot/ioc-lcls-plc-hxr-polycap/lcls_plc_hxr_polycap.db'

        # self.pvList = discover_pvs('', usr_db_path=iocpath)
        self.pvList = self.load_test_list()
        print(self.pvList[1])
        self.populate_axis(self.pvList)

    def populate_axis(self, pvList):
        # update enum with axis pulled from .db file
        print("in populate axis")
        self.axis_list = identify_axis(pvList)
        print(f"axis_list: {self.axis_list}")

        # if not hasattr(self.axis_selection, self.pvList):
        #     raise AttributeError("Provided widget is not a PyDMEnumComboBox or lacks enum vals")

        self.axis_selection.addItems(self.axis_list)
        self.axis_selection.setCurrentIndex(0)
        # self.axis_selection.activate()
        self.axis_selection.show()
        if not self.axis_selection.isEnabled():
            self.axis_selection.setEnabled(True)
        print(self.axis_selection)

    def update_nc_dropdown(self):
        """
        if axis selection current index is changed grab index and axis reference to populate NC dropdown
        get currently selected axis
        identify all NC params based on selected axis
        clear previous list
        add items
        """
        print("in update_nc_dropdown")
        # clear list and enum
        self.nc_list.clear()
        self.nc_param_dropdown.clear()
        axis_num = self.axis_selection.currentIndex()
        print(f"axis num: {axis_num}, axis ref: {self.axis_list[axis_num]}")
        self.nc_list = identify_nc_params(self.axis_list[axis_num], pv_list=self.pvList)
        print(f"sample nc pvs: {self.nc_list[:10]}")
        self.nc_param_dropdown.addItems(self.nc_list)
        self.nc_param_dropdown.setCurrentIndex(0)
        self.nc_param_dropdown.show()
        if not self.nc_param_dropdown.isEnabled():
            self.nc_param_dropdown.setEnabled(True)

        # if the nc param current index is changed update nc io
        # self.nc_param_dropdown.currentIndexChanged().connect(self.update_nc_io(self.nc_param_dropdown.currentIndex()))

    def update_nc_io(self, index):
        self.nc_param_io.set_display(self.nc_list[index])
        self.nc_param_io.show()

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
