#!/usr/bin/env python3
"""Start BEC services for benchmark workflows and keep them alive."""

from __future__ import annotations

import argparse
from pathlib import Path

from bec_ipython_client import BECIPythonClient
from bec_lib.redis_connector import RedisConnector
from bec_lib.service_config import ServiceConfig


def _load_demo_config(services_config: Path) -> None:
    bec = BECIPythonClient(ServiceConfig(services_config), RedisConnector, forced=True)
    bec.start()
    try:
        bec.config.load_demo_config()
    finally:
        bec.shutdown()
        bec._client._reset_singleton()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--services-config", required=True, type=Path)
    args = parser.parse_args()

    _load_demo_config(args.services_config)


if __name__ == "__main__":
    main()
