from ultralytics import YOLO

# Load a model
model = YOLO("yolov8n.pt")  # pretrained YOLO26n model

# Run batched inference on a list of images
results = model('/Users/danielpelzel/Library/Mobile Documents/com~apple~CloudDocs/Ki Bild r/PHOTO-2026-06-08-19-22-16 5.jpg', classes = 0)  # return a list of Results objects

# Process results list
for result in results:
    boxes = result.boxes  # Boxes object for bounding box outputs
    masks = result.masks  # Masks object for segmentation masks outputs
    keypoints = result.keypoints  # Keypoints object for pose outputs
    probs = result.probs  # Probs object for classification outputs
    obb = result.obb  # Oriented boxes object for OBB outputs
    result.show()  # display to screen
    result.save(filename="result.jpg")  # save to disk

