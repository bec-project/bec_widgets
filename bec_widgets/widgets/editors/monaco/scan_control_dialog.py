"""
Scan Control Dialog for Monaco Editor

This module provides a dialog wrapper around the ScanControl widget,
allowing users to configure and generate scan code that can be inserted
into the Monaco editor.
"""

from bec_lib.device import Device
from bec_lib.logger import bec_logger
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QPushButton, QVBoxLayout

from bec_widgets.widgets.control.scan_control import ScanControl

logger = bec_logger.logger


class ScanControlDialog(QDialog):
    """
    Dialog window containing the ScanControl widget for generating scan code.

    This dialog allows users to configure scan parameters and generates
    Python code that can be inserted into the Monaco editor.
    """

    def __init__(self, parent=None, client=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Scan")

        # Store the client for passing to ScanControl
        self.client = client
        self._scan_code = ""

        self._setup_ui()

    def sizeHint(self) -> QSize:
        return QSize(600, 800)

    def _setup_ui(self):
        """Setup the dialog UI with ScanControl widget and buttons."""
        layout = QVBoxLayout(self)

        # Create the scan control widget
        self.scan_control = ScanControl(parent=self, client=self.client)
        self.scan_control.show_scan_control_buttons(False)
        layout.addWidget(self.scan_control)

        # Create dialog buttons
        button_box = QDialogButtonBox(Qt.Orientation.Horizontal, self)

        # Create custom buttons with appropriate text
        insert_button = QPushButton("Insert")
        cancel_button = QPushButton("Cancel")

        button_box.addButton(insert_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addWidget(button_box)

        # Connect button signals
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _generate_scan_code(self):
        """Generate Python code for the configured scan."""
        try:
            # Get scan parameters from the scan control widget
            args, kwargs = self.scan_control.get_scan_parameters()
            scan_name = self.scan_control.current_scan

            if not scan_name:
                self._scan_code = ""
                return

            # Process arguments and add device prefix where needed
            processed_args = self._process_arguments_for_code_generation(args)
            processed_kwargs = self._process_kwargs_for_code_generation(kwargs)

            # Generate the Python code string
            code_parts = []

            # Process arguments and keyword arguments
            all_args = []

            # Add positional arguments
            if processed_args:
                all_args.extend(processed_args)

            # Add keyword arguments (excluding metadata)
            if processed_kwargs:
                kwargs_strs = [f"{k}={v}" for k, v in processed_kwargs.items() if k != "metadata"]
                all_args.extend(kwargs_strs)

            # Join all arguments and create the scan call
            args_str = ", ".join(all_args)
            if args_str:
                code_parts.append(f"scans.{scan_name}({args_str})")
            else:
                code_parts.append(f"scans.{scan_name}()")

            self._scan_code = "\n".join(code_parts)

        except Exception as e:
            logger.error(f"Error generating scan code: {e}")
            self._scan_code = f"# Error generating scan code: {e}\n"

    def _process_arguments_for_code_generation(self, args):
        """Process arguments to add device prefixes and proper formatting."""
        return [self._format_value_for_code(arg) for arg in args]

    def _process_kwargs_for_code_generation(self, kwargs):
        """Process keyword arguments to add device prefixes and proper formatting."""
        return {key: self._format_value_for_code(value) for key, value in kwargs.items()}

    def _format_value_for_code(self, value):
        """Format a single value for code generation."""
        if isinstance(value, Device):
            return f"dev.{value.name}"
        return repr(value)

    def get_scan_code(self) -> str:
        """
        Get the generated scan code.

        Returns:
            str: The Python code for the configured scan.
        """
        return self._scan_code

    def accept(self):
        """Override accept to generate code before closing."""
        self._generate_scan_code()
        super().accept()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = ScanControlDialog()
    dialog.show()
    sys.exit(app.exec_())
