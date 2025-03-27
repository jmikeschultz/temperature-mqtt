# =========================================== #
# temperature_mqtt.py (updated: now only sensor)
# =========================================== #
import threading
import serial
import paho.mqtt.client as mqtt
import os
import sys
import json
import time
import serial.tools.list_ports
import logging

# ============================== #
# Logging Setup
# ============================== #
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logger = logging.getLogger("TemperatureMQTT")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(console_handler)

# ============================== #
# MQTT Setup
# ============================== #
MQTT_BROKER = "hx0.duckdns.org"
MQTT_PORT = 1883
MQTT_TOPIC = "home/boat/usb_sht45"
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

is_connected = False
connected_event = threading.Event()

def on_connect(client, userdata, flags, reason_code, properties=None):
    global is_connected
    if reason_code != 0:
        logger.error(f"MQTT connection failed: {reason_code}")
        client.loop_stop()
        sys.exit(1)
    is_connected = True
    logger.info(f"Connected to MQTT broker at {MQTT_BROKER}")
    connected_event.set()

def find_device():
    device = 'SHT4x Trinkey M0'
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if device in port.description:
            logger.info(f"Found {device} at {port.device}")
            return port.device
    raise RuntimeError(f"{device} not found")

def setup_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    else:
        logger.warning("MQTT credentials not set")

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        logger.critical(f"MQTT connection failed: {e}")
        sys.exit(1)

    return client

def process_and_publish(line, mqtt_client):
    try:
        parts = line.split(", ")
        if len(parts) >= 3:
            temp_f = (float(parts[1]) * 9/5) + 32
            humidity = float(parts[2])

            if temp_f > 212:
                return

            payload = {
                "temperature": round(temp_f, 2),
                "humidity": round(humidity, 2)
            }

            result = mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"Failed to publish: {result.rc}")
            else:
                logger.info(f"Published sensor data: {json.dumps(payload)}")
    except ValueError:
        logger.error(f"Error parsing line: {line}")

def main():
    try:
        serial_port = find_device()
    except RuntimeError as e:
        logger.critical(str(e))
        sys.exit(1)

    mqtt_client = setup_mqtt()
    connected_event.wait()

    try:
        with serial.Serial(serial_port, 9600, timeout=1) as ser:
            while is_connected:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    process_and_publish(line, mqtt_client)
                    time.sleep(60)
    except serial.SerialException as e:
        logger.error(f"Serial error: {e}")
    except KeyboardInterrupt:
        logger.info("Script interrupted")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client disconnected")

if __name__ == "__main__":
    main()
