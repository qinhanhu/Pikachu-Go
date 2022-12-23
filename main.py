import random
from multiprocessing.connection import Listener, Client

import cocos
from cocos.menu import Menu, MenuItem
from cocos.sprite import Sprite
from cocos.director import director
from cocos.scene import Scene
from pyaudio import PyAudio, paInt16
from cocos.scenes import FadeTransition, SplitColsTransition
from cocos.text import Label
import os.path
import pyaudio
import struct
import wave
from matplotlib import pyplot
import math

PIKACHU_IMAGE_PATH = "pikachu.png"
BLOCK_IMAGE_PATH = "block.png"

class Pikachu(cocos.sprite.Sprite):
    def __init__(self, imagepath, **kwargs):
        super(Pikachu, self).__init__(imagepath)
        self.image_anchor = 0, 0
        # Reset
        self.reset(False)
        # Update
        self.schedule(self.update)

    def jump(self, h):
        if self.is_able_jump:
            self.y += 1
            self.speed -= max(min(h, 10), 7)
            self.is_able_jump = False

    def land(self, y):
        if self.y > y - 25:
            self.is_able_jump = True
            self.speed = 0
            self.y = y

    def update(self, dt):
        self.speed += 10 * dt
        self.y -= self.speed
        if self.y < -85:
            # End game, change Scene to MainMenu
            director.replace(SplitColsTransition(Scene(MainMenu())))

    def reset(self, flag=True):
        if flag: self.parent.reset()
        # Is able to jump or not
        self.is_able_jump = False
        # Speed
        self.speed = 0
        # Position
        self.position = 80, 280


class Block(cocos.sprite.Sprite):
    def __init__(self, imagepath, position, **kwargs):
        super(Block, self).__init__(imagepath)
        self.image_anchor = 0, 0
        x, y = position
        if x == 0:
            self.scale_x = 4.5
            self.scale_y = 1
        else:
            self.scale_x = 0.5 + random.random() * 1.5
            self.scale_y = min(max(y - 50 + random.random() * 100, 50), 300) / 100.0
            self.position = x + 50 + random.random() * 100, 0


class VCGame(cocos.layer.ColorLayer):

    def __init__(self):
        super(VCGame, self).__init__(255, 255, 255, 255)
        self.address = ('localhost', 6000)  # family is deduced to be 'AF_INET'
        self.listener = Listener(self.address, authkey=b'secret password')
        # self.conn = Client(self.address, authkey=b'secret password')
        print("------------start listening ---------- ")

        wavefile = 'game_start.wav'

        print("Play the wave file %s." % wavefile)

        # Open wave file (should be mono channel)
        wf = wave.open( wavefile, 'rb' )

        BLOCKSIZE = 4000      # length of block (samples)
        CHANNELS = wf.getnchannels()       	# Number of channels
        RATE = wf.getframerate()                # Sampling rate (frames/second)
        SIGNAL_LENGTH  = wf.getnframes()       	# Signal length
        WIDTH = wf.getsampwidth()       		# Number of bytes per sample

        f0 = 400    # Modulation frequency (Hz)
        # Initialize phase
        om = 2*math.pi*f0/RATE
        theta = 0

        NumBlocks = int( SIGNAL_LENGTH / BLOCKSIZE )

        # Open audio device:
        p1 = pyaudio.PyAudio()
        PA_FORMAT = p1.get_format_from_width(WIDTH)

        stream = p1.open(
            format    = PA_FORMAT,
            channels  = CHANNELS,
            rate      = RATE,
            input     = False,
            output    = True)

        output_block = BLOCKSIZE * [0]

        for i in range(0, NumBlocks):
            input_bytes = wf.readframes(BLOCKSIZE)                     # Read audio input stream
            input_tuple = struct.unpack('h' * BLOCKSIZE, input_bytes)  # Convert

            # Go through block
            for n in range(0, BLOCKSIZE):
                # No processing:
                # output_block[n] = input_tuple[n]  
                # OR
                # Amplitude modulation:
                theta = theta + om
                output_block[n] = int( input_tuple[n] * math.cos(theta) )

            # keep theta betwen -pi and pi
            while theta > math.pi:
                    theta = theta - 2*math.pi

            # Convert values to binary data
            output_bytes = struct.pack('h' * BLOCKSIZE, *output_block)

            # Write binary data to audio output stream
            stream.write(output_bytes)

        stream.stop_stream()
        stream.close()
        p1.terminate()
        
        self.conn = self.listener.accept()
        self.threshold = 3000
        self.speed = 1

        # frames_per_buffer
        self.num_samples = 1000
        # Voice bar
        self.vbar = Sprite(BLOCK_IMAGE_PATH)
        self.vbar.position = 20, 780
        self.vbar.scale_y = 0.1
        self.vbar.image_anchor = 0, 0
        self.add(self.vbar)
        
        self.pikachu = Pikachu(PIKACHU_IMAGE_PATH)
        self.add(self.pikachu)
        # Ground
        self.floor = cocos.cocosnode.CocosNode()
        self.add(self.floor)
        position = 0, 100
        for i in range(120):
            b = Block(BLOCK_IMAGE_PATH, position)
            self.floor.add(b)
            position = b.x + b.width, b.height
        # Audio input
        audio = PyAudio()
        self.stream = audio.open(format=paInt16,
                                 channels=1,
                                 rate=int(audio.get_device_info_by_index(0)['defaultSampleRate']),
                                 input=True,
                                 frames_per_buffer=self.num_samples)
        # Update
        self.schedule(self.update)

    def collide(self):
        diffx = self.pikachu.x - self.floor.x
        for b in self.floor.get_children():
            if (b.x <= diffx + self.pikachu.width * 0.8) and (diffx + self.pikachu.width * 0.2 <= b.x + b.width):
                if self.pikachu.y < b.height:
                    self.pikachu.land(b.height)
                    break

    def update(self, dt):
        # Get volumn
        audio_data = self.stream.read(self.num_samples, exception_on_overflow=False)
        k = max(struct.unpack('1000h', audio_data))
        self.vbar.scale_x = k / 10000.0
        pkg = self.conn.recv()
        self.threshold = pkg.get("threshold", self.threshold)
        self.speed = pkg.get("speed", self.speed)
        if k > 3000:
            self.floor.x -= min((k / 20.0), 150) * dt * self.speed
        # Jump
        if k > self.threshold:
            self.pikachu.jump((k - 8000) / 1000.0)
        # Collision detect
        self.collide()

    def reset(self):
        self.floor.x = 0


