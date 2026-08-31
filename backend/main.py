# import cv2
# import numpy as np
# from fastapi import FastAPI, File, Form, HTTPException, UploadFile
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import Response
#
# app = FastAPI()
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
#
# def normalize_kernel_size(param: float, minimum: int = 1) -> int:
#     size = max(minimum, int(round(param)))
#     if size % 2 == 0:
#         size += 1
#     return size
#
#
# @app.get("/api/health")
# async def health():
#     return {"status": "ok"}
#
#
# @app.post("/api/filter")
# async def process_filter(
#         file: UploadFile = File(...),
#         filter_type: str = Form(...),
#         param: float = Form(1.0),
# ):
#     contents = await file.read()
#     nparr = np.frombuffer(contents, np.uint8)
#     img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#
#     if img is None:
#         raise HTTPException(status_code=400, detail="Invalid image file")
#
#     if filter_type == "average":
#         k_size = normalize_kernel_size(param, minimum=1)
#         out = cv2.blur(img, (k_size, k_size))
#
#     elif filter_type == "median":
#         k_size = normalize_kernel_size(param, minimum=3)
#         out = cv2.medianBlur(img, k_size)
#
#     elif filter_type == "gaussian":
#         k_size = normalize_kernel_size(param, minimum=1)
#         out = cv2.GaussianBlur(img, (k_size, k_size), 0)
#
#     elif filter_type == "sharpen":
#         kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
#         out = cv2.filter2D(img, -1, kernel)
#
#     elif filter_type == "laplacian":
#         lap = cv2.Laplacian(img, cv2.CV_64F, ksize=3)
#         out = cv2.convertScaleAbs(lap)
#
#     elif filter_type == "sobel":
#         sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
#         sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
#         out = cv2.convertScaleAbs(cv2.magnitude(sobelx, sobely))
#
#     elif filter_type == "invert":
#         out = cv2.bitwise_not(img)
#
#     elif filter_type == "brightness":
#         out = cv2.convertScaleAbs(img, alpha=1.0, beta=param)
#
#     elif filter_type == "contrast":
#         out = cv2.convertScaleAbs(img, alpha=param, beta=0)
#
#     elif filter_type == "histogram":
#         ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
#         ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
#         out = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
#
#     else:
#         out = img
#
#     success, encoded_img = cv2.imencode(".jpg", out)
#     if not success:
#         raise HTTPException(status_code=500, detail="Failed to encode output image")
#
#     return Response(content=encoded_img.tobytes(), media_type="image/jpeg")


import cv2
import numpy as np
import os
import shutil
import uuid
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

app = FastAPI(title="Image Processing Backend API")

# Setup CORS for Angular local server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories for server-side file management
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


# --- Helper Methods ---
def process_opencv_filter(
        img: np.ndarray, filter_type: str, param: float
) -> np.ndarray:
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
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        return cv2.filter2D(img, -1, kernel)
    elif filter_type == "laplacian":
        return cv2.Laplacian(img, cv2.CV_8U, ksize=3)
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


# --- Extended API Endpoints ---


# 1. Direct Blob Processing (In-Memory Streams)
@app.post("/api/filter")
async def process_filter_stream(
        file: UploadFile = File(...),
        filter_type: str = Form(...),
        param: float = Form(1.0),
):
    """Processes uploaded binary directly and streams back processed JPEG binary."""
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(
            status_code=400, detail="Invalid binary image format"
        )

    out = process_opencv_filter(img, filter_type, param)
    _, encoded_img = cv2.imencode(".jpg", out)
    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")


# 2. File Upload & Server-side Persistence
@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Uploads and saves original image to server disk, returning metadata and unique file_id."""
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    file_id = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_id)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    img = cv2.imread(file_path)
    if img is None:
        os.remove(file_path)
        raise HTTPException(
            status_code=400, detail="Uploaded file is not a valid image."
        )

    h, w, c = img.shape
    return {
        "file_id": file_id,
        "filename": file.filename,
        "width": w,
        "height": h,
        "channels": c,
        "size_bytes": os.path.getsize(file_path),
    }


# 3. Process Saved Server File
@app.post("/api/files/process/{file_id}")
async def process_saved_file(
        file_id: str,
        filter_type: str = Form(...),
        param: float = Form(1.0),
        output_format: str = Form("jpg"),
):
    """Applies a filter to an uploaded file ID and persists processed output to disk."""
    input_path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="File ID not found.")

    img = cv2.imread(input_path)
    out = process_opencv_filter(img, filter_type, param)

    processed_filename = f"processed_{filter_type}_{uuid.uuid4().hex[:8]}.{output_format.lower()}"
    output_path = os.path.join(PROCESSED_DIR, processed_filename)

    cv2.imwrite(output_path, out)

    return {
        "processed_file_id": processed_filename,
        "download_url": f"/api/files/download/{processed_filename}",
        "filter_applied": filter_type,
    }


# 4. Image Inspection & Metadata Endpoint
@app.get("/api/files/metadata/{file_id}")
async def get_image_metadata(file_id: str):
    """Extracts dimensional, statistical, and channel metrics from a stored image."""
    path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(path):
        path = os.path.join(PROCESSED_DIR, file_id)
        if not os.path.exists(path):
            raise HTTPException(
                status_code=404, detail="Requested image not found."
            )

    img = cv2.imread(path)
    h, w, c = img.shape

    # Compute pixel stats per channel
    b_mean, g_mean, r_mean = cv2.mean(img)[:3]

    return {
        "file_id": file_id,
        "dimensions": {"width": w, "height": h},
        "channels": c,
        "mean_intensity": {
            "red": round(r_mean, 2),
            "green": round(g_mean, 2),
            "blue": round(b_mean, 2),
        },
    }


# 5. File Download Endpoint
@app.get("/api/files/download/{file_id}")
async def download_file(file_id: str):
    """Serves a stored original or processed image file as a file download."""
    processed_path = os.path.join(PROCESSED_DIR, file_id)
    upload_path = os.path.join(UPLOAD_DIR, file_id)

    target_path = (
        processed_path if os.path.exists(processed_path) else upload_path
    )
    if not os.path.exists(target_path):
        raise HTTPException(
            status_code=404, detail="File not found on server."
        )

    return FileResponse(
        path=target_path,
        filename=file_id,
        media_type="application/octet-stream",
    )


# 6. Housekeeping Cleanup Endpoint
@app.delete("/api/files/cleanup")
async def cleanup_server_storage():
    """Deletes temporary uploaded and processed files from disk storage."""
    deleted_count = 0
    for folder in [UPLOAD_DIR, PROCESSED_DIR]:
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                deleted_count += 1
    return {"status": "success", "files_deleted": deleted_count}
