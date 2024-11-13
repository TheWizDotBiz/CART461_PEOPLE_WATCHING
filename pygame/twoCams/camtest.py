import cv2

cap = cv2.VideoCapture(0)  # Try with 1, 2, etc., if 0 doesn't work
if not cap.isOpened():
    print("Cannot open camera")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame")
        break

    cv2.imshow("Camera Test", frame)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
