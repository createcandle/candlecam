# Candle Cam

Exploring what a privacy focused smart doorbell could look like.

This code turn a Raspberry Pi with a camera (and optionally a (ReSpeaker) microphone), into a security camera or smart doorbell for the WebThings Gateway.


# Installation
The goal is for this addon to be available in the addon list. For now though, you can install it manually.

(Turn of the Raspberry Pi and connect a camera module to your rapberry via the ribbon cable connector)

The easiest way to install it currently is:
- install the Seashell addon
- run this command: `cd /home/pi/.webthings/addons/; git clone https://github.com/createcandle/candlecam.git`
- wait a minute or two to make sure all files are fully downloaded
- Now we need to actualy install the addon using this command: `sudo chmod +x /home/pi/.webthings/addons/candlecam/package.sh; /home/pi/.webthings/addons/candlecam/package.sh`
- Give that at least another hour to do its work (not kidding).
- reboot

The addon should now appear in your installed addons list.
- enable it
