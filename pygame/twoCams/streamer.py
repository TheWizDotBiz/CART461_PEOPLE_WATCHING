import cv2
import socket
import pygame
import numpy as np
import pyaudio
import threading
import sys

# Initialize Pygame
pygame.init()
screen_width, screen_height = 640, 400  # Set Pygame window to 640x400

# Initialize PyAudio
p = pyaudio.PyAudio()

# Create one window for the video stream
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Video Stream")

# List available cameras
def list_cameras():
    available_cameras = []
    for i in range(5):  # Check up to 5 devices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
        cap.release()
    return available_cameras

# List available microphones
def list_microphones():
    available_microphones = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            available_microphones.append(i)
    return available_microphones

# Setup UDP communication for sending and receiving
def setup_udp_socket(port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(('0.0.0.0', port))
    return udp_socket

# Capture and send video
def capture_and_send_video(cap, udp_socket, target_ip, target_port):
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        # Resize the frame to 640x400 resolution
        frame_resized = cv2.resize(frame, (640, 400))  # Resize to 640x400

        # Convert frame to RGB for Pygame
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        frame_surface = pygame.surfarray.make_surface(frame_rgb)

        # Display the frame
        screen.blit(frame_surface, (0, 0))
        pygame.display.update()

        # Encode and send frame over UDP
        frame_data = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 50])[1].tobytes()  # Lower quality for smaller size
        udp_socket.sendto(frame_data, (target_ip, target_port))

        # Event handling to keep window responsive
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                cap.release()
                udp_socket.close()
                sys.exit()

        # Delay to manage frame rate
        pygame.time.delay(30)

# Receive and display video
def receive_video(udp_socket):
    while True:
        data, addr = udp_socket.recvfrom(65536)  # Adjust buffer size as needed
        # Decode the frame data
        nparr = np.frombuffer(data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is not None:
            # Convert frame to RGB for Pygame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_surface = pygame.surfarray.make_surface(frame_rgb)

            # Display the received frame
            screen.blit(frame_surface, (0, 0))
            pygame.display.update()

# Capture and send audio
def capture_and_send_audio(pyaudio_instance, udp_socket, target_ip, target_port, mic_index):
    audio_stream = pyaudio_instance.open(format=pyaudio.paInt16,
                                         channels=2,
                                         rate=44100,
                                         input=True,
                                         input_device_index=mic_index,
                                         frames_per_buffer=1024)
    while True:
        audio_data = audio_stream.read(1024)
        udp_socket.sendto(audio_data, (target_ip, target_port))

# Receive and play audio
def receive_audio(udp_socket):
    audio_stream = pyaudio.PyAudio().open(format=pyaudio.paInt16,
                                           channels=2,
                                           rate=44100,
                                           output=True,
                                           frames_per_buffer=1024)
    while True:
        data, addr = udp_socket.recvfrom(1024)  # Buffer size matches the audio capture size
        audio_stream.write(data)

# Switch to a different camera
def switch_camera(cap, camera_index):
    cap.release()
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Cannot open camera {camera_index}")
        return None
    return cap

# Switch to a different microphone
def switch_microphone(mic_index):
    return p.open(format=pyaudio.paInt16,
                 channels=2,
                 rate=44100,
                 input=True,
                 input_device_index=mic_index,
                 frames_per_buffer=1024)

def main(target_ip, target_port, local_port):
    # Initial camera and microphone setup
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        pygame.quit()
        sys.exit()

    # Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, screen_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, screen_height)

    # List available cameras and microphones
    cameras = list_cameras()
    print(f"Available cameras: {cameras}")
    microphones = list_microphones()
    print(f"Available microphones: {microphones}")
    
    mic_index = microphones[0]  # Default to the first microphone
    udp_socket = setup_udp_socket(local_port)

    # Start the UDP receiver threads for video and audio
    video_thread = threading.Thread(target=receive_video, args=(udp_socket,))
    video_thread.daemon = True
    video_thread.start()

    audio_thread = threading.Thread(target=receive_audio, args=(udp_socket,))
    audio_thread.daemon = True
    audio_thread.start()

    # Capture and send video and audio in the main thread
    capture_and_send_video(cap, udp_socket, target_ip, target_port)
    capture_and_send_audio(p, udp_socket, target_ip, target_port, mic_index)

    while True:
        # Check for console input to switch camera or microphone
        command = input("Enter command (switch camera [index] / switch mic [index]): ")
        if command.startswith("switch camera"):
            _, _, new_camera_index = command.split()
            new_camera_index = int(new_camera_index)
            if new_camera_index in cameras:
                cap = switch_camera(cap, new_camera_index)
            else:
                print("Invalid camera index")
        elif command.startswith("switch mic"):
            _, _, new_mic_index = command.split()
            new_mic_index = int(new_mic_index)
            if new_mic_index in microphones:
                mic_index = new_mic_index
                pyaudio_stream = switch_microphone(mic_index)
                print(f"Switched to microphone {new_mic_index}")
            else:
                print("Invalid microphone index")

if __name__ == "__main__":
    # Usage: python script.py <target_ip> <target_port> <local_port>
    if len(sys.argv) != 4:
        print("Usage: python script.py <target_ip> <target_port> <local_port>")
        sys.exit(1)

    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    local_port = int(sys.argv[3])

    main(target_ip, target_port, local_port)
