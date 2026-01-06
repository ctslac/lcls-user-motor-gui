import sys
import time
from enum import Enum
from os import path

import epics


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
