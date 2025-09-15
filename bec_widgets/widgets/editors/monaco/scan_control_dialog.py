"""
Scan Control Dialog for Monaco Editor

This module provides a dialog wrapper around the ScanControl widget,
allowing users to configure and generate scan code that can be inserted
into the Monaco editor.
"""

from bec_lib.device import Device
from PySide6.QtCore import QSize
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QPushButton, QVBoxLayout

from bec_widgets.widgets.control.scan_control import ScanControl


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

            # Add scan function call
            if processed_args and processed_kwargs:
                # Format arguments
                args_str = ", ".join(processed_args)
                # Format keyword arguments
                kwargs_str = ", ".join(
                    f"{k}={v}" for k, v in processed_kwargs.items() if k != "metadata"
                )

                if args_str and kwargs_str:
                    code_parts.append(f"scans.{scan_name}({args_str}, {kwargs_str})")
                elif args_str:
                    code_parts.append(f"scans.{scan_name}({args_str})")
                elif kwargs_str:
                    code_parts.append(f"scans.{scan_name}({kwargs_str})")
                else:
                    code_parts.append(f"scans.{scan_name}()")
            elif processed_args:
                args_str = ", ".join(processed_args)
                code_parts.append(f"scans.{scan_name}({args_str})")
            elif processed_kwargs:
                kwargs_str = ", ".join(
                    f"{k}={v}" for k, v in processed_kwargs.items() if k != "metadata"
                )
                if kwargs_str:
                    code_parts.append(f"scans.{scan_name}({kwargs_str})")
                else:
                    code_parts.append(f"scans.{scan_name}()")
            else:
                code_parts.append(f"scans.{scan_name}()")

            self._scan_code = "\n".join(code_parts)

        except Exception as e:
            print(f"Error generating scan code: {e}")
            self._scan_code = f"# Error generating scan code: {e}\n"

    def _process_arguments_for_code_generation(self, args):
        """Process arguments to add device prefixes and proper formatting."""
        processed = []

        for arg in args:
            if isinstance(arg, Device):
                processed.append(f"dev.{arg.name}")
            else:
                # Regular argument - format appropriately
                processed.append(repr(arg))

        return processed

    def _process_kwargs_for_code_generation(self, kwargs):
        """Process keyword arguments to add device prefixes and proper formatting."""
        processed = {}

        for key, value in kwargs.items():

            if isinstance(value, Device):
                processed[key] = f"dev.{value.name}"
            else:
                processed[key] = repr(value)

        return processed

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
