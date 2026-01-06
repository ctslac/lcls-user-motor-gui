import epics
import numpy as np

data = ["", "", ""]
data[0] = "TST:UM:01:EL5042:Id_RBV"
data[1] = "TST:UM:02:EL7062:COE:DG:SuppVUp:Goal"
data[2] = "TST:UM:02:EL5102:WCIB_RBV"


# if np.size(data) > 1:
#     zero_mask = data==0
#     zero_idx = np.where(zero_mask)
#     first_zero=zero_idx[0][0]
#     good_data = data[:first_zero]
#     data_bytes= good_data.tobytes()
#     good_string=data_bytes.decode("ascii")
# else:
#     good_string = data
# data_bytes= good_data.tobytes()
# good_string=data_bytes.decode("ascii")


# zero_mask = data==0
# zero_idx = np.where(zero_mask)
# first_zero=zero_idx[0][0]
# good_data = []
# if not zero_mask:
#     good_data = data
#     data_bytes= good_data.tobytes()
#     good_string=data_bytes.decode("ascii")
# else:
#     good_data = data[:first_zero]
#     data_bytes= good_data.tobytes()
#     good_string=data_bytes.decode("ascii")
