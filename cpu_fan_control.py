# fan_control.py
import os
import sys
import time
import json
import logging
import threading
import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTT_ERR_SUCCESS
import RPi.GPIO as GPIO

# ============================== #
# Configuration Section
# ============================== #
FAN_GPIO = 12  # BCM pin number (GPIO12)
FAN_ON_TEMP = 50.0  # Temp (C) to turn fan ON
FAN_OFF_TEMP = 45.0  # Temp (C) to turn fan OFF
SLEEP_SECS = 5  # Time between temp checks
MQTT_RETRY_SECS = 30  # Time between MQTT reconnection attempts

# MQTT Configuration
MQTT_BROKER = "hx0.duckdns.org"
MQTT_PORT = 1883
TOPIC_CPU = "home/boat/cpu"
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# ============================== #
# Logging Configuration
# ============================== #
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logger = logging.getLogger("FanController")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(console_handler)

# ============================== #
# GPIO Setup
# ============================== #
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(FAN_GPIO, GPIO.OUT)
    GPIO.output(FAN_GPIO, GPIO.LOW)
    logger.debug("GPIO initialized and fan set to OFF")

# ============================== #
# Fan State Reader
# ============================== #
def fan_on():
    return GPIO.input(FAN_GPIO) == GPIO.HIGH

# ============================== #
# Temperature Reading
# ============================== #
def get_cpu_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_millideg = int(f.read().strip())
            return round(temp_millideg / 1000.0, 1)
    except Exception as e:
        logger.error(f"Failed to read CPU temperature: {e}")
        return None

# ============================== #
# MQTT Lifecycle Manager Thread
# ============================== #
mqtt_client = None
mqtt_connected_event = threading.Event()

def mqtt_manager_thread():
    global mqtt_client

    while not mqtt_connected_event.is_set():
        try:
            logger.info("Attempting MQTT connection...")
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

            if MQTT_USERNAME and MQTT_PASSWORD:
                client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            else:
                logger.warning("MQTT_USERNAME and/or MQTT_PASSWORD not set")

            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()

            mqtt_client = client
            mqtt_connected_event.set()
            logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")

        except Exception as e:
            logger.warning(f"MQTT connect failed, retrying in {MQTT_RETRY_SECS}s: {e}")
            time.sleep(MQTT_RETRY_SECS)

# ============================== #
# MQTT Publishing (non-fatal)
# ============================== #
def publish_state(cpu_temp, fan_on):
    if not mqtt_client:
        return False

    payload = {
        "temp": cpu_temp,
        "fan": 1 if fan_on else 0
    }

    try:
        result = mqtt_client.publish(TOPIC_CPU, json.dumps(payload), qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
            
    except Exception as e:
        logger.warning(f"MQTT publish threw exception: {e}")
        return False

# ============================== #
# Main Loop
# ============================== #
def main():
    setup_gpio()
    threading.Thread(target=mqtt_manager_thread, daemon=True).start()

    try:
        while True:
            try:
                cpu_temp = get_cpu_temperature()
                if cpu_temp is None:
                    logger.warning("Could not read CPU temperature")
                else:
                    if not fan_on() and cpu_temp >= FAN_ON_TEMP:
                        GPIO.output(FAN_GPIO, GPIO.HIGH)

                    elif fan_on() and cpu_temp <= FAN_OFF_TEMP:
                        GPIO.output(FAN_GPIO, GPIO.LOW)

                    is_published = publish_state(cpu_temp, fan_on())
                    logger.info(f"CPU Temp: {cpu_temp:.1f}°C fan:{'ON' if fan_on() else 'OFF'} mqtt:{'PUBLISHED' if is_published else 'NOT_PUBLISHED'}")

            except Exception as e:
                logger.warning(f"Fan control loop error: {e}")

            time.sleep(SLEEP_SECS)

    except KeyboardInterrupt:
        logger.info("Exiting on KeyboardInterrupt")

    except Exception as e:
        logger.critical(f"Unexpected fatal error: {e}")

    finally:
        try:
            GPIO.output(FAN_GPIO, GPIO.LOW)
        except Exception:
            pass  # GPIO might not be initialized

        GPIO.cleanup()

        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

        logger.info("Fan OFF, MQTT disconnected, GPIO cleaned up")

# ============================== #
# Entry Point
# ============================== #
if __name__ == "__main__":
    main()
