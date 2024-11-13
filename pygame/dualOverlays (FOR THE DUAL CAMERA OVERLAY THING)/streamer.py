import socket
import cv2
import pyaudio
import threading
import numpy as np
import sys
import pickle

# Constants
BUFFER_SIZE = 65535
AUDIO_RATE = 44100
AUDIO_CHUNK = 1024
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHANNELS = 1

# Default device indices
video_capture_index_front = 0
video_capture_index_back = 1
audio_input_index = 0

# Global variables for spacebar toggle
spacebar_status = False
remote_spacebar_status = False

# Get target IP and ports from command-line arguments
if len(sys.argv) < 4:
    print("Usage: python script.py <target_ip> <video_port> <audio_port>")
    sys.exit(1)

TARGET_IP = sys.argv[1]
VIDEO_PORT = int(sys.argv[2])
AUDIO_PORT = int(sys.argv[3])
STATUS_PORT = VIDEO_PORT + 1  # Additional port for sending status updates

# Setup sockets
sock_video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_video.bind(("0.0.0.0", VIDEO_PORT))

sock_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_audio.bind(("0.0.0.0", AUDIO_PORT))

sock_status = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_status.bind(("0.0.0.0", STATUS_PORT))

# Audio setup
audio = pyaudio.PyAudio()

def list_video_devices():
    available_devices = []
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_devices.append(i)
            cap.release()
    return available_devices

def get_camera_stream(front_camera=True):
    cap = cv2.VideoCapture(video_capture_index_front if front_camera else video_capture_index_back)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    return cap

# Capture video and send it over UDP
def send_camera_stream():
    cap_front = get_camera_stream(True)
    cap_back = get_camera_stream(False)

    while True:
        # Select camera based on spacebar status
        cap = cap_front if spacebar_status else cap_back
        ret, frame = cap.read()
        if not ret:
            continue

        # Encode frame as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)

        if len(buffer) < BUFFER_SIZE:
            sock_video.sendto(buffer, (TARGET_IP, VIDEO_PORT))

# Receive video stream, render overlay if needed
def receive_camera_stream():
    cap_front = get_camera_stream(True)
    while True:
        packet, _ = sock_video.recvfrom(BUFFER_SIZE)
        frame_other = cv2.imdecode(np.frombuffer(packet, dtype=np.uint8), cv2.IMREAD_COLOR)

        if frame_other is None:
            continue

        # Capture current device's front camera if in overlay mode
        ret, frame_self = cap_front.read()
        if ret:
            # Rescale both frames to the same size
            frame_other = cv2.resize(frame_other, (640, 360))
            frame_self = cv2.resize(frame_self, (640, 360))

            # Check spacebar statuses to decide on rendering mode
            if spacebar_status and remote_spacebar_status:
                # Overlay other device's back camera over own front camera feed
                overlay = cv2.addWeighted(frame_self, 0.7, frame_other, 0.3, 0)
                cv2.imshow("Overlay Mode", overlay)
            else:
                cv2.imshow("Normal Mode", frame_other)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

# Capture audio and send it over UDP
def get_audio_stream():
    stream = audio.open(format=AUDIO_FORMAT,
                        channels=AUDIO_CHANNELS,
                        rate=AUDIO_RATE,
                        input=True,
                        frames_per_buffer=AUDIO_CHUNK,
                        input_device_index=audio_input_index)

    while True:
        data = stream.read(AUDIO_CHUNK, exception_on_overflow=False)
        sock_audio.sendto(data, (TARGET_IP, AUDIO_PORT))

# Receive audio stream and play it
def receive_audio_stream():
    stream = audio.open(format=AUDIO_FORMAT,
                        channels=AUDIO_CHANNELS,
                        rate=AUDIO_RATE,
                        output=True)

    while True:
        packet, _ = sock_audio.recvfrom(BUFFER_SIZE)
        stream.write(packet)

# Toggle spacebar status
def toggle_spacebar_status():
    global spacebar_status
    spacebar_status = not spacebar_status
    print(f"Spacebar status set to: {spacebar_status}")

# Send the spacebar status over UDP
def send_status():
    while True:
        status_data = pickle.dumps(spacebar_status)
        sock_status.sendto(status_data, (TARGET_IP, STATUS_PORT))

# Receive the other device's spacebar status
def receive_status():
    global remote_spacebar_status
    while True:
        packet, _ = sock_status.recvfrom(1024)
        remote_spacebar_status = pickle.loads(packet)

# Start threads for video, audio, and status
video_send_thread = threading.Thread(target=send_camera_stream, daemon=True)
video_receive_thread = threading.Thread(target=receive_camera_stream, daemon=True)
audio_send_thread = threading.Thread(target=get_audio_stream, daemon=True)
audio_receive_thread = threading.Thread(target=receive_audio_stream, daemon=True)
status_send_thread = threading.Thread(target=send_status, daemon=True)
status_receive_thread = threading.Thread(target=receive_status, daemon=True)

# Start threads
video_send_thread.start()
video_receive_thread.start()
audio_send_thread.start()
audio_receive_thread.start()
status_send_thread.start()
status_receive_thread.start()

# Monitor for spacebar presses
print("Press 'Space' to toggle overlay mode, 'q' to quit")
while True:
    key = cv2.waitKey(1)
    if key == ord(' '):
        toggle_spacebar_status()
    elif key == ord('q'):
        break

# Cleanup
cv2.destroyAllWindows()
sock_video.close()
sock_audio.close()
sock_status.close()
audio.terminate()
