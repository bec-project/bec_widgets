class EntryValidator:
    def __init__(self, devices):
        self.devices = devices

    def validate_signal(self, name: str, entry: str = None) -> str:
        if name not in self.devices:
            raise ValueError(f"Device '{name}' not found in current BEC session")

        device = self.devices[name]
        description = device.describe()

        if entry is None:
            entry = next(iter(device._hints), name) if hasattr(device, "_hints") else name
        if entry not in description:
            raise ValueError(f"Entry '{entry}' not found in device '{name}' signals")

        return entry
