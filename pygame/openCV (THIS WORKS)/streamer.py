import socket
import cv2
import pyaudio
import threading
import numpy as np
import sys

# Constants
BUFFER_SIZE = 65535
AUDIO_RATE = 44100
AUDIO_CHUNK = 1024
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHANNELS = 1

# Default device indices
video_capture_index = 0  # Default camera index
audio_input_index = 0    # Default microphone index

# Get target IP and ports from command-line arguments
if len(sys.argv) < 4:
    print("Usage: python script.py <target_ip> <video_port> <audio_port>")
    sys.exit(1)

TARGET_IP = sys.argv[1]
VIDEO_PORT = int(sys.argv[2])
AUDIO_PORT = int(sys.argv[3])

# Setup sockets
sock_video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_video.bind(("0.0.0.0", VIDEO_PORT))
sock_video.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
sock_video.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)

sock_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_audio.bind(("0.0.0.0", AUDIO_PORT))
sock_audio.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
sock_audio.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)

# Audio setup
audio = pyaudio.PyAudio()

# Function to list available video devices (cameras)
def list_video_devices():
    """Lists all available video capture devices (cameras)."""
    available_devices = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_devices.append(i)
            cap.release()
    return available_devices

# Function to list available audio devices (microphones)
def list_audio_devices():
    """Lists all available audio input devices (microphones)."""
    available_devices = []
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            available_devices.append(i)
    return available_devices

# Function to capture video and send it over UDP
def get_camera_stream():
    """Captures video from the selected camera and sends it over UDP."""
    global video_capture_index
    cap = cv2.VideoCapture(video_capture_index)
    
    # Set a lower capture resolution to reduce frame size
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            continue

        # Encode frame as JPEG with reduced quality
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)

        # Send only if the buffer size is within the limit
        if len(buffer) < BUFFER_SIZE:
            sock_video.sendto(buffer, (TARGET_IP, VIDEO_PORT))
        else:
            print("Warning: Frame size too large to send")

    cap.release()

# Function to receive video stream and display it
def receive_camera_stream():
    """Receives video stream and displays it using OpenCV."""
    while True:
        packet, _ = sock_video.recvfrom(BUFFER_SIZE)
        frame = cv2.imdecode(np.frombuffer(packet, dtype=np.uint8), cv2.IMREAD_COLOR)

        if frame is not None:
            # Rescale the received frame to 1024x600
            resized_frame = cv2.resize(frame, (1024, 600))
            cv2.imshow("Received Video", resized_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()

# Function to capture audio and send it over UDP
def get_audio_stream():
    """Captures audio from the selected microphone and sends it over UDP."""
    stream = audio.open(format=AUDIO_FORMAT,
                        channels=AUDIO_CHANNELS,
                        rate=AUDIO_RATE,
                        input=True,
                        frames_per_buffer=AUDIO_CHUNK,
                        input_device_index=audio_input_index)

    while True:
        data = stream.read(AUDIO_CHUNK, exception_on_overflow=False)
        sock_audio.sendto(data, (TARGET_IP, AUDIO_PORT))

# Function to receive audio stream and play it
def receive_audio_stream():
    """Receives audio stream and plays it using PyAudio."""
    stream = audio.open(format=AUDIO_FORMAT,
                        channels=AUDIO_CHANNELS,
                        rate=AUDIO_RATE,
                        output=True)

    while True:
        packet, _ = sock_audio.recvfrom(BUFFER_SIZE)
        stream.write(packet)

# Command to switch camera
def switch_camera():
    global video_capture_index
    print("Listing available video devices (cameras):")
    devices = list_video_devices()
    if devices:
        for i, device in enumerate(devices):
            print(f"{i}. Camera Index {device}")
        selected_index = int(input("Enter the index of the camera to switch to: "))
        if 0 <= selected_index < len(devices):
            video_capture_index = devices[selected_index]
            print(f"Switched to Camera Index {video_capture_index}")
        else:
            print("Invalid camera index.")
    else:
        print("No cameras detected.")

# Command to switch microphone
def switch_microphone():
    global audio_input_index
    print("Listing available audio devices (microphones):")
    devices = list_audio_devices()
    if devices:
        for i, device in enumerate(devices):
            print(f"{i}. Microphone Index {device}")
        selected_index = int(input("Enter the index of the microphone to switch to: "))
        if 0 <= selected_index < len(devices):
            audio_input_index = devices[selected_index]
            print(f"Switched to Microphone Index {audio_input_index}")
        else:
            print("Invalid microphone index.")
    else:
        print("No microphones detected.")

# Start video threads
video_send_thread = threading.Thread(target=get_camera_stream, daemon=True)
video_receive_thread = threading.Thread(target=receive_camera_stream, daemon=True)

# Start audio threads
audio_send_thread = threading.Thread(target=get_audio_stream, daemon=True)
audio_receive_thread = threading.Thread(target=receive_audio_stream, daemon=True)

# Start all threads
video_send_thread.start()
video_receive_thread.start()
audio_send_thread.start()
audio_receive_thread.start()

# Command loop
while True:
    print("\nCommands:")
    print("1: Switch Camera")
    print("2: Switch Microphone")
    print("3: Quit")
    
    command = input("Enter a command: ")
    
    if command == "1":
        switch_camera()
    elif command == "2":
        switch_microphone()
    elif command == "3":
        break
    else:
        print("Invalid command.")

# Wait for threads to finish
video_send_thread.join()
video_receive_thread.join()
audio_send_thread.join()
audio_receive_thread.join()

# Clean up resources
cv2.destroyAllWindows()
sock_video.close()
sock_audio.close()
audio.terminate()
