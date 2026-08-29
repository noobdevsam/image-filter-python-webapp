import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI()

# Enable CORS for Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/filter")
async def process_filter(
        file: UploadFile = File(...),
        filter_type: str = Form(...),
        param: float = Form(1.0),
):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return Response(status_code=400, content="Invalid image file")

    # 1. Smoothing & Sharpening Filters
    if filter_type == "average":
        k_size = max(1, int(param)) | 1
        out = cv2.blur(img, (k_size, k_size))
    elif filter_type == "median":
        k_size = max(1, int(param)) | 1
        out = cv2.medianBlur(img, k_size)
    elif filter_type == "gaussian":
        k_size = max(1, int(param)) | 1
        out = cv2.GaussianBlur(img, (k_size, k_size), 0)
    elif filter_type == "sharpen":
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        out = cv2.filter2D(img, -1, kernel)

    # 2. Spatial Domain Filters
    elif filter_type == "laplacian":
        out = cv2.Laplacian(img, cv2.CV_8U, ksize=3)
    elif filter_type == "sobel":
        sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
        out = cv2.magnitude(sobelx, sobely)
        out = np.uint8(np.clip(out, 0, 255))

    # 3. Gray-Level Transformations
    elif filter_type == "invert":
        out = cv2.bitwise_not(img)
    elif filter_type == "brightness":
        out = cv2.convertScaleAbs(img, alpha=1.0, beta=param)
    elif filter_type == "contrast":
        out = cv2.convertScaleAbs(img, alpha=param, beta=0)

    # 4. Histogram Processing
    elif filter_type == "histogram":
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        out = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
    else:
        out = img

    _, encoded_img = cv2.imencode(".jpg", out)
    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")
