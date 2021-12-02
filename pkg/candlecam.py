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

import socket
import ifaddr



import base64
import socket
import ifaddr
import asyncio

#import logging
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
import base64
#from pynput.keyboard import Key, Controller

import tornado.web
import tornado.gen

try:
    from gpiozero import Button
except:
    print("Could not load gpiozero library")


if os.path.isdir("/etc/voicecard"):

    try:
        import RPi.GPIO as GPIO
    except Exception as ex:
        print("Could not load gpiozero library: " + str(ex))

    try:
        #from apa102 import APA102
        from .apa102 import APA102
        #from .apa import APA102
    except:
        print("Could not load APA201 LED lights library")


try:
    from gateway_addon import Database, Adapter, APIHandler, APIResponse
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
                  
        self.has_repeaker_hat = False
                        
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
            
            self.adapter = CandlecamAdapter(self)
            if self.DEBUG:
                print("Candlecam adapter created")
            
            
            self.things = [] # Holds all the things, updated via the API. Used to display a nicer thing name instead of the technical internal ID.
            self.data_types_lookup_table = {}
            
            self.interval = 30
            self.contain = 1
        
            self.clock = False
        
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
            self.encode_audio = False
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
            
            # CHECK FOR RESPEAKER HAT
            
            self.has_respeaker_hat = False
            print("")
            print("aplay -l output:")
            aplay_output = run_command('aplay -l')
            print(str(aplay_output))
            if 'seeed' in aplay_output.lower():
                print("SEEED ReSpeaker hat spotted")
                self.has_repeaker_hat = True
            else:
                print("No SEEED ReSpeaker hat spotted")

            #ALTERNATIVE RESPEAKER CHECK
            
            #self.has_repeaker_hat = False # Is a ReSPeaker 2 mic hat installed?
            #if os.path.isdir("/etc/voicecard"):
            #    self.has_repeaker_hat = True

            
        except Exception as ex:
            print("Failed in first part of init: " + str(ex))
            
            
        self.kill_ffmpeg()

            
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
            print("check_camera_result = " + str(check_camera_result))
            if 'supported=0' in check_camera_result:
                print("Pi camera does not seem to be supported. Enabling it now.")
                #os.system('sudo raspi-config nonint do_i2c 1')

                with open("/boot/config.txt", "r") as file:
                    os.system('cp /boot/config.txt /boot/config.bak')
                    #for line in file:
                    #    print (line.split("'")[1])
                    
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
                            
                    self.adapter.send_pairing_prompt("Please reboot the device");
                
                
            elif 'detected=0' in check_camera_result:
                print("Pi camera is supported, but was not detected")
                self.adapter.send_pairing_prompt("Make sure the camera is plugged in");
            else:
                if self.DEBUG:
                    print("Pi camera seems good to go")
                
                
        except Exception as ex:
            print("Error checking if camera is enabled: " + str(ex))
                
                
                
                
                


        print("self.adapter.persistence_file_path = " + str(self.adapter.persistence_file_path))
    
        # Get persistent data
        self.persistence_file_path = self.adapter.persistence_file_path

    
        if self.DEBUG:
            print("Current working directory: " + str(os.getcwd()))
    
        try:
        
            # Get persistent data
            self.persistence_file_path = self.adapter.persistence_file_path
            print("self.persistence_file_path = " + str(self.persistence_file_path))
            self.persistent_data = {}
            first_run = False
            try:
                with open(self.persistence_file_path) as f:
                    self.persistent_data = json.load(f)
                    if self.DEBUG:
                        print("Persistence data was loaded succesfully.")
                    
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
                    
            except:
                first_run = True
                print("Could not load persistent data (if you just installed the add-on then this is normal)")
            
                try:
                    self.persistent_data = {'streaming':True, 'ringtone_volume':90, 'ringtone':'default', 'cover_state':'closed', 'politness':True, 'thing_settings':{}}
                    self.save_persistent_data()
                except Exception as ex:
                    print("Error creating initial persistence variable: " + str(ex))
    
    
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

            self.hostname = None
            if self.hostname is not None:
                self.hostname = self.hostname.lower()
                self.hosts.extend([
                    self.hostname,
                    '{}:{}'.format(self.hostname, self.webthing_port),
                ])
        
            #if self.DEBUG:
            #    print("self.manager_proxy = " + str(self.manager_proxy))
            #    print("Created new API HANDLER: " + str(manifest['id']))
    
        except Exception as e:
            print("Failed to init UX extension API handler: " + str(e))
        
            
            
                
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))

        
        if self.DEBUG:
            print("self.manager_proxy = " + str(self.manager_proxy))
            print("Created new API HANDLER: " + str(manifest['id']))

        
        #print("_ _ _ ")
        #print("self.user_profile = " + str(self.user_profile))
        #print("")

        try:
            print(str(self.user_profile['mediaDir']))
            self.media_dir_path = os.path.join(self.user_profile['mediaDir'], self.addon_name)
        except Exception as e:
            print("Error, mediadir did not exist in the user profile")
            self.media_dir_path = os.path.join('/home/pi/.webthings/media', self.addon_name)
        
        try:
            self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
            #self.persistence_file_folder = os.path.join(self.user_profile['configDir'])
            
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

            
            print("self.latest_photo_file_path = " + str(self.latest_photo_file_path))
            print("self.ffmpeg_output_path = " + str(self.ffmpeg_output_path))
            
        except Exception as e:
            print("Failed to make paths: " + str(e))
            
        try:
            
            #if not os.path.isdir( self.addon_photos_dir_path ):
            #    print(self.addon_photos_dir_path + " directory did not exist yet, creating it now")
            #    os.mkdir( self.addon_photos_dir_path )
            
            #if not os.path.isdir( self.addon_stream_dir_path ):
            #    print(self.addon_stream_dir_path + " directory did not exist yet, creating it now")
            #    os.mkdir( self.addon_stream_dir_path )
            
            if not os.path.isdir( self.media_dir_path ):
                print(self.media_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_dir_path )
            
            if not os.path.isdir( self.media_photos_dir_path ):
                print(self.media_photos_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_photos_dir_path )
                
            if not os.path.isdir( self.user_profile['mediaDir'] ):
                print("creating media dir")
                os.mkdir( self.user_profile['mediaDir'] )

            if not os.path.isdir( self.media_stream_dir_path ):
                print(self.media_stream_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_stream_dir_path )
            
        except Exception as ex:
            print("Error making photos directory: " + str(ex))
                
            
        # Respond to gateway version
        try:
            if self.DEBUG:
                print("Gateway version: " + self.gateway_version)
        except:
            if self.DEBUG:
                print("self.gateway_version did not exist")
            
        #self.keyboard = Controller()
        
        
        
        
        
        # Create ramdisk for dash files (to prevent wear on SD card)
        self.available = 0
        self.use_ramdrive = False # TODO DEBUG TEMPORARY, REMOVE ME
        if self.use_ramdrive:
            
            ram_data = subprocess.check_output('grep ^MemFree /proc/meminfo')
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
        cameralib_check = run_command('which which libcamera-vid')
        if len(cameralib_check) > 10:
            print("libcamera seems to be available")
            self.libcamera_available = True
            get_snapshot_command = 'libcamera-jpeg -o ' + str(self.latest_photo_file_path) + ' -n --width 640 --height 480'
            print("get_snapshot_command = " + str(get_snapshot_command))
            snapshot_result = run_command(get_snapshot_command)
            print("libcamera-jpeg result: " + str(snapshot_result))
            time.sleep(3)
            
 
 
        """
 
        args = [
          '-y',
          '-i', streamUrl.toString(),
          '-fflags', 'nobuffer',
          '-vsync', '0',
          '-copyts',
          '-probesize', '200000',
          '-window_size', '5',
          '-extra_window_size', '10',
          '-use_template', '1',
          '-use_timeline', '1',
        ];

        // ffmpeg 4.x
        if (this.ffmpegMajor >= 4) {
          args.push(
            '-streaming', '1',
            '-hls_playlist', '1'
          );
        }

        // ffmpeg 4.1+
        if (this.ffmpegMajor > 4 ||
            (this.ffmpegMajor === 4 && this.ffmpegMinor >= 1)) {
          args.push(
            // eslint-disable-next-line max-len
            '-format_options', 'movflags=empty_moov+omit_tfhd_offset+frag_keyframe+default_base_moof',
            '-seg_duration', '1',
            '-dash_segment_type', 'mp4'
          );
        }

        args.push(
          '-remove_at_exit', '1',
          '-loglevel', 'quiet'
        );

        const highQuality = this.findProperty('highQuality').value;

        // always transcode video so that we get the bitrate we want
        args.push('-c:v', 'libx264',
                  '-b:v:0', highQuality ? '800k' : '400k',
                  '-profile:v:0', 'high');

        if (haveAudio) {
          // always transcode audio so that we get the bitrate we want
          args.push('-c:a', 'aac',
                    '-b:a:0', highQuality ? '128k' : '64k');
        }

        args.push('-f', 'dash', path.join(this.mediaDir, 'index.mpd'));

        this.transcodeProcess = child_process.spawn('ffmpeg', args);
 
        """
        
        
        print("Starting the ffmpeg thread")
        if self.DEBUG:
            print("Starting the ffmpeg thread")
        try:
            # Restore the timers, alarms and reminders from persistence.
            #if 'action_times' in self.persistent_data:
            #    if self.DEBUG:
            #        print("loading action times from persistence") 
            #    self.persistent_data['action_times'] = self.persistent_data['action_times']
            
            self.t = threading.Thread(target=self.ffmpeg) #, args=(self.voice_messages_queue,))
            self.t.daemon = True
            self.t.start()
        except:
            print("Error starting the clock thread")
        
        

        #self.thingy()
        try:
            if self.DEBUG:
                print("starting the thingy thread")
            self.t = threading.Thread(target=self.thingy) #, args=(self.voice_messages_queue,))
            self.t.daemon = True
            self.t.start()
            
        except:
            print("Error starting the thingy thread")
        

        
        
        """
        args = [
            '_webthing._tcp.local.',
            '{}._webthing._tcp.local.'.format(self.name),
        ]
        kwargs = {
            'addresses': [socket.inet_aton(get_ip())],
            'port': self.port,
            'properties': {
                'path': '/',
            },
            'server': '{}.local.'.format(socket.gethostname()),
        }

        if self.https:
            kwargs['properties']['tls'] = '1'

        self.service_info = ServiceInfo(*args, **kwargs)
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.service_info)

        """

        




        #if __name__ == '__main__':
        
        #logging.basicConfig(
        #    level=10,
        #    format="%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
        #)
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        """
            -framerate 25 \          # Input framerate
            -i /dev/cameras/%i \     # Input device
            -vcodec h264_omx \       # Encoding codec
            -keyint_min 0 \          # Allow every frame to be a key frame
            -g 100 \                 # But at most every 100 frames will be a key frame
            -map 0:v \               # Map input stream 0 to the video of this stream
            -b:v 1000k \             # Set the bitrate to 1000k
            -f dash \                # Output format
            -min_seg_duration 4000 \ # Segment into ~4 second parts
            -use_template 1 \        # Use templated names for output
            -use_timeline 0 \        # Dont use the segment time in the template
            -init_seg_name \         # Initial segment name
                init-%i-$RepresentationID$.mp4 \
            -media_seg_name \        # Segment names
                %i-$RepresentationID$-$Number$.mp4
            -remove_at_exit 1 \      # Remove all files when stopping
            -window_size 20 \        # Keep 20 segments on disk
            /srv/http/dash/%i/%i.mpd # Dash manifest name
        """
 
        #print("server: " + str(server))
 
        '''
        PAGEX="""\
        <html>
        <head>
        <title>picamera MJPEG streaming demo</title>
        </head>
        <body>
        <h1>PiCamera MJPEG Streaming Demo</h1>
        <img src="/media/stream.mjpg" width="640" height="480" />
        </body>
        </html>
        """
        '''
        
        PAGE="""\
        {
            "adapterId": "urn:dev:ops:candlecam",
            "device": {
              "id": "candlecam",
              "title": "Candlecam",
              "@context": "https://webthings.io/schemas",
              "@type": [
                "VideoCamera"
              ],
              "description": "A privacy friendly smart doorbell or security camera",
              "properties": {
                "stream": {
                  "name": "stream",
                  "value": null,
                  "visible": true,
                  "type": null,
                  "@type": "VideoProperty",
                  "readOnly": true,
                  "links": [
                    {
                      "rel": "alternative",
                      "href": "http://"""
        
        PAGE+= self.own_ip
        
        
        PAGE+=""":8888/media/stream.mjpg",
                      "mediaType": "x-motion-jpeg"
                    }
                  ],
                  "forms": [
                    {
                      "rel": "alternative",
                      "href": "http://"""
        
        PAGE+= self.own_ip
        
        
        PAGE+=""":8888/media/stream.mjpg",
                      "mediaType": "x-motion-jpeg"
                    }
                  ]
                },
                "snapshot": {
                  "name": "snapshot",
                  "value": null,
                  "visible": true,
                  "type": null,
                  "@type": "ImageProperty",
                  "readOnly": true,
                  "links": [
                    {
                      "rel": "alternative",
                      "href": "/extensions/candlecam/photos/latest.jpg",
                      "mediaType": "image/jpeg"
                    }
                  ],
                  "forms": [
                    {
                      "rel": "alternative",
                      "href": "/extensions/candlecam/photos/latest.jpg",
                      "mediaType": "image/jpeg"
                    }
                  ]
                }
              },
              "actions": {},
              "events": {},
              "links": [],
              "baseHref": "",
              "pin": {
                "required": false,
                "pattern": ""
              },
              "credentialsRequired": false
            },
            "pluginId": "candlecam"
          }
        """


        #json_page = '{"id": "urn:dev:ops:candlecam-1234", "title": "Candle cam", "@context": "https://webthings.io/schemas/", "properties": {"stream": {"@type": "VideoProperty", "title": "Stream", "type": "null", "description": "Video stream", "links": [{"rel": "alternative", "href": "http://192.168.2.167:8888/media/stream.mjpg", "mediaType": "x-motion-jpeg"}, {"rel": "property", "href": "/properties/stream"}]}}, "actions": {}, "events": {}, "links": [{"rel": "properties", "href": "/properties"}, {"rel": "actions", "href": "/actions"}, {"rel": "events", "href": "/events"}, {"rel": "alternate", "href": "ws://192.168.2.167:8888/"}], "description": "Candlecam test description", "@type": ["VideoCamera"], "base": "http://192.168.2.167:8888/", "securityDefinitions": {"nosec_sc": {"scheme": "nosec"}}, "security": "nosec_sc"}'
        json_page = '{"id": "urn:dev:ops:candlecam-1234", "title": "Candle cam", "@context": "https://webthings.io/schemas/", "properties": {"stream": {"@type": "VideoProperty", "title": "Stream", "type": "null", "description": "Video stream", "forms": [{"rel": "alternative", "href": "http://' + self.own_ip + ':8888/media/stream.mjpg", "mediaType": "x-motion-jpeg"}, {"rel": "property", "href": "/properties/stream"}]}}, "actions": {}, "events": {}, "forms": [{"rel": "properties", "href": "/properties"}, {"rel": "actions", "href": "/actions"}, {"rel": "events", "href": "/events"}, {"rel": "alternate", "href": "ws://' + self.own_ip + ':8888/"}], "description": "Candlecam test description", "@type": ["VideoCamera"], "base": "http://' + self.own_ip + ':8888/", "securityDefinitions": {"nosec_sc": {"scheme": "nosec"}}, "security": "nosec_sc"}'
        
        json_return = '{"stream": null}'

        #print("PAGE:")
        #print(PAGE)
        
        """
        class StreamingOutput(object):
            def __init__(self):
                self.frame = None
                self.buffer = io.BytesIO()
                self.condition = Condition()

            def write(self, buf):
                if buf.startswith(b'\xff\xd8'):
                    # New frame, copy the existing buffer's content and notify all
                    # clients it's available
                    self.buffer.truncate()
                    with self.condition:
                        self.frame = self.buffer.getvalue()
                        self.condition.notify_all()
                    self.buffer.seek(0)
                return self.buffer.write(buf)

        class StreamingHandler(server.BaseHTTPRequestHandler):
            def do_GET(self):
                
                #print("in https request")
                #print(str(self))
                #for item in self:
                #    print(item, ':', self[item])
                #print("target_adapter = " + str(target_adapter))
                
                now = datetime.now()
                stamp = mktime(now.timetuple())
                print("in https request. Time: " + str(format_date_time(stamp)))
                
                
                if self.path == '/':
                    #self.send_response(301)
                    #self.send_header('Location', '/index.html')
                    #self.end_headers()
                #elif self.path == '/index.html' or self.path == '/index.json':
                    content = json_page.encode('utf-8') #PAGE.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Date', format_date_time(stamp))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept')
                    self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, PUT, POST, DELETE')
                    self.send_header('Etag', '574f45eb87bbda2d7bf323dfcca51ab2fa1e0df5')
                    self.send_header('Content-Length', len(content))
                    
                    self.end_headers()
                    self.wfile.write(content)
                    
                elif self.path == '/properties' or self.path == '/properties/stream':
                    content = json_return.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Date', format_date_time(stamp))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept')
                    self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, PUT, POST, DELETE')
                    self.send_header('Etag', '574f45eb87bbda2d7bf323dfcca51ab2fa1e0df5')
                    
                    self.send_header('Content-Length', len(content))
                    self.end_headers()
                    self.wfile.write(content)
                    
                elif self.path == '/media/stream.mjpg' or self.path == '/stream.mjpg':
                    self.send_response(200)
                    self.send_header('Age', 0)
                    self.send_header('Cache-Control', 'no-cache, private')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
                    self.end_headers()
                    try:
                        print("target_adapter.running = " + str(target_adapter.running))
                        while target_adapter.running == True:
                            with output.condition:
                                output.condition.wait()
                                frame = output.frame
                            self.wfile.write(b'--FRAME\r\n')
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.send_header('Content-Length', len(frame))
                            self.end_headers()
                            self.wfile.write(frame)
                            self.wfile.write(b'\r\n')
                        print("target_adapter.running is no longer true, exiting streaming")
                    except Exception as e:
                        logging.warning(
                            'Removed streaming client %s: %s',
                            self.client_address, str(e))
                    
                else:
                    self.send_error(404)
                    self.end_headers()

        class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
            allow_reuse_address = True
            daemon_threads = True

        with picamera.PiCamera(resolution='640x480', framerate=24) as self.camera:
            output = StreamingOutput()
            target_adapter = self.adapter
            self.output = output
            self.camera.start_recording(output, format='mjpeg')
            try:
                address = ('', 8888)
                self.server = StreamingServer(address, StreamingHandler)
                self.server.serve_forever()
            finally:
                self.camera.stop_recording()
 
        """
        
 
        # TODO: make sure raspi-config camera is enabled 
        # sudo raspi-config nonint do_camera 0
            
        #run_server()
        
        #self.thing = make_thing()
        
        # currently trying RPi.GPIO apparently.
        #if self.has_repeaker_hat:
        #    self.button = Button(17)

        #    self.button.when_pressed = self.ding_dong('ding')
        #    self.button.when_released = self.ding_dong('dong')
        
        
        print("end of init")
        
        
        
    
        
    def ffmpeg(self):
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
        
        print("calling ffmpeg command: " + str(ffmpeg_command))
                 
                 
        run_command(ffmpeg_command,None)     # -thread_queue_size 16
        #os.system(ffmpeg_command)
        print("beyond run ffmpeg")
        
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
    
        
    # Not useful on Raspian Bullseye yet, as libcamera has no python support yet...
    def run_picamera(self):
        print("in run_picamera. Should probably create mjpeg stream now.")
        
        
        if self.encode_audio == False:
            mjpeg_stream_command = 'libcamera-vid --codec mjpeg -o ' + str(self.mjpeg_file_path) + ' -n --width 640 --height 480'
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
        
    
    def ding(self, button):
        if self.DEBUG:
            print("in ding.")
        self.pressed = True
        self.pressed_countdown = self.pressed_countdown_time
        return
        
        
    #def ding_dong(self, state):
    #    print("in ding_dong. State: " + str(state))
    
        
        
    def thingy(self):
        if self.DEBUG:
            print("in thingy")
            print("self.persistent_data = ")
            print(str(self.persistent_data))
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        #dash_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/index.mpd'
        #m3u8_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/master.m3u8'
        
        thing = Thing(
            'urn:dev:ops:candlecam-1235',
            'Candle cam',
            ['VideoCamera'],
            'Candlecam test description'
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
                                'href':'/media/candlecam/stream/stream.mjpeg',
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
        prop = webthing.Property(thing,'stream',Value(None),met)
        print("propped")
        thing.add_property(prop)
        
        mjpeg_prop = webthing.Property(thing,'mjpeg-stream',Value(None),mjpeg_met)
        print("MJPEG propped")
        thing.add_property(mjpeg_prop)
        
        snapshot_prop = webthing.Property(thing,'snapshot',Value(None),snapshot_met)
        print("Snapshot propped")
        thing.add_property(snapshot_prop)
        
        
        
        
        thing.add_property(
            webthing.Property(thing,
                     'streaming',
                     Value(self.persistent_data['streaming'], self.streaming_change),
                     metadata={
                         '@type': 'OnOffProperty',
                         'title': 'Streaming',
                         'type': 'boolean',
                         'description': 'Whether video video (and audio) is streaming',
                     }))
        
        
        
        if self.has_respeaker_hat:
            
            thing.add_property(
                Prop(thing,
                         'button',
                         self.button_state,
                         metadata={
                             '@type': 'PushedProperty',
                             'title': 'Button',
                             'type': 'boolean',
                             'description': 'Shows the state of the doorbell button',
                         }))
                         
            thing.add_property(
                Prop(thing,
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
                Prop(thing,
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
                Prop(thing,
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
                print('starting the sensor update looping task')
            self.button_timer = tornado.ioloop.PeriodicCallback(
                self.update_button,
                100
            )
            self.button_timer.start()
        
        
        
        
        
        
        
        
        more_routes = [
            #(r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            (r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            (r"/media/candlecam/photos/(.*)", tornado.web.StaticFileHandler, {"path": self.media_photos_dir_path}),
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/(.*)", WebThingServer.tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media"}),
            #(r"/media/(.*)", self.serve_file),
            #(r"/static/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ]
        
        #"""
        if self.DEBUG:
            print("starting thing server (will block)")
        try:
            self.thing_server = WebThingServer(SingleThing(thing), port=self.webthing_port, additional_routes=more_routes)
            print("thing_server:")
            print(str(dir(self.thing_server)))
            self.thing_server.start()
            print("thing server started")
        except Exception as ex:
            print("Error starting thing server: " + str(ex))
            self.adapter.send_pairing_prompt("Error starting server. Tip: reboot.");
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
                print("countdown reached 0")
                if self.persistent_data['politeness'] == True:
                    print("polite, so closing cover")
                    self.move_cover('closed')
                    
                    
    def move_cover(self,state):
        if self.has_respeaker_hat:
            
            if state == 'closed':
                self.set_led(self.persistent_data['led_color'],self.persistent_data['led_brightness'],False)
                try:
                    print("closing cover?: " + str(self.servo_closed_position))
                    self.pwm.ChangeDutyCycle(70)
                    if self.DEBUG:
                        print("set servo to closed (1)")
                except Exception as ex:
                    print("could not set servo: " + str(ex))
                    
            elif state == 'open':
                self.set_led('#ff0000',30,False) # set LED to full brightness.
                try:
                    print("opening cover?: " + str(self.servo_open_position))
                    self.pwm.ChangeDutyCycle(1)
                    if self.DEBUG:
                        print("set servo to open (70)")
                except Exception as ex:
                    print("could not set servo: " + str(ex))
    
            elif state == 'maintenance':
                try:
                    self.pwm.ChangeDutyCycle(100)
                    if self.DEBUG:
                        print("set servo to maintenance (100)")
                except Exception as ex:
                    print("could not set servo: " + str(ex))
        
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
            print("new streaming state: " + str(state))
            
        # START STREAMING
        if state:
            if self.DEBUG:
                print("")
                print("STREAMING ON")
            
            if self.encode_audio:
                self.ffmpeg()
                if self.DEBUG:
                    print("past self.ffmpeg in streaming_change STREAMING ON")
            
            else:
                try:
                    if self.DEBUG:
                        print("starting the PiCamera thread")
                    self.ct = threading.Thread(target=self.run_picamera) #, args=(self.voice_messages_queue,))
                    self.ct.daemon = True
                    self.ct.start()
                except:
                    print("Error starting the picamera thread")

            self.move_cover('open')
             
        # STOP STREAMING
        else:
            if self.DEBUG:
                print("")
                print("STREAMING OFF")
            
            try:
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
                print("thread off error: " + str(ex))


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
        try:
            if str(self.persistent_data['ringtone']) != 'none':
                ringtone_command = 'aplay -M -D plughw:1,0 ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) + str(self.persistent_data['ringtone_volume'])+  '.wav'
                # --buffer-time=8000
                #ringtone_command = 'SDL_AUDIODRIVER="alsa" AUDIODEV="hw:1,0" ffplay ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) +  '.mp3'
                #ringtone_command = 'ffplay -autoexit ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) +  '.mp3'
            
                #if self.DEBUG:
                #    print("ringtone command: " + str(ringtone_command))
            
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
            
            self.lights.set_pixel(0, r, g, b, brightness)  # Pixel 1
            self.lights.set_pixel(1, r, g, b, brightness)  # Pixel 2
            self.lights.set_pixel(2, r, g, b, brightness)  # Pixel 3
            self.lights.show()
            
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
            
            
            
            
        if 'Use microphone' in config:
            self.encode_audio = bool(config['Use microphone'])
            if self.DEBUG:
                print("-Encode audio preference was in config: " + str(self.DEBUG))
        
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





    def handle_request(self, request):
        """
        Handle a new API request for this handler.

        request -- APIRequest object
        """
        
        try:
        
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
                                
                                if self.DEBUG:
                                    print('ajax handling init')
                                    print("self.persistent_data = " + str(self.persistent_data))
                                
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  #content=json.dumps({'state' : True, 'message' : 'initialisation complete', 'thing_settings': self.persistent_data['thing_settings'] }),
                                  content=json.dumps({'state': True, 'own_ip': self.own_ip, 'message': 'initialisation complete', 'thing_settings': self.persistent_data['thing_settings'] }),
                                  
                                )
                                
                            elif action == 'save_settings':
                                
                                self.persistent_data['thing_settings'] = request.body['thing_settings'] 
                                print("self.persistent_data['thing_settings'] = " + str(self.persistent_data['thing_settings'])) 
                                self.save_persistent_data()
                                 
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : True, 'message': 'settings saved succesfully'}),
                                )
                                
                            
                        except Exception as ex:
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
                            
                            
                            
                            
                    elif request.path == '/save':
                        if self.DEBUG:
                            print("SAVING")
                        try:
                            data = []
                            
                            data = self.save_photo(str(request.body['filename']), str(request.body['filedata']), str(request.body['parts_total']), str(request.body['parts_current']) ) #new_value,date,property_id
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
                            print("Error deleting point(s): " + str(ex))
                            return APIResponse(
                              status=500,
                              content_type='application/json',
                              content=json.dumps("Error while deleting point(s): " + str(ex)),
                            )
                        

                    elif request.path == '/wake':
                        if self.DEBUG:
                            print("WAKING")
                        
                        try:
                            #self.camera.capture(self.photos_file_path, use_video_port=True)
                            #cmd = 'DISPLAY=:0 xset dpms force on'
                            #os.system(cmd)
                            
                            
                            return APIResponse(
                              status=200,
                              content_type='application/json',
                              content=json.dumps({'state' : 'woken'}),
                            )
                        except Exception as ex:
                            print("Error waking dispay: " + str(ex))
                            return APIResponse(
                              status=500,
                              content_type='application/json',
                              content=json.dumps("Error while waking up the display: " + str(ex)),
                            )

                        
                        
                    else:
                        return APIResponse(
                          status=500,
                          content_type='application/json',
                          content=json.dumps("API error"),
                        )
                        
                        
                except Exception as ex:
                    print(str(ex))
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
            file_path = os.path.join(self.media_photos_dir_path, str(filename))
            os.remove(file_path)
            result = self.scan_photo_dir()
        except Exception as ex:
            print("Error deleting photo: " + str(ex))
        
        return result


    def scan_photo_dir(self):
        result = []
        try:
            for fname in os.listdir(self.media_photos_dir_path):
                if fname.endswith(".jpg") or fname.endswith(".jpeg") or fname.endswith(".gif"):
                    result.append(fname)    
        except:
            print("Error scanning photo directory")
        
        return result




    def unload(self):
        if self.DEBUG:
            print("Shutting down")
            
        if self.thing_server:
            self.thing_server.stop()
            
        os.system('pkill libcamera-jpeg')
        os.system('pkill libcamera-vid')
        
        try:
            self.pwm.stop()
            #self.pi.stop()
            
        except Exception as ex:
            print("Unload: stopping GPIO error: " + str(ex))
        
        try:
            poll = self.ffmpeg_process.poll()
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
        except Exception as ex:
            print("Unload: terminating ffmpeg_process error: " + str(ex))

        self.kill_ffmpeg() # for good measure

        time.sleep(1)
        if self.ramdrive_created:
            print("unmounting ramdrive")
            os.system('sudo umount ' + self.media_stream_dir_path)
        if self.DEBUG:
            print("candlecam ramdrive unmounted")


    def save_photo(self,filename, filedata, parts_total, parts_current):
        if self.DEBUG:
            print("in file save method. Filename: " + str(filename))

        result = []
        save_path = os.path.join(self.media_photos_dir_path, str(filename))

        
        base64_data = re.sub('^data:image/.+;base64,', '', filedata)
        

        # DEBUG save extra file with base64 data:
        #try: 
        #    with open(save_path + ".txt", "w") as fh:
                #fh.write(base64.decodebytes(filedata.encode()))
        #        fh.write(base64_data)
        #except:
        #    print("Saved debug file")

        # delete existing file first, if it exists:
        try:
            if os.path.isfile(save_path) and parts_current == 1:
                if self.DEBUG:
                    print("file already existed, deleting it first")
                os.remove(save_path)
        except Exception as ex:
            print("Error deleting existing file first: " + str(ex))

        # Save file
        try:
            if filename.endswith('.jpg') or filename.endswith('.jpeg') or filename.endswith('.gif'):
                if self.DEBUG:
                    print("saving to file: " + str(save_path))
                with open(save_path, "wb") as fh:
                    fh.write(base64.b64decode(base64_data))
                result = self.scan_photo_dir()
        except Exception as ex:
            print("Error saving data to file: " + str(ex))

        return result


    def speak(self, voice_message="",intent='default'):
        try:

            if intent == 'default':
                intent = {'siteId':self.persistent_data['site_id']}

            site_id = intent['siteId']

            # Make the voice detection ignore Voco speaking for the next few seconds:
            self.last_sound_activity = time.time() - 1
            if self.DEBUG:
                print("[...] speak: " + str(voice_message))
                print("[...] intent: " + str(intent))
                
                
            if not 'origin' in intent:
                intent['origin'] = 'voice'
            
            # text input from UI
            if self.DEBUG:
                print("in speak, site_id of intent is now: " + str(site_id) + " (my own is: " + str(self.persistent_data['site_id']) + ")")
                print("in speak, intent_message['origin'] = " + str(intent['origin']))
            

            if intent['origin'] == 'text':
                if self.DEBUG:
                    print("(...) response should be show as text: '" + voice_message + "' at: " + str(site_id))
            else:
                if self.DEBUG:
                    print("in speak, origin was not text")

                
            if site_id == 'everywhere' or site_id == self.persistent_data['site_id']:
                if self.DEBUG:
                    print("handling speak LOCALLY")
                if intent['origin'] == 'text':
                    if self.DEBUG:
                        print("setting self.last_text_response to: " + str(voice_message))
                    self.last_text_response = voice_message # this will cause the message to be displayed in the UI.
                    return
                
                #if self.orphaned and self.persistent_data['is_satellite']:
                #    voice_message = "I am not connected to the main voco server. " + voice_message
            
                if self.DEBUG:
                    print("")
                    print("(...) Speaking locally: '" + voice_message + "' at: " + str(site_id))
                environment = os.environ.copy()
                #FNULL = open(os.devnull, 'w')
            
                # unmute if the audio output was muted.
                self.unmute()
    
                for option in self.audio_controls:
                    if str(option['human_device_name']) == str(self.persistent_data['audio_output']):
                        environment["ALSA_CARD"] = str(option['simple_card_name'])
                        if self.DEBUG:
                            print("Alsa environment variable for speech output set to: " + str(option['simple_card_name']))

                        try:
                            if self.nanotts_process != None:
                                if self.DEBUG:
                                    print("terminiating old nanotts")
                                self.nanotts_process.terminate()
                        except:
                            if self.DEBUG:
                                print("nanotts_process did not exist yet")
    
                        nanotts_volume = int(self.persistent_data['speaker_volume']) / 100
    
                        if self.DEBUG:
                            print("nanotts_volume = " + str(nanotts_volume))
    
                        nanotts_path = str(os.path.join(self.snips_path,'nanotts'))
    
                        #nanotts_command = [nanotts_path,'-l',str(os.path.join(self.snips_path,'lang')),'-v',str(self.voice_accent),'--volume',str(nanotts_volume),'--speed',str(self.voice_speed),'--pitch',str(self.voice_pitch),'-w','-o',self.response_wav,"-i",str(voice_message)]
                        #print(str(nanotts_command))
                    
                    
                    
                        # generate wave file
                        self.echo_process = subprocess.Popen(('echo', str(voice_message)), stdout=subprocess.PIPE)
                        self.nanotts_process = subprocess.run((nanotts_path,'-l',str(os.path.join(self.snips_path,'lang')),'-v',str(self.voice_accent),'--volume',str(nanotts_volume),'--speed',str(self.voice_speed),'--pitch',str(self.voice_pitch),'-w','-o',self.response_wav), capture_output=True, stdin=self.echo_process.stdout, env=environment)

                    
                        # play wave file
                        try:
                            # Play sound at the top of a second, so synchronise audio playing with satellites
                            #print(str(time.time()))
                            #initial_time = int(time.time())
                            #while int(time.time()) == initial_time:
                            #    sleep(0.001)
                            
                            #os.system("aplay -D plughw:" + str(self.current_card_id) + "," + str(self.current_device_id) + ' ' + self.response_wav )
                            #speak_command = ["ffplay", "-nodisp", "-vn", "-infbuf","-autoexit", self.response_wav,"-volume","100"]
                            
                            # If a user is not using the default samplerate of 16000, then the wav file will have to be resampled.
                            if self.sample_rate != 16000:
                                os.system('ffmpeg -loglevel panic -y -i ' + self.response_wav + ' -vn -af aresample=out_sample_fmt=s16:out_sample_rate=' + str(self.sample_rate) + ' ' + self.response2_wav)
                                speak_command = ["aplay","-D","plughw:" + str(self.current_card_id) + "," + str(self.current_device_id), self.response2_wav] #,"2>/dev/null"
                                
                            else:
                                speak_command = ["aplay","-D","plughw:" + str(self.current_card_id) + "," + str(self.current_device_id), self.response_wav]
                            
                            
                            if self.DEBUG:
                                print("speak aplay command: " + str(speak_command))
                        
                            subprocess.run(speak_command, capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
                            
                            
                            #os.system('rm ' + self.response_wav)
                            #subprocess.check_call(speak_command,stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        except Exception as ex:
                            print("Error playing spoken voice response: " + str(ex))
        
        
            else:
                if self.DEBUG:
                    print("speaking: site_id '" + str(site_id) + "' is not relevant for this site, will publish to MQTT")
                self.mqtt_client.publish("hermes/voco/" + str(site_id) + "/speak",json.dumps({"message":voice_message,"intent":intent}))
            
                #self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/play",json.dumps({"sound_file":"start_of_input"}))
            
        except Exception as ex:
            print("Error speaking: " + str(ex))
            
            

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
