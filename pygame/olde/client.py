import socket
import pygame
import cv2
import numpy as np
import pyaudio

# UDP setup
UDP_IP = "localhost"  # Server IP
VIDEO_PORT = 5005
AUDIO_PORTS = [5006, 5007]

# Create UDP socket
sock_video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_video.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)  # Increase send buffer size
sock_audio = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in AUDIO_PORTS]

# Audio setup
p = pyaudio.PyAudio()
audio_streams = []

# Open audio streams for two microphones
for i in range(2):
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    input=True,
                    frames_per_buffer=1024)
    audio_streams.append(stream)

# Video setup
cap = cv2.VideoCapture(0)

def send_video():
    while True:
        ret, frame = cap.read()
        if ret:
            frame = cv2.resize(frame, (640, 480))
            frame_data = frame.tobytes()
            sock_video.sendto(frame_data, (UDP_IP, VIDEO_PORT))

def send_audio():
    while True:
        for i, stream in enumerate(audio_streams):
            data = stream.read(1024)
            sock_audio[i].sendto(data, (UDP_IP, AUDIO_PORTS[i]))

# Start threads for video and audio sending
import threading
video_thread = threading.Thread(target=send_video)
audio_thread = threading.Thread(target=send_audio)

video_thread.start()
audio_thread.start()

# Keep the client running
try:
    while True:
        pass
except KeyboardInterrupt:
    cap.release()
    for stream in audio_streams:
        stream.stop_stream()
        stream.close()
    p.terminate()
