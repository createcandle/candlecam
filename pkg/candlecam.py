"""Candlecam API handler."""

# Webthing
from __future__ import division
#from webthing import (Action, Event, Property, SingleThing, Thing, Value, WebThingServer)
#import webthings.Property as Property2


import io
import gc
import os
import re
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

import time
from time import sleep, mktime
import uuid
import json
#import base64
import ifaddr
import random
import socket
#import urllib 
import asyncio
import logging
#import datetime
import webthing
from webthing import (SingleThing, Thing, Value, WebThingServer)
#from webthing import Property as prop


#from os import listdir
#from os.path import isfile, join

#import picamera

#import datetime
import functools
import threading
import subprocess

#from threading import Condition
import requests
from requests.adapters import HTTPAdapter
#import base64
#from pynput.keyboard import Key, Controller

import tornado.web
import tornado.gen
#from tornado.util import TimeoutError

import picamera

try:
    from gpiozero import Button
except:
    print("Error, could not load gpiozero library")


if os.path.isdir("/etc/voicecard"):

    try:
        import RPi.GPIO as GPIO
    except Exception as ex:
        print("Error, could not load RPi.GPIO: " + str(ex))

    try:
        #from apa102 import APA102
        from .apa102 import APA102
        #from .apa import APA102
    except:
        print("Error, could not load APA201 LED lights library")


try:
    from gateway_addon import Database, Adapter, Device, Property, APIHandler, APIResponse
except:
    print("Error, could not load gateway addon library")
    
    
try:
    #from .candlecam_adapter import *
    pass
except Exception as ex:
    print("Error loading candlecam_adapter: " + str(ex))
    
#try:
#    from gateway_addon import Adapter, Device, Database
#except:
#    print("Gateway not loaded?!")

print = functools.partial(print, flush=True)

_TIMEOUT = 3

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.webthings', 'config'),
]

if 'WEBTHINGS_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['WEBTHINGS_HOME'], 'config'))


#candlecam_adapter_running = True

#global _loop, candlecammy, new_frame, frame
#_loop = None
#candlecammy = None
#frame = None


