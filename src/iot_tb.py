from __future__ import annotations

import json
import os
import ssl
from typing import Any

import paho.mqtt.client as mqtt


def send_json_to_thingsboard(
    payload: dict[str, Any],
    host: str,
    port: int,
    token: str,
    use_tls: bool = False,
) -> bool:
    """
    Send data to ThingsBoard in two steps:
    1) Flat telemetry (keys canalX_estado) to feed legacy widgets.
    2) Full payload (summary, channels, bands...) for structured telemetry.
    """
    try:
        client_id = f"AudioCinemaPi-{os.uname().nodename}-{os.getpid()}"
        client = mqtt.Client(client_id=client_id, clean_session=True)
        client.username_pw_set(token)

        if use_tls:
            client.tls_set(cert_reqs=ssl.CERT_NONE)
            client.tls_insecure_set(True)

        client.connect(host, port, keepalive=30)
        topic = "v1/devices/me/telemetry"

        flat_payload = {k: v for k, v in payload.items() if k.startswith("canal")}

        if flat_payload:
            client.publish(topic, json.dumps(flat_payload), qos=1)
            print("\n🔵 DEBUG flat:", json.dumps(flat_payload, indent=2))
            print("📡 Sent flat telemetry:", flat_payload)

        client.publish(topic, json.dumps(payload), qos=1)
        print("\n🟠 DEBUG full payload:", json.dumps(payload, indent=2))
        print("📡 Sent full payload")

        client.loop(timeout=2.0)
        client.disconnect()

        return True
    except Exception as exc:
        print(f"MQTT error: {exc}")
        return False
