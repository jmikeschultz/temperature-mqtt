# temperature-mqtt
code to send adafruit temperature readings over mqtt
venv = virtual environment for the service
env = environment vars, mqtt user,pass NOT CHECKED IN!

# cpu_fan_control
added cpu temperature to mqtt payload
also turns on/off fan
sends state to mqtt

sudo systemctl daemon-reload
sudo pinctrl set 12 op dh
sudo pinctrl set 12 dl
