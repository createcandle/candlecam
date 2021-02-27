(function() {
	class Candlecam extends window.Extension {
	    constructor() {
	      	super('candlecam');
			//console.log("Adding Photo frame to menu");
	      	this.addMenuEntry('Candlecam');

	      	this.content = '';
			//var filenames = [];
			this.filenames = [];
			window.candlecam_filenames = [];


			this.interval = 30;
			this.contain = true;
			this.clock = false;
            
            this.thing_settings = {
                'camera_source_thing_id': '',
                'camera_source_property_id': '',
    
                'push_button_thing_id':'',
                'push_button_property_id':'',
    
                'door_release_thing_id':'',
                'door_release_property_id': '',
            }
            
            
            
			
			fetch(`/extensions/${this.id}/views/content.html`)
			.then((res) => res.text())
			.then((text) => {
				this.content = text;
				if( document.location.href.endsWith("candlecam") ){
					this.show();
				}
			})
			.catch((e) => console.error('Failed to fetch content:', e));
			
	    }
		
		
		
		change_picture(){
			
			if( window.candlecam_filenames.length > 0 ){
				var random_file = window.candlecam_filenames[Math.floor(Math.random() * window.candlecam_filenames.length)];
				//console.log("new picture: " + random_file);
				this.show_file(random_file);
			}
		}


		create_thing_list(body){
			//console.log("Creating main thing list");
			
			const pre = document.getElementById('extension-candlecam-response-data');
			const thing_list = document.getElementById('extension-candlecam-thing-list');

			for (var key in body['data']) {

				var dataline = JSON.parse(body['data'][key]['name']);
				
				var this_object = this;
				
				var node = document.createElement("LI");
			}
			pre.innerText = "";
		}
		
	
		
		
		/*
		// HELPER METHODS
		
		hasClass(ele,cls) {
			return !!ele.className.match(new RegExp('(\\s|^)'+cls+'(\\s|$)'));
		}

		addClass(ele,cls) {
			if (!this.hasClass(ele,cls)) ele.className += " "+cls;
		}

		removeClass(ele,cls) {
			if (this.hasClass(ele,cls)) {
		    	var reg = new RegExp('(\\s|^)'+cls+'(\\s|$)');
		    	ele.className=ele.className.replace(reg,' ');
		  	}
		}
        
		
		thing_list_click(the_target){
			const pre = document.getElementById('extension-candlecam-response-data');
    	}
        */


        show() {
    		if(this.content == ''){
    			return;
    		}
    		else{
    			this.view.innerHTML = this.content;
    		}	
	  
    		const clock_element = document.getElementById('extension-candlecam-clock');
    		const pre = document.getElementById('extension-candlecam-response-data');
    		const thing_list = document.getElementById('extension-candlecam-thing-list');

            const camera_source_select = document.getElementById('extension-candlecam-camera-source-select');
            const push_button_select = document.getElementById('extension-candlecam-push-button-select');
            const door_release_select = document.getElementById('extension-candlecam-door-release-select');


    		pre.innerText = "";
		
    		var this_object = this;
		
    		if( window.innerHeight == screen.height) {
    			//console.log("fullscreen");
    			document.getElementById('extension-candlecam-photos-file-selector').outerHTML = "";
    			document.getElementById('extension-candlecam-dropzone').outerHTML = "";
			
    		}
    		else{
    			//console.log("Attaching file listeners");
    			document.getElementById("extension-candlecam-photos-file-selector").addEventListener('change', () => {
    				var filesSelected = document.getElementById("extension-candlecam-photos-file-selector").files;
    				this.upload_files(filesSelected);
    			});
			
    			this.createDropzoneMethods();
    		}
        
        
            console.log(API);
        
            window.API.postJson(
              `/extensions/candlecam/api/ajax`,
      				{'action':'init'}

            ).then((body) => {
                console.log(".");
      			console.log("init returned:");
      			console.log(body);
                //body_parsed = JSON.parse(body);
                //console.log(body_parsed);
                //this.thing_settings = JSON.parse(body['thing_settings']);
                this.thing_settings = body['thing_settings'];
                // Reveal settings button
    			this.removeClass(document.getElementById('extension-candlecam-settings-button'),"extension-candlecam-hidden");
        	    API.getThings().then((things) => {
			
            
                    console.log("GOT THINGS");
                    console.log(this.thing_settings);
                    if(this.thing_settings != null){
                        console.log(this.thing_settings.camera_source_thing_id);
                        console.log("this.thing_settings['camera_source_thing_id'] = " + this.thing_settings['camera_source_thing_id'] );
                    }
                    
        			this.all_things = things;
            
        			// pre-populate the hidden 'new' item with all the thing names
        			var thing_ids = [];
        			var thing_titles = [];
			
        			for (let key in things){

        				var thing_title = 'unknown';
        				if( things[key].hasOwnProperty('title') ){
        					thing_title = things[key]['title'];
        				}
        				else if( things[key].hasOwnProperty('label') ){
        					thing_title = things[key]['label'];
        				}
                        //console.log(thing_title);
                
                        var thing_id = things[key]['href'].substr(things[key]['href'].lastIndexOf('/') + 1);
                        thing_ids.push( things[key]['href'].substr(things[key]['href'].lastIndexOf('/') + 1) );
            
        				var property_lists = this.get_property_lists(things[key]['properties'],'videoProperty');
				
                        //for (let prop in property_lists['property1_list']){
                        for (var i = 0; i < property_lists['property1_list'].length; i++) {
        				//if(property_lists['property1_list'].length > 0){
        					console.log(i);
                            //console.log("adding thing to source list because it has a video Property");
                            var selected_state = false;
                            if(this.thing_settings != null){
                                //console.log("thing settings existed in body");
                                //if(thing_id == this.thing_settings['camera_source_thing_id'] && property_lists['property1_system_list'][i] == this.thing_settings['camera_source_property_id']){
                                console.log("this.thing_settings['camera_source_thing_id'] = " + this.thing_settings['camera_source_thing_id'] );
                                console.log("=?= thing_id = " + thing_id);
                                if(thing_id == this.thing_settings['camera_source_thing_id'] && property_lists['property1_system_list'][i] == this.thing_settings['camera_source_property_id']){
                                    console.log("setting option as selected");
                                    selected_state = true;
                                }
                            }
        					camera_source_select.options[camera_source_select.options.length] = new Option(thing_title + " - " + property_lists['property1_list'][i], thing_id + "_____" + property_lists['property1_system_list'][i],false,selected_state);
        				}
                
                
                        property_lists = this.get_property_lists(things[key]['properties'],'boolean');
				
                        //for (let prop in property_lists['property1_list']){
                        for (var i = 0; i < property_lists['property1_list'].length; i++) {
        				//if(property_lists['property1_list'].length > 0){
        					//console.log("adding thing to source list because it has a boolean Property");
                            var selected_state = false;
                            if(this.thing_settings != null){
                                //console.log("thing settings existed in body");
                                //if(thing_id == this.thing_settings['camera_source_thing_id'] && property_lists['property1_system_list'][i] == this.thing_settings['camera_source_property_id']){
                                if(thing_id == this.thing_settings['push_button_thing_id']  && property_lists['property1_system_list'][i] == this.thing_settings['push_button_property_id']){
                                    console.log("setting option as selected");
                                    selected_state = true;
                                }
                            }
                            push_button_select.options[push_button_select.options.length] = new Option(thing_title + " - " + property_lists['property1_list'][i], thing_id + "_____" + property_lists['property1_system_list'][i],false,selected_state);
					
        				}
                
                        property_lists = this.get_property_lists(things[key]['properties'],'actuator-boolean');
				
                        //for (let prop in property_lists['property1_list']){
                        for (var i = 0; i < property_lists['property1_list'].length; i++) {
        				//if(property_lists['property1_list'].length > 0){
        					//console.log("adding thing to source list because it has a boolean Property");
                            var selected_state = false;
                            if(this.thing_settings != null){
                                //console.log("thing settings existed in body");
                                console.log("_");
                                console.log(property_lists['property1_system_list'][i]);
                                console.log(this.thing_settings['door_release_property_id']);
                                //if(thing_id == this.thing_settings['camera_source_thing_id'] && property_lists['property1_system_list'][i] == this.thing_settings['camera_source_property_id']){
                                if(thing_id == this.thing_settings['door_release_thing_id']  && property_lists['property1_system_list'][i] == this.thing_settings['door_release_property_id']){
                                    console.log("setting option as selected");
                                    selected_state = true;
                                }
                            }
        					door_release_select.options[door_release_select.options.length] = new Option(thing_title + " - " + property_lists['property1_list'][i], thing_id + "_____" + property_lists['property1_system_list'][i],false,selected_state);
        				}
    				
                
                    }
                    this.generate_ui();
                });
            
            }).catch((e) => {
            	//pre.innerText = e.toString();
      			console.log("Candle cam: error during init phase: " + e.toString());
            });
        
        
        
	    
        
        
            const manifestUri = '/media/candlecam/index.mpd';

            function initApp() {
              // Install built-in polyfills to patch browser incompatibilities.
              shaka.polyfill.installAll();
              // Check to see if the browser supports the basic APIs Shaka needs.
          
              if (shaka.Player.isBrowserSupported()) {
                // Everything looks good!
                initPlayer();
              } else {
                // This browser does not have the minimum set of APIs we need.
                console.error('Browser not supported!');
              }
          
            }

            async function initPlayer() {
              // Create a Player instance.
              const video = document.getElementById('extension-candlecam-shaka-video');
              const player = new shaka.Player(video);
              console.log("shaka conf");
              console.log(player.getConfiguration());
              //player.configure('streaming.bufferingGoal', 0);
              //player.configure('streaming.bufferBehind', 0);
          
              player.configure({
                streaming: {
                  bufferingGoal: 0,
                  rebufferingGoal: 0,
                  bufferBehind:0
                }
              });
          
              player.getNetworkingEngine().registerRequestFilter((type, request) => {
                      request.headers = {
                        Authorization: `Bearer ${API.jwt}`,
                      };
                    });
          

              // Attach player to the window to make it easy to access in the JS console.
              window.player = player;

              // Listen for error events.
              player.addEventListener('error', onErrorEvent);

              // Try to load a manifest.
              // This is an asynchronous process.
              try {
                await player.load(manifestUri);
                // This runs if the asynchronous load is successful.
                console.log('The video has now been loaded!');
              } catch (e) {
                // onError is executed if the asynchronous load fails.
                onError(e);
              }
            }

            function onErrorEvent(event) {
              // Extract the shaka.util.Error object from the event.
              onError(event.detail);
            }

            function onError(error) {
              // Log the error.
              console.error('Error loading video: ', error.code, 'object', error);
            }

            //document.addEventListener('DOMContentLoaded', initApp);
        
        
    		try {
                //console.log(window.shaka);
                function waitForElement(){
                    if(typeof shaka !== "undefined"){
                        console.log("Shaka no longer undefined. Starting...");
                        initApp();
                    }
                    else{
                        console.log("wait...");
                        setTimeout(waitForElement, 250);
                    }
                }
                waitForElement();
			
    		}
    		catch (e) {
    			console.log("Could not start Shaka video player: " + e);
    		}
        
        
        
        
			

    		// EVENT LISTENERS

    		document.getElementById("extension-candlecam-picture-exit").addEventListener('click', () => {
    			event.stopImmediatePropagation();
    			const picture = document.getElementById('extension-candlecam-picture-holder');
    			const overview = document.getElementById('extension-candlecam-overview');
    			this.removeClass(overview,"extension-candlecam-hidden");
    			this.addClass(picture,"extension-candlecam-hidden");
    		});
			
    		/*	
    		document.getElementById("extension-candlecam-picture-holder").addEventListener('click', () => {
    			var menu_button = document.getElementById("menu-button");
    			menu_button.click();//dispatchEvent('click');
    		});
            */
        
        
            // Settings toggle
		
            document.getElementById("extension-candlecam-settings-button").addEventListener('click', () => {
    			console.log("click");
                event.stopImmediatePropagation();
    			const settings_view = document.getElementById('extension-candlecam-settings-container');
    			//const overview = document.getElementById('extension-candlecam-overview');
                if(this.hasClass(settings_view,'extension-candlecam-hidden')){
                    this.removeClass(settings_view,"extension-candlecam-hidden");
                }else{
                    this.addClass(settings_view,"extension-candlecam-hidden");
                
                    const camera_source_select = document.getElementById('extension-candlecam-camera-source-select');
                    const push_button_select = document.getElementById('extension-candlecam-push-button-select');
                    const door_release_select = document.getElementById('extension-candlecam-door-release-select');
        
                    console.log("push_button_select.value = " + push_button_select.value);
                    console.log("door_release_select.value = " + door_release_select.value);
        
                    this.thing_settings['camera_source_thing_id'] = camera_source_select.value.split("_____")[0];
                    this.thing_settings['camera_source_property_id'] = camera_source_select.value.split("_____")[1];
        
                    this.thing_settings['push_button_thing_id'] = push_button_select.value.split("_____")[0];
                    this.thing_settings['push_button_property_id'] = push_button_select.value.split("_____")[1];
        
                    this.thing_settings['door_release_thing_id'] = door_release_select.value.split("_____")[0];
                    this.thing_settings['door_release_property_id'] = door_release_select.value.split("_____")[1];
                
                    //console.log("this.thing_settings.door_release_thing_id = " + this.thing_settings.door_release_thing_id);
                    //console.log("this.thing_settings.door_release_property_id = " + this.thing_settings.door_release_property_id);
                    
        	        window.API.postJson(
        	          `/extensions/candlecam/api/ajax`,
                        {'action':'save_settings','thing_settings':this.thing_settings}

        	        ).then((body) => {
        	  			console.log("save settings returned:");
        	  			console.log(body);
        	        }).catch((e) => {
        	        	//pre.innerText = e.toString();
        	  			console.log("Candlecam: error saving settings: " + e.toString());
        	        });
                    
                    
                    this.generate_ui();
                }
    		});
        
            document.getElementById("extension-candlecam-door-release-button").addEventListener('click', () => {
                console.log("this.thing_settings.door_release_property_id = " + this.thing_settings.door_release_property_id);
                const property_id = this.thing_settings.door_release_property_id;
                const message = JSON.parse(`{ "${this.thing_settings.door_release_property_id}": true}`);
                console.log(message);
                API.putJson(`/things/${this.thing_settings.door_release_thing_id}/properties/${this.thing_settings.door_release_property_id}`, message);
            });
        
            document.getElementById("extension-candlecam-door-close-button").addEventListener('click', () => {
                console.log("this.thing_settings.door_release_property_id = " + this.thing_settings.door_release_property_id);
                const property_id = this.thing_settings.door_release_property_id;
                const message = JSON.parse(`{ "${this.thing_settings.door_release_property_id}": false}`);
                console.log(message);
                API.putJson(`/things/${this.thing_settings.door_release_thing_id}/properties/${this.thing_settings.door_release_property_id}`, message);
            });
        
			

    		// Get list of photos (as well as other variables)
			
          	window.API.postJson(
            	`/extensions/${this.id}/api/list`,
    				{'init':1}
			
    		).then((body) => {
    				this_object.settings = body['settings'];
    				this_object.interval = body['settings']['interval'];
    				this_object.contain = body['settings']['contain'];
    				this_object.clock = body['settings']['clock'];
		
    		if( this_object.contain ){
    			//console.log("Contain the image");
    			document.getElementById('extension-candlecam-picture-holder').style.backgroundSize = "contain";
    		}
    		else{
    			//console.log("Do not contain the image");
    			document.getElementById('extension-candlecam-picture-holder').style.backgroundSize = "cover";
    		}
		
		
    		// Interval
    		this_object.photo_interval = setInterval(function () {
    				//console.log("intervallo");
    				this_object.change_picture();

    		}, this_object.interval * 1000);
		
    		if( body['data'].length > 0 ){
    			this_object.filenames = body['data'];
    			this_object.show_list(body['data']);
    			this_object.change_picture();
    		}
		

    		if(this_object.clock){
    			// Start clock
    			clearInterval(window.candlecam_clock_interval); 
			
    			window.candlecam_clock_interval = setInterval(function () {
    				//console.log("Clock tick");
				
    				var hour_padding = "";
    				var minute_padding = "";
				
    				var date = new Date(); /* creating object of Date class */
    				var hour = date.getHours();
    				var min = date.getMinutes();
    				var sec = date.getSeconds();
	
    				if( min < 10 ){
    					minute_padding = "0";
    				}
    				if( hour < 10 ){
    					hour_padding = "0";
    				}
				
    				clock_element.innerText = hour + ":" + minute_padding + min;
	
    			}, 1000);
    		}
            

          	}).catch((e) => {
            	//pre.innerText = e.toString();
    			console.log("Photo frame: error in show list function: " + e.toString());
          	});
	  
	  
    	  	// Set interval to keep the screen awake
    		this_object.wake_interval = setInterval(function () {
    			//console.log("Sending wake command");
    	        window.API.postJson(
    	          `/extensions/candlecam/api/wake`,
    	  				{'init':1}

    	        ).then((body) => {
    	  			//console.log("wake returned:");
    	  			//console.log(body);
    	        }).catch((e) => {
    	        	//pre.innerText = e.toString();
    	  			console.log("Photo frame: error in keep awake function: " + e.toString());
    	        });
			
    		}, 30000);
	  
        } // and of show function
		
		
    	hide(){
		
    		try {
    			window.clearInterval(this.photo_interval);
    		}
    		catch (e) {
    			console.log("Could not clear photo rotation interval");
    			console.log(e); //logMyErrors(e); // pass exception object to error handler
    		}
		
    		try {
    			window.clearInterval(this.wake_interval);
    		}
    		catch (e) {
    			console.log("Could not clear keep awake interval");
    			console.log(e); //logMyErrors(e); // pass exception object to error handler
    		}
    	}



    	//
    	//  GENERATE UI
    	//

        async generate_ui(){
            console.log("Generating UI");
            //console.log("this.push_button_thing_id: " + this.push_button_thing_id);
        
            console.log(this.all_things);
        
            const things = this.all_things;
        
    		for (let key in things){

    			var thing_title = 'unknown';
    			if( things[key].hasOwnProperty('title') ){
    				thing_title = things[key]['title'];
    			}
    			else if( things[key].hasOwnProperty('label') ){
    				thing_title = things[key]['label'];
    			}
                //console.log(things[key]['href']);
                //console.log('/things/' + this.camera_source_thing_id);
            
                // LOAD VIDEO
                if(things[key]['href'] == '/things/' + this.thing_settings.camera_source_thing_id){
                    console.log("bingo1");
                    for (let prop in things[key]['properties']){
                        console.log(prop);
                        console.log(things[key]['properties'][prop]['name']);
                        console.log(this.camera_source_property_id);
                        if(things[key]['properties'][prop]['name'] == this.thing_settings.camera_source_property_id){
                            console.log("bingo");
                            for (var i = 0; i < things[key]['properties'][prop]['links'].length; i++) {
                                if(things[key]['properties'][prop]['links'][i]['rel'] == 'alternate'){
                                    //if(things[key]['properties'][prop]['links'][i]['mediaType'] == 'application/dash+xml'){
                                        try {
                                            console.log("loading video: " + things[key]['properties'][prop]['links'][i]['href']);
                                        
                                            await player.load( things[key]['properties'][prop]['links'][i]['href'] +'?jwt=' + API.jwt );
                                            // This runs if the asynchronous load is successful.
                                            console.log('- The video has now been loaded!');
                                            break;
                                        } catch (e) {
                                            console.log('- Loading video failed');
                                            // onError is executed if the asynchronous load fails.
                                            console.log(e);
                                        }
                                    //}
                                } 
                            }
                        }
                    }
                
                }
            
            }
        
        }




    	//
    	//  SHOW LIST
    	//

        show_list(file_list){
    		//console.log("Updating photo list")
    		const pre = document.getElementById('extension-candlecam-response-data');
    	  	const photo_list = document.getElementById('extension-candlecam-photos-list');
    		const picture = document.getElementById('extension-candlecam-picture-holder');
    		const overview = document.getElementById('extension-candlecam-overview');
		
    		file_list.sort();
		
    		window.candlecam_filenames = file_list;
    		//this.filenames = file_list;
		
    		photo_list.innerHTML = "";
		
    		for (var key in file_list) {
			
    			var this_object = this;
			
    			var node = document.createElement("LI");                 					// Create a <li> node
    			node.setAttribute("class", "extension-candlecam-list-item" ); 
    			node.setAttribute("data-filename", file_list[key] );
			
    			var img_container_node = document.createElement("div");                 					// Create a <li> node
    			img_container_node.setAttribute("class", "extension-candlecam-list-thumbnail-container" ); 
			
			
    			var imgnode = document.createElement("IMG");         // Create a text node
    			imgnode.setAttribute("class","extension-candlecam-list-thumbnail");
    			imgnode.setAttribute("data-filename",file_list[key]);
    			imgnode.src = "/extensions/candlecam/photos/" + file_list[key];
    			imgnode.onclick = function() { 
    				this_object.show_file( this.getAttribute("data-filename") ); //file_list[key]
    				this_object.addClass(overview,"extension-candlecam-hidden");
    				this_object.removeClass(picture,"extension-candlecam-hidden");
    			};
    			//console.log(imgnode);
    			img_container_node.appendChild(imgnode); 
    			node.appendChild(img_container_node); 
			
    			var textnode = document.createElement("span"); 
    			textnode.setAttribute("class","extension-candlecam-deletable_item");
    			textnode.setAttribute("data-filename", file_list[key]);
    			//console.log(textnode);
    			textnode.innerHTML = file_list[key];         // Create a text node
    			textnode.onclick = function() { 
    				//this_object.delete_file( file_list[key] );
    				//console.log(this.getAttribute("data-filename"));
    				this_object.delete_file( this.getAttribute("data-filename") );
    			};
    			node.appendChild(textnode); 
			
    			photo_list.appendChild(node);
    		}
    		pre.innerText = "";
    	}

		
		
    	delete_file(filename){
        //console.log("Deleting file:" + filename);
			
    	const pre = document.getElementById('extension-candlecam-response-data');
    	const photo_list = document.getElementById('extension-candlecam-photo-list');
		
        window.API.postJson(
            `/extensions/${this.id}/api/delete`,
            {'action':'delete', 'filename':filename}
				
          ).then((body) => { 
    				//console.log(body);
            this.show_list(body['data']);

          }).catch((e) => {
    				console.log("Photo frame: error in delete response");
            pre.innerText = e.toString();
          });
    
        }
		
	
    	show_file(filename){
    		const pre = document.getElementById('extension-candlecam-response-data');
    		const picture = document.getElementById('extension-candlecam-picture-holder');
    		const overview = document.getElementById('extension-candlecam-overview');
    		//console.log("showing photo: " + filename);
    		picture.style.backgroundImage="url(/extensions/candlecam/photos/" + filename + ")";
    	}


    	upload_files(files){
    		if (files && files[0]) {
			
    			var filename = files[0]['name'];
    				//console.log(filename);
    		    var FR = new FileReader();

    				var this_object = this;
    		    FR.addEventListener("load", function(e) {
			
    				var this_object2 = this_object;
    				window.API.postJson(
    		        	`/extensions/candlecam/api/save`,
    		        	{'action':'upload', 'filename':filename, 'filedata':e.target.result, 'parts_total':1, 'parts_current':1}

    			      ).then((body) => {
    			        this_object.show_list(body['data']);

    			      }).catch((e) => {
    					  document.getElementById('extension-candlecam-response-data').innerText = e.toString();
    			      });
			
    		    }); 

    		    FR.readAsDataURL( files[0] );
    	  	}
    	}



    	createDropzoneMethods() {
    	    let dropzone = document.getElementById("extension-candlecam-dropzone");
    			const pre = document.getElementById('extension-candlecam-response-data');

    			var this_object = this;
    	    dropzone.ondragover = function() {
    	        this.className = "extension-candlecam-dragover";
    	        return false;
    	    }

    	    dropzone.ondragleave = function() {
    	        this.className = "";
    	        return false;
    	    }

    	    dropzone.ondrop = function(e) {
    	        // Stop browser from simply opening that was just dropped
    	        e.preventDefault();  
    	        // Restore original dropzone appearance
    	        this.className = "";
    			var files = e.dataTransfer.files;
    			this_object.upload_files(files);
    	    }    
    	}
    

    	//
    	//  A helper method that generates nice lists of properties from a Gateway property dictionary
    	//
    	get_property_lists(properties, filter){
    		//console.log("checking properties on:");
    		//console.log(properties);
    		var property1_list = []; // list of user friendly titles
    		var property1_system_list = []; // list internal property id's
    		//var property2_list = [];
    		//var property2_system_list = [];
		
    		for (let prop in properties){
    			//console.log(properties[prop]);
    			var title = 'unknown';
    			if( properties[prop].hasOwnProperty('title') ){
    				title = properties[prop]['title'];
    			}
    			else if( properties[prop].hasOwnProperty('label') ){
    				title = properties[prop]['label'];
    			}
				
			
    			var system_title = properties[prop]['name']//properties[prop]['links'][0]['href'].substr(properties[prop]['links'][0]['href'].lastIndexOf('/') + 1);

    			// If a property is a number, add it to the list of possible source properties
    			if( filter == 'number' && (properties[prop]['type'] == 'integer' || properties[prop]['type'] == 'float' || properties[prop]['type'] == 'number')){
    				property1_list.push(title);
    				property1_system_list.push(system_title);
                }
                else if( filter == 'boolean' && (properties[prop]['type'] == 'boolean')){
    				property1_list.push(title);
    				property1_system_list.push(system_title);
                }
                else if( filter == 'actuator-boolean' && (properties[prop]['type'] == 'boolean')){
    				if ( 'readOnly' in properties[prop] ) { // If readOnly is set, it could still be set to 'false'.
    					if(properties[prop]['readOnly'] == false){
    						property1_list.push(title);
    						property1_system_list.push(system_title);
    					}
    				}
    				else{ // If readOnly is not set, we can asume the property is not readOnly.
        				property1_list.push(title);
        				property1_system_list.push(system_title);
    				}
                }
                else if( filter == 'null' && (properties[prop]['type'] == 'null')){
    				property1_list.push(title);
    				property1_system_list.push(system_title);
                }
                else if( filter == 'videoProperty' && (properties[prop]['@type'] == 'VideoProperty')){
    				property1_list.push(title);
    				property1_system_list.push(system_title);
                }
            
                /*
    				// If a property is not read-only, then it can be added to the list of 'target' properties that can be changed based on a 'source' property
    				if ( 'readOnly' in properties[prop] ) { // If readOnly is set, it could still be set to 'false'.
    					if(properties[prop]['readOnly'] == false){
    						property2_list.push(title);
    						property2_system_list.push(system_title);
    					}
    				}
    				else{ // If readOnly is not set, we can asume the property is not readOnly.
    					property2_list.push(title);
    					property2_system_list.push(system_title);
    				}
    			}
                */
    		}
		
    		// Sort lists alphabetically.
    		/*
    		property1_list.sort();
    		property1_system_list.sort();
    		property2_list.sort();
    		property2_system_list.sort();
    		*/
		
    		return { 'property1_list' : property1_list, 'property1_system_list' : property1_system_list }; //, 'property2_list' : property2_list,'property2_system_list' : property2_system_list };
    	}
    
    
    	// HELPER METHODS
	
    	hasClass(ele,cls) {
    		//console.log(ele);
    		//console.log(cls);
    	  	return !!ele.className.match(new RegExp('(\\s|^)'+cls+'(\\s|$)'));
    	}

    	addClass(ele,cls) {
    	  	if (!this.hasClass(ele,cls)) ele.className += " "+cls;
    	}

    	removeClass(ele,cls) {
    	  	if (this.hasClass(ele,cls)) {
    	    	var reg = new RegExp('(\\s|^)'+cls+'(\\s|$)');
    	    	ele.className=ele.className.replace(reg,' ');
    	  	}
    	}
    
    }

  new Candlecam();
	
})();