class CandlecamAPIHandler(APIHandler):
    """Power settings API handler."""

    def __init__(self, verbose=False):
        """Initialize the object."""
        print("INSIDE API HANDLER INIT")
        
        self.addon_name = 'candlecam'
        #self.server = 'http://127.0.0.1:8080'
        
        self.DEBUG = True # TODO: disable debugging by default
        self.ready = False
        self.running = True
        
        try:
            manifest_fname = os.path.join(
                os.path.dirname(__file__),
                '..',
                'manifest.json'
            )

            with open(manifest_fname, 'rt') as f:
                manifest = json.load(f)
            
            APIHandler.__init__(self, manifest['id'])
            self.manager_proxy.add_api_handler(self)            
            
        except Exception as ex:
            print("Failed creating handler for proxy: " + str(ex))
            
        try:
            #global frame
            #frame = b''
            #global viewers
            #viewers = 0
            #global streaming
            #streaming = True
            
            #global taking_a_photo_countdown
            #taking_a_photo_countdown = 0
            self.taking_a_photo_countdown = 0
            
            
            
            # RESPEAKER
            self.has_respeaker_hat = False
            self.pwm = None
            self.lights = None
            self.plughw_number = '0,0'
            self.has_respeaker_hat = False
            self.ringtones = ['default','classic','klingel','business','fart','none']
            
            
            # THINGS
            self.things = [] # Holds all the things, updated via the API. Used to display a nicer thing name instead of the technical internal ID.
            #self.data_types_lookup_table = {}
            
            
            # NETWORK
            self.last_network_scan_time = 0
            self.busy_doing_network_scan = False
            self.gateways_ip_list = [] # list of IP addresses of local candle servers
            self.gateways_ip_dict = {} # dict IP addresses and hostnames of local candle servers
            
            self.own_ip = '127.0.0.1'
            try:
                self.own_ip = get_ip()
            except Exception as ex:
                print(str(ex))
            
            
            # STREAMING
            self.frame = b''
            self.viewer_count = 0
            self.ffmpeg_process = None
            self.encode_audio = False
            self.only_stream_on_button_press = False
            self.own_mjpeg_url = 'http://' + self.own_ip + ':8889/media/candlecam/stream/stream.mjpeg'
            self.own_snapshot_url = 'http://' + self.own_ip + ':8889/snapshot.jpg'
            
            
            
            # CAMERA
            self.picam = None
            self.framerate = 10
            self.last_write_time = 0
            self.portrait_mode = False
            self.hires = False
            self.maximum_connections = 2
            
            # PRINT
            self.send_snapshots_to_printer = False
            self.photo_printer_available = False
            
            
            # WEBTHING THINGY & SERVER
            self.thingy = None
            self.thing_server = None
            self.webthing_port = 8889
            #self.name = 'candlecam' # thing name
            self.thingy_id = 'candlecam_webthing_' + str(randomWord(4)) # not really necessary, will be overwritten from persistent data
            self.https = False
            self.button_state = Value(False)
            
            self.snapshot_state = False #Value(False)
            self.previous_snapshot_state = False
            #self.streaming = True #Value(True)
            self.pressed = False
            self.pressed_sent = False
            self.pressed_countdown_time = 60 #1200 # 1200 = 2 minutes
            self.pressed_countdown = self.pressed_countdown_time
            self.webthings_addon_detected = False
            
            
            #GPIO
            self.button_pin = 17
            self.servo_pin = 13
            self.servo_open_position = 0
            self.servo_closed_position = 70
            
            
            # RAMDRIVE (not used currently)
            self.use_ramdrive = True
            self.ramdrive_created = False # it's only created is enough free memory is available (50Mb)

            
            # Matrix
            self.send_to_matrix = True
            
            #self.volume_level = 90
            
            self.snapshot1 = None
            self.snapshot2 = None
            
            
            #self.terminated = False
            
            self.take_a_photo = False
            self.taking_a_photo_countdown_start = 60
            
            
            # DETECT RESPEAKER HAT
            print("\naplay -l output:")
            aplay_output = run_command('aplay -l')
            print(str(aplay_output))
            if 'seeed' in aplay_output.lower():
                print("SEEED ReSpeaker hat spotted")
                self.has_respeaker_hat = True
            else:
                print("No SEEED ReSpeaker hat spotted")
                
            #print("\nself.has_respeaker_hat: " + str(self.has_respeaker_hat))


            #ALTERNATIVE RESPEAKER CHECK
            
            #self.has_respeaker_hat = False # Is a ReSPeaker 2 mic hat installed?
            #if os.path.isdir("/etc/voicecard"):
            #    self.has_respeaker_hat = True
            
            #self.network_scan()
            
            
            
        except Exception as ex:
            print("Failed in first part of init: " + str(ex))
            
            
        

            
        try: 
            if self.has_respeaker_hat:
            
                # Button (pin 17)
                GPIO.setmode(GPIO.BCM) # Use BCM pin numbering
                GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                #GPIO.setup(17, GPIO.IN)
                GPIO.add_event_detect(self.button_pin, GPIO.RISING, callback=self.ding, bouncetime=400)
        
                # https://www.mbtechworks.com/projects/raspberry-pi-pwm.html
        
        
        
                # servo (pin 13)
                GPIO.setup(self.servo_pin, GPIO.OUT)
                self.pwm = GPIO.PWM(self.servo_pin, 100) # 1000
        
                dc=1                                # set dc variable to 0 for 0%
                self.pwm.start(dc)                  # Start PWM with 0% duty cycle
        
                #for dc in range(0, 101, 5):         # Loop 0 to 100 stepping dc by 5 each loop
                #    self.pwm.ChangeDutyCycle(dc)
                #    time.sleep(0.05)              # wait .05 seconds at current LED brightness
                #    print(dc)
        
                #self.pwm.stop()
        
        except Exception as ex:
            print("Failed in GPIO init: " + str(ex))
            
            
            
            
            
                
        # CHECK IF CAMERA IS AVAILABLE
        self.camera_available = False

        try:
            check_camera_enabled_command_array = ['/opt/vc/bin/vcgencmd','get_camera']
            check_camera_result = subprocess.check_output(check_camera_enabled_command_array)
            check_camera_result = check_camera_result.decode('utf-8')
            if self.DEBUG:
                print("check_camera_result = " + str(check_camera_result))
            
            if 'supported=0' in check_camera_result:
                if self.DEBUG:
                    print("\n! Pi camera does not seem to be supported\n")
                #os.system('sudo raspi-config nonint do_i2c 1')
                """
                with open("/boot/config.txt", "r") as file:
                    os.system('cp /boot/config.txt /boot/config.bak')
                    #for line in file:
                    #    print (line.split("'")[1])
                    
                    if self.DEBUG:
                        print("modifying /boot/config.txt, and creating .bak backup copy")
                    if 'start_x' in file:
                        os.system('sudo sed -i "s/start_x=0/start_x=1/g" /boot/config.txt')
                    else:
                        
                        os.system('echo "start_x=1" >> /boot/config.txt')
                        
                    if self.armv6:
                        if 'gpu_mem' in file:
                            os.system("sed -i 's/^\(gpu_mem=\).*/\1128/' /boot/config.txt")
                        else:
                            os.system('echo "gpu_mem=128" >> /boot/config.txt')
                    else:
                        if 'gpu_mem' in file:
                            os.system("sed -i 's/^\(gpu_mem=\).*/\1256/' /boot/config.txt")
                        else:
                            os.system('echo "gpu_mem=256" >> /boot/config.txt')
                            
                    self.adapter.send_pairing_prompt("Please reboot the device")
                
                """
            elif 'detected=0' in check_camera_result:
                if self.DEBUG:
                    print("\nPi camera is supported, but was not detected\n")
                    self.adapter.send_pairing_prompt("No camera detected")
            else:
                if self.DEBUG:
                    print("\nPi camera seems good to go\n")
                self.camera_available = True
                
        except Exception as ex:
            print("Error checking if camera is enabled: " + str(ex))
                
                
                
                
                


        #print("self.adapter.persistence_file_path = " + str(self.adapter.persistence_file_path))
    
        # Get persistent data
        #self.persistence_file_path = self.adapter.persistence_file_path

    
        if self.DEBUG:
            print("Current working directory: " + str(os.getcwd()))
            print("self.user_profile: " + str(self.user_profile))
    
        
        self.persistent_data = {}
    
        try:
        
            self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
            #self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'data', self.addon_name,'persistence.json')
            self.persistence_dir_path = os.path.join(self.user_profile['dataDir'], self.addon_name)
            self.persistence_file_path = os.path.join(self.persistence_dir_path, 'persistence.json')


            # Make sure the persistence data directory exists
            try:
                if not os.path.isdir(self.persistence_dir_path):
                    os.mkdir( self.persistence_dir_path )
                    print("Persistence directory did not exist, created it now")
            except:
                print("Error: could not make sure persistence dir exists. intended persistence dir path: " + str(self.persistence_dir_path))
            
            
            
            # Get persistent data
            
            #self.persistence_file_path = self.adapter.persistence_file_path
            if self.DEBUG:
                print("self.persistence_file_path = " + str(self.persistence_file_path))
            
            first_run = False
            try:
                with open(self.persistence_file_path) as f:
                    self.persistent_data = json.load(f)
                    if self.DEBUG:
                        print("Persistence data was loaded succesfully.")
                    
            except:
                first_run = True
                if self.DEBUG:
                    print("Could not load persistent data (if you just installed the add-on then this is normal)")
            
                try:
                    self.persistent_data = {'streaming':True, 'ringtone_volume':90, 'ringtone':'default', 'cover_state':'closed', 'politeness':True, 'thing_settings':{}}
                except Exception as ex:
                    print("Error creating initial persistence variable: " + str(ex))
    
        except Exception as e:
            print("WARNING, Failed to load persistent data: " + str(e))
        
            
        
        
                
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))

        
        # Get hostname
        try:
            system_hostname = socket.gethostname().lower()
            self.hostname = system_hostname
            self.hosts = [
                'localhost',
                'localhost:{}'.format(self.webthing_port),
                '{}.local'.format(system_hostname),
                '{}.local:{}'.format(system_hostname, self.webthing_port),
            ]
    
            for address in get_addresses():
                self.hosts.extend([
                    address,
                    '{}:{}'.format(address, self.webthing_port),
                ])
            
            
            
            """
            self.hostname = None
            if self.hostname is not None:
                self.hostname = self.hostname.lower()
                self.hosts.extend([
                    self.hostname,
                    '{}:{}'.format(self.hostname, self.webthing_port),
                ])
            """
        
            #if self.DEBUG:
            #    print("self.manager_proxy = " + str(self.manager_proxy))
            #    print("Created new API HANDLER: " + str(manifest['id']))
        
        
        except Exception as ex:
            print("Error checking for hostname: " + str(ex))
        
        
        
        try:
            if 'thing_settings' not in self.persistent_data:
                self.persistent_data['thing_settings'] = {}
            if 'ringtone_volume' not in self.persistent_data:
                self.persistent_data['ringtone_volume'] = 90
            if 'streaming' not in self.persistent_data:
                self.persistent_data['streaming'] = True
            if 'ringtone' not in self.persistent_data:
                self.persistent_data['ringtone'] = 'default'
            if 'led_brightness' not in self.persistent_data:
                self.persistent_data['led_brightness'] = 10
            if 'led_color' not in self.persistent_data:
                self.persistent_data['led_color'] = "#ffffff"
            if 'cover_state' not in self.persistent_data:
                self.persistent_data['cover_state'] = 'closed'
            if 'politeness' not in self.persistent_data:
                self.persistent_data['politeness'] = True
            if 'thing_server_id' not in self.persistent_data:
                if self.hostname != 'candle':
                    self.persistent_data['thing_server_id'] = self.hostname
                else:
                    self.persistent_data['thing_server_id'] = randomWord(4)
            if 'data_retention_days' not in self.persistent_data:    
                self.persistent_data['data_retention_days'] = 2
            
            if self.DEBUG:
                print("\n\nself.persistent_data: " + str(self.persistent_data))
                print("\n\nthing_server_id: " + str(self.persistent_data['thing_server_id']))
    
    
    
            #streaming = self.persistent_data['streaming'] # global
            self.thingy_id = 'candlecam_webthing_' + self.persistent_data['thing_server_id']
    
            #self.streaming = self.persistent_data['streaming']
            self.previous_streaming_state = self.persistent_data['streaming']
            self.previous_ringtone = self.persistent_data['ringtone']
            self.previous_ringtone_volume = self.persistent_data['ringtone_volume']
            self.previous_led_color = self.persistent_data['led_color']
            self.previous_led_brightness = self.persistent_data['led_brightness']
            self.previous_politeness = self.persistent_data['politeness']
            #self.ringtone_value = Value(self.persistent_data['ringtone'])
            #self.ringtone_value = Value(self.persistent_data['ringtone'], lambda v: self.ringtone_change(v))
            #self.streaming_value = Value(self.persistent_data['streaming'], self.streaming_change)
            #self.ringtone_volume_value = Value(self.persistent_data['ringtone_volume'], lambda v: self.volume_change(v))
            
        except Exception as ex:
            print("Error checking for missing persistent data values: " + str(ex))
    
        
        
        if self.DEBUG:
            print("self.manager_proxy = " + str(self.manager_proxy))
            print("Created new API HANDLER: " + str(manifest['id']))

        
        #print("_ _ _ ")
        #print("self.user_profile = " + str(self.user_profile))
        #print("")

        if self.DEBUG:
            print("\nself.user_profile: " + str(self.user_profile))

        try:
            #print(str(self.user_profile['mediaDir']))
            self.media_dir_path = os.path.join(self.user_profile['mediaDir'], self.addon_name)
        except Exception as e:
            print("Error, mediadir did not exist in the user profile: " + str(ex))
            self.media_dir_path = os.path.join('/home/pi/.webthings/media', self.addon_name)
        
        try:
            self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
            #self.persistence_file_folder = os.path.join(self.user_profile['configDir'])
            if self.DEBUG:
                print("self.addon_path: " + str(self.addon_path))
            
            self.media_photos_dir_path = os.path.join(self.user_profile['mediaDir'], self.addon_name, 'photos')
            #self.addon_photos_dir_path = os.path.join(self.addon_path, 'photos')
            #self.addon_stream_dir_path = os.path.join(self.addon_path, 'stream')
            
            
            self.media_stream_dir_path = os.path.join(self.media_dir_path, 'stream')
            
            self.dash_file_path = os.path.join(self.media_stream_dir_path, 'index.mpd')
            #self.dash_stream_url = 'http://' + self.own_ip + ':8080/extensions/candlecam/stream/index.mpd'
            self.m3u8_file_path = os.path.join(self.media_stream_dir_path, 'master.m3u8')
            self.mjpeg_file_path = os.path.join(self.media_stream_dir_path, 'stream.mjpeg')
            #self.m3u8_stream_url = 'http://' + self.own_ip + ':8080/extensions/candlecam/stream/master.m3u8'
            
            #self.ffmpeg_output_path = os.path.join( self.addon_stream_dir_path, 'index.mpd')
            self.ffmpeg_output_path = os.path.join( self.media_stream_dir_path,'index.mpd')
            
            self.latest_photo_file_path = os.path.join( self.media_photos_dir_path,'latest.jpg')
            
            #self.dash_file_path = os.path.join(self.addon_path, 'stream', 'index.mpd')

            self.matrix_drop_dir = os.path.join(self.user_profile['dataDir'], 'voco','sendme')
            
            self.webthings_addon_dir = os.path.join(self.user_profile['addonsDir'], 'thing-url-adapter')
            
            self.not_streaming_image = os.path.join(self.addon_path, 'images','camera_not_available.jpg')
            
            self.addon_sounds_dir_path = os.path.join(self.addon_path, 'sounds')
            
            self.addon_sounds_dir_path += os.sep
            
            self.external_picture_drop_dir = os.path.join(self.user_profile['dataDir'], 'privacy-manager', 'printme')
            
            if self.DEBUG:
                print("self.latest_photo_file_path = " + str(self.latest_photo_file_path))
                print("self.ffmpeg_output_path = " + str(self.ffmpeg_output_path))
                print("self.addon_sounds_dir_path = " + str(self.addon_sounds_dir_path))
            
        except Exception as e:
            print("Failed to make paths: " + str(e))
            
        try:
            
            #if not os.path.isdir( self.addon_photos_dir_path ):
            #    print(self.addon_photos_dir_path + " directory did not exist yet, creating it now")
            #    os.mkdir( self.addon_photos_dir_path )
            
            #if not os.path.isdir( self.addon_stream_dir_path ):
            #    print(self.addon_stream_dir_path + " directory did not exist yet, creating it now")
            #    os.mkdir( self.addon_stream_dir_path )
            
            if not os.path.isdir( self.user_profile['mediaDir'] ):
                if self.DEBUG:
                    print("creating media dir")
                os.mkdir( self.user_profile['mediaDir'] )
            
            if not os.path.isdir( self.media_dir_path ):
                if self.DEBUG:
                    print(self.media_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_dir_path )
            
            if not os.path.isdir( self.media_photos_dir_path ):
                if self.DEBUG:
                    print(self.media_photos_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_photos_dir_path )
                
            if not os.path.isdir( self.media_stream_dir_path ):
                if self.DEBUG:
                    print(self.media_stream_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_stream_dir_path )
            
        except Exception as ex:
            print("Error making photos directory: " + str(ex))
                
            
        # Make photos directory available
        try:
            if self.DEBUG:
                print("Gateway version: " + self.gateway_version)
                
            self.photos_dir_path = os.path.join(self.addon_path, 'photos')
            if not os.path.isdir( self.photos_dir_path ):
                if self.DEBUG:
                    print(self.photos_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.photos_dir_path )
            
            self.data_photos_dir_path = os.path.join(self.user_profile['dataDir'], self.addon_name, 'photos')
            if not os.path.isdir( self.data_photos_dir_path ):
                if self.DEBUG:
                    print(self.data_photos_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.data_photos_dir_path )
            
            soft_link = 'ln -s ' + str(self.data_photos_dir_path) + " " + str(self.photos_dir_path)
            if self.DEBUG:
                print("linking: " + soft_link)
            os.system('rm -rf ' + str(self.photos_dir_path))
            os.system(soft_link)
                
                
        except Exception as ex:
            if self.DEBUG:
                print("Error prepating photos dir: " + str(ex))
            
        try:
            if os.path.isdir(self.webthings_addon_dir):
                self.webthings_addon_detected = True
            
            
        except Exception as ex:
            if self.DEBUG:
                print("Error checking for thing url adapter dir: " + str(ex))
        #self.keyboard = Controller()
        
        
        # Create ramdisk for dash files (to prevent wear on SD card)
        """
        self.use_ramdrive = False # TODO DEBUG TEMPORARY, REMOVE ME
        if self.use_ramdrive:
            
            ram_data = subprocess.check_output(['grep','^MemFree','/proc/meminfo'])
            ram_data = ram_data.decode('utf-8')
            ram_data = int(''.join(filter(str.isdigit, ram_data)))
            
            if self.DEBUG:
                print("freemem: " + str(ram_data))
            if ram_data > 80000:
                if self.DEBUG:
                    print("Enough free memory, so creating ramdrive")
                os.system('sudo mount -t tmpfs -o size=50m candlecam_ramdrive ' + self.media_stream_dir_path)
                self.ramdrive_created = True

        """
        
        # Do an initial network scan
        self.gateways_ip_dict = self.network_scan()
        
        
        # Create adapter
        try:
            self.adapter = CandlecamAdapter(self)
            if self.DEBUG:
                print("Candlecam adapter created")
                print("self.adapter.user_profile: " + str(self.adapter.user_profile))
        except Exception as ex:
            print("api handler: error creating adapter: " + str(ex))
            
            
        
        

        
        
        # Setup LED light
        self.lights = None
        try:
            if self.has_respeaker_hat:
                if self.DEBUG:
                    print("setting up LED light on ReSpeaker hat")
                self.lights = APA102(3)
                self.set_led(self.persistent_data['led_color'],self.persistent_data['led_brightness'], False)
            
        except Exception as ex:
            print("Failed in LED setup: " + str(ex))
        
        
        
        
        
        
        
        # start libcamera streaming if on Raspbian Bullseye
        """
        self.libcamera_available = False
        cameralib_check = run_command('which libcamera-vid')
        if self.DEBUG:
            print("cameralib_check result: " + str(cameralib_check))
        if cameralib_check != None:
            if len(cameralib_check) > 10:
                if self.DEBUG:
                    print("libcamera seems to be available")
                self.libcamera_available = True
                get_snapshot_command = 'libcamera-jpeg -o ' + str(self.latest_photo_file_path) + ' -n --width 640 --height 480'
                if self.DEBUG:
                    print("get_snapshot_command = " + str(get_snapshot_command))
                snapshot_result = run_command(get_snapshot_command)
                if self.DEBUG:
                    print("libcamera-jpeg result: " + str(snapshot_result))
                time.sleep(3)
        """
 
        
        #print("init: Starting the ffmpeg thread")
        #if self.DEBUG:
        #    print("Starting the ffmpeg thread")
        try:
            # Restore the timers, alarms and reminders from persistence.
            #if 'action_times' in self.persistent_data:
            #    if self.DEBUG:
            #        print("loading action times from persistence") 
            #    self.persistent_data['action_times'] = self.persistent_data['action_times']
            
            #self.t = threading.Thread(target=self.ffmpeg) #, args=(self.voice_messages_queue,))
            #self.t.daemon = True
            #self.t.start()
            pass
        except:
            print("Error starting the clock thread")
        
        
        if os.path.isdir(self.matrix_drop_dir):
            if self.DEBUG:
                print("matrix drop-off dir exists")
        else:
            if self.DEBUG:
                print("matrix drop-off dir does not exist")
        
        # Start the internal clock
        if self.DEBUG:
            print("Starting the internal clock")
        self.clock_threshold = 3000 # Delete old snapshots once every 5 minutes
        self.clock_counter = 0
            
        try:            
            #c = threading.Thread(target=self.main_clock)
            #c.daemon = True
            #c.start()
            pass
        except Exception as ex:
            print("Error starting the clock thread: " + str(ex))
            
        
        self.ready = True
        self.save_persistent_data()
        #time.sleep(10)
        #self.create_thingy()
        
        try:
            if self.has_respeaker_hat or self.camera_available:
                
                
                
                if self.camera_available:
                    if self.DEBUG:
                        print("init: starting the picam thread")
                    #self.not_streaming_image
                    #not_streaming_image_size = os.path.getsize(self.not_streaming_image)
                    with open(self.not_streaming_image, "rb") as file:
                        self.not_streaming_image = file.read()
                    
                    try:            
                        c = threading.Thread(target=self.run_picam)
                        c.daemon = True
                        c.start()
                        pass
                    except Exception as ex:
                        print("Error starting the clock thread: " + str(ex))
                    
                    #if self.persistent_data['streaming']:
                    #    self.run_picam()
                    #else:
                    #    print("init: not streaming, not starting picam yet")
                #self.picam = picamera.PiCamera(resolution=(640,480), framerate=15)
                #self.picam.exposure_mode = 'auto'
                #self.picam.awb_mode = 'auto'
                    # let camera warm up
                #    time.sleep(2)
                    
                if self.DEBUG:
                    print("init: starting the thingy thread")
                self.t = threading.Thread(target=self.create_thingy) #, args=(self.voice_messages_queue,))
                self.t.daemon = True
                self.t.start()
                
                
            else:
                if self.DEBUG:
                    print("init: NOT starting the thingy and picamera (no camera and no respeaker hat)")
        except Exception as ex:
            print("Error starting the thingy thread: " + str(ex))
        
        #self.create_thingy()
        
        
        #time.sleep(3)
        # Start stream if necessary
        #if self.camera_available and self.persistent_data['streaming']:
        #    if self.DEBUG:
        #        print("According to persistent data, streaming was on. Setting streaming_change to True (starting streaming).")
        #    self.streaming_change(True)
        
        
        if self.DEBUG:
            print("end of init")
        
        
    def run_picam(self):
        if self.DEBUG:
            print("in run_picam")
            print("hires: " + str(self.hires))
            print("portrait_mode: " + str(self.portrait_mode))
            
        
        while self.running:
            
            time.sleep(.1)
            
            if self.picam == None and self.persistent_data['streaming']:
                if self.DEBUG:
                    print("\n\nSTARTING PICAMERA")
                
                stream = io.BytesIO()
        
                resolution = (640,480)
                if self.hires:
                    resolution = (1280,720)
                if self.portrait_mode:
                    if self.hires:
                        resolution = (720,1280)
                    else:
                        resolution = (480,640)
        
                if self.DEBUG:
                    print("- resolution: " + str(resolution))
        
                with picamera.PiCamera(resolution=resolution, framerate=10) as self.picam:
                    self.picam.exposure_mode = 'auto'
                    self.picam.awb_mode = 'auto'
        
                    time.sleep(2)
            
                    for _ in self.picam.capture_continuous(stream, 'jpeg', use_video_port=True):
                        # return current frame
                
                        if self.persistent_data['streaming'] == False:
                            if self.DEBUG:
                                print("exiting picam loop")
                            break
                
                        else:
                            stream.seek(0)
                            self.frame = stream.read()
                    
                            if self.take_a_photo: # TODO: or if continous periodic recording should be active, perhaps while in security mode?
                                if self.DEBUG:
                                    print("\nself.take_a_photo was True.")
                                self.take_a_photo = False

                                filename = str(int(time.time())) + '.jpg'
                                file_path = os.path.join( self.data_photos_dir_path,filename)
                        
                                if time.time() - 1 > self.last_write_time: # rate limiter
                                    if self.DEBUG:
                                        print("- Saving a photo from the picamera stream")
                                    self.last_write_time = time.time()
                                    #with open(self.mjpeg_file_path, "wb") as binary_file: # if continous storage for mjpeg serving via webthings standard is required
                                    with open(file_path, "wb") as binary_file:
                                        #print("saving jpg as mjpeg")
                                        binary_file.write(self.frame)
                            
                                    # We end up here if the "shortcut" option was used to quickly save a snapshot from the local camera
                                    if self.send_to_matrix:
                                        if os.path.isdir(self.matrix_drop_dir) and os.path.isfile(file_path):
                                            if self.DEBUG:
                                                print("sending file to Matrix via Voco")
                                            drop_file_path = os.path.join(self.matrix_drop_dir, "Candlecam_" + socket.gethostname().lower() + '_' + filename)
                                            os.system('cp ' + file_path + ' ' + drop_file_path)
                    
                                    self.try_sending_to_printer(filename)
                    
                    
                        # reset stream for next frame
                        stream.seek(0)
                        stream.truncate()
                
                self.picam = None
                stream.close()
                if self.DEBUG:
                    print("picam is now stopped")
            
            #print("[z]")
            
            
        
        
    
