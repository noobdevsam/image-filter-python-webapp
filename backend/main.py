import io
import json
import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI(title="Mood Enhancer for Old Memories API")

# Setup CORS for Angular local server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Image-Meta"],
)


# =====================================================================
# 1. EMOTION ZONE DETECTION (Pure Digital Image Processing)
# =====================================================================
def detect_emotion_zones(
    img: np.ndarray, gray: np.ndarray
) -> tuple[dict[str, np.ndarray], list[dict]]:
    """
    Detects emotion zones (Skies, Nature/Texture, Faces/Subjects) using
    classical Spatial Domain Filtering (Sobel gradient magnitude, color/luminance analysis,
    and morphological connected-component clustering).
    """
    h, w = gray.shape
    masks = {
        "sky": np.zeros((h, w), dtype=np.float32),
        "nature": np.zeros((h, w), dtype=np.float32),
        "face": np.zeros((h, w), dtype=np.float32),
    }
    zones_meta = []

    # --- A. Sky Detection (Spatial Domain + Luminance) ---
    # In scanned vintage photos, sky regions occupy the upper half, with high luminance
    # and minimal spatial frequency (very low Sobel edge response).
    upper_limit = int(h * 0.6)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(grad_x, grad_y)

    sky_candidates = np.zeros((h, w), dtype=np.uint8)
    sky_candidates[:upper_limit, :] = (
        (gray[:upper_limit, :] > 140) & (grad_mag[:upper_limit, :] < 28)
    ).astype(np.uint8)

    # Clean up small noise with morphological opening and closing
    kernel_sky = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    sky_clean = cv2.morphologyEx(sky_candidates, cv2.MORPH_OPEN, kernel_sky)
    sky_clean = cv2.morphologyEx(sky_clean, cv2.MORPH_CLOSE, kernel_sky)

    sky_pixel_count = np.sum(sky_clean > 0)
    if sky_pixel_count > (h * w * 0.04):
        # Gaussian feathering to avoid hard transition seams
        masks["sky"] = (
            cv2.GaussianBlur(sky_clean.astype(np.float32), (31, 31), 0)
            / 255.0
        )
        # Find sky bounding box for frontend overlay
        contours, _ = cv2.findContours(
            sky_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if contours:
            largest_sky = max(contours, key=cv2.contourArea)
            sx, sy, sw, sh = cv2.boundingRect(largest_sky)
            if sw * sh > (h * w * 0.05):
                zones_meta.append({
                    "type": "sky",
                    "label": "Sky Zone",
                    "box": {
                        "x": round((sx / w) * 100, 1),
                        "y": round((sy / h) * 100, 1),
                        "width": round((sw / w) * 100, 1),
                        "height": round((sh / h) * 100, 1),
                    },
                })

    # --- B. Subject / Face Zone Detection (Morphological & Saliency) ---
    # Detect subject regions (faces / focal figures) using skin tone (if color) or
    # central elliptical saliency (warm midtone regions with defined contour borders).
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    # Standard Cr/Cb skin locus range
    skin_mask = (
        (ycrcb[:, :, 1] >= 133)
        & (ycrcb[:, :, 1] <= 173)
        & (ycrcb[:, :, 2] >= 77)
        & (ycrcb[:, :, 2] <= 127)
    ).astype(np.uint8)

    # For pure B&W / grayscale scans, skin_mask will be empty. Fallback to midtone subject analysis:
    is_bw = np.max(np.abs(img[:, :, 0].astype(int) - img[:, :, 1].astype(int))) < 15
    if is_bw or np.sum(skin_mask > 0) < 500:
        # Midtone focal subject detection (focal region in center with distinct edges)
        center_y1, center_y2 = int(h * 0.15), int(h * 0.75)
        center_x1, center_x2 = int(w * 0.15), int(w * 0.85)
        midtone_candidates = np.zeros((h, w), dtype=np.uint8)
        midtone_candidates[center_y1:center_y2, center_x1:center_x2] = (
            (gray[center_y1:center_y2, center_x1:center_x2] >= 85)
            & (gray[center_y1:center_y2, center_x1:center_x2] <= 210)
            & (grad_mag[center_y1:center_y2, center_x1:center_x2] < 60)
        ).astype(np.uint8)
        skin_mask = midtone_candidates

    kernel_face = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    skin_clean = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel_face)
    skin_clean = cv2.morphologyEx(skin_clean, cv2.MORPH_CLOSE, kernel_face)

    # Extract connected components as face/subject zones
    contours, _ = cv2.findContours(
        skin_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    face_count = 0
    face_combined_mask = np.zeros((h, w), dtype=np.uint8)

    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
        area = cv2.contourArea(cnt)
        # Filter for face/subject proportions
        if (h * w * 0.01) < area < (h * w * 0.35):
            fx, fy, fw, fh = cv2.boundingRect(cnt)
            aspect_ratio = fh / float(fw)
            if 0.6 <= aspect_ratio <= 2.2:
                cv2.drawContours(
                    face_combined_mask, [cnt], -1, 255, -1
                )
                face_count += 1
                zones_meta.append({
                    "type": "face",
                    "label": f"Subject / Face {face_count}",
                    "box": {
                        "x": round((fx / w) * 100, 1),
                        "y": round((fy / h) * 100, 1),
                        "width": round((fw / w) * 100, 1),
                        "height": round((fh / h) * 100, 1),
                    },
                })

    if face_count > 0:
        masks["face"] = (
            cv2.GaussianBlur(face_combined_mask.astype(np.float32), (25, 25), 0)
            / 255.0
        )

    # --- C. Nature & Scenery (High texture, non-sky, non-face) ---
    texture_mask = ((grad_mag > 35) & (sky_clean == 0) & (face_combined_mask == 0)).astype(np.uint8)
    masks["nature"] = (
        cv2.GaussianBlur(texture_mask.astype(np.float32), (15, 15), 0)
    )

    return masks, zones_meta


# =====================================================================
# 2. ADAPTIVE EMOTION & MOOD ENHANCEMENT PIPELINE
# =====================================================================
def apply_emotion_mood_pipeline(
    img: np.ndarray,
    mood_preset: str,
    face_brightness: float,
    sky_softness: float,
    clahe_limit: float,
) -> tuple[np.ndarray, list[dict]]:
    """
    Applies zone-aware mood enhancement combining:
    1. CLAHE (Contrast-Limited Adaptive Histogram Equalization)
    2. Adaptive Spatial Filtering (smoothing sky grain, unsharp masking textures)
    3. Gray-Level Transformation (face/subject dynamic range lift)
    4. Tonal / Mood Color Grading (Sepia, Silver Gelatin, Portrait Warmth)
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Detect Emotion Zones
    masks, zones_meta = detect_emotion_zones(img, gray)
    sky_mask = masks["sky"]
    face_mask = masks["face"]
    nature_mask = np.clip(masks["nature"], 0.0, 1.0)

    # 2. Module: Histogram Processing with CLAHE
    # Rather than destroying vintage tones via global equalization, CLAHE restores
    # faded shadow and highlight details with local adaptive tile grids.
    clahe = cv2.createCLAHE(
        clipLimit=max(1.0, float(clahe_limit)), tileGridSize=(8, 8)
    )
    equalized_gray = clahe.apply(gray)

    # Convert base equalized luminance back into 3 channels
    base_bgr = cv2.cvtColor(equalized_gray, cv2.COLOR_GRAY2BGR)

    # 3. Module: Smoothing / Spatial Filtering for Sky Zone
    # Smooth scan dust & noise in sky regions without blurring faces or textures
    k_sky = max(1, int(round(sky_softness))) | 1
    sky_smoothed = cv2.medianBlur(base_bgr, k_sky)

    # 4. Module: Spatial Domain Filtering (Unsharp Masking for Texture/Nature)
    # Enhance clothing, trees, architecture edges
    gaussian_blur = cv2.GaussianBlur(base_bgr, (5, 5), 1.5)
    unsharp_texture = cv2.addWeighted(base_bgr, 1.4, gaussian_blur, -0.4, 0)

    # 5. Module: Gray-Level Transformation for Face / Subject Zone
    # Lift face midtones gently so subjects pop out from faded scan backgrounds
    face_lifted = cv2.convertScaleAbs(
        base_bgr, alpha=1.05, beta=float(face_brightness)
    )

    # Composite layers based on detected emotion zone masks:
    # result = Base + Sky_Delta + Face_Delta + Nature_Delta
    result = base_bgr.astype(np.float32)

    # Blend Sky Smoothing
    sky_3ch = np.repeat(sky_mask[:, :, np.newaxis], 3, axis=2)
    result = result * (1.0 - sky_3ch) + sky_smoothed.astype(np.float32) * sky_3ch

    # Blend Face Lift
    face_3ch = np.repeat(face_mask[:, :, np.newaxis], 3, axis=2)
    result = result * (1.0 - face_3ch) + face_lifted.astype(np.float32) * face_3ch

    # Blend Texture Sharpening
    nature_3ch = np.repeat(nature_mask[:, :, np.newaxis], 3, axis=2) * 0.6
    result = result * (1.0 - nature_3ch) + unsharp_texture.astype(np.float32) * nature_3ch

    result = np.clip(result, 0, 255).astype(np.uint8)

    # 6. Mood / Emotional Color Grading (Lookup & Linear Transforms)
    if mood_preset == "nostalgic_warmth":
        # Nostalgic Warmth (Warm Sepia Tonal Mapping)
        sepia_matrix = np.array([
            [0.18, 0.58, 0.22],   # Blue
            [0.22, 0.68, 0.28],   # Green
            [0.28, 0.78, 0.35],   # Red
        ])
        result = cv2.transform(result, sepia_matrix)
        # Subtle vignette around borders to evoke vintage camera lenses
        result = apply_vignette(result)

    elif mood_preset == "gentle_portrait":
        # Soft warmth with glowing highlights
        warm_matrix = np.array([
            [0.85, 0.05, 0.05],
            [0.05, 0.95, 0.05],
            [0.05, 0.05, 1.10],
        ])
        result = cv2.transform(result, warm_matrix)

    elif mood_preset == "silver_gelatin":
        # Rich deep blacks, pure classic darkroom photographic paper look
        gray_res = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        # S-curve contrast mapping via LUT
        table = np.array([
            int(255 * (1 / (1 + np.exp(-0.035 * (i - 128))))) for i in range(256)
        ], dtype=np.uint8)
        contrasted = cv2.LUT(gray_res, table)
        result = cv2.cvtColor(contrasted, cv2.COLOR_GRAY2BGR)

    elif mood_preset == "vivid_scenery":
        # Deep dynamic range with crisp spatial detail
        result = cv2.convertScaleAbs(result, alpha=1.12, beta=2)

    return np.clip(result, 0, 255).astype(np.uint8), zones_meta


def apply_vignette(img: np.ndarray) -> np.ndarray:
    """Soft photographic vignette falloff to direct emotional focus toward center."""
    h, w = img.shape[:2]
    kernel_x = cv2.getGaussianKernel(w, w * 0.75)
    kernel_y = cv2.getGaussianKernel(h, h * 0.75)
    kernel = kernel_y * kernel_x.T
    mask = kernel / kernel.max()
    mask = np.repeat(mask[:, :, np.newaxis], 3, axis=2)
    vignetted = img * (0.45 + 0.55 * mask)
    return np.clip(vignetted, 0, 255).astype(np.uint8)


# =====================================================================
# 3. MANUAL LOW-LEVEL DIP FILTERS
# =====================================================================
def process_manual_filter(
    img: np.ndarray, filter_type: str, param: float
) -> np.ndarray:
    """Executes individual classical DIP algorithms directly."""
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


# =====================================================================
# 4. API ENDPOINTS
# =====================================================================
@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Mood Enhancer for Old Memories"}


@app.post("/api/filter")
async def process_filter_stream(
    file: UploadFile = File(...),
    pipeline_mode: str = Form("mood"),
    # Emotion Mood parameters
    mood_preset: str = Form("nostalgic_warmth"),
    face_brightness: float = Form(15.0),
    sky_softness: float = Form(5.0),
    clahe_limit: float = Form(2.0),
    # Manual DIP parameters
    filter_type: str = Form("average"),
    param: float = Form(1.0),
):
    """
    Pure ephemeral streaming endpoint:
    Processes the image completely in memory and directly streams back JPEG bytes
    along with JSON metadata in the X-Image-Meta header.
    """
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid binary image format")

    detected_zones = []
    active_mode_label = ""

    if pipeline_mode == "mood":
        out, detected_zones = apply_emotion_mood_pipeline(
            img=img,
            mood_preset=mood_preset,
            face_brightness=face_brightness,
            sky_softness=sky_softness,
            clahe_limit=clahe_limit,
        )
        active_mode_label = f"Mood Preset: {mood_preset}"
    else:
        out = process_manual_filter(img, filter_type, param)
        active_mode_label = f"Manual Filter: {filter_type}"

    success, encoded_img = cv2.imencode(".jpg", out)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode output image")

    # Diagnostic metadata for frontend
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
        "detected_zones": detected_zones,
        "active_mood": active_mode_label,
    }

    return Response(
        content=encoded_img.tobytes(),
        media_type="image/jpeg",
        headers={"X-Image-Meta": json.dumps(meta)},
    )


