"""Candlecam API handler."""

# Webthing
from __future__ import division
#from webthing import (Action, Event, Property, SingleThing, Thing, Value, WebThingServer)
#import webthings.Property as Property2


import io
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
import webthing
from webthing import (SingleThing, Thing, Value, WebThingServer)
#from webthing import Property as prop


#from os import listdir
#from os.path import isfile, join

#import picamera

import datetime
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

import picamera

try:
    from gpiozero import Button
except:
    print("Could not load gpiozero library")


if os.path.isdir("/etc/voicecard"):

    try:
        import RPi.GPIO as GPIO
    except Exception as ex:
        print("Could not load RPi.GPIO: " + str(ex))

    try:
        #from apa102 import APA102
        from .apa102 import APA102
        #from .apa import APA102
    except:
        print("Could not load APA201 LED lights library")


try:
    from gateway_addon import Database, Adapter,Device,Property, APIHandler, APIResponse
except:
    print("Could not load gateway addon library")
    
    
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
        self.server = 'http://127.0.0.1:8080'
        self.DEV = True
        self.DEBUG = True
        self.ready = False

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
            
            self.running = True
            
            self.encode_audio = False
            
            self.has_respeaker_hat = False
            self.picam = None
            self.ffmpeg_process = None
            
            self.lights = None
            
            
            self.things = [] # Holds all the things, updated via the API. Used to display a nicer thing name instead of the technical internal ID.
            self.data_types_lookup_table = {}
            
            self.interval = 30
            self.contain = 1
        
            self.clock = False
        
            self.gateways_ip_list = [] #list of IP addresses and hostnames of local candle servers
            self.gateways_ip_dict = {} #list of IP addresses and hostnames of local candle servers
            
            
            
            #self.port = 8888
            self.webthing_port = 8889
            self.name = 'candlecam' # thing name
            self.https = False
            
            self.own_ip = '127.0.0.1'
            try:
                self.own_ip = get_ip()
            except Exception as ex:
                print(str(ex))
            
            
            self.framerate = 10
            
            self.use_ramdrive = True
            self.ramdrive_created = False # it's only created is enough free memory is available (50Mb)

            self.only_stream_on_button_press = False
            
            self.button_state = Value(False)
            self.streaming = Value(True)
            
            self.volume_level = 90
            
            self.pressed = False
            self.pressed_sent = False
            self.pressed_countdown_time = 60 #1200 # 1200 = 2 minutes
            self.pressed_countdown = self.pressed_countdown_time
            
            self.button_pin = 17
            self.servo_pin = 13
            self.servo_open_position = 0
            self.servo_closed_position = 70
            
            self.terminated = False
            
            self.take_a_photo = False
            
            # CHECK FOR RESPEAKER HAT
            self.plughw_number = '0,0'
            self.has_respeaker_hat = False
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
            
            self.own_mjpeg_url = 'http://' + self.own_ip + ':8889/media/candlecam/stream/stream.mjpeg'
            
        except Exception as ex:
            print("Failed in first part of init: " + str(ex))
            
            
        #self.kill_ffmpeg()

        
        self.adapter = CandlecamAdapter(self)
        if self.DEBUG:
            print("Candlecam adapter created")
            
            print("self.adapter.user_profile: " + str(self.adapter.user_profile))
        

            
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
                    print("Pi camera does not seem to be supported. Enabling it now.")
                #os.system('sudo raspi-config nonint do_i2c 1')

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
                
                
            elif 'detected=0' in check_camera_result:
                if self.DEBUG:
                    print("Pi camera is supported, but was not detected")
                self.adapter.send_pairing_prompt("Make sure the camera is plugged in")
            else:
                if self.DEBUG:
                    print("\nPi camera seems good to go")
                self.camera_available = True
                
        except Exception as ex:
            print("Error checking if camera is enabled: " + str(ex))
                
                
                
                
                


        #print("self.adapter.persistence_file_path = " + str(self.adapter.persistence_file_path))
    
        # Get persistent data
        #self.persistence_file_path = self.adapter.persistence_file_path

    
        if self.DEBUG:
            print("Current working directory: " + str(os.getcwd()))
    
        try:
        
            # Get persistent data
            self.persistence_file_path = self.adapter.persistence_file_path
            if self.DEBUG:
                print("self.persistence_file_path = " + str(self.persistence_file_path))
            self.persistent_data = {}
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
                    self.persistent_data = {'streaming':True, 'ringtone_volume':90, 'ringtone':'default', 'cover_state':'closed', 'politness':True, 'thing_settings':{}}
                except Exception as ex:
                    print("Error creating initial persistence variable: " + str(ex))
    
        except Exception as e:
            print("WARNING, Failed to load persistent data: " + str(e))
        
            
        
            
                
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))

        
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
            if 'cover_sate' not in self.persistent_data:
                self.persistent_data['cover_state'] = 'closed'
            if 'politeness' not in self.persistent_data:
                self.persistent_data['politeness'] = True
            if 'thing_server_id' not in self.persistent_data:    
                self.persistent_data['thing_server_id'] = randomWord(4)
            
            print("\n\nself.persistent_data: " + str(self.persistent_data))
            print("\n\nthing_server_id: " + str(self.persistent_data['thing_server_id']))
    
            system_hostname = socket.gethostname().lower()
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
            print("Error checking for missing persistent data values and/or hostname: " + str(ex))
        
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

            self.matrix_drop_dir = os.path.join(self.user_profile['addonsDir'], 'voco','sendme')
            
            self.not_streaming_image = os.path.join(self.addon_path, 'images','camera_not_available.jpg')
            
            self.addon_sounds_dir_path = os.path.join(self.addon_path, 'sounds')
            
            self.addon_sounds_dir_path += os.sep
            
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
                
                
        except:
            if self.DEBUG:
                print("self.gateway_version did not exist")
            
        #self.keyboard = Controller()
        
        
        
        # Create ramdisk for dash files (to prevent wear on SD card)
        self.available = 0
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


        # Start stream if necessary
        if self.persistent_data['streaming']:
            if self.DEBUG:
                print("According to persistent data, streaming was on. Setting streaming_change to True (starting streaming).")
            self.streaming_change(True)

        
        
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
        
        
        self.ready = True
        self.save_persistent_data()
        #time.sleep(10)
        #self.thingy()
        try:
            if self.DEBUG:
                print("init: starting the thingy thread")
            self.t = threading.Thread(target=self.thingy) #, args=(self.voice_messages_queue,))
            self.t.daemon = True
            self.t.start()
            
        except:
            print("Error starting the thingy thread")
        
        #self.thingy()
        
        if self.DEBUG:
            print("end of init")
        
        
        
    
        
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
    
        
        
    def run_picamera(self):   
        if self.DEBUG:
            print("in run_picamera") 
        self.picam = picamera.PiCamera(resolution='720p', framerate=10)
        self.picam.exposure_mode = 'auto'
        self.picam.awb_mode = 'auto'
        
        try:
            self.picam.start_preview()
            # Give the camera some warm-up time
            time.sleep(2)
            self.output = StreamOutput(self,self.mjpeg_file_path)
            if self.DEBUG:
                print("run_picamera: start_recording")
            self.picam.start_recording(self.output, format='mjpeg')
        except:
           print('ERROR. run_picamera: Error setting up recording!')
        
        try:
            while self.persistent_data['streaming']:
                self.picam.wait_recording(2)
        except Exception as ex:
            print("ERROR. run_picamera: Error while getting image data from camera module: " + str(ex))
        self.picam.stop_recording()
        self.output.close()
        if self.DEBUG:
            print("at end of picamera thread. Does it close now?")
        #self.join()
        
        
        
    # Not useful on Raspian Bullseye yet, as libcamera has no python support yet...
    def run_picamera_libcamera(self):
        if self.DEBUG:
            print("in run_picamera. Should probably create mjpeg stream now.")
        
        
        if self.encode_audio == False:
            mjpeg_stream_command = 'libcamera-vid --codec mjpeg -o ' + str(self.mjpeg_file_path) + ' -n --width 640 --height 480'
            if self.DEBUG:
                print("Starting MJPEG stream with command: " + str(mjpeg_stream_command))
            run_command(mjpeg_stream_command, None)
        
        """
        self.picam = picamera.PiCamera(resolution='720p', framerate=10)
        self.picam.exposure_mode = 'auto'
        self.picam.awb_mode = 'auto'
        
        try:
            self.picam.start_preview()
            # Give the camera some warm-up time
            time.sleep(2)
            output = StreamOutput()
            self.picam.start_recording(output, format='mjpeg')
        except:
           print('Error setting up recording!')
        
        try:
            while self.persistent_data['streaming']:
                self.picam.wait_recording(2)
        except Exception as ex:
            print("Error while getting image data from camera module: " + str(ex))
        self.picam.stop_recording()
        output.close()
        print("at end of picamera thread. Does it close now?")
        #self.join()
        """
        
    
    # ding dong - button pressed on respeaker board
    def ding(self, button):
        if self.DEBUG:
            print("\nin ding.")
        self.pressed = True
        
        self.pressed_countdown = self.pressed_countdown_time
        #time.sleep(2)
        self.take_a_photo = True
        return
        
        
    #def ding_dong(self, state):
    #    print("in ding_dong. State: " + str(state))
    
        
        
    def thingy(self):
        if self.DEBUG:
            print("in thingy")
            print("self.persistent_data = ")
            print(str(self.persistent_data))
            print("thing_server_id: " + str(self.persistent_data['thing_server_id']))
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        #dash_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/index.mpd'
        #m3u8_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/master.m3u8'
        
        
        
        thing = Thing(
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
        #prop = webthing.Property(thing,'stream',Value(None),met)
        #print("propped")
        #thing.add_property(prop)
        
        if self.camera_available:
            if self.DEBUG:
                print("camera detected. Adding properties to thingy")
            
            """
            mjpeg_prop = webthing.Property(thing,'mjpeg-stream',Value(None),mjpeg_met)
            if self.DEBUG:
                print("MJPEG propped")
            thing.add_property(mjpeg_prop)
        
        
            snapshot_prop = webthing.Property(thing,'snapshot',Value(None),snapshot_met)
            if self.DEBUG:
                print("Snapshot propped")
            thing.add_property(snapshot_prop)
            """
        
            thing.add_property(
                webthing.Property(thing,
                         'streaming',
                         Value(self.persistent_data['streaming'], self.streaming_change),
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
            
            print("adding thing properties for respeaker hat")
            
            
            thing.add_property(
                webthing.Property(thing,
                         'button',
                         self.button_state,
                         metadata={
                             '@type': 'PushedProperty',
                             'title': 'Button',
                             'type': 'boolean',
                             'description': 'Shows the state of the doorbell button',
                         }))
                         
            thing.add_property(
                webthing.Property(thing,
                         'volume',
                         Value(self.persistent_data['ringtone_volume'], lambda v: self.volume_change(v)),
                         metadata={
                             '@type': 'BrightnessProperty',
                             'title': 'Ringtone volume',
                             'type': 'integer',
                             'description': 'The volume of the tone being played at the door itself',
                             'minimum': 0,
                             'maximum': 100,
                             'unit': 'percent',
                         }))
                     
            thing.add_property(
                webthing.Property(thing,
                         'led_brightness',
                         Value(self.persistent_data['led_brightness'], lambda v: self.set_led(self.persistent_data['led_color'],v)),
                         metadata={
                             '@type': 'BrightnessProperty',
                             'title': 'Brightness',
                             'type': 'integer',
                             'description': 'The brightness of the built-in color LED',
                             'minimum': 0,
                             'maximum': 100,
                             'unit': 'percent',
                         }))
                     
            thing.add_property(
                webthing.Property(thing,
                         'led_color',
                         Value(self.persistent_data['led_color'], lambda v: self.set_led(v,self.persistent_data['led_brightness'])),
                         metadata={
                             '@type': 'ColorProperty',
                             'title': 'Color',
                             'type': 'string',
                             'description': 'The color of the built-in LED',
                         }))
                     
            thing.add_property(
                webthing.Property(thing,
                         'ringtone',
                         Value(self.persistent_data['ringtone'], lambda v: self.ringtone_change(v)),
                         metadata={
                             'title': 'Ringtone',
                             'type': 'string',
                             'description': 'The volume of the tone being played at the door itself',
                             'enum':['default','classic','klingel','business','fart','none']
                         }))
                         
                         
            thing.add_property(
                webthing.Property(thing,
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
        more_routes.append( (r"/media/candlecam/stream/(.*)", StreamyHandler ) )
        #more_routes.append( (r'/mjpg', StreamyHandler) ) 
        
        #"""
        if self.DEBUG:
            print("starting thing server (will block). self.webthing_port: " + str(self.webthing_port))
        try:
            self.thing_server = WebThingServer(SingleThing(thing), port=self.webthing_port, additional_routes=more_routes)
            if self.DEBUG:
                print("thing_server dir:")
                print(str(dir(self.thing_server)))
                print("self.thing_server.name: " + str(self.thing_server.name))
            self.thing_server.start()
            if self.DEBUG:
                print("thing server started")
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





    # This is called every 100 milliseconds
    def update_button(self):
        #print("in update_button")
        if self.pressed:
            self.pressed = False
            if self.pressed_sent == False:
                self.pressed_sent = True
                self.button_state.notify_of_external_update(True)
                self.play_ringtone()
                #if self.persistent_data['cover_state'] == False:
                self.move_cover('open')
                    
        
        # After three seconds set the button state back to off
        elif self.pressed_sent == True:
            if self.pressed_countdown == (self.pressed_countdown_time - 30): # Three seconds after the button being pressed...
                self.pressed_sent = False
                self.button_state.notify_of_external_update(False)
        
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
                    
                    
    def move_cover(self,state):
        if self.has_respeaker_hat and self.camera_available:
            
            if state == 'closed':
                self.set_led(self.persistent_data['led_color'],self.persistent_data['led_brightness'],False)
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
                self.set_led('#ff0000',30,False) # set LED to full brightness.
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



    def volume_change(self,volume):
        if self.DEBUG:
            print("new volume: " + str(volume))
        self.persistent_data['ringtone_volume'] = volume
        self.save_persistent_data()            




    def streaming_change(self,state):
        if self.DEBUG:
            print("in streaming_change. new streaming state: " + str(state))
            print("self.encode_audio: " + str(self.encode_audio))
        # START STREAMING
        if state:
            if self.DEBUG:
                print("")
                print("STREAMING ON")
            
            if self.encode_audio:
                if self.DEBUG:
                    print("encode_audio was true, calling ffmpeg()")
                self.ffmpeg()
                if self.DEBUG:
                    print("past self.ffmpeg in streaming_change STREAMING ON")
            
            else:
                try:
                    if self.DEBUG:
                        print("starting the PiCamera thread (run_picamera)")
                    self.ct = threading.Thread(target=self.run_picamera)
                    self.ct.daemon = True
                    self.ct.start()
                    
                    #old
                    #self.ct = threading.Thread(target=self.run_picamera) #, args=(self.voice_messages_queue,))
                    #self.ct = threading.Thread(target=self.ffmpeg_mjpeg) #, args=(self.voice_messages_queue,))
                    #self.ffmpeg()
                    #self.ffmpeg_mjpeg()
                    
                except:
                    print("Error starting the picamera thread")

            self.move_cover('open')
             
        # STOP STREAMING
        else:
            if self.DEBUG:
                print("")
                print("STREAMING OFF")
            
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


            # should also stop libcamera-vid cleanly...

            self.move_cover('closed')
        
        self.persistent_data['streaming'] = state
        self.save_persistent_data()



                   
    def ringtone_change(self,choice):
        if self.DEBUG:
            print("new ringtone choice: " + str(choice))
        self.persistent_data['ringtone'] = choice
        self.save_persistent_data()
        self.play_ringtone()



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
                
                self.ringtone_process = subprocess.Popen(ringtone_command_array)
                
        except Exception as ex:
            print("Error playing ringtone: " + str(ex))

        
        
    def set_led(self,hex,brightness,save=True):
        if self.DEBUG:
            print("setting led color to: " + str(hex))
            print("setting led brightness to: " + str(brightness) + "%")
            #print("self.lights = " + str(self.lights))
        
        if save:
            self.persistent_data['led_color'] = hex
            self.persistent_data['led_brightness'] = brightness
            self.save_persistent_data()
        
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
        
        if 'Use ramdrive' in config:
            self.use_ramdrive = bool(config['Use ramdrive'])
            if self.DEBUG:
                print("-Use ramdrive preference was in config: " + str(self.DEBUG))
        
                


        #if 'Interval' in config:
        #    self.interval = int(config['Interval'])
        #    if self.DEBUG:
        #        print("-Interval preference was in config: " + str(self.interval))

        if 'Contain' in config:
            self.contain = bool(config['Contain'])
            if self.DEBUG:
                print("-Contain photo preference was in config: " + str(self.contain))

        if 'Clock' in config:
            self.clock = int(config['Clock'])
            if self.DEBUG:
                print("-Clock preference was in config: " + str(self.clock))




    def network_scan(self):
        gateways_ip_dict = {}
        try:
            # Satellite targets
            gateways_ip_dict = arpa_detect_gateways()
            if self.DEBUG:
                print("\n\nNETWORK SCAN\ninitial self.gateways_ip_dict: " + str(gateways_ip_dict))
        
            gateways_ip_dict[self.own_ip] = socket.gethostname()
        
            satellite_targets = {}
            for ip_address in gateways_ip_dict: # server = ip address
                if self.DEBUG:
                    print("checking server ip_address: " + str(ip_address))
                
                try:
                    #stream_url = 'http://' + ip_address + ':8889/media/candlecam/stream/stream.mjpeg';
                    #r = requests.get(stream_url)
                    #if self.DEBUG:
                    #    print("status code: " + str(r.status_code))
                    #if r.status_code == 200:
                    nbtscan_output = str(subprocess.check_output(['sudo','nbtscan','-q',str(ip_address)]))
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
            
        return gateways_ip_dict



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
            
            if request.path == '/init' or request.path == '/list' or request.path == '/delete' or request.path == '/save' or request.path == '/wake' or request.path == '/ajax':

                try:
                    if request.path == '/ajax':
                        if self.DEBUG:
                            print("Ajax")
                        
                            
                        try:
                            action = str(request.body['action'])    
                            
                            if action == 'init':
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
                                  content=json.dumps({'state': state, 'own_ip': self.own_ip, 'message': 'initialization complete', 'thing_settings': self.persistent_data['thing_settings'], 'gateways':self.gateways_ip_dict, 'photos':photos_list }),
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
                                    
                                        if stream_url.endswith('mjpg') or stream_url.endswith('mjpeg'):
                                            state = self.grab_mjpeg_frame(stream_url)
                                            
                                        time.sleep(1)
                                        try:
                                            photos_list = self.scan_photo_dir()
                                            if isinstance(photos_list, str):
                                                state = False
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
                              content=json.dumps({'state' : state, 'data' : data, 'settings': {'interval':self.interval, 'contain':self.contain, 'clock' : self.clock } }),
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
        



    # INIT
    def get_init_data(self):
        if self.DEBUG:
            print("Getting the initialisation data")



        
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




    def unload(self):
        if self.DEBUG:
            print("Shutting down")
        self.running = False
            
        try:
            if self.picam != None:
                self.picam.stop_recording()
                self.output.close()
                self.picam.stop_preview()
                self.picam.close()
        except Exception as ex:
            print("Unload: stopping picamera error: " + str(ex))
            
        if self.thing_server:
            self.thing_server.stop()
            
        #os.system('pkill libcamera-jpeg')
        #os.system('pkill libcamera-vid')
        
        try:
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

        

        time.sleep(1)
        if self.ramdrive_created:
            print("unmounting ramdrive")
            os.system('sudo umount ' + self.media_stream_dir_path)
        if self.DEBUG:
            print("candlecam ramdrive unmounted")


    


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
                self.take_a_photo = True
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
                            
                                break
                            
                        except Exception as ex:
                            print("Error in grab_mjpeg_frame for-loop: " + str(ex))
                        
                """
                stream = urllib.request.urlopen(stream_url)
                print(str(stream))
                fresh_bytes = stream.read(1024)
                looking_for_jpeg = True
                looking_loops_counter = 0
                a = -1
                b = -1
                while looking_for_jpeg:
                    looking_loops_counter += 1
                    print(str(looking_loops_counter))
                    fresh_bytes += stream.read(1024)
                    print("fresh_bytes read")
                    if a == -1:
                        a = fresh_bytes.find(b'\xff\xd8')
                    b = fresh_bytes.find(b'\xff\xd9')
                    print("bytes read. a: " + str(a))
                    print("bytes read. b: " + str(b))
                    if a != -1 and b != -1:
                        print("found beginning and end of jpeg")
                        jpg = fresh_bytes[a:b+2]
                        fresh_bytes = fresh_bytes[b+2:]
                
                        filename = str(int(time.time())) + '.jpg'
                        file_path = os.path.join( self.data_photos_dir_path,filename)
                        with open(file_path, "wb") as fh:
                            fh.write(jpg)
                    
                        looking_for_jpeg = False
                        found_jpeg = True
                        print("looking loops required: " + str(looking_loops_counter))
            
                    if looking_loops_counter > 1000:
                        looking_for_jpeg = False
                        print("Warning, reached maximum looking_loops_counter")
            
                """
                        
        except Exception as ex:
            print("Error in grab_mjpeg_frame: " + str(ex))
        return result










            

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
    



    



#
#  ADAPTER
#


class CandlecamAdapter(Adapter):
    """Adapter for Candlecam"""

    def __init__(self, verbose=False):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """

        #print("initialising adapter from class")
        self.addon_name = 'candlecam'
        self.name = self.__class__.__name__
        Adapter.__init__(self, self.addon_name, self.addon_name, verbose=verbose)

        # Setup persistence
        #for path in _CONFIG_PATHS:
        #    if os.path.isdir(path):
        #        self.persistence_file_path = os.path.join(
        #            path,
        #            'candlecam-persistence.json'
        #        )
        #        print("self.persistence_file_path is now: " + str(self.persistence_file_path))

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
        


#
#  PICAMERA CLASSES
#

class StreamOutput(object):
    def __init__(self,api_handler,file_path):
        self.snapshot = None
        
        self.mjpeg_file_path = file_path
        self.api_handler = api_handler
        print("StreamOutput: self.api_handler.name: " + str(self.api_handler.name ))
        self.last_write_time = 0

    def write(self, buf):
        
        #global new_frame
        global frame
        if self.api_handler.running == False:
            print("StreamOutput: no longer running")
            return
        if buf.startswith(b'\xff\xd8'):
            self.snapshot = io.BytesIO()
            #self.snapshot.seek(0)
        self.snapshot.write(buf)
        if buf.endswith(b'\xff\xd9'):
            #self.snapshot.close()
            frame = self.snapshot
            
            if self.api_handler.take_a_photo: # TODO: or if continous periodic recording should be active, perhaps while in security mode?
                
                self.api_handler.take_a_photo = False
                
                filename = str(int(time.time())) + '.jpg'
                file_path = os.path.join( self.api_handler.data_photos_dir_path,filename)
                # This stores a jpg as mjpeg on the SD card. Technically it could then be accessed via the Webthings standard.. if the remote location has a valid JWT. 
                # TODO: could be a security feature in the future
                if time.time() - 1 > self.last_write_time:
                    #if self.DEBUG:
                    print("saving a photo from the picamera stream")
                    self.last_write_time = time.time()
                    #with open(self.mjpeg_file_path, "wb") as binary_file: # if continous storage for mjpeg serving via webthings standard is required
                    with open(file_path, "wb") as binary_file:
                        #print("saving jpg as mjpeg")
                        binary_file.write(frame.getvalue())
            
    def close(self):
        self.snapshot.close()


class StreamyHandler(tornado.web.RequestHandler):

    
    #@tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self,something):
        print("in StreamyHandler get. something: " + str(something))
        global frame
        #global new_frame
        #global candlecammy
        #if self.streaming:
        mjpg_interval = .1
        #ioloop = tornado.ioloop.IOLoop.current()
        my_boundary = "--jpgboundary"
        self.served_image_timestamp = time.time()
        
        not_streaming_image_path = '/home/pi/.webthings/addons/candlecam/images/camera_not_available.jpg'
        
        not_streaming_image = b''
        not_streaming_image_size = os.path.getsize(not_streaming_image_path)
        with open(not_streaming_image_path, "rb") as file:
            not_streaming_image = file
        
        
        #self.set_header('Cache-Control', 'no-cache, private')
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.set_header('Pragma', 'no-cache')
        #self.set_header('Connection', 'close')
        self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--jpgboundary')
        self.flush()
        #counter = 0
        
        while True:
            #counter += 1
            
            #if counter > 100:
            #    print("that's enough of that________________")
            #    break
            try:
                self.write(my_boundary + '\r\n')
                self.write("Content-type: image/jpeg\r\n")
                self.write("Content-length: %s\r\n\r\n" % frame.getbuffer().nbytes)
                self.write(frame.getvalue())
            
                self.write('\r\n')
                self.served_image_timestamp = time.time()
                #print(str(self.served_image_timestamp))
                self.flush()
                yield tornado.gen.sleep(.1)
            except Exception as ex:
                print("Error posting frame: " + str(ex))
                
                
                self.write(my_boundary + '\r\n')
                self.write("Content-type: image/jpeg\r\n")
                self.write("Content-length: %s\r\n\r\n" % not_streaming_image_size)
                self.write(not_streaming_image)
            
                self.write('\r\n')
                self.served_image_timestamp = time.time()
                #print(str(self.served_image_timestamp))
                self.flush()
                yield tornado.gen.sleep(1)
                
                
                #break
                
        print("GET DONE")
        
    def on_finish(self):
        print("in on_finish")
        pass
    



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
                
                #if quick and "<incomplete>" in line:
                #    print("skipping incomplete ip")
                #    continue
                    
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
                        test_url_a = 'http://' + ip_address + ':8889/media/candlecam/stream/stream.mjpeg'; #'http://' + str(ip_address) + "/"
                        #test_url_b = 'https://' + str(ip_address) + "/"
                        #html = ""
                        try:
                            response = s.get(test_url_a, allow_redirects=True, timeout=1)
                            if response.status_code == 200:
                                if ip_address not in gateway_list:
                                    gateway_list.append(ip_address)
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
