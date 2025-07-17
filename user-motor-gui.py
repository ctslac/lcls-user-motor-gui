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
from parse_pvs import (
    identify_axis,
    identify_coe_drive_params,
    identify_coe_enc_params,
    identify_drive,
    identify_enc,
    identify_nc_params,
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
            self.axis_list = []
            self.enocder_type = []
            self.drive_list = []
            self.enc_list = []
            self.coe_drive_list = []
            self.coe_drive_list = []
            self.coe_enc_list = []
            self.drives_7047 = []
            self.drives_7062 = []
            self.drive_type = []
            self.nc_list_indx = 0
            self.nc_list = []
            self.pvList = []
            self.coe_drive_indx = 0
            self.flag_7047 = True
            self.flag_7062 = True
            self.flag_5102 = True
            self.flag_5042 = True
            self.coe_enc_indx = 0
            self.axis_init_flag = 0

        # finding children
        self.ioc_name = self.ui.findChild(QLineEdit, "input_ioc")
        self.axis_selection = self.ui.findChild(PyDMEnumComboBox, "axis_selection")
        self.nc_param_io = self.ui.findChild(PyDMLineEdit, "nc_param_io")
        self.nc_param_dropdown = self.ui.findChild(
            PyDMEnumComboBox, "nc_param_dropdown"
        )
        self.drive_selection = self.ui.findChild(PyDMEnumComboBox, "drive_selection")
        self.drive_coe_dropdown = self.ui.findChild(
            PyDMEnumComboBox, "drive_coe_dropdown"
        )
        self.drive_coe_io = self.ui.findChild(PyDMLineEdit, "drive_coe_io")
        self.encoder_selection = self.ui.findChild(
            PyDMEnumComboBox, "encoder_selection"
        )
        self.encoder_coe_dropdown = self.ui.findChild(
            PyDMEnumComboBox, "encoder_coe_dropdown"
        )
        self.encoder_coe_io = self.ui.findChild(PyDMLineEdit, "encoder_coe_io")

        # SIGNALS
        # want to update axis every time the ioc is being changed
        self.ioc_name.returnPressed.connect(self.get_pvs_from_input)

        # update NC params if axis selection is changed
        # if not self.axis_init_flag:
        #     print("gui init")
        #     self.axis_selection.currentIndexChanged.connect(self.update_nc_dropdown)
        #     self.axis_init_flag = 1

        if self.axis_selection.currentIndexChanged:
            print("after init")
            for slots in [
                self.update_nc_dropdown,
                self.populate_drives,
                self.populate_encoders,
                self.update_coe_drive_dropdown,
                self.update_enc_coe_dropdown,
            ]:
                self.axis_selection.currentIndexChanged.connect(slots)

        # update CoE drive params if axis selection is changed
        self.drive_selection.currentIndexChanged.connect(self.update_coe_drive_dropdown)
        # update CoE encoder params if axis selection is changed
        self.encoder_selection.currentIndexChanged.connect(self.update_enc_coe_dropdown)

        # update nc param if dropdown is changed
        self.nc_param_dropdown.currentIndexChanged.connect(self.update_nc_io)
        # update coe param if dropdown is changed
        self.drive_coe_dropdown.currentIndexChanged.connect(self.update_drive_coe_io)
        # update enc coe param if dropdown is changed
        self.encoder_coe_dropdown.currentIndexChanged.connect(self.update_enc_coe_io)

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

        # use this to pull db from ioc
        # iocpath, dbpath = grep_ioc(
        #     self.ioc_name.text(), "/cds/group/pcds/pyps/config/mec/iocmanager.cfg", "-p"
        # )
        # print(iocpath, dbpath)
        # iocpath = '/reg/g/pcds/epics-dev/ctsoi/ioc/tst/lcls-plc-hxr-polycap/iocBoot/ioc-lcls-plc-hxr-polycap/lcls_plc_hxr_polycap.db'

        # self.pvList = discover_pvs('', usr_db_path=iocpath)
        self.pvList = self.load_test_list()
        print(self.pvList[1])
        self.populate_axis()
        self.populate_drives()
        self.populate_encoders()

    def populate_axis(self):
        # update enum with axis pulled from .db file
        print("in populate axis")
        self.axis_list = identify_axis(self.pvList)
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

    def populate_drives(self):
        # update enum with drives pulled from .db file
        print("in populate drives")
        drive = self.axis_selection.currentText()
        stripped_axis_rbv = ":Axis:Id_RBV"
        stripped_drive = drive.replace(stripped_axis_rbv, "")
        print(f"PD: drive: {stripped_drive}")
        self.drive_type = identify_drive(stripped_drive, self.pvList)
        self.drive_selection.addItem(self.drive_type)
        self.drive_selection.setCurrentIndex(0)
        self.drive_selection.show()
        if not self.drive_selection.isEnabled():
            self.drive_selection.setEnabled(True)

        # print(self.drive_selection)

    def populate_encoders(self):
        # update enum with drives pulled from .db file
        print("in populate enc")
        encoder = self.axis_selection.currentText()
        stripped_axis_rbv = ":Axis:Id_RBV"
        stripped_encoder = encoder.replace(stripped_axis_rbv, "")
        self.enocder_type = identify_enc(stripped_encoder, self.pvList)
        self.encoder_selection.addItem(self.enocder_type)
        self.encoder_selection.setCurrentIndex(0)
        self.encoder_selection.show()
        if not self.encoder_selection.isEnabled():
            self.encoder_selection.setEnabled(True)
        print(self.encoder_selection)

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
        print(
            f"UNCDD: axis num: {axis_num}, axis ref: {self.axis_selection.currentText()}"
        )
        self.nc_list = identify_nc_params(
            self.axis_selection.currentText(), pv_list=self.pvList
        )
        # print(f"sample nc pvs: {self.nc_list[:10]}")
        self.nc_param_dropdown.addItems(self.nc_list)
        self.nc_param_dropdown.setCurrentIndex(0)
        self.nc_param_dropdown.show()
        if not self.nc_param_dropdown.isEnabled():
            self.nc_param_dropdown.setEnabled(True)

    def update_coe_drive_dropdown(self):
        self.coe_drive_list.clear()
        self.drive_coe_dropdown.clear()

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

    def update_enc_coe_dropdown(self):
        print("in update enc coe dropdown")
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
