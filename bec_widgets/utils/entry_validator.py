class EntryValidator:
    def __init__(self, devices):
        self.devices = devices

    def validate_signal(self, name: str, entry: str = None) -> str:
        """
        Validate a signal entry for a given device. If the entry is not provided, the first signal entry will be used from the device hints.

        Args:
            name(str): Device name
            entry(str): Signal entry

        Returns:
            str: Signal entry
        """
        if name not in self.devices:
            raise ValueError(f"Device '{name}' not found in current BEC session")

        device = self.devices[name]
        description = device.describe()

        if entry is None or entry == "":
            entry = next(iter(device._hints), name) if hasattr(device, "_hints") else name
        if entry not in description:
            raise ValueError(
                f"Entry '{entry}' not found in device '{name}' signals. Available signals: {description.keys()}"
            )

        return entry

    def validate_monitor(self, monitor: str) -> str:
        """
        Validate a monitor entry for a given device.

        Args:
            monitor(str): Monitor entry

        Returns:
            str: Monitor entry
        """
        if monitor not in self.devices:
            raise ValueError(f"Device '{monitor}' not found in current BEC session")

        return monitor
