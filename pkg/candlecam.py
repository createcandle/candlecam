"""Candlecam API handler."""

# Webthing
from __future__ import division
#from webthing import (Action, Event, Property, SingleThing, Thing, Value, WebThingServer)
#import webthings.Property as Property2

#import logging
import webthing
from webthing import (SingleThing, Thing, Value, WebThingServer)
#from webthing import Property as prop
import time
import uuid

import socket
import ifaddr

import functools
import json
import io
import os
import re
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
#from os import listdir
#from os.path import isfile, join
from time import sleep, mktime
import datetime
import subprocess
import threading
#from threading import Condition
import requests
import base64
#from pynput.keyboard import Key, Controller

import tornado.web

try:
    from gpiozero import Button
except:
    print("Could not load gpiozero library")



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
    from gateway_addon import Database, Adapter
    
    #from zeroconf import ServiceInfo, Zeroconf
    
    #import http.server as server
    print("libraries loaded")
    #print(str(server))
except:
    print("Could not load Pi Camera library")



try:
    from gateway_addon import APIHandler, APIResponse #, Database, Adapter, Device, Property
    
    #print("succesfully loaded APIHandler and APIResponse from gateway_addon")
except:
    print("Import APIHandler and APIResponse from gateway_addon failed. Use at least WebThings Gateway version 0.10")

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
            #if self.DEBUG:
            #    print("Candlecam adapter created")
            
            
            self.things = [] # Holds all the things, updated via the API. Used to display a nicer thing name instead of the technical internal ID.
            self.data_types_lookup_table = {}
            
            self.interval = 30
            self.contain = 1
        
            self.clock = False
        
            self.port = 8888
            self.name = 'candlecam' # thing name
            self.https = False
            self.own_ip = get_ip()
            
            self.encode_audio = False
            
            print("")
            print("aplay -l output:")
            aplay_output = run_command('aplay -l')
            print(str(aplay_output))
            if 'seeed' in aplay_output.lower():
                print("SEEED ReSpeaker hat spotted")
            else:
                print("No SEEED ReSpeaker hat spotted")

            print("self.adapter.persistence_file_path = " + str(self.adapter.persistence_file_path))
        
            # Get persistent data
            self.persistence_file_path = self.adapter.persistence_file_path

        
            if self.DEBUG:
                print("Current working directory: " + str(os.getcwd()))
        
            first_run = False
            try:
                with open(self.persistence_file_path) as f:
                    self.persistent_data = json.load(f)
                    if self.DEBUG:
                        print("Persistence data was loaded succesfully.")
                        
                    if 'thing_settings' not in self.persistent_data:
                        self.persistent_data['thing_settings'] = {}
                        
            except:
                first_run = True
                print("Could not load persistent data (if you just installed the add-on then this is normal)")
                try:
                    self.persistent_data = {'thing_settings':{}}
                    self.save_persistent_data()
                except Exception as ex:
                    print("Error creating initial persistence variable: " + str(ex))
        
        
        
        
        
        
            system_hostname = socket.gethostname().lower()
            self.hosts = [
                'localhost',
                'localhost:{}'.format(self.port),
                '{}.local'.format(system_hostname),
                '{}.local:{}'.format(system_hostname, self.port),
            ]
        
            for address in get_addresses():
                self.hosts.extend([
                    address,
                    '{}:{}'.format(address, self.port),
                ])

            self.hostname = None
            if self.hostname is not None:
                self.hostname = self.hostname.lower()
                self.hosts.extend([
                    self.hostname,
                    '{}:{}'.format(self.hostname, self.port),
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
        
        #print("_ _ _ ")
        #print("self.user_profile = " + str(self.user_profile))
        #print("")
        
        try:
            self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
            #self.persistence_file_folder = os.path.join(self.user_profile['configDir'])
            self.media_dir_path = os.path.join(self.user_profile['mediaDir'], self.addon_name)
            self.photos_dir_path = os.path.join(self.user_profile['mediaDir'], self.addon_name, 'photos')
            self.addon_photos_dir_path = os.path.join(self.addon_path, 'photos')
            self.addon_stream_dir_path = os.path.join(self.addon_path, 'stream')
            self.photo_file_path = os.path.join(self.addon_path, 'photos', 'latest.jpg')
            #self.photo_file_path = os.path.join(self.photos_dir_path,'latest.jpg')
            
            self.media_stream_dir_path = os.path.join(self.media_dir_path, 'stream')
            
            self.dash_file_path = os.path.join(self.media_stream_dir_path, 'index.mpd')
            #self.dash_stream_url = 'http://' + self.own_ip + ':8080/extensions/candlecam/stream/index.mpd'
            self.m3u8_file_path = os.path.join(self.media_stream_dir_path, 'master.m3u8')
            #self.m3u8_stream_url = 'http://' + self.own_ip + ':8080/extensions/candlecam/stream/master.m3u8'
            
            #self.ffmpeg_output_path = os.path.join( self.addon_stream_dir_path, 'index.mpd')
            self.ffmpeg_output_path = os.path.join( self.media_stream_dir_path,'index.mpd')
            #self.dash_file_path = os.path.join(self.addon_path, 'stream', 'index.mpd')

            
            print("self.photo_file_path = " + str(self.photo_file_path))
            print("self.ffmpeg_output_path = " + str(self.ffmpeg_output_path))
            
        except Exception as e:
            print("Failed to make paths: " + str(e))
            
        try:
            
            if not os.path.isdir( self.addon_photos_dir_path ):
                print(self.addon_photos_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.addon_photos_dir_path )
            
            if not os.path.isdir( self.addon_stream_dir_path ):
                print(self.addon_stream_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.addon_stream_dir_path )
            
            if not os.path.isdir( self.media_dir_path ):
                print(self.media_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.media_dir_path )
            
            if not os.path.isdir( self.photos_dir_path ):
                print(self.photos_dir_path + " directory did not exist yet, creating it now")
                os.mkdir( self.photos_dir_path )
                
            if not os.path.isdir( self.media_stream_dir_path ):
                print(self.self.media_stream_dir_path + " directory did not exist yet, creating it now")
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
        
        

        if self.DEBUG:
            print("Starting the ffmpeg command")
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
        
        

        self.thingy()

        

        
        
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
        
        PAGE+= self.adapter.own_ip
        
        
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


        json_page = '{"id": "urn:dev:ops:candlecam-1234", "title": "Candle cam", "@context": "https://iot.mozilla.org/schemas", "properties": {"stream": {"@type": "VideoProperty", "title": "Stream", "type": "null", "description": "Video stream", "links": [{"rel": "alternative", "href": "http://192.168.2.167:8888/media/stream.mjpg", "mediaType": "x-motion-jpeg"}, {"rel": "property", "href": "/properties/stream"}]}}, "actions": {}, "events": {}, "links": [{"rel": "properties", "href": "/properties"}, {"rel": "actions", "href": "/actions"}, {"rel": "events", "href": "/events"}, {"rel": "alternate", "href": "ws://192.168.2.167:8888/"}], "description": "Candlecam test description", "@type": ["VideoCamera"], "base": "http://192.168.2.167:8888/", "securityDefinitions": {"nosec_sc": {"scheme": "nosec"}}, "security": "nosec_sc"}'
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
        
        self.button = Button(17)

        self.button.when_pressed = self.ding_dong('ding')
        button.when_released = self.ding_dong('dong')
        
        
        print("end of init")
        
    def ding_dong(self, state):
        print("in ding_dong. State: " + str(state))
        
        
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
        
        print("encode_audio = " + str(self.encode_audio))
        ffmpeg_command = 'ffmpeg  -y -f v4l2 -fflags nobuffer -vsync 0 -video_size 640x480 -framerate 10 -i /dev/video0 '
        ffmpeg_command += '-muxdelay 0 -vcodec h264_omx -keyint_min 0 -g 10 '
        if self.encode_audio:
            ffmpeg_command += '-f alsa -thread_queue_size 16 -ac 1 -ar 44100 -i dsnoop:1,0 '
        ffmpeg_command += '-map 0:v -b:v 400k -video_track_timescale 9000 '
        if self.encode_audio:
            ffmpeg_command += '-map 1:a -c:a aac -b:a 96k '
        
        ffmpeg_command += ' -f dash -seg_duration 1 -use_template 1 -use_timeline 1 -remove_at_exit 1 -window_size 6 -extra_window_size 10 '
        ffmpeg_command += self.ffmpeg_output_path
                 #+ self.dash_file_path
        
        print("calling ffmpeg command: " + str(ffmpeg_command))
                 
                 
        run_command(ffmpeg_command)     # -thread_queue_size 16
        #os.system(ffmpeg_command)
        print("beyond run ffmpeg")
        
        # -muxdelay 0
        # -re # realtime
        # -f alsa -ac 1 -ar 44100 -i hw:1,0 -map 1:a -c:a aac -b:a 96k
        
        # -init_seg_name init-$RepresentationID$.mp4 -media_seg_name segment-$RepresentationID$-$Number$.mp4
        
        # -init_seg_name init-cam1-$RepresentationID$.mp4 -media_seg_name cam1-$RepresentationID$-$Number$.mp4
        
        
        
        
    def thingy(self):
        print("in thingy")
        
        
        #dash_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/index.mpd'
        #m3u8_stream_url = 'http://' + self.own_ip + '/extensions/candlecam/stream/master.m3u8'
        
        thing = Thing(
            'urn:dev:ops:candlecam-1234',
            'Candle cam',
            ['VideoCamera'],
            'Candlecam test description'
        )

        met = {'@type': 'VideoProperty',
                        'title': 'Stream',
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
        
        #prop = Property.__init__(thing,'stream',Value(None),met)
        prop = webthing.Property(thing,'stream',Value(None),met)
        print("propped")
        thing.add_property(prop)
        
        more_routes = [
            #(r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            (r"/media/candlecam/stream/(.*)", tornado.web.StaticFileHandler, {"path": self.media_stream_dir_path}),
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/candlecam/(.*)", tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media/candlecam"}),
            #(r"/media/(.*)", WebThingServer.tornado.web.StaticFileHandler, {"path": "/home/pi/.webthings/media"}),
            #(r"/media/(.*)", self.serve_file),
            #(r"/static/(.*)", web.StaticFileHandler, {"path": "/var/www"}),
        ]
        
        thing_server = WebThingServer(SingleThing(thing), port=8888, additional_routes=more_routes)
        print("thing_server:")
        print(str(dir(thing_server)))
        thing_server.start()
        print("thing server started")
        #while(True):
        #    sleep(1)
        


    #def serve_file(self, path_args, *args, **kwargs):
    def serve_file(self, var1, **kwargs):
        print("in server_file")
        print("path_args = " + str(var1))


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
        
        if self.DEV:
            print(str(config))
            
            
            
            
        if 'Use microphone' in config:
            self.encode_audio = bool(config['Use microphone'])
            if self.DEBUG:
                print("-Encode audio preference was in config: " + str(self.DEBUG))

        if 'Debugging' in config:
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("-Debugging preference was in config: " + str(self.DEBUG))

        if 'Interval' in config:
            self.interval = int(config['Interval'])
            if self.DEBUG:
                print("-Interval preference was in config: " + str(self.interval))

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
                                print('ajax handling init')
                                print("self.persistent_data = " + str(self.persistent_data))
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : True, 'message' : 'initialisation complete', 'thing_settings': self.persistent_data['thing_settings'] }),
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