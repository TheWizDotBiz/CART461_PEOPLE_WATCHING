import socket
import cv2
import pygame
import pyaudio
import numpy as np
import struct
import sys
import threading

# Set up Pygame window with updated resolution
pygame.init()
window_size = (1024, 600)  # Set to 1024x600
screen = pygame.display.set_mode(window_size)
pygame.display.set_caption('Audio and Video Streaming')

# UDP setup
TARGET_IP = sys.argv[1]  # The IP address of the target device
VIDEO_PORT = 12345
AUDIO_PORT = 12346
BUFFER_SIZE = 65507  # Maximum UDP packet size (65507 bytes)
MAX_FRAME_SIZE = 1024 * 600 * 3  # 1024x600 resolution, 3 bytes per pixel (RGB)

# Global variables for camera and microphone
cap = None
p = None
stream = None

# Set up camera function
def open_camera(camera_index=0):
    global cap
    cap = cv2.VideoCapture(camera_index)  # Open camera by index
    cap.set(3, 1024)  # Set width to 1024
    cap.set(4, 600)   # Set height to 600

# Set up microphone function
def open_microphone(device_index=0):
    global p, stream
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    input=True,
                    frames_per_buffer=1024,
                    input_device_index=device_index)

# Start with the default front camera and microphone
open_camera(0)  # Front camera
open_microphone(0)  # Default microphone

# Create UDP sockets for video and audio
video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Set the socket buffer size to the maximum allowed (send buffer)
video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)  # Increase send buffer size
audio_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)  # Increase send buffer size

# Bind the sockets to receive data
video_socket.bind(('', VIDEO_PORT))  # Video socket binds to the video port
audio_socket.bind(('', AUDIO_PORT))  # Audio socket binds to the audio port

# Function to chunk data
def chunk_data(data, chunk_size=1400):  # Reduced chunk size to avoid exceeding packet limits
    chunks = []
    total_chunks = (len(data) // chunk_size) + (1 if len(data) % chunk_size != 0 else 0)
    for i in range(total_chunks):
        chunk = data[i * chunk_size: (i + 1) * chunk_size]
        chunks.append((i, total_chunks, chunk))
    return chunks

# Function to stream video
def stream_video():
    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Scale down the frame
        frame_resized = cv2.resize(frame, (1024, 600))  # Resize to 1024x600

        # Rotate the frame 90 degrees if it appears rotated
        frame_resized = cv2.rotate(frame_resized, cv2.ROTATE_90_CLOCKWISE)

        # Encode the frame to JPEG to reduce size
        _, frame_encoded = cv2.imencode('.jpg', frame_resized)
        frame_data = frame_encoded.tobytes()

        # Log the size of the frame data
        print(f"Sending frame size: {len(frame_data)} bytes")

        # Chunk the data (use a smaller chunk size)
        chunks = chunk_data(frame_data, chunk_size=1400)  # Limit chunk size to 1400 bytes

        # Send each chunk via UDP
        for chunk_idx, total_chunks, chunk in chunks:
            header = struct.pack('!HH', chunk_idx, total_chunks)  # 2 bytes for chunk index, 2 bytes for total chunks
            video_socket.sendto(header + chunk, (TARGET_IP, VIDEO_PORT))

# Function to stream audio
def stream_audio():
    while True:
        audio_data = stream.read(1024)
        # Chunk the audio data (use a smaller chunk size)
        chunks = chunk_data(audio_data, chunk_size=1400)  # Limit chunk size to 1400 bytes

        # Send each chunk via UDP
        for chunk_idx, total_chunks, chunk in chunks:
            header = struct.pack('!HH', chunk_idx, total_chunks)  # 2 bytes for chunk index, 2 bytes for total chunks
            audio_socket.sendto(header + chunk, (TARGET_IP, AUDIO_PORT))

# Function to receive video
def receive_video():
    received_chunks = {}
    while True:
        data, addr = video_socket.recvfrom(BUFFER_SIZE)
        if data:
            # Extract header and chunk
            chunk_idx, total_chunks = struct.unpack('!HH', data[:4])
            chunk = data[4:]

            if chunk_idx not in received_chunks:
                received_chunks[chunk_idx] = chunk
            else:
                received_chunks[chunk_idx] += chunk

            # If all chunks are received, reassemble the full frame
            if len(received_chunks) == total_chunks:
                # Reassemble the frame
                frame_data = b''.join(received_chunks[i] for i in range(total_chunks))
                received_chunks.clear()

                try:
                    # Decode the image data
                    frame = np.frombuffer(frame_data, dtype=np.uint8)
                    frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)

                    # Check if the frame is valid
                    if frame is not None:
                        # Resize and display the frame
                        frame_resized = cv2.resize(frame, (1024, 600))  # Resize to 1024x600
                        frame_resized = cv2.rotate(frame_resized, cv2.ROTATE_90_CLOCKWISE)  # Rotate 90 degrees if needed
                        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                        frame_surface = pygame.surfarray.make_surface(frame_rgb)

                        # Display the received frame in Pygame window
                        screen.blit(frame_surface, (0, 0))
                        pygame.display.flip()
                    else:
                        print("Error: Received an empty frame.")
                except Exception as e:
                    print(f"Error during frame processing: {e}")

# Function to receive audio
def receive_audio():
    received_chunks = {}
    while True:
        data, addr = audio_socket.recvfrom(BUFFER_SIZE)
        if data:
            # Extract header and chunk
            chunk_idx, total_chunks = struct.unpack('!HH', data[:4])
            chunk = data[4:]

            if chunk_idx not in received_chunks:
                received_chunks[chunk_idx] = chunk
            else:
                received_chunks[chunk_idx] += chunk

            # If all chunks are received, reassemble the full audio data
            if len(received_chunks) == total_chunks:
                audio_data = b''.join(received_chunks[i] for i in range(total_chunks))
                # Play or process audio data (you can implement audio playback here)

                # Clear received chunks
                received_chunks.clear()

# Function to handle runtime commands (switching between front and back camera/microphone)
def handle_console_commands():
    while True:
        command = input("Enter command (front/back camera, switch mic, list mics): ").lower()
        if command == "front":
            open_camera(0)  # Switch to front camera
            print("Switched to front camera")
        elif command == "back":
            open_camera(1)  # Switch to back camera
            print("Switched to back camera")
        elif command == "switch mic":
            # You can list available microphones here and switch between them
            available_mics = [p.get_device_info_by_index(i) for i in range(p.get_device_count()) if p.get_device_info_by_index(i)['maxInputChannels'] > 0]
            print("Available microphones:")
            for idx, mic in enumerate(available_mics):
                print(f"{idx}: {mic['name']}")
            mic_choice = int(input("Select microphone: "))
            open_microphone(available_mics[mic_choice]['index'])
            print(f"Switched to microphone: {available_mics[mic_choice]['name']}")
        elif command == "exit":
            break

# Create and start threads for video and audio streaming
video_thread = threading.Thread(target=stream_video)
audio_thread = threading.Thread(target=stream_audio)
recv_video_thread = threading.Thread(target=receive_video)
recv_audio_thread = threading.Thread(target=receive_audio)
command_thread = threading.Thread(target=handle_console_commands)

video_thread.start()
audio_thread.start()
recv_video_thread.start()
recv_audio_thread.start()
command_thread.start()

# Handle Pygame events
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
