import time
from math import cos, pi
import pyaudio, struct
import tkinter as Tk
import wave
from matplotlib import pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from multiprocessing.connection import Client, Listener


def fun_fast():
    global SPEED
    SPEED = 3


def fun_slow():
    global SPEED
    SPEED = 1


# plt.ion()           # Turn on interactive mode so plot gets updated

outputFile = 'output.wav'
wf = wave.open(outputFile, 'w')

Fs = 8000  # rate (samples/second)

wf.setnchannels(1)  # one channel (mono)
wf.setsampwidth(2)  # one byte per sample (8 bits per sample)
wf.setframerate(Fs)  # samples per second

# Define Tkinter root
root = Tk.Tk()

# Define Tk variables
threshold = Tk.DoubleVar()

# Initialize Tk variables
threshold.set(3000)

# Define widgets
S_threshold = Tk.Scale(root, label='Jump threshold', variable=threshold, from_=500, to=30000)
B_fast = Tk.Button(root, text='Fast', command=fun_fast)
B_slow = Tk.Button(root, text='Slow', command=fun_slow)

# Place widgets
S_threshold.pack(side=Tk.LEFT)
B_fast.pack(side=Tk.BOTTOM, fill=Tk.X)
B_slow.pack(side=Tk.BOTTOM, fill=Tk.X)

BLOCKLEN = 256
CONTINUE = True
SPEED = 1

# Create Pyaudio object
p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=Fs,
    input=True,
    output=True,
    frames_per_buffer=BLOCKLEN)
# specify low frames_per_buffer to reduce latency

# Initialize plot window:
fig = plt.figure(1)
canvas = FigureCanvasTkAgg(fig, master=root)  # A tk.DrawingArea.
canvas.get_tk_widget().pack(side=Tk.BOTTOM, fill=Tk.BOTH, expand=1)
plt.ylim(0, Fs * 40)

# Frequency axis (Hz)
plt.xlim(0, Fs * 0.5)  # set x-axis limits
plt.xlabel('Frequency (Hz)')
ff = Fs / BLOCKLEN * np.arange(0, BLOCKLEN)

line1, = plt.plot([], [], color='blue')  # Create empty line
line1.set_xdata(ff)  # x-data of plot (frequency)
line1.set_ydata(np.arange(0, BLOCKLEN))
plt.ion()

address = ('localhost', 6000)
conn = Client(address, authkey=b'secret password')
# listener = Listener(address, authkey=b'secret password')
print('* Start')
    # start = int(time.time())
pkg = {
    "threshold": threshold.get(),
    "speed": SPEED
}
while CONTINUE:
    # now = int(time.time())
    root.update()
    # if (now - start) % 1 == 0:
    #     print(now - start)
    pkg["threshold"] = threshold.get()
    pkg["speed"] = SPEED
    conn.send(pkg)
    # print(f"send threshold={threshold.get()}, speed = {SPEED}")

    # input_bytes = stream.read(BLOCKLEN)
    input_bytes = stream.read(BLOCKLEN, exception_on_overflow=False)
    input_tuple = struct.unpack('h' * BLOCKLEN, input_bytes)  # Convert
    X = np.fft.fft(input_tuple)
    line1.set_ydata(np.abs(X))
    wf.writeframes(input_bytes)


print('* Finished')

# plt.ioff()           # Turn off interactive mode
plt.close()
wf.close()

stream.stop_stream()
stream.close()
p.terminate()
