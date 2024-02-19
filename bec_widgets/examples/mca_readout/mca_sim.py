from bec_lib import messages, MessageEndpoints, RedisConnector
import time

connector = RedisConnector("localhost:6379")
producer = connector.producer()
metadata = {}

scanID = "ScanID1"

metadata.update(
    {
        "scanID": scanID,  # this will be different for each scan
        "async_update": "append",
    }
)
for ii in range(20):
    data = {"mca1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "mca2": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]}
    msg = messages.DeviceMessage(
        signals=data,
        metadata=metadata,
    ).dumps()

    # producer.send(topic=MessageEndpoints.device_status(device="mca"), msg=msg)

    producer.xadd(
        topic=MessageEndpoints.device_async_readback(
            scanID=scanID, device="mca"
        ),  # scanID will be different for each scan
        msg={"data": msg},  # TODO should be msg_dict
        expire=1800,
    )

    print(f"Sent {ii}")
    time.sleep(0.5)