#
#  CLOCK
#
    
    """
    def main_clock(self):
        
        if self.DEBUG:
            print("CLOCK INIT.. ")
            print("clock: self.persistent_data['data_retention_days']: " + str(self.persistent_data['data_retention_days']))
        #time.sleep(2)
        

        while self.running:
            try:
                loop_counter += loop_sleep_duration
                if loop_counter > loop_threshold:
                    loop_counter = 0
                    if self.DEBUG:
                        print("5 minutes passed. Checking for old snapshots to delete")
                    threshold_time = int(time.time()) - (int(self.persistent_data['data_retention_days']) * 86400) # the moment in the past before which photos should be removed
                    if self.DEBUG:
                        print("threshold_time: " + str(threshold_time))
                    
                    snapshots = os.listdir(self.data_photos_dir_path)
                    print("snapshots: " + str(snapshots))
                    for filename in snapshots:
                        try:
                            
                            #filename = os.path.basename(snapshot_path)
                            snapshot_time = int(os.path.splitext(filename)[0])
                            if self.DEBUG:
                                print("checking is snapshot is too old: " + str(snapshot_time))
                            if snapshot_time < threshold_time:
                                file_path = os.path.join(self.data_photos_dir_path,filename)
                                if self.DEBUG:
                                    print("- Too old. Deleting: " + str(file_path))
                                os.remove(file_path)
                                    
                        except Exception as ex:
                            print("Clock: error looping over list of snapshots: " + str(ex))
                
            except Exception as ex:
                print("Error in clock: " + str(ex))
    
            time.sleep(5)
    
        
    
    
    def ffmpeg(self):
        if self.DEBUG:
            print("in ffmpeg")
        os.system('pkill ffmpeg')
        
        #os.system('ffmpeg -input_format yuyv422 -fflags nobuffer -vsync 0 -f video4linux2 -s 1280x720 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v h264_omx -r 10 -b:v 2M -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -f dash ' + self.dash_file_path + ' -remove_at_exit 1')
        #os.system('ffmpeg -input_format yuyv422 -fflags nobuffer -vsync 0 -f video4linux2 -s 1280x720 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v libx264 -r 10 -b:v:0 400k -profile:v:0 high -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -f dash ' + self.dash_file_path + ' ')
        #os.system('ffmpeg -input_format yuyv422 -fflags nobuffer -vsync 0 -f video4linux2 -s 1280x720 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v libx264 -r 10 -b:v:0 400k -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -f dash ' + self.dash_file_path + ' ')
        #os.system('ffmpeg -fflags nobuffer -vsync 0 -f video4linux2 -s 640x360 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v libx264 -r 10 -b:v:0 400k -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -f dash ' + self.dash_file_path + ' ')
        
        
        # WORKS
        #os.system('ffmpeg -y -f v4l2 -video_size 1280x720 -framerate 25 -i /dev/video0 -vcodec h264_omx -keyint_min 0 -g 100 -map 0:v -b:v 1000k -f dash -min_seg_duration 4000 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 20 ' +  self.dash_file_path )
        
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 2 -i /dev/video0 -vcodec h264_omx -keyint_min 0 -g 100 -map 0:v -b:v 600k -f dash -min_seg_duration 4000 -use_template 1 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -window_size 5 -extra_window_size 10  ' +  self.dash_file_path )
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 -vcodec h264_omx -copyts -keyint_min 0 -g 10 -map 0:v -b:v 600k -f dash -use_template 1 -use_timeline 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -window_size 5 -extra_window_size 10  ' +  self.dash_file_path )
        
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 -muxdelay 0 -vcodec h264_omx -keyint_min 0 -g 10 -map 0:v -b:v 400k -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 ' +  self.dash_file_path )
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 -muxdelay 0 -vcodec h264_omx -keyint_min 0 -g 10 -map 0:v -b:v 400k -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 ' +  self.dash_file_path )
        
        # with audio:
        
        if self.DEBUG:
            print("Creating FFMEG dash command. self.encode_audio = " + str(self.encode_audio))
        ffmpeg_command = 'ffmpeg  -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 '
        ffmpeg_command += '-muxdelay 0  -keyint_min 0 -g 10 '
        if self.encode_audio:
            ffmpeg_command += '-f alsa -thread_queue_size 16 -ac 1 -ar 44100 -i dsnoop:1,0 '
        ffmpeg_command += '-map 0:v -b:v 400k -video_track_timescale 9000 '
        if self.encode_audio:
            ffmpeg_command += '-map 1:a -c:a aac -b:a 96k '
        
        ffmpeg_command += ' -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 '
        ffmpeg_command += self.ffmpeg_output_path
                 #+ self.dash_file_path
        
        if self.DEBUG:
            print("calling ffmpeg command: " + str(ffmpeg_command))
                 
                 
        run_command(ffmpeg_command,None)     # -thread_queue_size 16
        #os.system(ffmpeg_command)
        if self.DEBUG:
            print("beyond run ffmpeg")
        
        # -muxdelay 0
        # -re # realtime
        # -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 1:a -c:a aac -b:a 96k
        
        # -init_seg_name init-$RepresentationID$.mp4 -media_seg_name segment-$RepresentationID$-$Number$.mp4
        
        # -init_seg_name init-cam1-$RepresentationID$.mp4 -media_seg_name cam1-$RepresentationID$-$Number$.mp4
        
    
    def ffmpeg_mjpeg(self):
        if self.DEBUG:
            print("in ffmpeg_mjpeg")
        os.system('pkill ffmpeg')
        
        #os.system('ffmpeg -input_format yuyv422 -fflags nobuffer -vsync 0 -f video4linux2 -s 1280x720 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v h264_omx -r 10 -b:v 2M -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -f dash ' + self.dash_file_path + ' -remove_at_exit 1')
        #os.system('ffmpeg -input_format yuyv422 -fflags nobuffer -vsync 0 -f video4linux2 -s 1280x720 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v libx264 -r 10 -b:v:0 400k -profile:v:0 high -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -f dash ' + self.dash_file_path + ' ')
        #os.system('ffmpeg -input_format yuyv422 -fflags nobuffer -vsync 0 -f video4linux2 -s 1280x720 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v libx264 -r 10 -b:v:0 400k -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -f dash ' + self.dash_file_path + ' ')
        #os.system('ffmpeg -fflags nobuffer -vsync 0 -f video4linux2 -s 640x360 -r 10 -i /dev/video0 -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 0:0 -map 1:0 -c:a aac -b:a 96k -c:v libx264 -r 10 -b:v:0 400k -copyts -probesize 200000 -window_size 5 -extra_window_size 10 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -f dash ' + self.dash_file_path + ' ')
        
        
        # WORKS
        #os.system('ffmpeg -y -f v4l2 -video_size 1280x720 -framerate 25 -i /dev/video0 -vcodec h264_omx -keyint_min 0 -g 100 -map 0:v -b:v 1000k -f dash -min_seg_duration 4000 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 20 ' +  self.dash_file_path )
        
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 2 -i /dev/video0 -vcodec h264_omx -keyint_min 0 -g 100 -map 0:v -b:v 600k -f dash -min_seg_duration 4000 -use_template 1 -use_timeline 1 -use_template 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -window_size 5 -extra_window_size 10  ' +  self.dash_file_path )
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 -vcodec h264_omx -copyts -keyint_min 0 -g 10 -map 0:v -b:v 600k -f dash -use_template 1 -use_timeline 1 -hls_playlist 1 -format_options movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof -seg_duration 1 -dash_segment_type mp4 -remove_at_exit 1 -window_size 5 -extra_window_size 10  ' +  self.dash_file_path )
        
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 -muxdelay 0 -vcodec h264_omx -keyint_min 0 -g 10 -map 0:v -b:v 400k -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 ' +  self.dash_file_path )
        #os.system('ffmpeg -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 -muxdelay 0 -vcodec h264_omx -keyint_min 0 -g 10 -map 0:v -b:v 400k -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 ' +  self.dash_file_path )
        
        # with audio:
        
        if self.DEBUG:
            print("Creating FFMEG mjpeg command. self.encode_audio = " + str(self.encode_audio))
        ffmpeg_command = 'ffmpeg  -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 '
        #ffmpeg_command += '-muxdelay 0  -keyint_min 0 -g 10 '
        #if self.encode_audio:
        #    ffmpeg_command += '-f alsa -thread_queue_size 16 -ac 1 -ar 44100 -i dsnoop:1,0 '
        #ffmpeg_command += '-map 0:v -b:v 400k -video_track_timescale 9000 '
        #if self.encode_audio:
        #    ffmpeg_command += '-map 1:a -c:a aac -b:a 96k '
        
        #ffmpeg_command += ' -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 '
        
        ffmpeg_command += '-c:v mjpeg -q:v 3 -huffman optimal -an '
        ffmpeg_command += self.mjpeg_file_path #self.ffmpeg_output_path
                 #+ self.dash_file_path
        
        if self.DEBUG:
            print("calling ffmpeg_mjpeg command: " + str(ffmpeg_command))
                 
                 
        run_command(ffmpeg_command,None)     # -thread_queue_size 16
        #os.system(ffmpeg_command)
        if self.DEBUG:
            print("beyond run ffmpeg_mjpeg")
        
        # -muxdelay 0
        # -re # realtime
        # -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 1:a -c:a aac -b:a 96k
        
        # -init_seg_name init-$RepresentationID$.mp4 -media_seg_name segment-$RepresentationID$-$Number$.mp4
        
        # -init_seg_name init-cam1-$RepresentationID$.mp4 -media_seg_name cam1-$RepresentationID$-$Number$.mp4
        
        
        
    
    def kill_ffmpeg(self):
        try:
            ffmpeg_check_command = 'ps -aux | grep media/candlecam/stream/index.mpd | grep -v "grep"'
            ffmpeg_check = subprocess.run(ffmpeg_check_command, shell=True, capture_output=True)
            ffmpeg_check = ffmpeg_check.stdout
            ffmpeg_check = ffmpeg_check.decode('utf-8')
            if self.DEBUG:
                print(str("ffmpeg_check = " + str(ffmpeg_check)))
            pid = re.match("^pi\s*([0-9]*)\s", ffmpeg_check)

            if pid:
                if self.DEBUG:
                    print("stopping pid: " + str(pid.groups()[0]))
                os.system( 'kill ' + str(pid.groups()[0]) )
        
        except Exception as ex:
            print("Error trying to find and stop running ffmpeg: " + str(ex))
    """
        
        
    def run_picamera(self):   
        if self.DEBUG:
            print("in run_picamera") 
        #self.picam = picamera.PiCamera(resolution='720p', framerate=10)
        #self.picam.exposure_mode = 'auto'
        #self.picam.awb_mode = 'auto'
        global streaming
        global frame
        frame = b''
        
        print("run picamera: streaming global: " + str(streaming))
        try:
            #self.picam.start_preview()
            # Give the camera some warm-up time
            #time.sleep(2)
            #self.output = StreamOutput(self,self.mjpeg_file_path)
            #if self.DEBUG:
            #    print("run_picamera: start stream capture")
            #self.picam.start_recording(self.output, format='mjpeg')
            
            self.picam = picamera.PiCamera(resolution=(640,480), framerate=15)
            self.picam.exposure_mode = 'auto'
            self.picam.awb_mode = 'auto'
            
            #with picamera.PiCamera(resolution='720p', framerate=10) as self.picam:
            #    self.picam.exposure_mode = 'auto'
            #    self.picam.awb_mode = 'auto'
                
                # let camera warm up
            #    time.sleep(2)
                
            #streaming = True
            """
            stream = io.BytesIO()
            for _ in self.picam.capture_continuous(stream, 'jpeg', use_video_port=True):
                
                
                
                # return current frame
                stream.seek(0)
                frame = stream.read()
                
                # reset stream for next frame
                stream.seek(0)
                stream.truncate()
                
                if self.take_a_photo: # TODO: or if continous periodic recording should be active, perhaps while in security mode?
                    if self.DEBUG:
                        print("\nself.take_a_photo was True.")
                    self.take_a_photo = False

                    filename = str(int(time.time())) + '.jpg'
                    file_path = os.path.join( self.data_photos_dir_path,filename)
                    # This stores a jpg as mjpeg on the SD card. Technically it could then be accessed via the Webthings standard.. if the remote location has a valid JWT. 
                    # TODO: could be a security feature in the future
                    if time.time() - 1 > self.last_write_time:
                        #if self.DEBUG:
                        if self.DEBUG:
                            print("- Saving a photo from the picamera stream")
                        self.last_write_time = time.time()
                        #with open(self.mjpeg_file_path, "wb") as binary_file: # if continous storage for mjpeg serving via webthings standard is required
                        with open(file_path, "wb") as binary_file:
                            #print("saving jpg as mjpeg")
                            binary_file.write(frame)
                            
                        # We end up here if the "shortcut" option was used to quickly save a snapshot from the local camera
                        if self.send_to_matrix:
                            if os.path.isdir(self.matrix_drop_dir) and os.path.isfile(file_path):
                                if self.DEBUG:
                                    print("sending file to Matrix via Voco")
                                drop_file_path = os.path.join(self.matrix_drop_dir, "Candlecam_" + socket.gethostname().lower() + '_' + filename)
                                os.system('cp ' + file_path + ' ' + drop_file_path)
                            
                #if streaming == False or self.persistent_data['streaming'] == False:
                #    print("picamera: stopping streaming")
                #    break
                stream.truncate()
            
            """
            print("picamera should now be up")
            
        except Exception as ex:
           print('ERROR. run_picamera: Error setting up recording: ' + str(ex))
        
        #try:
        #    while self.persistent_data['streaming']:
        #        self.picam.wait_recording(2)
        #except Exception as ex:
        #    print("ERROR. run_picamera: Error while getting image data from camera module: " + str(ex))
        #self.picam.stop_recording()
        #self.output.close()
        if self.DEBUG:
            print("at end of picamera thread. Does it close now?")
        #self.join()
        
        
    # Not useful on Raspian Bullseye yet, as libcamera has no python support yet...
    
    """
    def run_picamera_libcamera(self):
        if self.DEBUG:
            print("in run_picamera. Should probably create mjpeg stream now.")
        
        
        if self.encode_audio == False:
            mjpeg_stream_command = 'libcamera-vid --codec mjpeg -o ' + str(self.mjpeg_file_path) + ' -n --width 640 --height 480'
            if self.DEBUG:
                print("Starting MJPEG stream with command: " + str(mjpeg_stream_command))
            run_command(mjpeg_stream_command, None)
    """
        
        
    



    
    
    
    
    
    
    
    
    
    
    
    
    
                    
                    
                    
    def move_cover(self,state,save=True):
        if self.has_respeaker_hat and self.camera_available:
            
            if state == 'closed':
                #self.set_led(self.persistent_data['led_color'],self.persistent_data['led_brightness'],False)
                try:
                    if self.DEBUG:
                        print("closing cover?: " + str(self.servo_closed_position))
                    self.pwm.ChangeDutyCycle(70)
                    if self.DEBUG:
                        print("set servo to closed (1)")
                except Exception as ex:
                    if self.DEBUG:
                        print("could not set servo: " + str(ex))
                    
            elif state == 'open':
                #self.set_led('#ff0000',30,False) # set LED to full brightness.
                try:
                    if self.DEBUG:
                        print("opening cover?: " + str(self.servo_open_position))
                    self.pwm.ChangeDutyCycle(1)
                    if self.DEBUG:
                        print("set servo to open (70)")
                except Exception as ex:
                    if self.DEBUG:
                        print("could not set servo: " + str(ex))
    
            elif state == 'maintenance':
                try:
                    self.pwm.ChangeDutyCycle(100)
                    if self.DEBUG:
                        print("set servo to maintenance (100)")
                except Exception as ex:
                    if self.DEBUG:
                        print("could not set servo: " + str(ex))
        
        else:
            if self.DEBUG:
                print("no hat and/or no camera, so no need to move the servo")
        #if self.politeness:
        #    state = 'closed'
        if save:
            self.persistent_data['cover_state'] = state
            self.save_persistent_data()



    def politeness_change(self,politeness_state):
        if self.DEBUG:
            print("in politeness, state changes to: " + str(politeness_state))
        self.persistent_data['politeness'] = politeness_state
        self.save_persistent_data()
        
        if self.pressed_countdown == 0:
            self.move_cover('closed')
            self.streaming_change(False)

        try:
            self.adapter.candlecam_device.properties["politeness"].update(politeness_state)
        except Exception as ex:
            print("Error setting politeness_state on thing: " + str(ex))

        

    def volume_change(self,ringtone_volume):
        if self.DEBUG:
            print("new ringtone_volume: " + str(ringtone_volume))
        self.persistent_data['ringtone_volume'] = ringtone_volume
        self.save_persistent_data()            

        try:
            self.adapter.candlecam_device.properties["ringtone_volume"].update(ringtone_volume)
        except Exception as ex:
            print("Error setting ringtone volume on thing: " + str(ex))
        
        

    def streaming_change(self,state):
        if self.DEBUG:
            print("in streaming_changereally. new streaming state: " + str(state))
            #print("self.encode_audio: " + str(self.encode_audio))
        
        if self.camera_available == False:
            print("no camera available")
            return
        
        global streaming
        streaming = state
        #self.streaming = state
        self.persistent_data['streaming'] = state
    
        if state:
            pass
            #self.snapshot1 = tracemalloc.take_snapshot()
        else:
            
            """
            self.snapshot2 = tracemalloc.take_snapshot()
            if self.snapshot1 != None:
                top_stats = self.snapshot2.compare_to(self.snapshot1, 'lineno')
                print("[ Top 10 differences ]")
                for stat in top_stats[:10]:
                    print(stat)
            """
        
            collected = gc.collect()
 
            # Prints Garbage collector
            # as 0 object
            print("Garbage collector: collected",
                      "%d objects." % collected)
        
        
        # START STREAMING
        if state:
            if self.DEBUG:
                print("")
                print("STREAMING ON")
            
            self.set_led('#ff0000',self.persistent_data['led_brightness'],False)
            
            self.move_cover('open')
            
        # STOP STREAMING
        else:
            if self.DEBUG:
                print("")
                print("STREAMING OFF")
            
            
            
            """
            try:
                if self.ffmpeg_process != None:
                    self.ffmpeg_process.terminate()
                    if self.DEBUG:
                        print("ffmpeg process terminated command sent")
                    self.ffmpeg_process.kill()
                    if self.DEBUG:
                        print("ffmpeg process kill command sent")
                    self.ffmpeg_process.wait()
                    if self.DEBUG:
                        print("ffmpeg process terminated?")
                    
                    self.kill_ffmpeg()
                
            except Exception as ex:
                print("stop streaming ffmpeg error: " + str(ex))
            """

            # should also stop libcamera-vid cleanly...
            
            # set LED color back to user preference
            self.set_led(self.persistent_data['led_color'],self.persistent_data['led_brightness'], False)
            
            self.move_cover('closed')
        
        
        try:
            if self.DEBUG:
                print("updating streaming state on adapter thing")
            self.adapter.candlecam_device.properties["streaming"].update(state)
        except Exception as ex:
            print("Error setting streaming state on thing: " + str(ex))
        
        self.save_persistent_data()



                   
    def ringtone_change(self,choice):
        if self.DEBUG:
            print("\nnew ringtone choice: " + str(choice))
        self.persistent_data['ringtone'] = choice
        self.save_persistent_data()
        self.play_ringtone()
        
        try:
            #if self.thingy != None:
             #   print("\n Thingy ringtone should get updated now...")
                #self.ringtone_value.notify_of_external_update(choice)
            
            #self.get_loop()
            #print("ringtone prop: " + str(dir(self.thingy.properties["ringtone"])))
            #print("ringtone value prop: " + str(dir(self.thingy.properties["ringtone"].value)))
            
            #print("self.thingy.properties[ringtone].get_value(): " + str(self.thingy.properties["ringtone"].get_value()))
            #if self.thingy.properties["ringtone"].get_value() != choice:
            #    if self.DEBUG:
            #        print("ringtone_change: routing to thingy, since it was not in this state")
            #    time.sleep(.5)
            #    #self.thingy.properties["ringtone"].value.set(choice) # this will cause streaming_change to be called again, but this time from the thingy
            #    self.thingy.properties["ringtone"].value.notify_of_external_update(choice)
        
        
            self.adapter.candlecam_device.properties["ringtone"].update(choice)
        except Exception as ex:
            print("Error setting ringtone on thing: " + str(ex))
            
        



    def play_ringtone(self):
        if self.DEBUG:
            print('in play_ringtone')
        try:
            if str(self.persistent_data['ringtone']) != 'none':
                ringtone_command = 'aplay -M -D plughw:' + str(self.plughw_number) + ' ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) + str(self.persistent_data['ringtone_volume'])+  '.wav'
                # --buffer-time=8000
                #ringtone_command = 'SDL_AUDIODRIVER="alsa" AUDIODEV="hw:1,0" ffplay ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) +  '.mp3'
                #ringtone_command = 'ffplay -autoexit ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) +  '.mp3'
            
                if self.DEBUG:
                    print("ringtone command: " + str(ringtone_command))
            
                ringtone_command_array = ringtone_command.split()
        
                if self.DEBUG:
                    print('running ringtone split command:' + str(ringtone_command_array))
                
                #self.ringtone_process = subprocess.Popen(ringtone_command_array)
                os.system(ringtone_command + " &")
                
        except Exception as ex:
            print("Error playing ringtone: " + str(ex))

        
        
    def set_led(self,hex,brightness,save=True): # sometimes the color should not be save saved, E.g. when the led turns red temporarily when the button is pressed
        if self.DEBUG:
            print("setting led color to: " + str(hex))
            print("setting led brightness to: " + str(brightness) + "%")
            #print("self.lights = " + str(self.lights))
        
        if save:
            self.persistent_data['led_color'] = hex
            self.persistent_data['led_brightness'] = brightness
            self.save_persistent_data()
        
            try:
                self.adapter.candlecam_device.properties["led_color"].update(str(hex))
            except Exception as ex:
                print("Error setting color on thing: " + str(ex))

            try:
                self.adapter.candlecam_device.properties["led_brightness"].update(int(brightness))
            except Exception as ex:
                print("Error setting led brightness on thing: " + str(ex))
        
        
        # make sure the red LED light is always on while streaming
        if self.persistent_data['streaming']:
            self.set_leds_really(hex,brightness)
            time.sleep(1)
            hex = '#ff0000'
            if brightness < 10:
                brightness = 10
        
        self.set_leds_really(hex,brightness)
        
        
    def set_leds_really(self,hex,brightness):
        try:
            hex = hex.lstrip('#')
            rgb = tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))

            r = rgb[0]
            g = rgb[1]
            b = rgb[2]
        
            #brightness = brightness / 100 # requires values between 0 and 1
            
            if self.DEBUG:
                print('RGB =', str(rgb))
                print('Brightness =', str(brightness))
            
            if self.lights:
                self.lights.set_pixel(0, r, g, b, brightness)  # Pixel 1
                self.lights.set_pixel(1, r, g, b, brightness)  # Pixel 2
                self.lights.set_pixel(2, r, g, b, brightness)  # Pixel 3
                self.lights.show()
            else:
                print("set_led: lights was None?")
            
        except Exception as ex:
            print("could not set LED brightness: " + str(ex))


        

    
                    
                    

    # Read the settings from the add-on settings page
    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database(self.addon_name)
            if not database.open():
                print("Could not open settings database")
                return
            
            config = database.load_config()
            database.close()
            
        except Exception as ex:
            print("Error! Failed to open settings database: " + str(ex))
        
        if not config:
            print("Error loading config from database")
            return
        
        if 'Debugging' in config:
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("-Debugging preference was in config: " + str(self.DEBUG))
        
        if self.DEBUG:
            print(str(config))
            
            
        
            
        #if 'Use microphone' in config:
        #    self.encode_audio = bool(config['Use microphone'])
        #    if self.DEBUG:
        #        print("-Encode audio preference was in config: " + str(self.DEBUG))
        
        #if 'Use ramdrive' in config:
        #    self.use_ramdrive = bool(config['Use ramdrive'])
        #    if self.DEBUG:
        #        print("-Use ramdrive preference was in config: " + str(self.DEBUG))
        
                
        if 'Portrait mode' in config:
            self.portrait_mode = bool(config['Portrait mode'])
            if self.DEBUG:
                print("-Portait mode preference was in config: " + str(self.portrait_mode))

        if 'High resolution' in config:
            self.hires = bool(config['High resolution'])
            
            if self.DEBUG:
                print("-High resolution preference was in config: " + str(self.hires))
            
            if self.hires:
                self.maximum_connections = 1
                if self.DEBUG:
                    print("- set maximum connections to 1")
                

        #if 'Interval' in config:
        #    self.interval = int(config['Interval'])
        #    if self.DEBUG:
        #        print("-Interval preference was in config: " + str(self.interval))



        if 'Send snapshots to Matrix messenger' in config:
            self.send_to_matrix = bool(config['Send snapshots to Matrix messenger'])
            if self.DEBUG:
                print("-Send snapshots to Matrix messenger preference was in config: " + str(self.send_to_matrix))

        if 'Send snapshots to printer' in config:
            self.send_snapshots_to_printer = bool(config['Send snapshots to printer'])
            if self.DEBUG:
                print("-Send snapshots to printer preference was in config: " + str(self.send_snapshots_to_printer))



