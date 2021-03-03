"""Candlecam API handler."""

# Webthing
from __future__ import division
#from webthing import (Action, Event, Property, SingleThing, Thing, Value, WebThingServer)
#import webthings.Property as Property2

import io
import os
import time

os.system('pkill ffmpeg') #TODO DEBUG TEMPORARY

import subprocess

#subprocess.Popen('pgrep','pigpiod')

"""
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
        
"""

#os.system('export PIGPIO_PORT=9999')
#os.system('sudo ./pigpiod -l -p 9999')

#os.system('export PIGPIO_PORT=9999')

#pigpio_running = subprocess.check_output(['pgrep','pigpiod'])
#pigpio_running = pigpio_running.decode('utf-8')
#print(str(pigpio_running))
#if str(pigpio_running) == 'None':
#    print("pigpio wasn't already running, starting it now")
#    subprocess.Popen(['sudo','./pigpiod','-l'])


import re
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
#from os import listdir
#from os.path import isfile, join


#import logging
import webthing
from webthing import (SingleThing, Thing, Value, WebThingServer)
from webthing import Property as Prop

import uuid

import asyncio

import socket
import ifaddr

import functools
import json


from time import sleep, mktime
import datetime

import threading
#from threading import Condition
#import requests
import base64
#from pynput.keyboard import Key, Controller

import tornado.web

try:
    #from gpiozero import Button
#    import pigpio
    from apa102 import APA102
    
except:
    print("Could not load APA201 LED lights library")
    
try:
    import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
    #from gpiozero.pins.native import NativeFactory
    #from gpiozero import Servo, Button, AngularServo
    #from gpiozero.pins.pigpio import PiGPIOFactory
except Exception as ex:
    print("Could not load gpiozero library: " + str(ex))


try:
    #from picamera import PiCamera
    #import picamera
    #import logging
    #import socketserver
    #from wsgiref.handlers import format_date_time
    #from datetime import datetime
    #from threading import Condition
    #import http 
    #from http import server
    from gateway_addon import Database, Adapter, APIHandler, APIResponse
    
    #from zeroconf import ServiceInfo, Zeroconf
    
    #import http.server as server
    print("libraries loaded")
    #print(str(server))
except:
    print("Could not load gateway addon library")



#try:
    #from gateway_addon import APIHandler, APIResponse #, Database, Adapter, Device, Property
    
    #print("succesfully loaded APIHandler and APIResponse from gateway_addon")
#except:
#    print("Import APIHandler and APIResponse from gateway_addon failed. Use at least WebThings Gateway version 0.10")

#try:
    #from .candlecam_adapter import *
#    pass
#except Exception as ex:
#    print("Error loading candlecam_adapter: " + str(ex))
    
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


