my_motor_gui/
|-- main.py
|-- my_display.py
|-- widgets/
|    |-- filtered_list_widget.py
|    |-- logger_handler.py
|-- dialogs/
|    |-- mapping_window.py
|    |-- stage_settings.py
|-- logic/
|    |-- pv_discovery.py
|    |-- data_processing.py
|    |-- pvdict_tools.py
|-- ui/
|    |-- user-motor-gui.ui
|    |-- stage-config.ui
|    |-- mapping-window.ui
|    |-- param.ui


Method	Called?	Notes
load_axis_di	YES	Called in identify_WCIB
load_axis_di_ui	YES	Called in identify_WCIB
load_drives	YES	Called in identify_WCIB
load_di	YES	Called in identify_WCIB
load_di_ui	YES	Called in identify_WCIB
load_di_channel	YES	Connected to digital_input_hardware.currentRowChanged
load_di_channel_ui	YES	Connected to ui_digital_input_hardware.currentRowChanged
select_di_channel	YES	Slot connected, called in publish_axis_di
select_di_channel_ui	YES	Slot connected, called in publish_axis_di_ui
detect_linked_drv	YES	Called in select_axis
detect_linked_drv_ui	YES	Called in select_axis_ui
detect_linked_enc	YES	Called in select_axis
detect_linked_enc_ui	YES	Called in select_axis_ui
see_stage	YES	Connected to see_mapping.clicked
open_stage_settings	YES	Connected to stage_settings.clicked
expert_update_nc	YES	Connected to expert_axis.currentIndexChanged
expert_update_drive	YES	Connected to expert_axis.currentIndexChanged
expert_update_encoder	YES	Connected to expert_axis.currentIndexChanged
expert_update_nc_io	NOT USED	Never connected or called (unless somewhere else)
update_drive_coe_io	NOT USED	Never connected or called (unless somewhere else)
update_enc_coe_io	NOT USED	Never connected or called (unless somewhere else)
expert_update_nc_index	NOT USED	Never connected or called (unless somewhere else)
load_test_list	YES	Connected to load_ioc.clicked
populate_options	YES	Connected to load_ioc.clicked
configure_param_widgets	YES	Called in add_param_widgets
configure_diagnostic_widgets	YES	Called in populate_diagnostic_widget
add_param_widgets	YES	Called in expert_update_nc, expert_update_drive, expert_update_encoder
highlight_nc_param	YES	Connected to expert_nc_filter.currentIndexChanged
highlight_coe_drive_param	YES	Connected to expert_drive_filter.currentIndexChanged
highlight_coe_encoder_param	YES	Connected to expert_encoder_filter.currentIndexChanged
publish_axis	YES	Called in load_axis
publish_axis_ui	YES	Called in load_axis
publish_axis_expert	YES	Called in load_axis
publish_axis_diagnostic	YES	Called in load_axis
populate_diagnostic_hardware	YES	Connected to diagnostic_axis_selection.currentIndexChanged
populate_diagnostic_coe	YES	Connected to diagnostic_hardware_selection.currentRowChanged
populate_diagnostic_widget	YES	Connected to diagnostic_param_filter.currentIndexChanged
clear_stage	YES	Used in staged mapping logic
load_di_slot	NOT USED	Not referenced, not connected, only commented
load_di_c_ui	NOT USED	Not referenced, not connected
load_drives_ui	NOT USED	Not referenced, not connected
load_encoders_ui	NOT USED	Not referenced, not connected
check_duplicate_di_flag	YES	Connected to duplicate_di_cb.stateChanged
check_duplicate_drv_flag	YES	Connected to duplicate_drv_cb.stateChanged
check_duplicate_enc_flag	YES	Connected to duplicate_enc_cb.stateChanged
check_duplicate_di	YES	Called in save_stage
check_duplicate_drv	YES	Called in save_stage
check_duplicate_enc	YES	Called in save_stage
