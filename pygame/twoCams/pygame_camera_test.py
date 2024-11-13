import cv2
import pygame
import numpy as np

# Initialize Pygame
pygame.init()
screen_width, screen_height = 640, 480
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Pygame Camera Test")

# OpenCV Camera Initialization
cap = cv2.VideoCapture(0)  # Try changing the index if it doesn't work

if not cap.isOpened():
    print("Cannot open camera")
    pygame.quit()
    exit()

# Set Camera Resolution
cap.set(cv2.CAP_PROP_FRAME_WIDTH, screen_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, screen_height)

running = True
while running:
    # Pygame event handling to keep the window responsive
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Capture frame from OpenCV
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break

    # Convert the frame to Pygame-compatible format
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = np.rot90(frame)  # Rotate the frame if needed
    frame_surface = pygame.surfarray.make_surface(frame)

    # Display the frame in Pygame window
    screen.blit(pygame.transform.scale(frame_surface, (screen_width, screen_height)), (0, 0))
    pygame.display.update()

    # Add a small delay to prevent high CPU usage
    pygame.time.delay(10)

cap.release()
pygame.quit()