#
#  NETWORK SCAN
#
    def network_scan(self): # looks for Candlecams on the local network
        if self.DEBUG:
            print("\n\nIn NETWORK SCAN")
            
        if self.busy_doing_network_scan:
            if self.DEBUG:
                print("- already doing scan, returning existing dict")
            return self.gateways_ip_dict
            
        if (self.last_network_scan_time + 300) < time.time():
            self.last_network_scan_time = int(time.time())
            self.busy_doing_network_scan = True
            if self.DEBUG:
                print("doing a fresh network scan")
            gateways_ip_dict = {}
            try:
                # Satellite targets
                gateways_ip_dict = arpa_detect_gateways()
                if self.DEBUG:
                    print("- arpascan result: " + str(gateways_ip_dict))
        
                if self.camera_available:
                    gateways_ip_dict[self.own_ip] = socket.gethostname()
        
                satellite_targets = {}
                for ip_address in gateways_ip_dict: # server = ip address
                
                    if ip_address == self.own_ip:
                        if self.DEBUG:
                            print("skipping checking own IP")
                            continue
                        
                    if self.DEBUG:
                        print("checking server ip_address: " + str(ip_address))
                
                    try:
                        #stream_url = 'http://' + ip_address + ':8889/media/candlecam/stream/stream.mjpeg';
                        #r = requests.get(stream_url)
                        #if self.DEBUG:
                        #    print("status code: " + str(r.status_code))
                        #if r.status_code == 200:
                        nbtscan_output = subprocess.check_output(['sudo','nbtscan','-q',str(ip_address)])
                        nbtscan_output = nbtscan_output.decode('utf-8')
                        if self.DEBUG:
                            print("nbtscan_output: " + str(nbtscan_output))
                    
                        if len(nbtscan_output) > 10:
                            if self.DEBUG:
                                print("nbtscan_output: " + str(nbtscan_output))
                            shorter = nbtscan_output.split(" ",1)[1]
                            shorter = shorter.lstrip()
                            parts = shorter.split()
                            gateways_ip_dict[ip_address] = parts[0]
                    except Exception as ex:
                        print("Error while checking server IP address: " + str(ex))
            
                if self.DEBUG:
                    print("\nnew gateways_ip_dict: " + str(gateways_ip_dict))
        
                self.gateways_ip_dict = gateways_ip_dict
            except Exception as ex:
                print("Error in network_scan: " + str(ex))
            
            self.busy_doing_network_scan = False
            
            if len(gateways_ip_dict.keys()) == 0:
                last_network_scan_time = 0
                
            return gateways_ip_dict
        
        else:
            if self.DEBUG:
                print("Returning previous network scan results")
            return self.gateways_ip_dict




    def check_photo_printer(self):
        if self.DEBUG:
            print("Checking if a bluetooth photo printer is paired")

        try:
            if os.path.isdir(self.external_picture_drop_dir):
                if self.DEBUG:
                    print("privacy manager photo drop-off dir existed")
                bluetooth_printer_check = run_command('sudo bluetoothctl paired-devices')
                if self.DEBUG:
                    print("bluetooth_printer_check: " + str(bluetooth_printer_check))
                if 'peripage' in bluetooth_printer_check.lower():
                    self.photo_printer_available = True
                    if self.DEBUG:
                        print("paired bluetooth printer was detected")
                    return True
            else:
                if self.DEBUG:
                    print("privacy manager photo drop-off dir did not exist, so no photo printing capability available")
                    
        except Exception as ex:
            print("Error while checking photo printer: " + str(ex))
        
        self.photo_printer_available = False
        return False


    def try_sending_to_printer(self, filename):
        if self.DEBUG:
            print("in try_sending_to_printer")
        try:
            if self.send_snapshots_to_printer:
                if self.DEBUG:
                    print("should send snapshot to printer: " + str(filename))
                if self.check_photo_printer():
                    if self.DEBUG:
                        print("- Paired bluetooth printer detected")
                    from_filename = os.path.join(self.data_photos_dir_path, filename)
                    if os.path.isfile(from_filename):
                        if os.path.isdir(self.external_picture_drop_dir):
                            to_filename = os.path.join(self.external_picture_drop_dir, filename)
                            copy_command = 'cp -n ' + str(from_filename) + ' ' + str(to_filename)
                            if self.DEBUG:
                                print("copy_command: " + str(copy_command))
                            os.system(copy_command)
                        else:
                            if self.DEBUG:
                                print("photo drop dir (no longer) exists?")
                    else:
                        if self.DEBUG:
                            print("Could not send to printer: filename not found")
                else:
                    if self.DEBUG:
                        print("Could not send to printer: no bluetooth printer paired?")
        except Exception as ex:
            print("Error while sending to photo printer: " + str(ex))

