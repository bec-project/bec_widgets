from bec_lib.core import BECMessage, MessageEndpoints, RedisConnector
import time

connector = RedisConnector("localhost:6379")
producer = connector.producer()
metadata = {}

scanID = "ScanID1"

metadata.update(
    {
        "scanID": scanID,
        "async_update": "append",
    }
)
for ii in range(20):
    data = {"mca1": [10, 2, 3, 4, 5, 6, 7, 8, 9, 10], "mca2": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]}
    msg = BECMessage.DeviceMessage(
        signals=data,
        metadata=metadata,
    ).dumps()
    producer.xadd(
        topic=MessageEndpoints.device_async_readback(scanID=scanID, device="mca"),
        msg={"data": msg},
        expire=1800,
    )
    print(f"Sent {ii}")
    time.sleep(0.5)
