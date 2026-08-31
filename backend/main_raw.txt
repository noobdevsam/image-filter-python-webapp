import io
from PIL import Image
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper Functions (I/O) ---
def load_img(file_bytes) -> tuple[list[list[list[int]]], int, int]:
    with Image.open(io.BytesIO(file_bytes)) as img:
        img = img.convert("RGB")  # [cite: 1, 2, 3]
        w, h = img.size
        pixels = list(img.getdata())
        image_list = [
            [list(pixels[y * w + x]) for x in range(w)] for y in range(h)
        ]  # [cite: 1, 2, 3]
        return image_list, w, h


def save_img(image_list: list[list[list[int]]]) -> bytes:
    h, w = len(image_list), len(image_list[0])  # [cite: 1, 2, 3]
    flat_pixels = [
        tuple(image_list[y][x]) for y in range(h) for x in range(w)
    ]  # [cite: 1, 2, 3]
    out_img = Image.new("RGB", (w, h))
    out_img.putdata(flat_pixels)  # [cite: 1, 2, 3]
    buf = io.BytesIO()
    out_img.save(buf, format="JPEG")
    return buf.getvalue()


# --- Core Pure Python Algorithms ---
def apply_gray_transform(img, mode: str, factor: float = 1.0):
    """Gray-Level Transformations (Inversion, Contrast/Brightness)"""
    h, w = len(img), len(img[0])
    res = []
    for y in range(h):
        row = []
        for x in range(w):
            pixel = []
            for c in range(3):
                val = img[y][x][c]
                if mode == "invert":
                    val = 255 - val
                elif mode == "brightness":
                    val = max(0, min(255, int(val + factor)))
                elif mode == "contrast":
                    val = max(0, min(255, int(128 + factor * (val - 128))))
                pixel.append(val)
            row.append(pixel)
        res.append(row)
    return res


def apply_spatial_filter(img, kernel_type: str):
    """Smoothing / Sharpening / Spatial Domain Filtering"""
    h, w = len(img), len(img[0])
    res = []

    # Defined Kernels
    kernels = {
        "average": [[1 / 9] * 3 for _ in range(3)],  # [cite: 1]
        "sharpen": [[0, -1, 0], [-1, 5, -1], [0, -1, 0]],
        "laplacian": [[0, 1, 0], [1, -4, 1], [0, 1, 0]],  # [cite: 2]
    }

    if kernel_type == "median":  # Non-linear filter[cite: 3]
        for y in range(h):
            row = []
            for x in range(w):
                pixel = []
                for c in range(3):
                    neighbors = []
                    for ky in range(-1, 2):
                        for kx in range(-1, 2):
                            ny = max(0, min(h - 1, y + ky))  # [cite: 1, 2, 3]
                            nx = max(0, min(w - 1, x + kx))  # [cite: 1, 2, 3]
                            neighbors.append(
                                img[ny][nx][c]
                            )  # Collect neighborhood values[cite: 3]
                    neighbors.sort()  # Sort for median extraction[cite: 3]
                    pixel.append(neighbors[4])
                row.append(pixel)
            res.append(row)
        return res

    k = kernels.get(kernel_type, kernels["average"])
    for y in range(h):
        row = []
        for x in range(w):
            pixel = []
            for c in range(3):
                acc = 0.0
                for ky in range(-1, 2):
                    for kx in range(-1, 2):
                        ny = max(0, min(h - 1, y + ky))  # [cite: 1, 2, 3]
                        nx = max(0, min(w - 1, x + kx))  # [cite: 1, 2, 3]
                        acc += img[ny][nx][c] * k[ky + 1][kx + 1]
                pixel.append(max(0, min(255, int(abs(acc)))))
            row.append(pixel)
        res.append(row)
    return res


def apply_histogram_equalization(img):
    """Histogram Processing: Equalization using CDF"""
    h, w = len(img), len(img[0])
    total_pixels = h * w

    # Calculate Luminance / Intensity Histogram (256 bins)
    hist = [0] * 256
    for y in range(h):
        for x in range(w):
            gray = int(
                0.299 * img[y][x][0]
                + 0.587 * img[y][x][1]
                + 0.114 * img[y][x][2]
            )
            hist[gray] += 1

    # Cumulative Distribution Function (CDF) calculation
    cdf = [0] * 256
    acc = 0
    for i in range(256):
        acc += hist[i]
        cdf[i] = acc

    cdf_min = next(val for val in cdf if val > 0)

    # Equalization Mapping Formula
    lut = [
        round(((cdf[i] - cdf_min) / (total_pixels - cdf_min)) * 255)
        for i in range(256)
    ]

    res = []
    for y in range(h):
        row = []
        for x in range(w):
            pixel = [lut[img[y][x][c]] for c in range(3)]
            row.append(pixel)
        res.append(row)
    return res


# --- API Endpoint ---
@app.post("/api/filter")
async def process_filter(
        file: UploadFile = File(...),
        filter_type: str = Form(...),
        param: float = Form(1.0),
):
    contents = await file.read()
    raw_img, w, h = load_img(contents)

    if filter_type in ["invert", "brightness", "contrast"]:
        out = apply_gray_transform(raw_img, filter_type, param)
    elif filter_type in ["average", "sharpen", "laplacian", "median"]:
        out = apply_spatial_filter(raw_img, filter_type)
    elif filter_type == "histogram":
        out = apply_histogram_equalization(raw_img)
    else:
        out = raw_img

    processed_bytes = save_img(out)
    return Response(content=processed_bytes, media_type="image/jpeg")
