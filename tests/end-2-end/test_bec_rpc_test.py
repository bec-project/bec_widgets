def test_rpc_gui_obj(connected_gui_and_bec_with_scope_session):

    gui = connected_gui_and_bec_with_scope_session
    for key in gui.available_widgets.__dict__:
        gui.new().new().new(key)
