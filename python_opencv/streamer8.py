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
video_capture_indices = []  
audio_input_index = 0    
current_camera_index = 0  

# Overlay status for both devices
overlay_status = False  # Local overlay status
remote_overlay_status = False  # Remote device's overlay status

# Get target IP and ports from command-line arguments
if len(sys.argv) < 4:
    print("Usage: python script.py <target_ip> <video_port> <audio_port>")
    sys.exit(1)

TARGET_IP = sys.argv[1]
VIDEO_PORT_FRONT = int(sys.argv[2])  # Front camera port
VIDEO_PORT_BACK = int(sys.argv[3])   # Back camera port
AUDIO_PORT = 10003  # Port for audio stream
STATUS_PORT = 9999   # Port for exchanging overlay status

# Setup sockets
sock_video_front = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_video_front.bind(("0.0.0.0", VIDEO_PORT_FRONT))

sock_video_back = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_video_back.bind(("0.0.0.0", VIDEO_PORT_BACK))

sock_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_audio.bind(("0.0.0.0", AUDIO_PORT))
sock_audio.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
sock_audio.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)

sock_status = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_status.bind(("0.0.0.0", STATUS_PORT))

#float array sending setup
FLOAT_ARRAY_PORT = 10004  # Port for sending/receiving float arrays
sock_float_array = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_float_array.bind(("0.0.0.0", FLOAT_ARRAY_PORT))

# Audio setup
audio = pyaudio.PyAudio()

# Function to initialize all cameras
def initialize_cameras():
    global video_capture_indices
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            video_capture_indices.append(cap)

# Function to capture and send front camera stream
def get_front_camera_stream():
    global video_capture_indices, current_camera_index, overlay_status, remote_overlay_status
    while True:
        # Only capture and send front camera stream if both toggle variables are False
        if not (overlay_status and remote_overlay_status):
            cap = video_capture_indices[current_camera_index]
            ret, frame = cap.read()
            if not ret:
                continue

            # Resize the frame to a smaller resolution (e.g., 320x180)
            frame_resized = cv2.resize(frame, (320, 180))

            # Increase JPEG compression by reducing the quality to 30
            _, buffer = cv2.imencode('.jpg', frame_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 30])

            if len(buffer) < BUFFER_SIZE:
                sock_video_front.sendto(buffer, (TARGET_IP, VIDEO_PORT_FRONT))

# Function to capture and send back camera stream
def get_back_camera_stream():
    global video_capture_indices, current_camera_index, overlay_status, remote_overlay_status
    while True:
        # Only capture and send back camera stream if both toggle variables are True
        if overlay_status and remote_overlay_status:
            cap = video_capture_indices[(current_camera_index + 1) % len(video_capture_indices)]  # Back camera
            ret, frame = cap.read()
            if not ret:
                continue

            # Resize the frame to a smaller resolution (e.g., 320x180)
            frame_resized = cv2.resize(frame, (320, 180))

            # Increase JPEG compression by reducing the quality to 30
            _, buffer = cv2.imencode('.jpg', frame_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 30])

            if len(buffer) < BUFFER_SIZE:
                sock_video_back.sendto(buffer, (TARGET_IP, VIDEO_PORT_BACK))