class MainMenu(Menu):
    def __init__(self):
        super(MainMenu, self).__init__("Audio Game")
        items = [MenuItem("Start", self.start), MenuItem("Exit", self.on_quit)]
        self.file_path = "output.wav"
        if os.path.exists(self.file_path):
            items.append(MenuItem("Last Run Record", self.play_wav))
        self.create_menu(items)
        self.playFlag = True

    # Start game
    def start(self):
        director.replace(SplitColsTransition(Scene(VCGame())))

    # Exit game
    def on_quit(self):
        director.window.close()


    # Watch Last Run Record
    def play_wav(self):

        # Open wave file
        wf = wave.open(self.file_path, 'rb')

        # Read wave file properties
        RATE = wf.getframerate()  # Frame rate (frames/second)
        WIDTH = wf.getsampwidth()  # Number of bytes per sample
        LEN = wf.getnframes()  # Signal length
        CHANNELS = wf.getnchannels()  # Number of channels

        BLOCKLEN = 512  # Blocksize

        # Set up plotting...

        pyplot.ion()  # Turn on interactive mode so plot gets updated

        fig = pyplot.figure(1)

        [g1] = pyplot.plot([], [])

        g1.set_xdata(range(BLOCKLEN))
        pyplot.ylim(-32000, 32000)
        pyplot.xlim(0, BLOCKLEN)

        # Open the audio output stream
        p = pyaudio.PyAudio()

        PA_FORMAT = p.get_format_from_width(WIDTH)
        stream = p.open(
            format=PA_FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=False,
            output=True,
            frames_per_buffer=512)  # low latency so that plot and output audio are synchronized

        # Get block of samples from wave file
        input_bytes = wf.readframes(BLOCKLEN)

        def on_close(event):
            self.playFlag = False

        while self.playFlag and len(input_bytes) >= BLOCKLEN * WIDTH:
            # Convert binary data to number sequence (tuple)
            signal_block = struct.unpack('h' * BLOCKLEN, input_bytes)

            g1.set_ydata(signal_block)
            pyplot.pause(0.0001)

            # Write binary data to audio output stream
            stream.write(input_bytes, BLOCKLEN)

            # Get block of samples from wave file
            input_bytes = wf.readframes(BLOCKLEN)
            fig.canvas.mpl_connect('close_event', on_close)

        self.playFlag = True
        stream.stop_stream()
        stream.close()

        wf.close()

        pyplot.ioff()  # Turn off interactive mode
        pyplot.show()  # Keep plot showing at end of program
        pyplot.close()
        p.terminate()

'''run'''
if __name__ == '__main__':
    director.init(width=1500, height=800, caption="Pikachu Go Go Go", resizable=True)
    director.run(Scene(MainMenu()))
