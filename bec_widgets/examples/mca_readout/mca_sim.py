import time

from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
from bec_lib.redis_connector import RedisConnector

connector = RedisConnector("localhost:6379")
metadata = {}

scan_id = "ScanID1"

metadata.update(
    {"scan_id": scan_id, "async_update": "append"}  # this will be different for each scan
)
for ii in range(20):
    data = {"mca1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "mca2": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]}
    msg = messages.DeviceMessage(signals=data, metadata=metadata).dumps()

    connector.xadd(
        topic=MessageEndpoints.device_async_readback(
            scan_id=scan_id, device="mca"
        ),  # scan_id will be different for each scan
        msg={"data": msg},  # TODO should be msg_dict
        expire=1800,
    )

    print(f"Sent {ii}")
    time.sleep(0.5)