#
#  HANDLE REQUESTS TO API
#
    def handle_request(self, request):
        """
        Handle a new API request for this handler.

        request -- APIRequest object
        """
        
        try:
            
            if self.ready == False:
                time.sleep(4)
            
            if request.method != 'POST':
                return APIResponse(status=404)
            
            if request.path == '/ajax' or request.path == '/list' or request.path == '/delete':

                try:
                    if request.path == '/ajax':
                        if self.DEBUG:
                            print("Ajax")
                        
                            
                        try:
                            action = str(request.body['action'])    
                            
                            if action == 'init': # /init
                                state = True
                                if self.DEBUG:
                                    print('ajax handling init')
                                    print("self.persistent_data = " + str(self.persistent_data))
                                
                                try:
                                    self.gateways_ip_dict = self.network_scan()
                                except Exception as ex:
                                    print("Error gettings gateways dict: " + str(ex))
                                    state = False
                                
                                try:
                                    photos_list = self.scan_photo_dir()
                                    if isinstance(photos_list, str):
                                        state = False
                                except Exception as ex:
                                    print("Error scanning for existing photos: " + str(ex))
                                    photos_list = []
                                    
                                    
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  #content=json.dumps({'state' : True, 'message' : 'initialisation complete', 'thing_settings': self.persistent_data['thing_settings'] }),
                                  content=json.dumps({'state': state, 'own_ip': self.own_ip, 'message': 'initialization complete', 'thing_settings': self.persistent_data['thing_settings'], 'gateways':self.gateways_ip_dict, 'photos':photos_list, 'camera_available':self.camera_available,'webthings_addon_detected':self.webthings_addon_detected }),
                                )
                                
                                
                            elif action == 'save_settings':
                                
                                self.persistent_data['thing_settings'] = request.body['thing_settings'] 
                                if self.DEBUG:
                                    print("self.persistent_data['thing_settings'] = " + str(self.persistent_data['thing_settings'])) 
                                self.save_persistent_data()
                                 
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : True, 'message': 'settings saved succesfully'}),
                                )
                                
                                
                            elif action == 'grab_picture_from_stream':
                                state = False
                                photos_list = []
                                try:
                                    if 'stream_url' in request.body:
                                        stream_url = str(request.body['stream_url'])    
                                    
                                        state = self.grab_snapshots(stream_url)
                                            
                                        time.sleep(1)
                                        try:
                                            photos_list = self.scan_photo_dir()
                                            if isinstance(photos_list, str):
                                                state = False
                                                photos_list = []
                                        except Exception as ex:
                                            print("Error scanning for existing photos: " + str(ex))
                                            photos_list = []
                                            
                                except Exception as ex:
                                    if self.DEBUG:
                                        print("error grabbing image from stream: " + str(ex))
                            
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'message': '','photos':photos_list}),
                                )
                            
                            
                            elif action == 'delete_all':
                                if self.DEBUG:
                                    print("DELETING ALL")
                                state = False
                                data = []
                                #target_data_type = self.data_types_lookup_table[int(request.body['property_id'])]
                                #print("target data type from internal lookup table: " + str(target_data_type))
                                # action, data_type, property_id, new_value, old_date, new_date
                                try:
                                    data = self.delete_all()
                                    if isinstance(data, str):
                                        state = False
                                    else:
                                        state = True
                                except Exception as ex:
                                    print("Error handling delete_all: " + str(ex))
                        
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'data' : data}),
                                )
                                
                            
                            
                            """
                            elif action == 'download_snapshot':
                                state = False
                                photos_list = []
                                try:
                                    if 'snapshot_url' in request.body:
                                        snapshot_url = str(request.body['snapshot_url'])    
                                    
                                        if snapshot_url.endswith('.jpg') or snapshot_url.endswith('.jpeg'):
                                            state = self.download_snapshot(snapshot_url)
                                            
                                        time.sleep(1)
                                        try:
                                            photos_list = self.scan_photo_dir()
                                            if isinstance(photos_list, str):
                                                state = False
                                                photos_list = []
                                        except Exception as ex:
                                            print("Error scanning for existing photos: " + str(ex))
                                            photos_list = []
                                            
                                except Exception as ex:
                                    if self.DEBUG:
                                        print("error downloading snapshot: " + str(ex))
                            
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'message': '','photos':photos_list}),
                                )
                             """
                            
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error getting init data: " + str(ex))
                            return APIResponse(
                              status=500,
                              content_type='application/json',
                              content=json.dumps("Error while getting thing data: " + str(ex)),
                            )
                    
                    
                    
                    if request.path == '/list':
                        if self.DEBUG:
                            print("LISTING")
                        # Get the list of photos
                        try:
                            
                            #self.camera.capture(self.photos_file_path, use_video_port=True)
                            
                            data = self.scan_photo_dir()
                            if isinstance(data, str):
                                state = 'error'
                            else:
                                state = 'ok'
                            
                            return APIResponse(
                              status=200,
                              content_type='application/json',
                              content=json.dumps({'state' : state, 'data' : data}),
                            )
                        except Exception as ex:
                            print("Error getting init data: " + str(ex))
                            return APIResponse(
                              status=500,
                              content_type='application/json',
                              content=json.dumps("Error while getting thing data: " + str(ex)),
                            )
                            
                            
                            
                    elif request.path == '/delete':
                        if self.DEBUG:
                            print("DELETING")
                        try:
                            data = []
                            #target_data_type = self.data_types_lookup_table[int(request.body['property_id'])]
                            #print("target data type from internal lookup table: " + str(target_data_type))
                            # action, data_type, property_id, new_value, old_date, new_date
                            data = self.delete_file( str(request.body['filename']) )
                            if isinstance(data, str):
                                state = 'error'
                            else:
                                state = 'ok'
                            
                            return APIResponse(
                              status=200,
                              content_type='application/json',
                              content=json.dumps({'state' : state, 'data' : data}),
                            )
                        except Exception as ex:
                            print("Error getting thing data: " + str(ex))
                            return APIResponse(
                              status=500,
                              content_type='application/json',
                              content=json.dumps("Error while changing point: " + str(ex)),
                            )
                            
                            
                            
                        
                        
                    else:
                        return APIResponse(
                          status=500,
                          content_type='application/json',
                          content=json.dumps("API error"),
                        )
                        
                        
                except Exception as ex:
                    if self.DEBUG:
                        print("general api error: " + str(ex))
                    return APIResponse(
                      status=500,
                      content_type='application/json',
                      content=json.dumps("Error"),
                    )
                    
            else:
                return APIResponse(status=404)
                
        except Exception as e:
            print("Failed to handle UX extension API request: " + str(e))
            return APIResponse(
              status=500,
              content_type='application/json',
              content=json.dumps("API Error"),
            )
        



    def unload(self):
        if self.DEBUG:
            print("Shutting down")
        self.running = False
            
        try:
            if self.picam != None:
                #self.picam.stop_recording()
                #self.output.close()
                #self.picam.stop_preview()
                self.picam.close()
        except Exception as ex:
            print("Unload: stopping picamera error: " + str(ex))
            
        if self.thing_server != None:
            self.thing_server.stop()
            
        #os.system('pkill libcamera-jpeg')
        #os.system('pkill libcamera-vid')
        
        try:
            if self.pwm != None:
                self.pwm.stop()
            #self.pi.stop()
            
        except Exception as ex:
            print("Unload: stopping GPIO error: " + str(ex))
        
        try:
            if self.ffmpeg_process != None:
                poll = self.ffmpeg_process.poll()
                if self.DEBUG:
                    print("poll = " + str(poll))
                if poll == None:
                    if self.DEBUG:
                        print("poll was None - ffmpeg is still running.")
                    self.ffmpeg_process.terminate()
                    if self.DEBUG:
                        print("past terminate")
                    self.ffmpeg_process.wait()
                    if self.DEBUG:
                        print("past wait")
                else:
                    print("poll was not none - ffmpeg crashed earlier?")
                    
                self.kill_ffmpeg() # for good measure
        except Exception as ex:
            print("Unload: terminating ffmpeg_process error: " + str(ex))

        #time.sleep(1)
        if self.ramdrive_created:
            print("unmounting ramdrive")
            os.system('sudo umount ' + self.media_stream_dir_path)
            if self.DEBUG:
                print("candlecam ramdrive unmounted")



    
    # If the 'take snapshot' button is pressed on the webthingy
    def thingy_take_snapshot(self,state):
        if self.DEBUG:
            print("\nHERE\nin thingy_take_snapshot. state: " + str(state))
        if state:
            #global taking_a_photo_countdown
            if self.taking_a_photo_countdown == 0:
                self.taking_a_photo_countdown = self.taking_a_photo_countdown_start
            #self.grab_snapshots(self.own_mjpeg_url)
            # Switch thingy snapshot button back to off        
    
    
    # From UI, takes snapshots from all discovered cameras unless a specific stream URL is specified
    def grab_snapshots(self,url=None):
        if self.DEBUG:
            print("in grab_snapshots. url?: " + str(url))
        
        try:
            stream_urls = []
            if url == None:
                for ip in self.gateways_ip_dict.keys():
                    stream_urls.append('http://' + ip + ':8889/media/candlecam/stream/stream.mjpeg')
            else:
                stream_urls = [url]
            
            if self.DEBUG:
                print("grab_snapshots: stream_urls: " + str(stream_urls))
        
            for stream_url in stream_urls:
                if stream_url.endswith('mjpg') or stream_url.endswith('mjpeg'):
            
                    if '/media/candlecam/stream/stream.mjpeg' in stream_url:
                        stream_url = stream_url.replace('/media/candlecam/stream/stream.mjpeg','/snapshot.jpg')
                        state = self.download_snapshot(stream_url)
                    else:
                        state = self.grab_mjpeg_frame(stream_url)
        except Exception as ex:
            print("error grabbing snapshots: " + str(ex))
            return False
        
        return True


    def grab_mjpeg_frame(self, stream_url):
        found_jpeg = False
        filename = ""
        result = False
        try:
            
            looking_for_jpeg = True
            looking_loops_counter = 0
            
            if self.DEBUG:
                print("grabbing jpeg from: " + str(stream_url))
            
            # If we're asked to grab a frame from our own stream, then take a shortcut by asking picamera to save a photo.
            if stream_url == self.own_mjpeg_url:
                if self.DEBUG:
                    print("target mjpeg stream url is own mjpeg stream url. Taking shortcut.")
                #self.take_a_photo = True
                #global taking_a_photo_countdown
                
                if self.taking_a_photo_countdown == 0:
                    self.taking_a_photo_countdown = self.taking_a_photo_countdown_start
                result = True
            
            else:
            
                stream = requests.get(stream_url, stream=True)
                if stream.ok:
                    a = -1
                    b = -1
                    chunk_size = 1024
                    fresh_bytes = b''
                    for chunk in stream.iter_content(chunk_size=chunk_size):
                        fresh_bytes += chunk
                        try:
                            looking_loops_counter += 1
                            #if self.DEBUG:
                            #    print(str(looking_loops_counter))
                        
                            if looking_loops_counter > 1000:
                                looking_for_jpeg = False
                                if self.DEBUG:
                                    print("Warning, reached maximum looking_loops_counter")
                                break
                            
                            if a == -1:
                                a = fresh_bytes.find(b'\xff\xd8')
                            b = fresh_bytes.find(b'\xff\xd9')
                            #if self.DEBUG:
                            #    print("bytes read. a: " + str(a))
                            #    print("bytes read. b: " + str(b))
                            if a != -1 and b != -1:
                                jpg = fresh_bytes[a:b+2]
                                fresh_bytes = fresh_bytes[b+2:]
                
                                filename = str(int(time.time())) + '.jpg'
                                file_path = os.path.join( self.data_photos_dir_path,filename)
                                with open(file_path, "wb") as fh:
                                    fh.write(jpg)
                                found_jpeg = True
                                result = True
                                looking_for_jpeg = False
                                if self.DEBUG:
                                    print("looking loops required: " + str(looking_loops_counter))
                            
                                # Copy into matrix drop-off dir, if it exists
                                if os.path.isdir(self.matrix_drop_dir) and os.path.isfile(file_path):
                                    drop_file_path = os.path.join(self.matrix_drop_dir, "Candlecam_" + filename)
                                    os.system('cp ' + file_path + ' ' + drop_file_path)
                            
                                # Print to bluetooth printer if so desired
                                self.try_sending_to_printer(filename)
                            
                                break
                            
                        except Exception as ex:
                            print("Error in grab_mjpeg_frame for-loop: " + str(ex))
                        
        except Exception as ex:
            print("Error in grab_mjpeg_frame: " + str(ex))
        return result



    def download_snapshot(self,snapshot_url):
        if self.DEBUG:
            print("in download_snapshot with snapshot_url: " + str(snapshot_url))
        try:
            
            if snapshot_url == self.own_snapshot_url:
                if self.DEBUG:
                    print("target snapshot url is own snapshot url. Taking shortcut.")
                #self.take_a_photo = True
                
                #global taking_a_photo_countdown
                
                if self.taking_a_photo_countdown == 0:
                    self.taking_a_photo_countdown = self.taking_a_photo_countdown_start
                return True
            
            else:
            
                with requests.get(snapshot_url) as response:
                    #response.raise_for_status()
            
                    filename = str(int(time.time())) + '.jpg'
                    file_path = os.path.join( self.data_photos_dir_path,filename)
                    if self.DEBUG:
                        print("downloading snapshot to: " + str(file_path))
                    with open(file_path, 'wb') as f:
                        #for chunk in r.iter_content(chunk_size=8192): 
                            # If you have chunk encoded response uncomment if
                            # and set chunk_size parameter to None.
                            #if chunk: 
                            #f.write(chunk)
                        f.write(response.content)
                
                    if self.DEBUG:
                        print("snapshot written to disk succesfully?: " + str(os.path.isfile(file_path)))
                
                    # Also send to Matrix
                    if self.send_to_matrix:
                        if self.DEBUG:
                            print("- sending snapshot to Matrix is allowed")
                            print("- file to send: " + str(file_path))
                            print("- self.matrix_drop_dir: " + str(self.matrix_drop_dir))
                        if os.path.isdir(self.matrix_drop_dir) and os.path.isfile(file_path):
                            if self.DEBUG:
                                print("- Voco's Matrix drop-off dir exists")
                            drop_file_path = os.path.join(self.matrix_drop_dir, "Candlecam_" + filename)
                            if self.DEBUG:
                                print("drop_file_path: " + str(drop_file_path))
                            os.system('cp ' + file_path + ' ' + drop_file_path)
                        else:
                            if self.DEBUG:
                                print("matrix drop-off dir doesn't exist, or the snapshot wasn't saved")
                
                    # Print to bluetooth printer if so desired
                    self.try_sending_to_printer(filename)
                
                    return True
        except Exception as ex:
            print("Error in download_snapshot: " + str(ex))

        return False


    # DELETE A FILE
    
    def delete_file(self,filename):
        result = "error"
        try:
            file_path = os.path.join(self.data_photos_dir_path, str(filename))
            os.remove(file_path)
            result = self.scan_photo_dir()
        except Exception as ex:
            if self.DEBUG:
                print("Error deleting photo: " + str(ex))
        
        return result


    def scan_photo_dir(self):
        result = []
        try:
            for fname in os.listdir(self.data_photos_dir_path):
                if fname.endswith(".jpg") or fname.endswith(".jpeg") or fname.endswith(".gif"):
                    result.append(fname)    
        except:
            print("Error scanning photo directory")
        
        return result

    
    def delete_all(self):
        result = []
        try:
            for fname in os.listdir(self.data_photos_dir_path):
                file_path = os.path.join(self.data_photos_dir_path,fname)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print("- deleted: " + str(file_path))
        except:
            print("Error deleting files in photo directory")
        
        return self.scan_photo_dir()


            

    #
    #  PERSISTENCE
    #

    def save_persistent_data(self):
        if self.DEBUG:
            print("Saving to persistence data store at path: " + str(self.persistence_file_path))
            
        try:
            if not os.path.isfile(self.persistence_file_path):
                open(self.persistence_file_path, 'a').close()
                if self.DEBUG:
                    print("Created an empty persistence file")
            else:
                if self.DEBUG:
                    print("Persistence file existed. Will try to save to it.")

            with open(self.persistence_file_path) as f:
                #if self.DEBUG:
                #    print("saving persistent data: " + str(self.persistent_data))
                json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                if self.DEBUG:
                    print("Data stored")
                return True

        except Exception as ex:
            print("Error: could not store data in persistent store: " + str(ex) )
            print(str(self.persistent_data))
            return False
    


    def get_loop(self):
        
        
        try:
            loop = asyncio.get_running_loop()
            asyncio.set_event_loop(loop)
        except Exception as ex:
            if self.DEBUG:
                print("ERROR, using get_running_loop failed: " + str(ex))
            
            try:
                loop = tornado.ioloop.IOLoop.current()
                asyncio.set_event_loop(loop)
            except Exception as ex:
                if self.DEBUG:
                    print("ERROR, using tornado.ioloop.IOLoop.current failed: " + str(ex))
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                    
                
        """
        if self.loop != None:
            #return self.loop
            print("get_loop:  self.loop was not none, setting it as event loop")
            print("tornado.ioloop.IOLoop.current(): " + str(tornado.ioloop.IOLoop.current()))
            asyncio.set_event_loop(tornado.ioloop.IOLoop.current())
            
        else:
            print("self.loop was None?! ------- ++++")
            
        try:
            if self.loop != None:
                #return self.loop
                print("get_loop:  self.loop was not none, setting it as event loop")
                asyncio.set_event_loop(self.loop)
            else:
                print("\nself.loop was NONE????-----------")
                try:
                    #self.loop = asyncio.get_running_loop()
                    self.loop = tornado.ioloop.IOLoop.current()
                    asyncio.set_event_loop(self.loop)
                except Exception as ex:
                    print("DARNIT, re-setting tornade event loop failed: " + str(ex))
                    
        except Exception as ex:
            if self.DEBUG:
                print("ERROR, using running Tornado event loop failed: " + str(ex))
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        """
        
    

    # ding dong - button pressed on respeaker board
    def ding(self, button):
        if self.DEBUG:
            print("\nin ding.")
        self.pressed = True
        
        self.pressed_countdown = self.pressed_countdown_time
        #time.sleep(2)
        if taking_a_photo_countdown == 0:
            taking_a_photo_countdown = self.taking_a_photo_countdown_start
        return
        
        
    # This is called every 100 milliseconds
    def update_button(self):
        
        if self.previous_streaming_state != self.persistent_data['streaming']:
            print("\n.\n.update button: streaming state changed to: " + str(self.persistent_data['streaming']))
            self.previous_streaming_state = self.persistent_data['streaming']
            self.thingy.properties["streaming"].value.notify_of_external_update(bool(self.persistent_data['streaming']))
        
        if self.previous_ringtone != self.persistent_data['ringtone']:
            self.previous_ringtone = self.persistent_data['ringtone']
            self.thingy.properties["ringtone"].value.notify_of_external_update(str(self.persistent_data['ringtone']))
            
        if self.previous_ringtone_volume != self.persistent_data['ringtone_volume']:
            self.previous_ringtone_volume = self.persistent_data['ringtone_volume']
            self.thingy.properties["ringtone_volume"].value.notify_of_external_update(int(self.persistent_data['ringtone_volume']))
        
        if self.previous_led_color != self.persistent_data['led_color']:
            self.previous_led_color = self.persistent_data['led_color']
            #self.streaming_value.notify_of_external_update(self.streaming)
            self.thingy.properties["led_color"].value.notify_of_external_update(str(self.persistent_data['led_color']))
        
        if self.previous_led_brightness != self.persistent_data['led_brightness']:
            self.previous_led_brightness = self.persistent_data['led_brightness']
            self.thingy.properties["led_brightness"].value.notify_of_external_update(int(self.persistent_data['led_brightness']))
            
        if self.previous_politeness != self.persistent_data['politeness']:
            self.previous_politeness = self.persistent_data['politeness']
            self.thingy.properties["politeness"].value.notify_of_external_update(bool(self.persistent_data['politeness']))
        
        #global taking_a_photo_countdown
        
        if self.taking_a_photo_countdown > 0:
            if self.DEBUG:
                print("[o] " + str(self.taking_a_photo_countdown))
            
            if self.taking_a_photo_countdown == (self.taking_a_photo_countdown_start - 1):
                self.move_cover('open')
            
                self.thingy.properties["snapshot"].value.notify_of_external_update(True)
                
            if self.taking_a_photo_countdown == (self.taking_a_photo_countdown_start - 20):
                if self.DEBUG:
                    print("\nSNAPSHOT COUNTDOWN HALFWAY, TAKING PHOTO")
                self.take_a_photo = True
                
            if self.taking_a_photo_countdown == 1:
                if self.persistent_data['politeness']:
                    self.move_cover('closed')
                self.thingy.properties["snapshot"].value.notify_of_external_update(False)
                
            self.taking_a_photo_countdown -= 1
        
        #print("in update_button")
        if self.pressed:
            self.pressed = False
            if self.pressed_sent == False:
                self.pressed_sent = True
                self.button_state.notify_of_external_update(True)
                
                try:
                    self.adapter.candlecam_device.properties["button"].update(True)
                except Exception as ex:
                    print("Error setting button pressed state on thing: " + str(ex))
                
                self.play_ringtone()
                #if self.persistent_data['cover_state'] == False:
                
                    
        
        # After three seconds set the button state back to off
        elif self.pressed_sent == True:
            if self.pressed_countdown == (self.pressed_countdown_time - 30): # Three seconds after the button being pressed...
                self.pressed_sent = False
                self.button_state.notify_of_external_update(False)
                
                try:
                    self.adapter.candlecam_device.properties["button"].update(False)
                except Exception as ex:
                    print("Error setting button pressed state on thing: " + str(ex))
        
        if self.pressed_countdown > 0:
            self.pressed_countdown -= 1
            #if self.DEBUG:
            #    print(str(self.pressed_countdown))
                
            # After a minute or two, go back into a polite state?
            if self.pressed_countdown == 0: # as it reaches 0
                if self.DEBUG:
                    print("button pressed countdown reached 0")
                if self.persistent_data['politeness'] == True:
                    if self.DEBUG:
                        print("polite, so closing cover")
                    self.move_cover('closed')
                    
                    
        try:
            self.clock_counter += 1
            if self.clock_counter > self.clock_threshold:
                self.clock_counter = 0
                if self.DEBUG:
                    print("5 minutes passed. Checking for old snapshots to delete")
                threshold_time = int(time.time()) - (int(self.persistent_data['data_retention_days']) * 86400) # the moment in the past before which photos should be removed
                if self.DEBUG:
                    print("threshold_time: " + str(threshold_time))
                
                snapshots = os.listdir(self.data_photos_dir_path)
                if self.DEBUG:
                    print("snapshots: " + str(snapshots))
                for filename in snapshots:
                    try:
                        #filename = os.path.basename(snapshot_path)
                        snapshot_time = int(os.path.splitext(filename)[0])
                        #if self.DEBUG:
                        #    print("checking if snapshot is too old: " + str(snapshot_time))
                        if snapshot_time < threshold_time:
                            file_path = os.path.join(self.data_photos_dir_path,filename)
                            if self.DEBUG:
                                print("- Snapshot too old. Deleting: " + str(file_path))
                            os.remove(file_path)
                                
                    except Exception as ex:
                        print("Clock: error looping over list of snapshots: " + str(ex))
            
        except Exception as ex:
            print("Error in clock: " + str(ex))
        
    #def ding_dong(self, state):
    #    print("in ding_dong. State: " + str(state))
    
        
        
    def create_thingy(self):
        if self.DEBUG:
            print("in create_thingy")
            print("self.persistent_data = ")
            print(str(self.persistent_data))
            print("thing_server_id: " + str(self.persistent_data['thing_server_id']))
            print("create thingy: data_retention_days: " + str(self.persistent_data['data_retention_days']))
        
        time.sleep(2)
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        #dash_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/index.mpd'
        #m3u8_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/master.m3u8'
        
        
        
        self.thingy = Thing(
            'urn:dev:ops:candlecam-' + str(self.persistent_data['thing_server_id']),
            'Candle cam ' + str(self.persistent_data['thing_server_id']),
            ['VideoCamera'],
            'Candle Camera'
        )

        met = {'@type': 'VideoProperty',
                        'title': 'DASH Stream',
                        'type': 'null',
                        'description': 'Video stream',
                        'forms':[
                            {
                                'rel':'alternate',
                                'href':'/media/candlecam/stream/index.mpd',
                                #'href':self.dash_file_path,
                                #'mediaType':'x-motion-jpeg' #video/x-jpeg or video/x-motion-jpeg ?
                                'mediaType': 'application/dash+xml'
                            },
                            {
                                'rel': 'alternate',
                                'href': '/media/candlecam/stream/master.m3u8',
                                #'href': self.m3u8_file_path,
                                'mediaType': 'application/vnd.apple.mpegurl'
                            }
                        ],
                        'links':[
                            {
                                'rel':'alternate',
                                'href':'/media/candlecam/stream/index.mpd',
                                #'href':self.dash_file_path,
                                #'mediaType':'x-motion-jpeg' #video/x-jpeg or video/x-motion-jpeg ?
                                'mediaType': 'application/dash+xml'
                            },
                            {
                                'rel': 'alternate',
                                'href': '/media/candlecam/stream/master.m3u8',
                                #'href': self.m3u8_file_path,
                                'mediaType': 'application/vnd.apple.mpegurl'
                            }
                        ]
                    }
        
        
        mjpeg_met = {'@type': 'VideoProperty',
                        'title': 'MJPEG Stream',
                        'type': 'null',
                        'description': 'MJPEG Video stream',
                        'forms':[
                            {
                                'rel':'alternate',
                                'href':'/media/candlecam/stream/stream.mjpeg', #str(self.mjpeg_file_path),
                                #'href':self.dash_file_path,
                                'mediaType':'x-motion-jpeg' #video/x-jpeg or video/x-motion-jpeg ?
                                #'mediaType': 'application/dash+xml'
                            }
                        ],
                        'links':[
                            {
                                'rel':'alternate',
                                'href':'/media/candlecam/stream/stream.mjpeg',
                                #'href':self.dash_file_path,
                                #'mediaType':'x-motion-jpeg' #video/x-jpeg or video/x-motion-jpeg ?
                                'mediaType':'x-motion-jpeg'
                            }
                        ]
                    }
                    
                    
        if self.DEBUG:
            print("\nmjpeg_met: " + str(mjpeg_met))
            print("\n")
                    
        snapshot_met = {'@type': 'ImageProperty',
                        'title': 'Snapshot',
                        'type': 'null',
                        'description': 'Snapshot from camera',
                        'forms':[
                            {
                                'rel':'alternate',
                                'href':'/media/candlecam/photos/latest.jpg',
                                #'href':self.dash_file_path,
                                'mediaType':'image/jpeg' #video/x-jpeg or video/x-motion-jpeg ?
                                #'mediaType': 'application/dash+xml'
                            }
                        ],
                        'links':[
                            {
                                'rel':'alternate',
                                'href':'/media/candlecam/photos/latest.jpg',
                                #'href':self.dash_file_path,
                                #'mediaType':'x-motion-jpeg' #video/x-jpeg or video/x-motion-jpeg ?
                                'mediaType':'image/jpeg'
                            }
                        ]
                    }
        
        
        #prop = Property.__init__(thing,'stream',Value(None),met)
        
        # The FFMPEG stream with audio. Disabled for now.
        #prop = webthing.Property(self.thingy,'stream',Value(None),met)
        #print("propped")
        #self.thingy.add_property(prop)
        
        if self.camera_available:
            if self.DEBUG:
                print("camera detected. Adding properties to thingy")
            
            """
            mjpeg_prop = webthing.Property(self.thingy,'mjpeg-stream',Value(None),mjpeg_met)
            if self.DEBUG:
                print("MJPEG propped")
            self.thingy.add_property(mjpeg_prop)
        
        
            snapshot_prop = webthing.Property(self.thingy,'snapshot',Value(None),snapshot_met)
            if self.DEBUG:
                print("Snapshot propped")
            self.thingy.add_property(snapshot_prop)
            """
        
            self.thingy.add_property(
                webthing.Property(self.thingy,
                         'streaming',
                         Value(self.persistent_data['streaming'], self.streaming_change),  #self.streaming_value,
                         metadata={
                             '@type': 'OnOffProperty',
                             'title': 'Streaming',
                             'type': 'boolean',
                             'description': 'Whether the camera may stream video',
                         }))
        else:
            if self.DEBUG:
                print("\n! NO CAMERA detected! Not adding start/stop streaming button to thing.")
        
        
        if self.DEBUG:
            print("self.has_respeaker_hat: " + str(self.has_respeaker_hat))
        if self.has_respeaker_hat:
            
            if self.DEBUG:
                print("adding thing properties for respeaker hat")
            
            if self.persistent_data['data_retention_days'] > 0:
                self.thingy.add_property(
                    webthing.Property(self.thingy,
                             'snapshot',
                             Value(self.snapshot_state, self.thingy_take_snapshot),
                             metadata={
                                 #'@type': 'OnOffProperty',
                                 'title': 'Take snapshot',
                                 'type': 'boolean',
                                 'description': 'Enable to take a snapshot',
                             }))
            
            
            self.thingy.add_property(
                webthing.Property(self.thingy,
                         'button',
                         self.button_state,
                         metadata={
                             '@type': 'PushedProperty',
                             'title': 'Button',
                             'type': 'boolean',
                             'description': 'Shows the state of the doorbell button',
                         }))
                         
            #self.ringtone = Value(self.ringtone_value, lambda v: self.ringtone_change(v))
            self.thingy.add_property(
                webthing.Property(self.thingy,
                         'ringtone',
                         Value(self.persistent_data['ringtone'], lambda v: self.ringtone_change(v)),
                         metadata={
                             'title': 'Ringtone',
                             'type': 'string',
                             'description': 'The volume of the tone being played at the door itself',
                             'enum':self.ringtones
                         }))
                         
                         
            self.thingy.add_property(
                webthing.Property(self.thingy,
                         'ringtone_volume',
                         Value(self.persistent_data['ringtone_volume'], lambda v: self.volume_change(v)),
                         metadata={
                             '@type': 'LevelProperty',
                             'title': 'Ringtone volume',
                             'type': 'integer',
                             'description': 'The volume of the tone being played at the door itself',
                             'minimum': 0,
                             'maximum': 100,
                             'unit': 'percent',
                         }))
                     
                     
            self.thingy.add_property(
                webthing.Property(self.thingy,
                         'led_color',
                         Value(self.persistent_data['led_color'], lambda v: self.set_led(v,self.persistent_data['led_brightness'])), # sic
                         metadata={
                             '@type': 'ColorProperty',
                             'title': 'Color',
                             'type': 'string',
                             'description': 'The color of the built-in LED',
                         }))
                     
                     
            self.thingy.add_property(
                webthing.Property(self.thingy,
                         'led_brightness',
                         Value(self.persistent_data['led_brightness'], lambda v: self.set_led(self.persistent_data['led_color'],v)), # sic
                         metadata={
                             '@type': 'LevelProperty',
                             'title': 'Brightness',
                             'type': 'integer',
                             'description': 'The brightness of the built-in color LED',
                             'minimum': 0,
                             'maximum': 100,
                             'unit': 'percent',
                         }))
                     
            
            self.thingy.add_property(
                webthing.Property(self.thingy,
                     'politeness',
                     Value(self.persistent_data['politeness'], lambda v: self.politeness_change(v)),
                     metadata={
                         'title': 'Politeness',
                         'type': 'boolean',
                         'description': 'When the camera cover should automatically close itself',
                     }))
        
        
        
        
            # Watch for button press events, but only if a respeaker hat is present
            if self.DEBUG:
                print('thingy: starting the sensor update looping task')
            self.button_timer = tornado.ioloop.PeriodicCallback(
                self.update_button,
                100
            )
            self.button_timer.start()
            print("self.button_timer: " + str(self.button_timer))
        
        
        
        
        
        
        
        more_routes = [
            #(r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            
            #(r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            #(r"/media/candlecam/photos/(.*)", tornado.web.StaticFileHandler, {"path": self.media_photos_dir_path}),
            
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/(.*)", WebThingServer.tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media"}),
            #(r"/media/(.*)", self.serve_file),
            #(r"/static/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ]
        
        #more_routes.append( (r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}) )
        #more_routes.append( (r"/media/candlecam/stream/(.*)", StreamyHandler ) )
        more_routes.append( (r"/media/candlecam/stream/(.*)", StreamyHandler, {"api_handler" : self} ) )
        #(r"/test", SomeHandler, {"ref_object" : self.ref_object}),
        more_routes.append( (r"/snapshot.jpg", SnapshotHandler, {"api_handler" : self} ) )
        more_routes.append( (r"/ping", PingHandler ) )
        #more_routes.append( (r'/mjpg', StreamyHandler) ) 
        
        #"""
        
        if self.DEBUG:
            print("starting thing server (will block). self.webthing_port: " + str(self.webthing_port))
            print("\n\n")
            print("self.thingy: " + str(dir(self.thingy)))
            print("\n\n")
        try:
            self.thing_server = WebThingServer(SingleThing(self.thingy), port=self.webthing_port, additional_routes=more_routes)
            if self.DEBUG:
                print("thing_server dir:")
                print(str(dir(self.thing_server)))
                print("self.thing_server.name: " + str(self.thing_server.name))
                
            #asyncio.set_event_loop_policy(asyncio.AnyThreadEventLoopPolicy())
            #asyncio.set_event_loop_policy(tornado.platform.asyncio.AnyThreadEventLoopPolicy())
            #self.loop = tornado.ioloop.IOLoop.current()
            #print("\n\nTORNADO LOOP: " + str(self.loop))
            
            self.thing_server.start()
            if self.DEBUG:
                print("thing server started")
                
            #try:
            #    self.loop.run_forever()
            #finally:
            #    self.loop.close()
            
                
        except Exception as ex:
            if self.DEBUG:
                print("ERROR starting thing server: " + str(ex))
                self.adapter.send_pairing_prompt("Error starting server. Tip: reboot.")
        #while(True):
        #    sleep(1)
        #"""
        


    # Can be used to have the server serve a file
    #def serve_file(self, path_args, *args, **kwargs):
    #def serve_file(self, var1, **kwargs):
    #    print("in server_file")
    #    print("path_args = " + str(var1))






    """
    def get_frame(self, size=None):
        if size is None:
            size = (640,480)
        output = io.BytesIO()
        self.picam.capture(output, format='jpeg', resize=(640,480), use_video_port=True)
        output.seek(0)
        return output
    """
    
