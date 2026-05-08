how to run this gui:

$ source pcds_conda

$ conda create -n lcls-user-motor-gui python=3.12 pip

$ conda activate lcls-user-motor-gui

$ pip install -e .

$ lcls_user_motor_gui gui --ioc-name [IOC_NAME]
