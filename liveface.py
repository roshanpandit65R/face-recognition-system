import cv2
import os
from datetime import datetime
import time

# Configuration
SAVE_FOLDER = "event_faces"
COOLDOWN = 2  # Seconds between captures (kam karo agar zyada log hain)
MIN_FACE_SIZE = (60, 60)  # Chhote faces bhi detect honge

os.makedirs(SAVE_FOLDER, exist_ok=True)

# Load face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Start camera with better resolution
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

face_count = 0
last_capture = {}
start_time = time.time()

print("=" * 50)
print("EVENT MODE - Multiple People Detection")
print("=" * 50)
print("Camera started! Press 'Q' to stop")
print()

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    current_time = time.time()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Detect multiple faces - optimized for crowds
    faces = face_cascade.detectMultiScale(
        gray, 
        scaleFactor=1.1,
        minNeighbors=4,  # Kam sensitivity for better detection in crowds
        minSize=MIN_FACE_SIZE
    )
    
    # Process each detected face
    for (x, y, w, h) in faces:
        # Position tracking
        pos_key = f"{x//80}_{y//80}"
        
        # Check if enough time passed since last capture at this position
        if pos_key not in last_capture or (current_time - last_capture[pos_key]) > COOLDOWN:
            
            # Extract face with padding
            padding = 15
            y1 = max(0, y - padding)
            y2 = min(frame.shape[0], y + h + padding)
            x1 = max(0, x - padding)
            x2 = min(frame.shape[1], x + w + padding)
            face_img = frame[y1:y2, x1:x2]
            
            # Save
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            filename = f"face_{face_count+1:05d}_{timestamp}.jpg"
            cv2.imwrite(os.path.join(SAVE_FOLDER, filename), face_img)
            
            face_count += 1
            last_capture[pos_key] = current_time
            
            print(f"✓ Face #{face_count:05d} saved - {len(faces)} people detected")
            
            # Green box for newly captured
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
        else:
            # Yellow box for already captured
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
    
    # Display info
    elapsed = int(current_time - start_time)
    
    # Background for stats
    cv2.rectangle(frame, (10, 10), (380, 110), (0, 0, 0), -1)
    
    cv2.putText(frame, f'Total Saved: {face_count}', (20, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f'Now Detecting: {len(faces)}', (20, 65), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    cv2.putText(frame, f'Time: {elapsed//60}m {elapsed%60}s', (20, 95), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    cv2.imshow('Event Face Capture - Press Q to Stop', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# Final stats
elapsed_total = int(time.time() - start_time)
print("\n" + "=" * 50)
print("EVENT SUMMARY")
print("=" * 50)
print(f"Total Faces Captured: {face_count}")
print(f"Total Time: {elapsed_total//60}m {elapsed_total%60}s")
if elapsed_total > 0:
    print(f"Average Rate: {face_count/(elapsed_total/60):.1f} faces/minute")
print(f"Saved in: {SAVE_FOLDER}/")
print("=" * 50)