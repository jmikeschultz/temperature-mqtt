import threading
import serial
import paho.mqtt.client as mqtt
import os
import sys
import json
import time
import serial.tools.list_ports
import logging
from logging.handlers import RotatingFileHandler

# Logging Configuration
LOG_FILE = "/var/log/temperature_mqtt.log"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Configure logger
logger = logging.getLogger("TemperatureMQTT")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(LOG_FORMAT)

# File handler with rotation
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5000000, backupCount=3)
file_handler.setFormatter(formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# MQTT Configuration
MQTT_BROKER = "hx0.duckdns.org"
MQTT_PORT = 1883
MQTT_TOPIC = "home/boat/sensor_data"
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Global connection status
is_connected = False
event = threading.Event()

def find_device():
    device = 'SHT4x Trinkey M0'
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if device in port.description:
            logger.info(f'Found {device} at {port.device}')
            return port.device
    logger.error(f"{device} not found!")
    raise RuntimeError(f"{device} not found!")

def on_connect(client, userdata, flags, reason_code, properties=None):
    global is_connected
    if reason_code != 0:
        logger.error(f"Failed to connect to MQTT broker: {reason_code}")
        client.loop_stop()
        sys.exit(f"Exiting: Failed to connect to MQTT broker. Reason: {reason_code}")
    else:
        is_connected = True
        logger.info(f'Connected to MQTT broker {MQTT_BROKER}')
    event.set()

# Serial Port Configuration
try:
    serial_port = find_device()
except RuntimeError as e:
    logger.critical(str(e))
    sys.exit(1)

baud_rate = 9600
SLEEP_SECS = 60

# MQTT Client Setup
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect

if MQTT_USERNAME and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
else:
    logger.critical('Missing OS envs: MQTT_USERNAME, MQTT_PASSWORD')
    sys.exit(1)

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    logger.critical(f"Error connecting to MQTT broker: {e}")
    sys.exit(1)

# Start the MQTT loop in a separate thread
mqtt_client.loop_start()

# Function to parse the line and send JSON to MQTT
def process_and_publish(line):
    try:
        parts = line.split(", ")
        if len(parts) >= 3:
            temperature = (float(parts[1]) * 9/5) + 32 # fahrenheit
            humidity = float(parts[2])

            # Create a JSON payload
            payload = {
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2)
            }

            # Publish the JSON payload
            result = mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning(f"Failed to publish message: {result.rc}")
            else:
                logger.info(f"Published: {json.dumps(payload)}")
    except ValueError:
        logger.error(f"Error parsing line: {line}")

# Open the serial port and read data
try:
    event.wait()
    with serial.Serial(serial_port, baud_rate, timeout=1) as ser:
        while is_connected:
            line = ser.readline().decode('utf-8').strip()
            if line:
                process_and_publish(line)
                time.sleep(SLEEP_SECS)

except serial.SerialException as e:
    logger.error(f"Serial error: {e}")
except KeyboardInterrupt:
    logger.info("Exiting script.")
finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    logger.info("MQTT client disconnected.")
