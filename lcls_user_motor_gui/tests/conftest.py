import json

import pytest


@pytest.fixture(scope="function")
def linking_axis():
    filepath1 = "./unit_test_data.json"
    # filepath2 = "./expert_unit_test.json"
    try:
        # with open(f"{filepath}", "r") as f:
        #     for pvs in f:
        #         pv_list.append(pvs)

        with open(filepath1, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Failed to read {filepath1}: {e}")
    # for pvs in pv_list:
    #     print(pvs)
    # pv_list = json.loads(pv_list)
    # print(f"type: {type(self.pvDict)}")
