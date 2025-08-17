import glob
import json
import os
import re
import sys

# from epics import PV, fake_caget


def fake_caget(pv_dict, pv):
    # with open('./unit_test_data.json', 'r') as file:
    #     data = json.load(file)
    value = pv_dict.get(pv)
    print(f"value: {value}")
    return value


def identify_axis(pv_dict):
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
    """
    # List implemenation

    # for pv in pv_list:
    #     if re.search(r"Axis:Id_RBV", pv):
    #         print("Found 'Axis:Id_RBV' in the string.")
    #         axis_list.append(pv.strip())
    #     else:
    #         # print("Not an axis")
    #         continue
    """
    # dict implementation
    for key in pv_dict.keys():
        if re.search(r"Axis:Id_RBV", key):
            val = fake_caget(pv_dict, key)
            axis_list.append(val)
    return axis_list


def identify_inputs(pv_list, axis_name):
    """
    Given a list of PVs, find all the unique axis then output a seperate list with only axis that is enumerated

    NEED TO FIX THIS LOGIC

    Inputs:
    list: list of pvs

    Outputs:
    list: enumerated list of axis
        List of all axis found
    """
    print("in identify di")
    print(f"axis: {axis_name}")
    di_list = []
    delimiter = ":Axis:Id_RBV"
    cleaned_axis = axis_name.replace(delimiter, "")
    print(f"cleaned axis: {cleaned_axis}")
    for pv in pv_list:
        if re.search(rf"{axis_name}:NUMDI", pv):
            # print("Found Digital Input in the string.")
            di_list.append(pv.strip())
        else:
            # print("Not an axis")
            continue
    # for index, pv in enumerate(axis_list):
    #     enumerated_list.append(str(index) + " " + pv)
    # print(enumerated_list)
    return di_list


def identify_drive(pv_list, axis_name):
    """
    Given a list of axis id and a pv list, identify if the axis type


    Inputs:
    list: list of pvs

    Outputs:
    list: enumerated list of axis
        List of all axis found
    """
    print("in identify_drive")
    print(f"axis: {axis_name}")
    drive_type = []

    for pv in pv_list:
        if re.search(rf"{axis_name}:(EL7047|EL7062):WCIB_RBV", pv):
            drive_type.append(pv.strip())
        # else:
        # print("Can't find any drive modules")

    return drive_type


def identify_enc(pv_list, axis_name):
    """
    Given a list of PVs, find all the unique axis then output a seperate list with only axis that is enumerated


    Inputs:
    list: list of pvs

    Outputs:
    list: enumerated list of axis
        List of all axis found
    """

    print("in identify_enc")
    print(f"axis: {axis_name}")
    encoder_type = []

    for pv in pv_list:
        if re.search(rf"{axis_name}:(EL5102|EL5042):WCIB_RBV", pv):
            encoder_type.append(pv.strip())
        # else:
        # print("Can't find any drive modules")

    return encoder_type


def identify_nc_params(axis, dict):
    """
    Given a list of PVs, find all of the NC params for a given axis prefix
    """
    print("in identify_nc_params")
    print(f"axis: {axis}")
    # stripped_axis_rbv = ":Axis:Id_RBV"
    # prefix = prefix.strip()
    # cleaned_prefix = prefix.replace(stripped_axis_rbv, "")
    # print(f"after axis prefix: {cleaned_prefix}")
    nc_list = []
    nc_param = axis + ":NC:"
    print(f"nc_param: {nc_param}")
    c_nc_p = "r" + '"' + nc_param + '"'
    print(f"nc p: {c_nc_p}")
    print(f"nc_param type: {type(c_nc_p)}, pv_list type: {type(dict)}")
    for pv in dict:
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
    print(f"IDP: axis id: {axis_id}")
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
    Inputs:
    """
    print("in identify_coe_drive_params")
    # print(f"search: {axis_id+drive_type}")
    # 7047 = 0, 7062 = 1
    stripped_axis_rbv = "Axis:Id_RBV"
    print(f"IDP: axis id: {axis_id}")
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


def strip_key(key):
    key = str(key).replace("'", "")
    key = key.replace("[", "")
    key = key.replace("]", "")
    delimiter = ":Axis:Id_RBV"
    stripped_key = key.replace(delimiter, "")
    return stripped_key


def what_can_i_be(pv):
    """
    This assumes we can fake_caget the selected DI ID PV, a string,
    and use that to populate the available components

    """
    print("in what can i be")
    print(f"I am: {pv}")
    # comp_type = fake_caget(pv)
    # if p is "DI":
    #     pass
    # print(comp_type)
