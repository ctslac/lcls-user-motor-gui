import glob
import os
import re
import sys


def identify_axis(pv_list):
    """
    Given a list of PVs, find all the unique axis then output a seperate list with only axis that is enumerated


    Inputs:
    list: list of pvs

    Outputs:
    list: enumerated list of axis
        List of all axis found
    """
    print("in identify_axis")
    axis_list = []
    enumerated_list = []
    for pv in pv_list:
        if re.search(r"Axis:Id_RBV", pv):
            print("Found 'Axis:Id_RBV' in the string.")
            axis_list.append(pv.strip())
        else:
            # print("Not an axis")
            continue
    # for index, pv in enumerate(axis_list):
    #     enumerated_list.append(str(index) + " " + pv)
    # print(enumerated_list)
    return axis_list


def identify_drive(pv_list):
    """
    Given a list of PVs, find all the unique axis then output a seperate list with only axis that is enumerated


    Inputs:
    list: list of pvs

    Outputs:
    list: enumerated list of axis
        List of all axis found
    """
    print("in identify_axis")
    drive_list = []
    el7047s = []
    el7062s = []
    is7047 = False
    is7062 = False
    for pv in pv_list:
        if re.search(r"EL7047", pv):
            el7047s.append(pv.strip())
        elif re.search(r"EL7062", pv):
            el7062s.append(pv.strip())
        # else:
        # print("Can't find any drive modules")

    if len(el7062s) > 0:
        is7062 = True
    else:
        is7062 = False

    if len(el7047s) > 0:
        is7047 = True
    else:
        is7047 = False

    return is7062, is7047


def identify_enc(pv_list):
    """
    Given a list of PVs, find all the unique axis then output a seperate list with only axis that is enumerated


    Inputs:
    list: list of pvs

    Outputs:
    list: enumerated list of axis
        List of all axis found
    """

    print("in identify_enc")
    drive_list = []
    el5102s = []
    el5042s = []
    is5102 = False
    is5042 = False
    for pv in pv_list:
        if re.search(r"EL5102", pv):
            el5102s.append(pv.strip())
        elif re.search(r"EL5042", pv):
            el5042s.append(pv.strip())
        # else:
        #     print("Can't find any drive modules")

    if len(el5102s) > 0:
        is5102 = True
    else:
        is5102 = False

    if len(el5042s) > 0:
        is5042 = True
    else:
        is5042 = False

    return is5102, is5042


def identify_nc_params(prefix, pv_list):
    """
    Given a list of PVs, find all of the NC params for a given axis prefix
    """
    print("in identify_nc_params")
    print(f"prefix before strip: {prefix}")
    stripped_axis_rbv = ":Axis:Id_RBV"
    prefix = prefix.strip()
    cleaned_prefix = prefix.replace(stripped_axis_rbv, "")
    print(f"after axis prefix: {cleaned_prefix}")
    nc_list = []
    nc_param = cleaned_prefix + ":NC:"
    print(f"nc_param: {nc_param}")
    # c_nc_p = 'r'+'"'+nc_param+'"'
    # print(f"nc p: {c_nc_p}")
    # print(f"nc_param type: {type(c_nc_p)}, pv_list type: {type(pv_list)}")
    for pv in pv_list:
        # print(f"nc p: {c_nc_p}, pv: {pv}")
        if re.search(nc_param, pv):
            # print(f"Found nc_param in the list, param: {pv}")
            nc_list.append(pv.strip())
            # print("Not an axis")
            # print("didnt find a match")

    return nc_list


def identify_coe_drive_params(axis_id, drive_types, pv_list):
    """
    Given a list of PVs, find all of the drive params for a given axis prefix
    """
    print("in identify_coe_drive_params")
    # print(f"search: {axis_id+drive_type}")
    # 7047 = 0, 7062 = 1
    stripped_axis_rbv = "Axis:Id_RBV"
    axis_id = axis_id.replace(stripped_axis_rbv, "")
    axis_prefix = axis_id + drive_types

    print(f"axis prefix: {axis_prefix}, drive type: {drive_types}")
    stripped_axis_rbv = "Axis:Id_RBV"

    coe_list = []
    for pv in pv_list:
        # print(f"nc p: {c_nc_p}, pv: {pv}")
        if re.search(axis_prefix, pv):
            # print("Found nc_param in the list, param: {}")
            coe_list.append(pv.strip())

    return coe_list


def identify_coe_enc_params(axis_id, enc_types, pv_list):
    """
    Given a list of PVs, find all of the drive params for a given axis prefix
    """
    print("in identify_coe_drive_params")
    # print(f"search: {axis_id+drive_type}")
    # 7047 = 0, 7062 = 1
    stripped_axis_rbv = "Axis:Id_RBV"
    axis_id = axis_id.replace(stripped_axis_rbv, "")
    axis_prefix = axis_id + enc_types

    print(f"axis prefix: {axis_prefix}, drive type: {enc_types}")
    stripped_axis_rbv = "Axis:Id_RBV"

    coe_list = []
    for pv in pv_list:
        # print(f"nc p: {c_nc_p}, pv: {pv}")
        if re.search(axis_prefix, pv):
            # print("Found nc_param in the list, param: {}")
            coe_list.append(pv.strip())

    return coe_list
