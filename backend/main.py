import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_kernel_size(param: float, minimum: int = 1) -> int:
    size = max(minimum, int(round(param)))
    if size % 2 == 0:
        size += 1
    return size


@app.get("/api/health")
async def health():
    return {"status": "ok"}


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
        raise HTTPException(status_code=400, detail="Invalid image file")

    if filter_type == "average":
        k_size = normalize_kernel_size(param, minimum=1)
        out = cv2.blur(img, (k_size, k_size))

    elif filter_type == "median":
        k_size = normalize_kernel_size(param, minimum=3)
        out = cv2.medianBlur(img, k_size)

    elif filter_type == "gaussian":
        k_size = normalize_kernel_size(param, minimum=1)
        out = cv2.GaussianBlur(img, (k_size, k_size), 0)

    elif filter_type == "sharpen":
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        out = cv2.filter2D(img, -1, kernel)

    elif filter_type == "laplacian":
        lap = cv2.Laplacian(img, cv2.CV_64F, ksize=3)
        out = cv2.convertScaleAbs(lap)

    elif filter_type == "sobel":
        sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
        out = cv2.convertScaleAbs(cv2.magnitude(sobelx, sobely))

    elif filter_type == "invert":
        out = cv2.bitwise_not(img)

    elif filter_type == "brightness":
        out = cv2.convertScaleAbs(img, alpha=1.0, beta=param)

    elif filter_type == "contrast":
        out = cv2.convertScaleAbs(img, alpha=param, beta=0)

    elif filter_type == "histogram":
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        out = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

    else:
        out = img

    success, encoded_img = cv2.imencode(".jpg", out)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode output image")

    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")
