import io
import json
import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI(title="Image Processing Backend API")

# Setup CORS for Angular local server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Image-Meta"],
)


def process_opencv_filter(img: np.ndarray, filter_type: str, param: float) -> np.ndarray:
    """Core image processing router using OpenCV."""
    if filter_type == "average":
        k_size = max(1, int(param)) | 1
        return cv2.blur(img, (k_size, k_size))
    elif filter_type == "median":
        k_size = max(1, int(param)) | 1
        return cv2.medianBlur(img, k_size)
    elif filter_type == "gaussian":
        k_size = max(1, int(param)) | 1
        return cv2.GaussianBlur(img, (k_size, k_size), 0)
    elif filter_type == "sharpen":
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        return cv2.filter2D(img, -1, kernel)
    elif filter_type == "laplacian":
        lap = cv2.Laplacian(img, cv2.CV_64F, ksize=3)
        return cv2.convertScaleAbs(lap)
    elif filter_type == "sobel":
        sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
        out = cv2.magnitude(sobelx, sobely)
        return np.uint8(np.clip(out, 0, 255))
    elif filter_type == "invert":
        return cv2.bitwise_not(img)
    elif filter_type == "brightness":
        return cv2.convertScaleAbs(img, alpha=1.0, beta=param)
    elif filter_type == "contrast":
        return cv2.convertScaleAbs(img, alpha=param, beta=0)
    elif filter_type == "histogram":
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
    return img


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/filter")
async def process_filter_stream(
    file: UploadFile = File(...),
    filter_type: str = Form(...),
    param: float = Form(1.0),
):
    """Pure ephemeral in-memory processing. Directly returns the processed JPEG stream and metadata header."""
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid binary image format")

    out = process_opencv_filter(img, filter_type, param)

    success, encoded_img = cv2.imencode(".jpg", out)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode output image")

    # Extract metadata for dynamic stats display
    h, w, c = out.shape
    b_mean, g_mean, r_mean = cv2.mean(out)[:3]
    meta = {
        "dimensions": {"width": w, "height": h},
        "channels": c,
        "mean_intensity": {
            "red": round(float(r_mean), 2),
            "green": round(float(g_mean), 2),
            "blue": round(float(b_mean), 2),
        },
    }

    return Response(
        content=encoded_img.tobytes(),
        media_type="image/jpeg",
        headers={"X-Image-Meta": json.dumps(meta)},
    )