# Function to receive and display the camera streams
def receive_camera_stream():
    global overlay_status, remote_overlay_status
    while True:
        # Receive data from both front and back camera streams (using different ports)
        
        # Receiving front camera stream
        if overlay_status and remote_overlay_status:
            front_camera = video_capture_indices[(current_camera_index) % len(video_capture_indices)]
            ret_front, frame_front = front_camera.read()
            if frame_front is None:
                continue
        else:
            packet_front, _ = sock_video_front.recvfrom(BUFFER_SIZE)
            frame_front = cv2.imdecode(np.frombuffer(packet_front, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        # Receiving back camera stream (only if both overlay_status and remote_overlay_status are True)
        if overlay_status and remote_overlay_status:
            packet_back, _ = sock_video_back.recvfrom(BUFFER_SIZE)
            frame_back = cv2.imdecode(np.frombuffer(packet_back, dtype=np.uint8), cv2.IMREAD_COLOR)
        else:
            frame_back = None  # No back camera stream when overlay is disabled

        # Ensure valid frames
        if frame_front is None:
            continue

        # Resize frames (to match the reduced resolution for both front and back)
        resized_front = cv2.resize(frame_front, (320, 180))

        # If back camera stream is available (both toggles true), apply overlay
        if frame_back is not None:
            resized_back = cv2.resize(frame_back, (320, 180))
            overlay = cv2.addWeighted(resized_front, 0.7, resized_back, 0.3, 0)
            
            # Rescale the overlay to 1024x600 before displaying it
            overlay_rescaled = cv2.resize(overlay, (1024, 600))
            cv2.imshow("Camera Stream", overlay_rescaled)
        else:
            # Rescale the front camera stream to 1024x600
            resized_front_rescaled = cv2.resize(resized_front, (1024, 600))
            cv2.imshow("Camera Stream", resized_front_rescaled)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

# Function to capture audio and send it over UDP
def get_audio_stream():
    """Captures audio from the selected microphone and sends it over UDP."""
    audioIndex = 0
    if overlay_status and remote_overlay_status:
        audioIndex = 1
    stream = audio.open(format=AUDIO_FORMAT,
                        channels=AUDIO_CHANNELS,
                        rate=AUDIO_RATE,
                        input=True,
                        frames_per_buffer=AUDIO_CHUNK,
                        input_device_index=audioIndex)

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

# Function to list available audio devices (microphones)
def list_audio_devices():
    """Lists all available audio input devices (microphones)."""
    available_devices = []
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            available_devices.append(i)
    return available_devices

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

# Function to send the current overlay status to the other device
def send_overlay_status():
    global overlay_status
    status_message = str(int(overlay_status)).encode()
    sock_status.sendto(status_message, (TARGET_IP, STATUS_PORT))

# Function to receive the overlay status from the other device
def receive_overlay_status():
    global remote_overlay_status
    while True:
        packet, _ = sock_status.recvfrom(1024)
        remote_overlay_status = bool(int(packet.decode()))

# Function to toggle overlay status
def toggle_overlay():
    global overlay_status
    overlay_status = not overlay_status
    print(f"Overlay status: {overlay_status}")
    send_overlay_status()

def send_float_array(float_array): #USE THIS TO SEND GYRO DATA AS A FLOAT ARRAY
    """Sends an array of floats to the remote device."""
    # Convert the list of floats to a numpy array
    array_np = np.array(float_array, dtype=np.float32)
    
    # Convert the numpy array to bytes
    byte_data = array_np.tobytes()
    
    # Send the byte data via UDP
    sock_float_array.sendto(byte_data, (TARGET_IP, FLOAT_ARRAY_PORT))
    print(f"Sent float array: {float_array}")

def receive_float_array():
    """Receives an array of floats from the remote device."""
    while True:
        try:
            byte_data, _ = sock_float_array.recvfrom(1024)  # Adjust buffer size as needed
            # Convert bytes back to a numpy array
            float_array = np.frombuffer(byte_data, dtype=np.float32)
            print(f"Received float array: {float_array}")
        except Exception as e:
            print(f"Error receiving float array: {e}")


# Initialize cameras and start threads
initialize_cameras()
video_send_thread_front = threading.Thread(target=get_front_camera_stream, daemon=True)
video_send_thread_back = threading.Thread(target=get_back_camera_stream, daemon=True)
video_receive_thread = threading.Thread(target=receive_camera_stream, daemon=True)
status_receive_thread = threading.Thread(target=receive_overlay_status, daemon=True)

video_send_thread_front.start()
video_send_thread_back.start()
video_receive_thread.start()
status_receive_thread.start()

# Start audio threads
audio_send_thread = threading.Thread(target=get_audio_stream, daemon=True)
audio_receive_thread = threading.Thread(target=receive_audio_stream, daemon=True)
audio_send_thread.start()
audio_receive_thread.start()

#float threads
float_array_receive_thread = threading.Thread(target=receive_float_array, daemon=True)
float_array_receive_thread.start()



# Command loop
while True:
    print("\nCommands:")
    print("1: Toggle Overlay")
    print("2: Quit")
    print("3: list default microphone (switching mics should not do anything)")
    print("4: send float array")
    command = input("Enter a command: ")
    
    match command:
        case "1":
            toggle_overlay()
        case "2":
            break
        case "3":
            switch_microphone()
        case "4":
             # Prompt user to enter a list of floats
            float_array_input = input("Enter comma-separated float values (e.g., 1.0, 2.5, 3.75): ")
            float_array = [float(val) for val in float_array_input.split(",")]
            send_float_array(float_array)
        case _:
            print("Invalid command")

# Clean up resources
sock_video_front.close()
sock_video_back.close()
sock_audio.close()
sock_status.close()
audio.terminate()
cv2.destroyAllWindows()
