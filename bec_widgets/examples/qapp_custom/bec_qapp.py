from qtpy.QtWidgets import QApplication


class BECQApplication(QApplication):
    def setup_bec_features(self):
        self.bec_props = {}
        self.is_bec_app = True
        print("[BECQApplication]: Features initialized.")

    def inject_property(self, name, value):
        self.bec_props[name] = value
        print(f"[BECQApplication]: Injected property '{name}' = {value}")


def upgrade_to_becqapp():
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("No QApplication instance found!")

    if getattr(app, "is_bec_app", False):
        print("[BECQApplication]: Already upgraded.")
        return app

    # Only inject your explicitly defined Python methods
    methods_to_inject = ["setup_bec_features", "inject_property"]

    for method_name in methods_to_inject:
        method = getattr(BECQApplication, method_name)
        setattr(app, method_name, method.__get__(app, QApplication))

    app.setup_bec_features()
    print("[BECQApplication]: QApplication upgraded to BECQApplication.")
    return app