#
#  TORNADO CALLBACKS
#


class StreamyHandler(tornado.web.RequestHandler):

    def initialize(self, api_handler):
        self.api_handler = api_handler

    #@tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self,something):
        #print("in StreamyHandler get. something: " + str(something))
        #loop = tornado.ioloop.IOLoop.current()
        #global frame
        #global streaming
        #global viewers
        
        self.api_handler.viewer_count += 1
        #print("viewer count: " + str(viewers))
        viewer_count = self.api_handler.viewer_count
        #global new_frame
        #global candlecammy
        #if self.streaming:
        mjpg_interval = .1
        #ioloop = tornado.ioloop.IOLoop.current()
        my_boundary = "--jpgboundary"
        self.served_image_timestamp = time.time()
        
        #self.set_header('Cache-Control', 'no-cache, private')
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.set_header('Pragma', 'no-cache')
        #self.set_header('Connection', 'close')
        self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--jpgboundary')
        self.set_header('Connection', 'close')
        self.flush()
        #counter = 0
        
        while True:
            #counter += 1
            
            #if counter > 100:
            #    print("that's enough of that________________")
            #    break
            try:
                
                
                if self.api_handler.viewer_count < viewer_count - (self.api_handler.maximum_connections - 1):
                    print("Too many viewers, stopping get loop: " + str(self.viewer_count))
                    #self.flush()
                    break
                    
                #if streaming == False:
                #    print("streaming was set to disabled")
                #    break
                    
                
                if self.served_image_timestamp + mjpg_interval < time.time():
                    self.served_image_timestamp = time.time()
                    
                    self.write(my_boundary + '\r\n')
                    self.write("Content-type: image/jpeg\r\n")
                    #self.write("Content-length: %s\r\n\r\n" % frame.getbuffer().nbytes)
                    #self.write(frame.getvalue())
                    if self.api_handler.persistent_data['streaming']:
                        #output = io.BytesIO()
                        #self.api_handler.picam.capture(output, format='jpeg', resize=(640,480), use_video_port=True)
                        #output.seek(0)
                        #self.write("Content-length: %s\r\n\r\n" % sys.getsizeof(output))
                        #self.write(output.read())
                        #output.close()
                        self.write("Content-length: %s\r\n\r\n" % sys.getsizeof(self.api_handler.frame))
                        self.write(self.api_handler.frame)
                        mjpg_interval = .1
                    else:
                        #self.write("Content-length: %s\r\n\r\n" % not_streaming_image_size)
                        self.write("Content-length: %s\r\n\r\n" % sys.getsizeof(self.api_handler.not_streaming_image))
                        self.write(self.api_handler.not_streaming_image)
                        mjpg_interval = 1
                    self.write('\r\n')
                    #self.served_image_timestamp = time.time()
                    #print(str(self.served_image_timestamp))
                
                    #yield tornado.gen.Task(self.flush)
                
                    self.flush()
                    
                    #print(">")
                    yield tornado.gen.sleep(0.05)
                    #self.write(my_boundary)
                    #self.write("Content-type: image/jpeg\r\n")
                    #self.write("Content-length: %s\r\n\r\n" % len(img))
                    #self.write(img)
                    
                    #yield tornado.gen.Task(self.flush)
                    #print("x. yield self.flush")
                    #self.flush()
                    #yield tornado.gen.Task(self.flush)
                else:
                    #print("z")
                    yield tornado.gen.sleep(0.01)
                
                
                
                
            except Exception as ex:
                print("Error posting frame: " + str(ex))
                
                """
                self.write(my_boundary + '\r\n')
                self.write("Content-type: image/jpeg\r\n")
                self.write("Content-length: %s\r\n\r\n" % not_streaming_image_size)
                self.write(not_streaming_image)
            
                self.write('\r\n')
                self.served_image_timestamp = time.time()
                #print(str(self.served_image_timestamp))
                self.flush()
                yield tornado.gen.sleep(1)
                """
                
                break
                
        #print("streamyhandler: GET while loop ended")
        
    def on_finish(self):
        print("streamyhandler: in on_finish")
        pass
        
        
        
        
        

    
    