class CandlecamAPIHandler(APIHandler):
    """Power settings API handler."""

    def __init__(self, verbose=False):
        """Initialize the object."""
        #print("INSIDE API HANDLER INIT")
        
        self.addon_name = 'candlecam'
        self.server = 'http://127.0.0.1:8080'
        self.DEV = True
        self.DEBUG = True
                        
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
        
            self.webthing_port = 8889
            self.webthing_port = 8889
            self.name = 'candlecam' # thing name
            self.https = False
            self.own_ip = get_ip()
            
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
            self.pressed_count = 30
            
            self.button_pin = 17
            self.servo_pin = 13
            
        except Exception as ex:
            print("Failed in first part of init: " + str(ex))
            
            
        try:
            print(" - - LIGHTS - -")
            #self.lights = APA102(3, 10, 11, 8)
            
            self.lights = APA102(3) #14,15,None,0.5
            print(str(self.lights))
            
            self.led_color('00ff00')
            self.led_brightness(10)
            
        except Exception as ex:
            print("Failed in LED setup: " + str(ex))
           
            
        try: 
            
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
            
            
        try:
            self.armv6 = False # indication that this is a Raspberry Pi Zero.
            for varname in os.uname():
                if self.DEBUG:
                    print(varname)
                if 'armv6' in varname:
                    if self.DEBUG:
                        print("armv6 spotted")
                    self.armv6 = True
                    self.framerate = 4
                  


            # Raspi config commands:
            # https://raspberrypi.stackexchange.com/questions/28907/how-could-one-automate-the-raspbian-raspi-config-setup

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
                

            if self.DEBUG:
                print("self.adapter.persistence_file_path = " + str(self.adapter.persistence_file_path))
        


        except Exception as e:
            print("Failed in first part of init: " + str(e))
        
           
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

                        
            except:
                first_run = True
                print("Could not load persistent data (if you just installed the add-on then this is normal)")
                
                try:
                    self.persistent_data = {'streaming':True, 'ringtone_volume':90, 'ringtone':'default', 'thing_settings':{}}
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
            
            
            
                
            # LOAD CONFIG
            try:
                self.add_from_config()
            except Exception as ex:
                print("Error loading config: " + str(ex))

            
            if self.DEBUG:
                print("self.manager_proxy = " + str(self.manager_proxy))
                print("Created new API HANDLER: " + str(manifest['id']))
        
        except Exception as e:
            print("Failed to init UX extension API handler: " + str(e))
        
        
        try:
            self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
            self.media_dir_path = os.path.join(self.user_profile['mediaDir'], self.addon_name)
            self.media_photos_dir_path = os.path.join(self.user_profile['mediaDir'], self.addon_name, 'photos')
            self.photos_file_path = os.path.join(self.addon_path, 'photos', 'latest.jpg')            
            self.media_stream_dir_path = os.path.join(self.media_dir_path, 'stream')
            self.addon_sounds_dir_path = os.path.join(self.addon_path, 'sounds')
            self.addon_sounds_dir_path = self.addon_sounds_dir_path + os.sep
            
            self.dash_file_path = os.path.join(self.media_stream_dir_path, 'index.mpd')
            #self.dash_stream_url = 'http://' + self.own_ip + ':8889/extensions/candlecam/stream/index.mpd'
            self.m3u8_file_path = os.path.join(self.media_stream_dir_path, 'master.m3u8')
            #self.m3u8_stream_url = 'http://' + self.own_ip + ':8889/extensions/candlecam/stream/master.m3u8'
            
            self.ffmpeg_output_path = os.path.join( self.media_stream_dir_path,'index.mpd')

            if self.DEBUG:
                print("self.media_dir_path = " + str(self.media_dir_path))
                print("self.media_photos_dir_path = " + str(self.media_photos_dir_path))
                print("self.ffmpeg_output_path = " + str(self.ffmpeg_output_path))
                print("self.addon_sounds_dir_path = " + str(self.addon_sounds_dir_path))
            
        except Exception as ex:
            print("Failed to generate paths: " + str(ex))
            
            
        try:
            print("mediaDir = " + str(self.user_profile['mediaDir']))
            
            media_dir = str(self.user_profile['mediaDir'])
            if not os.path.isdir( media_dir ):
                print( media_dir + " directory did not exist yet, creating it now")
                os.mkdir( media_dir )
        except Exception as ex:
            print("Error making media directory: " + str(ex))
            
        try:   
            print("self.media_dir_path = " + str(self.media_dir_path) )
            if not os.path.isdir( self.media_dir_path ):
                print( str(self.media_dir_path) + " directory did not exist yet, creating it now")
                os.mkdir( self.media_dir_path )
                
        except Exception as ex:
            print("Error making media/candlecam directory: " + str(ex))
                
        try:
            print("self.photos_dir_path = " + str(self.media_photos_dir_path) )
            if not os.path.isdir( self.media_photos_dir_path ):
                print(self.media_photos_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_photos_dir_path )
                
        except Exception as ex:
            print("Error making photos directory: " + str(ex))
            
        try:    
            if not os.path.isdir( self.media_stream_dir_path ):
                print(self.media_stream_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_stream_dir_path )
            
        except Exception as ex:
            print("Error making stream directory: " + str(ex))
                
            
        
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


        if self.persistent_data['streaming']:
            if self.DEBUG:
                print("According to persistent data, streaming was on. Setting streaming_change to True (starting ffmpeg).")
            self.streaming_change(True)

 
 
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
        
        

        #if self.DEBUG:
        #    print("Starting the ffmpeg thread")
        #try:
            #self.t = threading.Thread(target=self.ffmpeg) #, args=(self.voice_messages_queue,))
            #self.t.daemon = True
            #self.t.start()
        #    pass
        #except:
        #    print("Error starting the ffmpeg thread")
        
        

        
        """
        pwm = pigpio.pi() 
        pwm.set_mode(servo, pigpio.OUTPUT)
 
        pwm.set_PWM_frequency( servo, 50 )
 
        print( "0 deg" )
        pwm.set_servo_pulsewidth( servo, 500 ) ;
        time.sleep( 3 )
 
        print( "90 deg" )
        pwm.set_servo_pulsewidth( servo, 1500 ) ;
        time.sleep( 3 )
 
        print( "180 deg" )
        pwm.set_servo_pulsewidth( servo, 2500 ) ;
        time.sleep( 3 )
 
        # turning off servo
        pwm.set_PWM_dutycycle(servo, 0)
        pwm.set_PWM_frequency( servo, 0 )
        


        
        #self.gpio_button.when_released = self.dong
        
        """
        
        #my_factory = NativeFactory()
        #my_factory = PiGPIOFactory()
        
        # button
        #self.gpio_button = Button(17,bounce_time=1, pin_factory=my_factory)
        
        #self.gpio_button.when_pressed = self.ding

        #print("starting ffmpeg old school")
        #self.ffmpeg()
        #print("past starting ffmpeg old school")
        
        
        try:
            print("starting the thingy thread")
            self.t = threading.Thread(target=self.thingy) #, args=(self.voice_messages_queue,))
            self.t.daemon = True
            self.t.start()
            
        except:
            print("Error starting the thingy thread")
        
        #self.thingy()
        print("past creating thingy")
        

        
        
        """
        args = [
            '_webthing._tcp.local.',
            '{}._webthing._tcp.local.'.format(self.name),
        ]
        kwargs = {
            'addresses': [socket.inet_aton(get_ip())],
            'port': self.webthing_port,
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
        
        #PAGE+= self.adapter.own_ip
        
        
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


        #json_page = '{"id": "urn:dev:ops:candlecam-1234", "title": "Candle cam", "@context": "https://iot.mozilla.org/schemas", "properties": {"stream": {"@type": "VideoProperty", "title": "Stream", "type": "null", "description": "Video stream", "links": [{"rel": "alternative", "href": "http://192.168.2.167:8888/media/stream.mjpg", "mediaType": "x-motion-jpeg"}, {"rel": "property", "href": "/properties/stream"}]}}, "actions": {}, "events": {}, "links": [{"rel": "properties", "href": "/properties"}, {"rel": "actions", "href": "/actions"}, {"rel": "events", "href": "/events"}, {"rel": "alternate", "href": "ws://192.168.2.167:8888/"}], "description": "Candlecam test description", "@type": ["VideoCamera"], "base": "http://192.168.2.167:8888/", "securityDefinitions": {"nosec_sc": {"scheme": "nosec"}}, "security": "nosec_sc"}'
        #json_return = '{"stream": null}'

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
        

        
        if self.DEBUG:
            print("end of Candlecam init")
        
    #def ding_dong(self, state):
    #    print("in ding_dong. State: " + str(state))
    #    self.play_ringtone()
    #    self.button_state.notify_of_external_update(state)
        
    ###
    def ding(self, button):
    #def ding(self, button, **kwargs):
        print("in ding.")
        #print(str(button))
        #print(str(self.button_state))
        self.pressed = True
        self.pressed_count = 30
        return
        #loop = asyncio.new_event_loop()
        #            asyncio.set_event_loop(loop)
        #            return asyncio.get_event_loop()
        #asyncio.get_event_loop().create_task(self.pressed())
        
        #return
        #asyncio.run_coroutine_threadsafe(stop_loop(), self.loop)

        #try:
        #    pass
        #except Exception as ex:
        #    print("ding error: " + str(ex))
    
    #async def pressed(self):
    #    try:
    #        print("in pressed")
    #        self.button_state.notify_of_external_update(True)
    #        await time.sleep(2)
    #        self.button_state.notify_of_external_update(False)
    #    except CancelledError:
    #        print("cancelled")
            #pass
    ###
    
    #def dong(self, button):
    #    print("in dong")
        #try:
        #    
        #except Exception as ex:
        #    print("dong error: " + str(ex))
        
        
    """
    def gpio_thread(self):
        #GPIO.setwarnings(False) # Ignore warning for now
        GPIO.setmode(GPIO.BCM) # Use BCM pin numbering
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 17 to be an input pin and set initial value to be pulled low (off)
        
        self.button_being_pressed = False
        while True:
            if GPIO.input(17) == GPIO.LOW and self.button_being_pressed == False:
                self.button_being_pressed = True
                print("Button was pushed!")
                try:
                    self.button_state.notify_of_external_update(True)
                except Exception as ex:
                    print("GPIO thread error: " + str(ex))
                time.sleep(1)
                
            elif GPIO.input(17) == GPIO.HIGH and self.button_being_pressed == True:
                print("Button was released!")
                self.button_being_pressed = False
                try:
                    self.button_state.notify_of_external_update(False)
                except Exception as ex:
                    print("GPIO thread error: " + str(ex))
                time.sleep(1)
    """
        
        
        
    def ffmpeg(self):
        #os.system('pkill ffmpeg')
        
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
            print("encode_audio = " + str(self.encode_audio))
        
        #ffmpeg_command = 'ffmpeg -y -re -f v4l2 -thread_queue_size 64 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 '
        ffmpeg_command = '/usr/bin/ffmpeg '
        
        if self.DEBUG:
            ffmpeg_command += '-loglevel warning '
        if not self.DEBUG:
            ffmpeg_command += '-hide_banner -loglevel quiet '
            
        
        ffmpeg_command += ' -y -re -f v4l2 -fflags nobuffer -vsync 0 -thread_queue_size 128 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate ' + str(self.framerate) + ' -i /dev/video0 '
        
        if self.encode_audio:
            ffmpeg_command += '-f alsa  -fflags nobuffer -thread_queue_size 128 -ac 1 -ar 44100 -i plughw:1,0 -map 1:a -c:a aac -b:a 96k '
        #ffmpeg_command += '-map 0:v -b:v 400k -video_track_timescale 9000 '
        #if self.encode_audio:
        #    ffmpeg_command += '-map 1:a -c:a aac -b:a 96k '
        
        ffmpeg_command += '-map 0:v -video_track_timescale 900000 -vcodec h264_omx -b:v 400k -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 '
        ffmpeg_command += self.ffmpeg_output_path
                 #+ self.dash_file_path
        
        ffmpeg_command_array = ffmpeg_command.split()
        
        if self.DEBUG:
            #print("running ffmpeg command: " + str(ffmpeg_command))
            print("running ffmpeg split command: " + str(ffmpeg_command_array))
                 
        #run_command(ffmpeg_command)     # -thread_queue_size 16
        #self.ffmpeg_process = subprocess.call(ffmpeg_command_array)
        #self.ffmpeg_process = asyncio.run(run(ffmpeg_command)) 
        self.ffmpeg_process = subprocess.Popen(ffmpeg_command_array)
        #os.system(ffmpeg_command)
        print("end of run ffmpeg")
        
        # -muxdelay 0
        # -re # realtime
        # -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 1:a -c:a aac -b:a 96k
        # -init_seg_name init-$RepresentationID$.mp4 -media_seg_name segment-$RepresentationID$-$Number$.mp4
        # -init_seg_name init-cam1-$RepresentationID$.mp4 -media_seg_name cam1-$RepresentationID$-$Number$.mp4
        
        
        
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
            'urn:dev:ops:candlecam-1234',
            'Candle cam',
            ['VideoCamera','OnOffSwitch','PushButton'],
            'Candlecam test description'
        )

        met = {'@type': 'VideoProperty',
                        'title': 'Video',
                        'type': 'null',
                        'description': 'Video stream',
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
        
        prop = webthing.Property(thing,'stream',Value(None),met)
        if self.DEBUG:
            print("added videoProperty")
        thing.add_property(prop)
        
        
        # Enable or disable streaming
        streaming_atype = None
        button_atype = None
        
        if self.only_stream_on_button_press:
            button_atype = 'OnOffProperty'
        else:
            streaming_atype = 'OnOffProperty'
            
        
        thing.add_property(
            webthing.Property(thing,
                     'streaming',
                     #Value(self.persistent_data['streaming'], lambda v: self.streaming_change(v)),
                     Value(self.persistent_data['streaming'], self.streaming_change),
                     metadata={
                         '@type': streaming_atype,
                         'title': 'Streaming',
                         'type': 'boolean',
                         'description': 'Whether video video (and audio) is streaming',
                     }))
        
        thing.add_property(
            Prop(thing,
                     'button',
                     self.button_state,
                     metadata={
                         '@type': 'PushedProperty',
                         'title': 'Button',
                         'type': 'boolean',
                         'description': 'Whether video video (and audio) is streaming',
                     }))
                   
        thing.add_property(
            Prop(thing,
                     'volume',
                     Value(self.persistent_data['ringtone_volume'], lambda v: self.volume_change(v)),
                     metadata={
                         '@type': 'BrightnessProperty',
                         'title': 'Doorbell volume',
                         'type': 'integer',
                         'description': 'The volume of the tone being played at the door itself',
                         'minimum': 0,
                         'maximum': 100,
                         'unit': 'percent',
                     }))
                     
        thing.add_property(
            Prop(thing,
                     'led_brightness',
                     Value(self.persistent_data['led_brightness'], lambda v: self.led_brightness(v)),
                     metadata={
                         '@type': 'BrightnessProperty',
                         'title': 'Light brightness',
                         'type': 'integer',
                         'description': 'The brightness of the built-in color LED',
                         'minimum': 0,
                         'maximum': 100,
                         'unit': 'percent',
                     }))
                     
        thing.add_property(
            Prop(thing,
                     'led_color',
                     Value(self.persistent_data['led_color'], lambda v: self.led_color(v)),
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
                     

        if self.DEBUG:
            print('starting the sensor update looping task')
        self.button_timer = tornado.ioloop.PeriodicCallback(
            self.update_button,
            100
        )
        self.button_timer.start()
        
        
        """
        met = {'@type': 'OnOffProperty',
                        'title': 'Stream',
                        'type': 'boolean',
                        'description': 'Stream video (and audio)',
                        #'links': [{'href': '/things/lamp/properties/on'}]

                    }
        
        prop = webthing.Property(thing,'stream',Value(None),met)
        print("added videoPropperty")
        thing.add_property(prop)
        """

        
        """
        # Todo: look into doorbell press event
        thing.add_available_event(
            'overheated',
            {
                'description':
                'The lamp has exceeded its safe operating temperature',
                'type': 'number',
                'unit': 'degree celsius',
            })
        """
        if self.DEBUG:
            print("all thing properties added")
        
        more_routes = [
            #(r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            (r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/(.*)", WebThingServer.tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media"}),
            #(r"/media/(.*)", self.serve_file),
            #(r"/static/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ]
        
        if self.DEBUG:
            print("starting thing server (will block)")
        try:
            thing_server = WebThingServer(SingleThing(thing), port=self.webthing_port, additional_routes=more_routes)    
            thing_server.start()
        except Exception as ex:
            print("Error starting webthing server: " + str(ex))
            self.adapter.send_pairing_prompt("Error starting server. Tip: reboot.");
        if self.DEBUG:
            print("thing server started")
        #while(True):
        #    sleep(1)


    def update_button(self):
        if self.pressed:
            self.pressed = False
            if self.pressed_sent == False:
                self.pressed_sent = True
                self.button_state.notify_of_external_update(True)
                self.play_ringtone()
                
        elif self.pressed_sent == True:
            if self.pressed_count > 0:
                self.pressed_count -= 1
                if self.DEBUG:
                    print(str(self.pressed_count))
                
            else:
                self.pressed_sent = False
                self.button_state.notify_of_external_update(False)


    def volume_change(self,volume):
        if self.DEBUG:
            print("new volume: " + str(volume))
        self.persistent_data['ringtone_volume'] = volume
        self.save_persistent_data()

        
    def streaming_change(self,state):
        if self.DEBUG:
            print("new streaming state: " + str(state))
            
        if state:
            print("")
            print("THREAD ON")
            #self.t = threading.Thread(target=self.ffmpeg) #, args=(self.voice_messages_queue,))
            #self.t.daemon = True
            #self.t.start()
            self.ffmpeg()
            print("past self.ffmpeg in THREAD ON")
            
            try:
                #self.servo.min()
                #self.servo.angle = -90
                #print(str(self.pi))
                #self.pi.set_servo_pulsewidth(self.servo_pin, 1000) # 1000 -> 2000
                
                self.pwm.ChangeDutyCycle(99)
                
                """
                self.pwm.start(0)                  # Start PWM with 0% duty cycle
            
                for dc in range(0, 101, 5):         # Loop 0 to 100 stepping dc by 5 each loop
                    self.pwm.ChangeDutyCycle(dc)
                    time.sleep(0.05)              # wait .05 seconds at current LED brightness
                    print(dc)
                
                self.pwm.stop()
                """
                
                
                if self.DEBUG:
                    print("set servo to min")
            except Exception as ex:
                print("could not set servo: " + str(ex))
                
        else:
            print("")
            print("THREAD OFF")
            
            try:
                self.ffmpeg_process.terminate()
                print("ffmpeg process terminated command sent")
                self.ffmpeg_process.kill()
                print("ffmpeg process kill command sent")
                self.ffmpeg_process.wait()
                print("ffmpeg process terminated?")
            except Exception as ex:
                print("thread off error: " + str(ex))
            
            #try:
            #    self.t.stop()
            #except Exception as ex:
            #    print("thread t.stop() error: " + str(ex))
            
            try:
                #self.servo.max()
                #self.servo.angle = 90
                #self.pi.set_servo_pulsewidth(self.servo_pin,2000)
                
                self.pwm.ChangeDutyCycle(1)
                
                """
                self.pwm.start(100)                  # Start PWM with 0% duty cycle
            
                for dc in range(100, 0, 5):         # Loop 0 to 100 stepping dc by 5 each loop
                    self.pwm.ChangeDutyCycle(dc)
                    time.sleep(0.05)              # wait .05 seconds at current LED brightness
                    print(dc)
                
                self.pwm.stop()
                """
                
                if self.DEBUG:
                    print("set servo to max")
            except Exception as ex:
                print("could not set servo: " + str(ex))
            
        self.persistent_data['streaming'] = state
        self.save_persistent_data()


    def ringtone_change(self,choice):
        if self.DEBUG:
            print("new ringtone choice: " + str(choice))
        self.persistent_data['ringtone'] = choice
        self.save_persistent_data()
        self.play_ringtone()

        
    def play_ringtone(self):
        # aplay can only handle .wav files
        if str(self.persistent_data['ringtone']) != 'none':
            ringtone_command = 'aplay -D plughw:1,0 ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) + str(self.persistent_data['ringtone_volume'])+  '.wav'
            #ringtone_command = 'SDL_AUDIODRIVER="alsa" AUDIODEV="hw:1,0" ffplay ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) +  '.mp3'
            #ringtone_command = 'ffplay -autoexit ' + str(self.addon_sounds_dir_path) + str(self.persistent_data['ringtone']) +  '.mp3'
            
            if self.DEBUG:
                print("ringtone command: " + str(ringtone_command))
            
            ringtone_command_array = ringtone_command.split()
        
            if self.DEBUG:
                #print("running ffmpeg command: " + str(ffmpeg_command))
                print("running ringtone split command: " + str(ringtone_command_array))
                 
            #run_command(ffmpeg_command)     # -thread_queue_size 16
            #self.ffmpeg_process = subprocess.call(ffmpeg_command_array)
            #self.ffmpeg_process = asyncio.run(run(ffmpeg_command)) 
            self.ringtone_process = subprocess.Popen(ringtone_command_array)



    def led_color(self, hex):
        if self.DEBUG:
            print("setting led color to: " + str(hex))
        try:
            hex = hex.lstrip('#')
            rgb = tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))
            print('RGB =', str(rgb))
        
            r = rgb[0]
            g = rgb[1]
            b = rgb[2]
        
            self.lights.set_pixel(0, r, g, b)  # Pixel 1 to Red
            self.lights.set_pixel(1, r, g, b)  # Pixel 2 to Green
            self.lights.set_pixel(2, r, g, b)  # Pixel 3 to Blue
            self.lights.show()
        except Exception as ex:
            print("could not set LED brightness: " + str(ex))


    def led_brightness(self,brightness):
        if self.DEBUG:
            print("setting brightness to: " + str(brightness) + "%")
          
        print(dir(self.lights))
          
        try:  
            brightness = brightness / 100 # requires values between 0 and 1
            
            self.lights.global_brightness(0,brightness)
            self.lights.global_brightness(1,brightness)
            self.lights.global_brightness(2,brightness)
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
            self.clock = bool(config['Clock'])
            if self.DEBUG:
                print("-Clock preference was in config: " + str(self.clock))

        if 'Debugging' in config:
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("-Debugging preference was in config: " + str(self.DEBUG))



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
                                print('ajax handling init')
                                print("self.persistent_data = " + str(self.persistent_data))
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
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
                            
                            #self.camera.capture(self.photo_file_path, use_video_port=True)
                            
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
                            #self.camera.capture(self.photo_file_path, use_video_port=True)
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
            file_path = os.path.join(self.photos_dir_path, str(filename))
            os.remove(file_path)
            result = self.scan_photo_dir()
        except Exception as ex:
            print("Error deleting photo: " + str(ex))
        
        return result


    def scan_photo_dir(self):
        result = []
        try:
            for fname in os.listdir(self.photos_dir_path):
                if fname.endswith(".jpg") or fname.endswith(".jpeg") or fname.endswith(".gif"):
                    result.append(fname)    
        except:
            print("Error scanning photo directory")
        
        return result



    def unload(self):
        if self.DEBUG:
            print("Shutting down")


            
        try:
            self.pwm.stop()
            self.pi.stop()
            
        except Exception as ex:
            print("Unload: stopping pigpio error: " + str(ex))
        
        try:
            poll = self.ffmpeg_process.poll()
            print("poll = " + str(poll))
            if poll == None:
                print("poll was None - ffmpeg is still running.")
                self.ffmpeg_process.terminate()
                print("past treminate")
                self.ffmpeg_process.wait()
                print("past wait")
            else:
                print("poll was not none - ffmpeg crashed earlier?")
        except Exception as ex:
            print("Unload: terminating ffmpeg_process error: " + str(ex))

        #try:
        #    self.t.stop()
        #except Exception as ex:
        #    print("Unload: stopping thread error: " + str(ex))
        #os.system('pkill ffmpeg')
        #self.loop.stop()
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
        save_path = os.path.join(self.photos_dir_path, str(filename))

        
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

        # Make sure the persistence data directory exists
        try:
            
            self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
            #self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'data', self.addon_name,'persistence.json')
            self.persistence_dir_path = os.path.join(self.user_profile['dataDir'], self.addon_name)
            self.persistence_file_path = os.path.join(self.persistence_dir_path, 'persistence.json')
            
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
    
    
import asyncio

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        print(f'[stdout]\n{stdout.decode()}')
    if stderr:
        print(f'[stderr]\n{stderr.decode()}')

   
