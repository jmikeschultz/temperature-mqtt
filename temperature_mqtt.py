import threading
import serial
import paho.mqtt.client as mqtt
import os
import sys
import json
import time
import serial.tools.list_ports

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
            print(f'found {device} at {port.device}')
            return port.device
    raise RuntimeError(f"{device} not found!")

def on_connect(client, userdata, flags, reason_code, properties=None):
    global is_connected
    if reason_code != 0:
        print(f"Failed to connect: {reason_code}")
        client.loop_stop()
        sys.exit(f"Exiting: Failed to connect to MQTT broker. Reason: {reason_code}")
    else:
        is_connected = True
        print(f'Connection to MQTT broker {MQTT_BROKER} succeeded')
    event.set()

# Serial Port Configuration
serial_port = find_device()
baud_rate = 9600
SLEEP_SECS = 60

# MQTT Client Setup
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect

if MQTT_USERNAME and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
else:
    sys.exit('Missing OS envs: MQTT_USERNAME, MQTT_PASSWORD')

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    sys.exit(f"Error connecting to MQTT broker: {e}")

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
                print(f"Failed to publish message: {result.rc}")
            else:
                print(f"Published: {json.dumps(payload)}")
    except ValueError:
        print(f"Error parsing line: {line}")

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
    print(f"Serial error: {e}")
except KeyboardInterrupt:
    print("Exiting script.")
finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
