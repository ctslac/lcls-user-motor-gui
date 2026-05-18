how to run this gui:

with conda

$ source pcds_conda

$ conda create -n lcls-user-motor-gui python=3.12 pip

$ conda activate lcls-user-motor-gui

$ pip install -e .

$ lcls_user_motor_gui gui --ioc-name [IOC_NAME]

with uv

$ pathmunge /cds/group/pcds/pyps/demo/bundles/dev/linux-x86_64

$ uv run lcls-user-motor-gui -l INFO gui --ioc-name ioc-lcls-plc-template-user-motors
