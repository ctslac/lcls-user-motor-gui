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
    # for index, pv in enumerate(axis_list):
    #     enumerated_list.append(str(index) + " " + pv)
    # print(enumerated_list)

    return nc_list
