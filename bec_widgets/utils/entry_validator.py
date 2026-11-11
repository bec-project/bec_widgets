class EntryValidator:
    def __init__(self, devices):
        self.devices = devices

    def validate_signal(self, device: str, signal: str | None = None) -> str:
        """
        Validate a signal for a given device. If the signal is not provided, the first signal will be used from the device hints.

        Args:
            device(str): Device name
            signal(str): Signal name

        Returns:
            str: Signal name
        """
        if device not in self.devices:
            raise ValueError(f"Device '{device}' not found in current BEC session")

        device_obj = self.devices[device]

        # Build list of available signal entries from device._info['signals']
        signals_dict = getattr(device_obj, "_info", {}).get("signals", {})
        available_entries = [
            sig.get("obj_name") for sig in signals_dict.values() if sig.get("obj_name")
        ]

        # If no signals are found, means device is a signal, use the device name as the entry
        if not available_entries:
            available_entries = [device]

        # edge case for if name is passed instead of full_name, should not happen
        if signal in signals_dict:
            signal = signals_dict[signal].get("obj_name", signal)

        if signal is None or signal == "":
            signal = (
                next(iter(device_obj._hints), device) if hasattr(device_obj, "_hints") else device
            )
        if signal not in available_entries:
            raise ValueError(
                f"Entry '{signal}' not found in device '{device}' signals. "
                f"Available signals: '{available_entries}'"
            )

        return signal

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
