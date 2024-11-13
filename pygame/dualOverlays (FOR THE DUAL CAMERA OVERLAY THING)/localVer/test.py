import cv2

def overlay_with_transparency(frame1, frame2, alpha=0.5):
    """
    Overlay frame2 on top of frame1 with a given transparency.
    alpha: transparency level for frame2 (0 = fully transparent, 1 = fully opaque)
    """
    return cv2.addWeighted(frame1, 1 - alpha, frame2, alpha, 0)

def main():
    # Attempt to open two camera feeds (camera 0 and camera 1)
    cap1 = cv2.VideoCapture(0)
    cap2 = cv2.VideoCapture(1)

    if not cap1.isOpened():
        print("Error: Unable to access camera 0.")
        return
    if not cap2.isOpened():
        print("Error: Unable to access camera 1.")
        return

    print("Both cameras accessed successfully.")

    while True:
        # Read frames from both cameras
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if not ret1:
            print("Error: Unable to read from camera 0.")
            break
        if not ret2:
            print("Error: Unable to read from camera 1.")
            break

        print("Frames captured successfully.")

        # Resize frames to the same size if necessary
        height, width = frame1.shape[:2]
        frame2 = cv2.resize(frame2, (width, height))

        # Overlay the second frame on top of the first with transparency
        blended_frame = overlay_with_transparency(frame1, frame2, alpha=0.5)

        # Display the blended frame
        cv2.imshow("Overlayed Camera Feeds", blended_frame)

        # Exit if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Exiting...")
            break

    # Release resources and close windows
    cap1.release()
    cap2.release()
    cv2.destroyAllWindows()
    print("Cameras released and windows closed.")

if __name__ == "__main__":
    main()
