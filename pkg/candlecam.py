"""Candlecam API handler."""

# Webthing
from __future__ import division
#from webthing import (Action, Event, Property, SingleThing, Thing, Value, WebThingServer)
#import webthings.Property as Property2

import re
import io
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

import time
from time import sleep, mktime
import uuid
import json


import base64
import socket
import ifaddr
import asyncio

import webthing
from webthing import (SingleThing, Thing, Value, WebThingServer)
from webthing import Property as Prop

import datetime
import threading
from threading import Condition
import functools
import subprocess
import tornado.web
import tornado.gen

import picamera

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

print = functools.partial(print, flush=True)


_TIMEOUT = 3

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.webthings', 'config'),
]

if 'WEBTHINGS_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['WEBTHINGS_HOME'], 'config'))


global _loop, candlecammy, new_frame, frame
#_loop = None
candlecammy = None
frame = None

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
            
            self.respeaker = False # Is a ReSPeaker 2 mic hat installed?
            if os.path.isdir("/etc/voicecard"):
                self.respeaker = True
            
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
            self.pressed_countdown_time = 60 #1200 # 1200 = 2 minutes
            self.pressed_countdown = self.pressed_countdown_time
            
            self.button_pin = 17
            self.servo_pin = 13
            
            self.terminated = False
            
        except Exception as ex:
            print("Failed in first part of init: " + str(ex))
            
            
        self.kill_ffmpeg()

            
        try: 
            if self.respeaker:
                
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
        
        
        
        # PATHS & DIRECTORIES
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


        # Start stream if necessary
        if self.persistent_data['streaming']:
            if self.DEBUG:
                print("According to persistent data, streaming was on. Setting streaming_change to True (starting streaming).")
            self.streaming_change(True)

        
        
        # Setup LED light
        try:
            if self.respeaker:
                if self.DEBUG:
                    print("setting up LED light on ReSpeaker hat")
                self.lights = APA102(3)
                self.set_led(self.persistent_data['led_color'],self.persistent_data['led_brightness'], False)
            
        except Exception as ex:
            print("Failed in LED setup: " + str(ex))
        

        
        
        try:
            if self.DEBUG:
                print("starting the thingy thread")
            self.t = threading.Thread(target=self.thingy) #, args=(self.voice_messages_queue,))
            self.t.daemon = True
            self.t.start()
            
        except:
            print("Error starting the thingy thread")
        
        
        if self.DEBUG:
            print("end of Candlecam init")
        

    def ding(self, button):
        if self.DEBUG:
            print("in ding.")
        self.pressed = True
        self.pressed_countdown = self.pressed_countdown_time
        return
        
        
    def ffmpeg(self):
        if self.DEBUG:
            print("encode_audio = " + str(self.encode_audio))
        
        ffmpeg_command = '/usr/bin/ffmpeg '
        
        if self.DEBUG:
            ffmpeg_command += '-loglevel warning '
        if not self.DEBUG:
            ffmpeg_command += '-hide_banner -loglevel quiet '
            
        
        ffmpeg_command += ' -y -re -f v4l2 -fflags nobuffer -vsync 0 -thread_queue_size 128 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate ' + str(self.framerate) + ' -i /dev/video0 '
        
        if self.encode_audio:
            ffmpeg_command += '-f alsa  -fflags nobuffer -thread_queue_size 128 -ac 1 -ar 44100 -i plughw:1,0 -map 1:a -c:a aac -b:a 96k '
        
        ffmpeg_command += '-map 0:v -video_track_timescale 900000 -vcodec h264_omx -b:v 400k -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 '
        ffmpeg_command += self.ffmpeg_output_path
                 #+ self.dash_file_path
        
        ffmpeg_command_array = ffmpeg_command.split()
        
        if self.DEBUG:
            print("running ffmpeg split command: " + str(ffmpeg_command_array))
                 
        self.ffmpeg_process = subprocess.Popen(ffmpeg_command_array)
        
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


        if self.encode_audio:
            met = {'@type': 'VideoProperty',
                            'title': 'Video',
                            'type': 'null',
                            'description': 'Video stream',
                            'links':[
                                {
                                    'rel':'alternate',
                                    'href':'/media/candlecam/stream/index.mpd',
                                    'mediaType': 'application/dash+xml'
                                },
                                {
                                    'rel': 'alternate',
                                    'href': '/media/candlecam/stream/master.m3u8',
                                    'mediaType': 'application/vnd.apple.mpegurl'
                                }
                            ]
                        }
        else:
            met = {'@type': 'VideoProperty',
                            'title': 'Video',
                            'type': 'null',
                            'description': 'Video stream',
                            'links':[
                                {
                                    'rel':'alternate',
                                    'href':'/mjpg',
                                    'mediaType':'video/x-motion-jpeg'
                                },
                            ]
                        }
        
        prop = webthing.Property(thing,'stream',Value(None),met)
        if self.DEBUG:
            print("added videoProperty")
        thing.add_property(prop)
        
        
        # Enable or disable streaming
        #streaming_atype = None
        #button_atype = None
        
        #if self.respeaker and self.only_stream_on_button_press:
        #    button_atype = 'OnOffProperty'
        #else:
        #    streaming_atype = 'OnOffProperty'
            
        
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
        
        
        
        if self.respeaker:
            
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
                     

        if self.DEBUG:
            print('starting the sensor update looping task')
        self.button_timer = tornado.ioloop.PeriodicCallback(
            self.update_button,
            100
        )
        self.button_timer.start()
        

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
        
        
        more_routes = []
        
        if self.encode_audio == False:
            
            test = "hoi"
            
            #self.picamera = FrameCamera()
            #print("self.picamera = " + str(self.picamera))
            
            #print("BEYOND WITH PICAMERA")
            
            #global candlecammy
            
            #self.candlecammy_thread()
            
            #global candlecammy
            #candlecammy = cam()
            #print("pre-candlecammy: " + str(candlecammy))
            
            """
            try:
                if self.DEBUG:
                    print("starting the thingy thread")
                self.c = threading.Thread(target=self.candlecammy_thread, args=(candlecammy,))
                self.c.daemon = True
                self.c.start()
            
            except:
                print("Error starting the thingy thread")
            """
            
            #print("creating streaminghandler")
            
            #streaming_handler = StreamingHandler()
            #test_handler = TestHandler()
            
            #more_routes.append( (r'/media/mjpg', StreamingHandler) )
            #more_routes.append( (r"/media/test/(.*)", TestHandler) )
            more_routes.append( (r'/mjpg', StreamyHandler) ) #, {"cam":candlecammy}
            
            
            
            print("MORE ROUTES APPENDED: " + str(more_routes))
            
        else:
            print("not starting picamera and it's mjpeg streamhandler")

        more_routes.append( (r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}) )
        
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
        if self.respeaker:
            
            if state == 'closed':
                self.set_led(self.persistent_data['led_color'],self.persistent_data['led_brightness'],False)
                try:
                    self.pwm.ChangeDutyCycle(1)
                    if self.DEBUG:
                        print("set servo to closed (1)")
                except Exception as ex:
                    print("could not set servo: " + str(ex))
                    
            elif state == 'open':
                self.set_led('#ffffff',100,False) # set LED to full brightness.
                try:
                    self.pwm.ChangeDutyCycle(70)
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
        
        if self.DEBUG:
            print(str(config))
            
            
        if 'Use microphone' in config:
            self.encode_audio = bool(config['Use microphone'])
            self.encode_audio = False
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
                        
                            
                        action = str(request.body['action'])    
                        
                        if action == 'init':
                            
                            if self.DEBUG:
                                print('ajax handling init')
                                print("self.persistent_data = " + str(self.persistent_data))
                                
                            return APIResponse(
                              status=200,
                              content_type='application/json',
                              content=json.dumps({'state': True, 'own_ip': self.own_ip, 'message': 'initialisation complete', 'thing_settings': self.persistent_data['thing_settings'] }),
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
    #def get_init_data(self):
    #    if self.DEBUG:
    #        print("Getting the initialisation data")


        
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
        self.join()
 

        
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


        # Make sure the persistence data directory exists
        try:            
            self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
            self.persistence_dir_path = os.path.join(self.user_profile['dataDir'], self.addon_name)
            self.persistence_file_path = os.path.join(self.persistence_dir_path, 'persistence.json')
            
            if not os.path.isdir(self.persistence_dir_path):
                os.mkdir( self.persistence_dir_path )
                print("Persistence directory did not exist, created it now")
        except:
            print("Error: could not make sure persistence dir exists. intended persistence dir path: " + str(self.persistence_dir_path))



#
#  PICAMERA CLASSES
#

class StreamOutput(object):
    def __init__(self):
        self.snapshot = None

    def write(self, buf):
        #global new_frame
        global frame
        if buf.startswith(b'\xff\xd8'):
            self.snapshot = io.BytesIO()
            #self.snapshot.seek(0)
        self.snapshot.write(buf)
        if buf.endswith(b'\xff\xd9'):
            #self.snapshot.close()
            frame = self.snapshot
            
    def close(self):
        self.snapshot.close()


class StreamyHandler(tornado.web.RequestHandler):

    #@tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        global frame
        #global new_frame
        #global candlecammy
            
        mjpg_interval = .1
        #ioloop = tornado.ioloop.IOLoop.current()
        my_boundary = "--jpgboundary"
        self.served_image_timestamp = time.time()
        
        #self.set_header('Cache-Control', 'no-cache, private')
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.set_header('Pragma', 'no-cache')
        #self.set_header('Connection', 'close')
        self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--jpgboundary')
        self.flush()
        
        while True:
            self.write(my_boundary + '\r\n')
            self.write("Content-type: image/jpeg\r\n")
            self.write("Content-length: %s\r\n\r\n" % frame.getbuffer().nbytes)
            self.write(frame.getvalue())
            self.write('\r\n')
            self.served_image_timestamp = time.time()
            #print(str(self.served_image_timestamp))
            self.flush()
            yield tornado.gen.sleep(.1)
        
    def on_finish(self):
        #print("in on_finish")
        pass


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
   

