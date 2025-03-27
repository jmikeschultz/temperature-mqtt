# fan_control.py
import os
import sys
import time
import json
import logging
import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO

# ============================== #
# Configuration Section
# ============================== #
FAN_GPIO = 12  # BCM pin number (GPIO12)
FAN_ON_TEMP = 50.0  # Temp (C) to turn fan ON
FAN_OFF_TEMP = 45.0  # Temp (C) to turn fan OFF
SLEEP_SECS = 5  # Time between temp checks

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
# MQTT Setup
# ============================== #
def setup_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    else:
        logger.warning("MQTT_USERNAME and/or MQTT_PASSWORD not set")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.critical(f"Failed to connect to MQTT broker: {e}")
        sys.exit(1)
    return client

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
# MQTT Publishing
# ============================== #
def publish_state(mqtt_client, cpu_temp, fan_on):
    payload = {
        "temp": cpu_temp,
        "fan": 1 if fan_on else 0
        }
    
    try:
        mqtt_client.publish(TOPIC_CPU, json.dumps(payload), qos=1)
        logger.info(f"Published cpu temp and fan state to MQTT: {cpu_temp} fan_on={fan_on}")
    except Exception as e:
        logger.warning(f"MQTT publish failed cpu temp and fan state: {e}")

# ============================== #
# Main Loop
# ============================== #
def main():
    setup_gpio()
    mqtt_client = setup_mqtt()
    mqtt_client.loop_start()  # Start MQTT loop for background handling

    fan_on = False

    try:
        while True:
            try:
                cpu_temp = get_cpu_temperature()
                if cpu_temp is None:
                    logger.warning("Could not read CPU temperature")
                else:
                    logger.info(f"CPU Temp: {cpu_temp:.1f}°C")

                    if not fan_on and cpu_temp >= FAN_ON_TEMP:
                        GPIO.output(FAN_GPIO, GPIO.HIGH)
                        fan_on = True
                        logger.info("Fan turned ON")

                    elif fan_on and cpu_temp <= FAN_OFF_TEMP:
                        GPIO.output(FAN_GPIO, GPIO.LOW)
                        fan_on = False
                        logger.info("Fan turned OFF")

                    publish_state(mqtt_client, cpu_temp, fan_on)

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
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("Fan OFF, MQTT disconnected, GPIO cleaned up")

# ============================== #
# Entry Point
# ============================== #
if __name__ == "__main__":
    main()