# Used to help other Candlecam instances easily detect this camera
class PingHandler(tornado.web.RequestHandler):

    #@tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        print("in PingHandler get")
        #self.set_header('Cache-Control', 'no-cache, private')
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.set_header('Pragma', 'no-cache')
        self.set_header('Connection', 'close')
        #self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--jpgboundary')
        self.flush()
        #counter = 0
        yield tornado.gen.sleep(.1)
        
    def on_finish(self):
        print("pingy in on_finish")
        pass


# Returns a JPEG when /snapshot.jpg is get-requested
class SnapshotHandler(tornado.web.RequestHandler):

    def initialize(self, api_handler):
        self.api_handler = api_handler

    #@tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        print("in SnapshotHandler get")
    
        #global frame
        #global streaming
        #global taking_a_photo_countdown
        
        #not_streaming_image_path = '/home/pi/.webthings/addons/candlecam/images/camera_not_available.jpg'
        #not_streaming_image = b''
        
        #self.clear()
        """
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        print("[ Top 10 ]")
        for stat in top_stats[:10]:
            print(stat)
        """
        
        if self.api_handler.taking_a_photo_countdown == 0:
            if self.api_handler.persistent_data['streaming'] == False:
                self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
                self.set_header('Pragma', 'no-cache')
                #self.set_header('Connection', 'close')
                self.set_header("Content-type",  "image/jpeg")
                
                #not_streaming_image_size = os.path.getsize(not_streaming_image_path)
                #with open(not_streaming_image_path, "rb") as file:
                #    not_streaming_image = file.read()
                #    self.write(not_streaming_image)
                #self.write("Content-length: %s\r\n\r\n" % sys.getsizeof(self.api_handler.not_streaming_image))
                self.write(self.api_handler.not_streaming_image)
                
                self.flush()
                yield tornado.gen.sleep(.1)
                    
            else:
                self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
                self.set_header('Pragma', 'no-cache')
                #self.set_header('Connection', 'close')
                self.set_header("Content-type",  "image/jpeg")
                self.api_handler.taking_a_photo_countdown = 60
                yield tornado.gen.sleep(2.1)
                self.write(self.api_handler.frame)
                self.flush()
                yield tornado.gen.sleep(.1)
                
        else:
            #self.clear()
            self.set_status(500)
        
            self.flush()
            yield tornado.gen.sleep(.1)
        #print("not_streaming_image type: " + str(type(not_streaming_image)))
        #print("not_streaming_image size: " + str(not_streaming_image_size))
        #print("sys.getsizeof(not_streaming_image): " + str(sys.getsizeof(not_streaming_image)))
        
        #self.set_header('Cache-Control', 'no-cache, private')
        
        #self.flush()
        #print("sys.getsizeof(frame): " + str(sys.getsizeof(frame)))
        
        # self.write("Content-type: image/jpeg\r\n")
        #self.write("Content-type: image/jpeg\r\n")
        
        #self.write("Content-length: %s\r\n\r\n" % sys.getsizeof(frame))
        #if streaming:
        #    self.write(frame)
        #else:
        #    self.write(not_streaming_image)
        #print(str(not_streaming_image))
        #print(str(frame))
        #self.write("Content-length: %s\r\n\r\n" % sys.getsizeof(not_streaming_image_size))
        #self.write("Content-length: %s\r\n\r\n" % sys.getsizeof(not_streaming_image))
        #
        #self.write('\r\n')
        #self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--jpgboundary')
        #self.flush()
        #counter = 0
        #yield tornado.gen.sleep(.1)
    
        
    
    def on_finish(self):
        print("snapshot in on_finish")
        pass






















