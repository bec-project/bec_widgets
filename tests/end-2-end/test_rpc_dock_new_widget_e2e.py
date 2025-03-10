def test_gui_rpc_registry(qtbot, connected_client_gui_obj):
    gui = connected_client_gui_obj
    dock_name = "dock"
    global name
    name = None

    def check_dock_created():
        dock_dict = gui._registry_state.get(gui.bec._gui_id, {}).get("config", {}).get("docks", {})
        return len(dock_dict) > 0

    def check_dock_removed():
        dock_dict = gui._registry_state.get(gui.bec._gui_id, {}).get("config", {}).get("docks", {})
        return len(dock_dict) == 0

    def check_widget_created():
        widgets_dict = (
            (gui._registry_state.get(gui.bec._gui_id, {}).get("config", {}).get("docks", {}))
            .get(dock_name, {})
            .get("widgets", {})
        )
        widget_config = widgets_dict.get(name, {})
        return len(widget_config) > 0

    def check_widget_remove():
        widgets_dict = (
            (gui._registry_state.get(gui.bec._gui_id, {}).get("config", {}).get("docks", {}))
            .get(dock_name, {})
            .get("widgets", {})
        )
        return name not in widgets_dict

    for widget_name, _ in gui.available_widgets.__dict__.items():
        name = widget_name
        gui.bec.new(dock_name, widget=widget_name, widget_name=widget_name)

        qtbot.wait_until(check_dock_created)
        qtbot.wait_until(check_widget_created)

        assert hasattr(gui.bec.elements, f"{widget_name}")
        assert hasattr(gui.bec, f"{dock_name}")
        gui.bec.delete(dock_name)

        qtbot.wait_until(check_dock_removed)

        assert not hasattr(gui.bec.elements, f"{widget_name}")
        assert not hasattr(gui.bec, f"{dock_name}")
