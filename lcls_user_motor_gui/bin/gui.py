"""
`lcls-user-motor-gui gui` launches the graphical user interface.
"""

import argparse
import sys
from qtpy.QtWidgets import QApplication

from lcls_user_motor_gui.user_motor_gui import MainWindow

DESCRIPTION = __doc__


def build_arg_parser(argparser=None):
    if argparser is None:
        argparser = argparse.ArgumentParser()

    argparser.description = DESCRIPTION
    argparser.formatter_class = argparse.RawTextHelpFormatter

    # Add any GUI-specific args here if needed
    # argparser.add_argument("--config", type=str, help="Configuration file.")

    return argparser


def main(**kwargs):
    app = QApplication(sys.argv)
    gui = MainWindow()
    gui.show()
    sys.exit(app.exec_())