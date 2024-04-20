"""
Module to handle the vscode server
"""

import subprocess


class VSCodeServer:
    """
    Class to handle the vscode server
    """

    _instance = None

    def __init__(self, port=7000, token="bec"):
        self.started = False
        self._server = None
        self.port = port
        self.token = token

    def __new__(cls, *args, forced=False, **kwargs):
        if cls._instance is None or forced:
            cls._instance = super(VSCodeServer, cls).__new__(cls)
        return cls._instance

    def start_server(self):
        """
        Start the vscode server in a subprocess
        """
        if self.started:
            return
        self._server = subprocess.Popen(
            f"code serve-web --port {self.port} --connection-token={self.token} --accept-server-license-terms",
            shell=True,
        )
        self.started = True

    def wait(self):
        """
        Wait for the server to finish
        """
        if not self.started:
            return
        if not self._server:
            return
        self._server.wait()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start the vscode server")
    parser.add_argument("--port", type=int, default=7000, help="Port to start the server")
    parser.add_argument("--token", type=str, default="bec", help="Token to start the server")
    args = parser.parse_args()

    server = VSCodeServer(port=args.port, token=args.token)
    server.start_server()
    server.wait()