#
#  ADAPTER
#


class CandlecamAdapter(Adapter):
    """Adapter for Candlecam"""

    def __init__(self, api_handler, verbose=False):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """

        #print("initialising adapter from class")
        self.addon_name = 'candlecam_adapter'
        self.name = self.__class__.__name__
        Adapter.__init__(self, self.addon_name, self.addon_name, verbose=verbose)

        self.api_handler = api_handler
        self.DEBUG = api_handler.DEBUG
        
        # Create the candlecam device
        try:
            print("adapter: creating device with id: " + str(self.api_handler.thingy_id))
            self.candlecam_device = CandlecamDevice(self) # self.audio_output_options  # , self.api_handler.thingy_id
            self.handle_device_added(self.candlecam_device)
            if self.DEBUG:
                print("candlecam_device created")
            self.devices['candlecam_device'].connected = True
            self.devices['candlecam_device'].connected_notify(True)

        except Exception as ex:
            print("Error, could not create candlecam_device: " + str(ex))
            


#
# DEVICE
#

class CandlecamDevice(Device):
    """Candlecam device type."""

    def __init__(self, adapter):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """

        Device.__init__(self, adapter, 'candlecam_device')

        self._id = 'candlecam_device'
        self.id = 'candlecam_device'
        self.adapter = adapter
        self.api_handler = adapter.api_handler
        self.DEBUG = self.api_handler.DEBUG

        self.name = 'candlecam_device'
        if self.api_handler.camera_available:
            self.title = 'Candle Camera'
        else:
            self.title = 'Candle Camera viewer'
        self.description = 'A privacy friendly smart doorbell or security camera'
        self._type = ['OnOffSwitch']
        #self.connected = False


        try:
            
            if self.api_handler.camera_available:
                
                self.properties["streaming"] = CandlecamProperty(
                                self,
                                "streaming",
                                {
                                    '@type': 'OnOffProperty',
                                    'label': "Streaming",
                                    'type': 'boolean'
                                },
                                self.api_handler.persistent_data['streaming'])


                # snapshots can always be taken, both on the camera or the viewer (unless fully disabled in settings)
                if self.api_handler.persistent_data['data_retention_days'] > 0:
                    self.properties["snapshot"] = CandlecamProperty(
                                        self,
                                        "snapshot",
                                        {
                                            'label': "Take snapshot",
                                            'type': 'boolean'
                                        },
                                        False)

            elif self.api_handler.persistent_data['data_retention_days'] > 0:
                # snapshots can always be taken
                self.properties["snapshot"] = CandlecamProperty(
                                    self,
                                    "snapshot",
                                    {
                                        '@type': 'OnOffProperty',
                                        'label': "Take snapshot",
                                        'type': 'boolean'
                                    },
                                    False)
                                


            if self.api_handler.has_respeaker_hat:
                
                self.properties["button"] = CandlecamProperty(
                                self,
                                "button",
                                {
                                    '@type': 'PushedProperty',
                                    'label': "Button",
                                    'type': 'boolean'
                                },
                                False)
                                
                                
                
                            
                self.properties["ringtone"] = CandlecamProperty(
                                self,
                                "ringtone",
                                {
                                    'label': "Ring tone",
                                    'type': 'string',
                                    'enum': self.api_handler.ringtones,
                                },
                                self.api_handler.persistent_data['ringtone'])
                            
            
                self.properties["ringtone_volume"] = CandlecamProperty(
                                self,
                                "ringtone_volume",
                                {
                                    '@type': 'LevelProperty',
                                    'label': "Ringtone volume",
                                    'type': 'integer',
                                    'minimum': 0,
                                    'maximum': 100,
                                    'unit': 'percent'
                                },
                                self.api_handler.persistent_data['ringtone_volume'])


                self.properties["led_color"] = CandlecamProperty(
                                self,
                                "led_color",
                                {
                                    '@type': 'ColorProperty',
                                    'title': 'Color',
                                    'type': 'string',
                                    'description': 'The color of the built-in LED',
                                },
                                self.api_handler.persistent_data['led_color'])

            
                self.properties["led_brightness"] = CandlecamProperty(
                                self,
                                "led_brightness",
                                {
                                    '@type': 'LevelProperty',
                                    'label': "LED brightness",
                                    'type': 'integer',
                                    'minimum': 0,
                                    'maximum': 100,
                                    'unit': 'percent'
                                },
                                self.api_handler.persistent_data['led_brightness'])
            
                self.properties["politeness"] = CandlecamProperty(
                                self,
                                "politeness",
                                {
                                    'label': "Politeness",
                                    'type': 'boolean'
                                },
                                self.api_handler.persistent_data['politeness'])
                
            

                """
                if sys.platform != 'darwin':
                    print("adding audio output property with list: " + str(audio_output_list))
                    self.properties["audio output"] = CandlecamProperty(
                                    self,
                                    "audio output",
                                    {
                                        'label': "Audio output",
                                        'type': 'string',
                                        'enum': audio_output_list,
                                    },
                                    self.adapter.persistent_data['audio_output'])
                """
            
        except Exception as ex:
            print("error adding properties: " + str(ex))

        if self.DEBUG:
            print("Candlecam thing has been created.")



#
# PROPERTY
#

class CandlecamProperty(Property):

    def __init__(self, device, name, description, value):
        Property.__init__(self, device, name, description)
        self.device = device
        self.name = name
        self.title = name
        self.description = description # dictionary
        self.value = value
        self.set_cached_value(value)



    def set_value(self, value):
        if self.device.DEBUG:
            print("property: set_value called for " + str(self.title))
            print("property: set value to: " + str(value))
        
        #self.api_handler.set_led(self.api_handler.persistent_data['led_color'],self.api_handler.persistent_data['led_brightness'], False)
        
        try:
            if self.name == 'streaming':
                self.device.api_handler.streaming_change(bool(value))
                #self.update(bool(value))

            elif self.name == 'snapshot':
                if self.device.api_handler.camera_available:
                    self.device.api_handler.take_a_photo = True
                else:
                    self.device.api_handler.grab_snapshots() # grab snapshots from all servers in the network
                    
                self.update(True)
                time.sleep(2)
                self.update(False)
                
            elif self.name == 'politeness':
                self.device.api_handler.politeness_change(bool(value))
                
            elif self.name == 'ringtone':
                self.device.api_handler.ringtone_change(str(value))
                #self.update(str(value))
                
            elif self.name == 'ringtone_volume':
                self.device.api_handler.volume_change(int(value))
                #self.update(int(value))

            elif self.name == 'led_color':
                self.device.api_handler.set_led(value,self.device.api_handler.persistent_data['led_brightness'])
                #self.update(str(value))
                
            elif self.name == 'led_brightness':
                self.device.api_handler.set_led(self.device.api_handler.persistent_data['led_color'],int(value))
                #self.update(int(value))
                
            #if self.name == 'audio output':
            #    self.device.api_handler.set_audio_output(str(value))

        except Exception as ex:
            print("set_value error: " + str(ex))



    def update(self, value):
        #print("property -> update")
        if value != self.value:
            self.value = value
            self.set_cached_value(value)
            self.device.notify_property_changed(self)

















#
#  HELPER FUNCTIONS
#

def get_ip():
    """
    Get the default local IP address.
    From: https://stackoverflow.com/a/28950776
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except (socket.error, IndexError):
        ip = '127.0.0.1'
    finally:
        s.close()

    return ip


def get_addresses():
    """
    Get all IP addresses.
    Returns list of addresses.
    """
    addresses = set()

    for iface in ifaddr.get_adapters():
        for addr in iface.ips:
            # Filter out link-local addresses.
            if addr.is_IPv4:
                ip = addr.ip

                if not ip.startswith('169.254.'):
                    addresses.add(ip)
            elif addr.is_IPv6:
                # Sometimes, IPv6 addresses will have the interface name
                # appended, e.g. %eth0. Handle that.
                ip = addr.ip[0].split('%')[0].lower()

                if not ip.startswith('fe80:'):
                    addresses.add('[{}]'.format(ip))

    return sorted(list(addresses))
    
    
    
def run_command(cmd, timeout_seconds=20):
    try:
        
        p = subprocess.run(cmd, timeout=timeout_seconds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)

        if p.returncode == 0:
            return p.stdout # + '\n' + "Command success" #.decode('utf-8')
            #yield("Command success")
        else:
            if p.stderr:
                return "Error: " + str(p.stderr) # + '\n' + "Command failed"   #.decode('utf-8'))

    except Exception as e:
        print("Error running command: "  + str(e))


#
#  A quick scan of the network.
#
def arpa_detect_gateways(quick=True):
    command = "arp -a"
    gateway_list = []
    gateway_dict = {}
    try:
        
        s = requests.Session()
        s.mount('http://', HTTPAdapter(max_retries=0))
        s.mount('https://', HTTPAdapter(max_retries=0))
        
        result = subprocess.run(command, shell=True, universal_newlines=True, stdout=subprocess.PIPE) #.decode())
        for line in result.stdout.split('\n'):
            print("arp -a line: " + str(line))
            if len(line) > 10:
                
                if quick and "<incomplete>" in line:
                    print("skipping incomplete ip")
                    continue
                    
                #print("--useable")
                #name = "?"

                try:
                    ip_address_list = re.findall(r'(?:\d{1,3}\.)+(?:\d{1,3})', str(line))
                    print("ip_address_list = " + str(ip_address_list))
                    ip_address = str(ip_address_list[0])
                    if not valid_ip(ip_address):
                        print("not a valid IP address")
                        continue
                        
                    #print("found valid IP address: " + str(ip_address))
                    try:
                        test_url_a = 'http://' + ip_address + ':8889/ping'; #'http://' + str(ip_address) + "/"
                        #test_url_b = 'https://' + str(ip_address) + "/"
                        #html = ""
                        try:
                            response = s.get(test_url_a, allow_redirects=True, timeout=4)
                            print("response code: " + str(response.status_code))
                            if response.status_code == 200:
                                print("OK")
                                if ip_address not in gateway_list:
                                    gateway_list.append(ip_address)
                                    gateway_dict[ ip_address ] = ip_address
                            #print("http response: " + str(response.content.decode('utf-8')))
                            #html += response.content.decode('utf-8').lower()
                        except Exception as ex:
                            print("Error scanning network for gateway using http: " + str(ex))
                            
                            #try:
                            #    response = s.get(test_url_b, allow_redirects=True, timeout=1)
                            #    #print("https response: " + str(response.content.decode('utf-8')))
                            #    html += response.content.decode('utf-8').lower()
                            #except Exception as ex:
                            #    #print("Error scanning network for gateway using https: " + str(ex))
                            #    pass
                            
                        #if 'webthings' in html:
                        #    print("arp: WebThings controller spotted at: " + str(ip_address))
                            #print(str(response.content.decode('utf-8')))
                        #    if ip_address not in gateway_list:
                        #        gateway_list.append(ip_address) #[ip_address] = "option"
                            
                        #    gateway_dict[ip_address] = ip_address #[ip_address] = "option"
                    
                    except Exception as ex:
                        print("Error: could not analyse IP from arp -a line: " + str(ex))
                        
                except Exception as ex:
                    print("no IP address in line: " + str(ex))
                    
               
                
    except Exception as ex:
        print("Arp -a error: " + str(ex))
        
    #return gateway_list
    return gateway_dict


def valid_ip(ip):
    return ip.count('.') == 3 and \
        all(0 <= int(num) < 256 for num in ip.rstrip().split('.')) and \
        len(ip) < 16 and \
        all(num.isdigit() for num in ip.rstrip().split('.'))
        
        
def randomWord(length=8):
    consonants = "bcdfghjklmnpqrstvwxyz"
    vowels = "aeiou"
    return "".join(random.choice((consonants, vowels)[i%2]) for i in range(length))

