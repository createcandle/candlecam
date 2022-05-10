import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

import time
import spidev


def set_leds_really(hex,brightness):
    try:
        hex = hex.lstrip('#')
        rgb = tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))

        r = rgb[0]
        g = rgb[1]
        b = rgb[2]
        
        #brightness = brightness / 100 # requires values between 0 and 1
        
        print('RGB =', str(rgb))
        print('Brightness =', str(brightness))
        
        
            
        # Open SPI
        spi = spidev.SpiDev()
        spi.open(0,1)
        spi.max_speed_hz = 8000000
        
        
        # Brightness
        if brightness > 100:
            brightness = 100
        brightness = int(brightness * 2.5)
        brightness_byte = (brightness & 0b00011111)
        print("brightness_byte: " + str(brightness_byte))
        
        # Create data for LEDs
        data = []
        
        for led_index in range(3):
            data.append( brightness_byte )
            data.append( b )
            data.append( g )
            data.append( r )
        
        print("data: " + str(data))
        
        # start
        spi.xfer2([0] * 4)
        
        # send data
        spi.xfer2(data)
        
        # end
        spi.xfer2([0xFF] * 4)
        
        
        # close SPI
        spi.close()
            
        
    except Exception as ex:
        print("could not set LED: " + str(ex))


def main():
    set_leds_really('#ff0000', 10)
    time.sleep(2)
    set_leds_really('#ffff00', 20)
    time.sleep(2)
    set_leds_really('#ffffff', 50)
    time.sleep(2)
    set_leds_really('#ff00ff', 60)
    time.sleep(2)
    set_leds_really('#00ffff', 100)
    time.sleep(2)
    set_leds_really('#ff0000', 10)
    
if __name__ == "__main__":
    main()
