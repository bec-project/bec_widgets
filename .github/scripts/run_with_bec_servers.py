#!/usr/bin/env python3
"""Run a command with BEC e2e services available."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import bec_lib
from bec_ipython_client import BECIPythonClient
from bec_lib.redis_connector import RedisConnector
from bec_lib.service_config import ServiceConfig, ServiceConfigModel
from redis import Redis


def _wait_for_redis(host: str, port: int) -> None:
    client = Redis(host=host, port=port)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if client.ping():
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"Redis did not start on {host}:{port}")


def _start_redis(files_path: Path, host: str, port: int) -> subprocess.Popen:
    redis_server = shutil.which("redis-server")
    if redis_server is None:
        raise RuntimeError("redis-server executable not found")

    return subprocess.Popen(
        [
            redis_server,
            "--bind",
            host,
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            str(files_path),
        ]
    )


def _write_configs(files_path: Path, host: str, port: int) -> Path:
    test_config = files_path / "test_config.yaml"
    services_config = files_path / "services_config.yaml"

    bec_lib_path = Path(bec_lib.__file__).resolve().parent
    shutil.copyfile(bec_lib_path / "tests" / "test_config.yaml", test_config)

    service_config = ServiceConfigModel(
        redis={"host": host, "port": port}, file_writer={"base_path": str(files_path)}
    )
    services_config.write_text(service_config.model_dump_json(indent=4), encoding="utf-8")
    return services_config


def _load_demo_config(services_config: Path) -> None:
    bec = BECIPythonClient(ServiceConfig(services_config), RedisConnector, forced=True)
    bec.start()
    try:
        bec.config.load_demo_config()
    finally:
        bec.shutdown()
        bec._client._reset_singleton()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        raise ValueError("No command provided")

    host = "127.0.0.1"
    port = 6379

    with tempfile.TemporaryDirectory(prefix="bec-benchmark-") as tmp:
        files_path = Path(tmp)
        services_config = _write_configs(files_path, host, port)
        redis_process = _start_redis(files_path, host, port)
        processes = None
        service_handler = None
        try:
            _wait_for_redis(host, port)

            from bec_server.bec_server_utils.service_handler import ServiceHandler

            service_handler = ServiceHandler(
                bec_path=files_path, config_path=services_config, interface="subprocess"
            )
            processes = service_handler.start()
            _load_demo_config(services_config)

            env = os.environ.copy()
            return subprocess.run(args.command, env=env, check=False).returncode
        finally:
            if service_handler is not None and processes is not None:
                service_handler.stop(processes)
            redis_process.terminate()
            try:
                redis_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                redis_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
