import time
import board
import adafruit_sht45
import paho.mqtt.client as mqtt
import os

# MQTT Configuration
MQTT_BROKER = "hx0.duckdns.org"
MQTT_PORT = 1883
MQTT_TOPIC = "home/boat/temperature"
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")  
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")  

# Initialize the SHT45 sensor
i2c = board.I2C()
sensor = adafruit_sht45.SHT45(i2c)

# MQTT Client Setup
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
    else:
        print(f"Failed to connect, return code {rc}")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
if MQTT_USERNAME and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Function to read temperature and send to MQTT
try:
    while True:
        temperature = sensor.temperature  # Read temperature in Celsius
        print(f"Temperature: {temperature:.2f} °C")

        # Publish to MQTT
        mqtt_client.publish(MQTT_TOPIC, f"{temperature:.2f}")

        time.sleep(60)  # Send data every 60 seconds

except KeyboardInterrupt:
    print("Script terminated.")

finally:
    mqtt_client.disconnect()
