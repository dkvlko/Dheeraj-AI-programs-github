import cv2
import os
import time

# Output directory
output_dir = "/mnt/ramdisk/videodump"
os.makedirs(output_dir, exist_ok=True)

# Camera index (0 = default/front camera in most laptops)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Cannot access camera")
    exit()

# Get camera properties
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = 20.0  # You can tweak this

recording = False
out = None

print("Press 'r' to start recording")
print("Press 's' to stop recording")
print("Press 'q' to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break

    # Show preview
    cv2.imshow("Camera", frame)

    # Write frame if recording
    if recording and out is not None:
        out.write(frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('r') and not recording:
        filename = os.path.join(
            output_dir,
            f"video_{time.strftime('%Y%m%d_%H%M%S')}.avi"
        )

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(filename, fourcc, fps, (frame_width, frame_height))

        recording = True
        print(f"Recording started: {filename}")

    elif key == ord('s') and recording:
        recording = False
        if out:
            out.release()
            out = None
        print("Recording stopped")

    elif key == ord('q'):
        print("Exiting...")
        break

# Cleanup
if recording and out:
    out.release()

cap.release()
cv2.destroyAllWindows()
