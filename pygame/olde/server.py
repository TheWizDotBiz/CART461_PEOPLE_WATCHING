import socket
import pygame
import cv2
import numpy as np
import pyaudio

# Initialize Pygame
pygame.init()

# Set up the display
screen_width, screen_height = 640, 480
screen = pygame.display.set_mode((screen_width, screen_height))

# Audio setup
p = pyaudio.PyAudio()
audio_streams = []

# Open audio streams for two microphones
for i in range(2):
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    output=True)
    audio_streams.append(stream)

# UDP setup
UDP_IP = "localhost"
VIDEO_PORT = 5005
AUDIO_PORTS = [5006, 5007]

# Create UDP socket
sock_video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_video.bind((UDP_IP, VIDEO_PORT))
sock_video.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)  # Increase send buffer size

sock_audio = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM).bind((UDP_IP, port)) for port in AUDIO_PORTS]

def receive_video():
    while True:
        data, _ = sock_video.recvfrom(65536)
        frame = np.frombuffer(data, np.uint8).reshape((480, 640, 3))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_surface = pygame.surfarray.make_surface(frame)
        screen.blit(frame_surface, (0, 0))
        pygame.display.flip()

def receive_audio():
    while True:
        for i, sock in enumerate(sock_audio):
            data, _ = sock.recvfrom(1024)
            audio_streams[i].write(data)

# Main loop
import threading
video_thread = threading.Thread(target=receive_video)
audio_thread = threading.Thread(target=receive_audio)

video_thread.start()
audio_thread.start()

# Keep the server running
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            break
