import base64
import html
import io
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance
from skimage import transform

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PIXEL_SIZE = 1.0
DEFAULT_NUM_COLORS = 5
THUMBNAIL_MAX_EDGE = 360

ALGORITHM_SPECS = [
    ("Style 1", "cv2_pillow"),
    ("Style 2", "skimage"),
    ("Style 3", "pixelate"),
    ("Style 4", "edge_preserved"),
]


def sanitize_stem(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", name).strip("-._")
    return slug or "upload"


def sanitize_filename(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", name).strip("-._")
    return slug or "result"


def format_numeric(value):
    if value is None:
        return ""
    return str(value)


def input_value_attr(value):
    if value in (None, ""):
        return ""
    escaped = html.escape(format_numeric(value), quote=True)
    return f' value="{escaped}"'


def image_from_bytes(file_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(file_bytes)).convert("RGB")


def get_image_dimensions_from_bytes(file_bytes: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(file_bytes)) as image:
        width, height = image.size
    return int(width), int(height)


def quantize_to_exact_colors_no_dither(pil_img: Image.Image, num_colors: int = 5) -> Image.Image:
    img_np = np.array(pil_img.convert("RGB"))
    h, w, c = img_np.shape
    img_lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
    pixels = img_lab.reshape((-1, 3)).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(
        pixels,
        max(1, int(num_colors)),
        None,
        criteria,
        10,
        cv2.KMEANS_PP_CENTERS,
    )

    centers = np.uint8(centers)
    quantized_lab = centers[labels.flatten()].reshape((h, w, c))
    quantized_rgb = cv2.cvtColor(quantized_lab, cv2.COLOR_LAB2RGB)
    return Image.fromarray(quantized_rgb)


def small_grid_size(target_size: tuple[int, int], pixel_w: float, pixel_h: float) -> tuple[int, int]:
    small_w = max(1, int(round(target_size[0] / pixel_w)))
    small_h = max(1, int(round(target_size[1] / pixel_h)))
    return small_w, small_h


def image_to_data_url(pil_img: Image.Image, image_format: str = "JPEG", quality: int = 90) -> str:
    return f"data:{image_mime_type(image_format)};base64,{image_bytes_to_base64(image_to_bytes(pil_img, image_format, quality))}"


def image_to_bytes(pil_img: Image.Image, image_format: str = "JPEG", quality: int = 90) -> bytes:
    buffer = io.BytesIO()
    save_kwargs = {}
    if image_format.upper() == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    pil_img.save(buffer, format=image_format, **save_kwargs)
    return buffer.getvalue()


def image_bytes_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("ascii")


def image_mime_type(image_format: str) -> str:
    return "image/jpeg" if image_format.upper() == "JPEG" else "image/png"


def make_contained_thumbnail(pil_img: Image.Image, max_edge: int = THUMBNAIL_MAX_EDGE) -> Image.Image:
    thumbnail = pil_img.copy()
    thumbnail.thumbnail((max_edge, max_edge), Image.NEAREST)
    return thumbnail


def build_result_card(label: str, large_image: Image.Image):
    thumbnail = make_contained_thumbnail(large_image)
    return {
        "label": label,
        "download_name": f"{sanitize_filename(label)}.jpg",
        "preview_url": image_to_data_url(thumbnail, image_format="JPEG", quality=82),
        "full_image_bytes": image_to_bytes(large_image, image_format="JPEG", quality=90),
        "full_image_mime": image_mime_type("JPEG"),
    }


def method_pillow_opencv(image: Image.Image, target_size, pixel_w, pixel_h, num_colors) -> Image.Image:
    img = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_filtered = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)
    small_w, small_h = small_grid_size(target_size, pixel_w, pixel_h)
    img_small = cv2.resize(img_filtered, (small_w, small_h), interpolation=cv2.INTER_AREA)
    pil_img = Image.fromarray(img_small)
    pil_img = ImageEnhance.Color(pil_img).enhance(1.8)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2.0)
    return quantize_to_exact_colors_no_dither(pil_img, num_colors=num_colors)


def method_skimage(image: Image.Image, target_size, pixel_w, pixel_h, num_colors) -> Image.Image:
    img = np.array(image.convert("RGB"))
    small_w, small_h = small_grid_size(target_size, pixel_w, pixel_h)
    img_small = transform.resize(img, (small_h, small_w), anti_aliasing=True)
    img_small = (img_small * 255).astype(np.uint8)
    pil_img = Image.fromarray(img_small)
    pil_img = ImageEnhance.Color(pil_img).enhance(1.8)
    return quantize_to_exact_colors_no_dither(pil_img, num_colors=num_colors)


def method_pixelate_lib(image: Image.Image, target_size, pixel_w, pixel_h, num_colors) -> Image.Image:
    small_w, small_h = small_grid_size(target_size, pixel_w, pixel_h)
    pil_img = image.convert("RGB").resize((small_w, small_h), Image.NEAREST)
    pil_img = ImageEnhance.Color(pil_img).enhance(1.8)
    return quantize_to_exact_colors_no_dither(pil_img, num_colors=num_colors)

def method_edge_preserved(image: Image.Image, target_size, pixel_w, pixel_h, num_colors) -> Image.Image:
    img = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    img_filtered = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)
    img_filtered = cv2.cvtColor(img_filtered, cv2.COLOR_BGR2RGB)
    small_w, small_h = small_grid_size(target_size, pixel_w, pixel_h)
    img_small = cv2.resize(img_filtered, (small_w, small_h), interpolation=cv2.INTER_AREA)
    pil_img = Image.fromarray(img_small)
    pil_img = ImageEnhance.Color(pil_img).enhance(1.8)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2.0)
    return quantize_to_exact_colors_no_dither(pil_img, num_colors=num_colors)


METHODS = {
    "cv2_pillow": method_pillow_opencv,
    "skimage": method_skimage,
    "pixelate": method_pixelate_lib,
    "edge_preserved": method_edge_preserved,
}


def generate_result_payload(file_bytes: bytes, filename: str, target_size, pixel_w, pixel_h, num_colors):
    image = image_from_bytes(file_bytes)
    original_thumbnail = make_contained_thumbnail(image)

    results = []
    for label, method_key in ALGORITHM_SPECS:
        method = METHODS[method_key]
        print(f"  -> Generating {label} (Size: {target_size[0]}x{target_size[1]})...")
        small_image = method(image, target_size, pixel_w, pixel_h, num_colors)
        large_image = small_image.resize(target_size, Image.NEAREST)
        results.append(build_result_card(label, large_image))

    return {
        "original_preview_url": image_to_data_url(original_thumbnail, image_format="JPEG", quality=82),
        "original_image_bytes": image_to_bytes(image, image_format="JPEG", quality=90),
        "original_image_mime": image_mime_type("JPEG"),
        "results": results,
        "filename": sanitize_stem(Path(filename).stem),
    }


def render_results_html(results):
    if not results:
        return """
    <section class="empty-state">
        <div class="empty-card">
            <h2>Upload an image to start generating</h2>
            <p>Result thumbnails are displayed on this page, and large images are loaded on demand when you click. Refreshing the page or closing the server will clear these results.</p>
        </div>
    </section>
"""

    cards = ['    <section class="results-grid">']
    for result in results:
        cards.append(
            f"""
        <article class="result-card">
            <h3>{html.escape(result["label"])}</h3>
            <button class="image-button" type="button">
                <img src="{result["preview_url"]}" data-full-src="{html.escape(result["full_url"], quote=True)}" alt="{html.escape(result["label"])}" loading="lazy">
            </button>
            <div class="result-actions">
                <a class="download-link" href="{html.escape(result["full_url"], quote=True)}" download="{html.escape(result["download_name"], quote=True)}">Download JPG</a>
            </div>
        </article>
"""
        )
    cards.append("    </section>")
    return "".join(cards)


def render_index_html(
    form_values=None,
    results=None,
    original_preview_url="",
    original_full_url="",
    session_id="",
    error_message="",
):
    form_values = form_values or {}
    results = results or []
    width_value = input_value_attr(form_values.get("img_w"))
    height_value = input_value_attr(form_values.get("img_h"))
    pixel_width_value = input_value_attr(form_values.get("px_w"))
    pixel_height_value = input_value_attr(form_values.get("px_h"))
    color_value = input_value_attr(form_values.get("num_colors"))

    preview_visible_class = " is-visible" if original_preview_url else ""
    preview_src = original_preview_url
    session_literal = html.escape(session_id, quote=True)
    error_html = ""
    if error_message:
        error_html = f'<div class="error-banner">{html.escape(error_message)}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pixel Art Generator</title>
    <style>
        :root {{
            --bg: #f7efe2;
            --panel: rgba(255, 251, 245, 0.9);
            --panel-strong: #fffaf1;
            --text: #2f241d;
            --muted: #746459;
            --accent: #d95f39;
            --accent-dark: #9d3c22;
            --line: rgba(82, 56, 42, 0.14);
            --shadow: 0 18px 48px rgba(72, 45, 31, 0.12);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at top left, rgba(217, 95, 57, 0.18), transparent 32%),
                radial-gradient(circle at bottom right, rgba(82, 130, 107, 0.14), transparent 28%),
                linear-gradient(160deg, #f4ead8 0%, #f7f1e7 42%, #efe4d2 100%);
            padding: 32px 20px 56px;
        }}
        .shell {{
            width: min(1180px, 100%);
            margin: 0 auto;
            display: grid;
            gap: 24px;
        }}
        .hero, .control-panel, .empty-card, .result-card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 24px;
            box-shadow: var(--shadow);
        }}
        .hero {{
            padding: 28px;
        }}
        .hero h1 {{
            margin: 0 0 10px;
            font-size: clamp(34px, 6vw, 56px);
            line-height: 0.95;
            letter-spacing: -0.04em;
        }}
        .hero p {{
            margin: 0;
            max-width: 760px;
            color: var(--muted);
            font-size: 16px;
            line-height: 1.7;
        }}
        .control-panel {{
            padding: 24px;
        }}
        .upload-form {{
            display: grid;
            gap: 18px;
        }}
        .file-field {{
            display: grid;
            gap: 10px;
        }}
        .file-label {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 72px;
            border: 1.5px dashed rgba(217, 95, 57, 0.45);
            border-radius: 20px;
            background: rgba(255, 243, 235, 0.75);
            cursor: pointer;
            padding: 16px;
            text-align: center;
            color: var(--accent-dark);
            font-weight: 600;
        }}
        .file-input {{
            display: none;
        }}
        .file-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px 16px;
            color: var(--muted);
            font-size: 14px;
        }}
        .original-preview {{
            display: none;
            width: min(240px, 100%);
            aspect-ratio: 1;
            overflow: hidden;
            border: 1px solid rgba(82, 56, 42, 0.12);
            background: linear-gradient(180deg, #fff8ef, #f2e7d6);
        }}
        .original-preview.is-visible {{
            display: block;
        }}
        .original-preview img {{
            width: 100%;
            height: 100%;
            display: block;
            object-fit: contain;
            background: rgba(255, 255, 255, 0.9);
            cursor: zoom-in;
        }}
        .error-banner {{
            border-radius: 16px;
            border: 1px solid rgba(183, 39, 39, 0.22);
            background: rgba(255, 231, 231, 0.88);
            color: #8e1d1d;
            padding: 14px 16px;
            font-size: 14px;
        }}
        .form-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 14px;
        }}
        .form-group {{
            display: grid;
            gap: 8px;
        }}
        .form-group label {{
            font-size: 13px;
            color: var(--muted);
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }}
        .form-group input {{
            width: 100%;
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 13px 14px;
            font-size: 15px;
            color: var(--text);
            background: rgba(255, 255, 255, 0.92);
        }}
        .actions {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 12px;
        }}
        .submit-btn {{
            border: none;
            border-radius: 999px;
            padding: 14px 24px;
            background: linear-gradient(135deg, var(--accent) 0%, #eb8a52 100%);
            color: #fff;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 12px 24px rgba(217, 95, 57, 0.22);
        }}
        .tip {{
            color: var(--muted);
            font-size: 14px;
        }}
        .empty-state, .results-grid {{
            display: grid;
            gap: 18px;
        }}
        .empty-card {{
            padding: 28px;
        }}
        .empty-card h2 {{
            margin: 0 0 10px;
            font-size: 24px;
        }}
        .empty-card p {{
            margin: 0;
            color: var(--muted);
            line-height: 1.7;
        }}
        .results-grid {{
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        }}
        .result-card {{
            padding: 18px;
            display: grid;
            gap: 14px;
            align-content: start;
        }}
        .result-card h3 {{
            margin: 0;
            font-size: 17px;
        }}
        .image-button {{
            padding: 0;
            border: none;
            background: transparent;
            cursor: zoom-in;
        }}
        .image-button img, .result-card img {{
            width: 100%;
            background: linear-gradient(180deg, #fef8f2, #f4ecdf);
            border: 1px solid rgba(82, 56, 42, 0.12);
            image-rendering: pixelated;
        }}
        .result-note {{
            margin: 0;
            font-size: 14px;
            color: var(--muted);
        }}
        .result-actions {{
            display: grid;
            gap: 10px;
        }}
        .download-link {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 40px;
            padding: 0 14px;
            border-radius: 999px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 700;
            color: var(--accent-dark);
            background: rgba(217, 95, 57, 0.08);
            border: 1px solid rgba(217, 95, 57, 0.16);
        }}
        .modal {{
            display: none;
            position: fixed;
            inset: 0;
            z-index: 1000;
            background: rgba(24, 16, 11, 0.84);
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .modal-content {{
            max-width: min(90vw, 1200px);
            max-height: 88vh;
            image-rendering: pixelated;
            border: 2px solid rgba(255, 255, 255, 0.85);
            box-shadow: 0 20px 48px rgba(0, 0, 0, 0.35);
        }}
        .close {{
            position: absolute;
            top: 18px;
            right: 28px;
            color: white;
            font-size: 38px;
            font-weight: 700;
            cursor: pointer;
        }}
        .loading-overlay {{
            position: fixed;
            inset: 0;
            z-index: 2000;
            display: none;
            align-items: center;
            justify-content: center;
            background: rgba(31, 22, 15, 0.45);
            backdrop-filter: blur(6px);
        }}
        .loading-overlay.is-visible {{
            display: flex;
        }}
        .loading-card {{
            min-width: 280px;
            padding: 24px 28px;
            border-radius: 24px;
            background: rgba(255, 251, 245, 0.96);
            border: 1px solid rgba(82, 56, 42, 0.12);
            box-shadow: var(--shadow);
            text-align: center;
        }}
        .spinner {{
            width: 42px;
            height: 42px;
            margin: 0 auto 16px;
            border-radius: 50%;
            border: 4px solid rgba(217, 95, 57, 0.16);
            border-top-color: var(--accent);
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        @media (max-width: 640px) {{
            body {{ padding: 20px 14px 36px; }}
            .hero, .control-panel, .empty-card, .result-card {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <main class="shell">
        <section class="hero">
            <h1>Pixel Art Generator</h1>
            <p>Upload a single image, and the system will automatically read the original width and height to fill in recommended parameters. All results are stored only in memory for this page and will not be saved to the server directory. They will be cleared when the page is refreshed or the server is closed.</p>
        </section>
        <section class="control-panel">
            {error_html}
            <form class="upload-form" action="/generate" method="POST" enctype="multipart/form-data" autocomplete="off">
                <div class="file-field">
                    <label class="file-label" for="imageFile">Choose an image to upload</label>
                    <input class="file-input" id="imageFile" type="file" name="image_file" accept=".jpg,.jpeg,.png,.tif,.tiff,image/*">
                    <div class="file-meta">
                        <span id="fileName">No image selected</span>
                    </div>
                    <div class="original-preview{preview_visible_class}" id="originalPreview">
                        <img id="originalPreviewImage" src="{preview_src}" data-full-src="{html.escape(original_full_url, quote=True)}" alt="Original preview">
                    </div>
                </div>
                <div class="form-grid">
                    <div class="form-group">
                        <label for="imgWidth">Image Width (Max 1024px)</label>
                        <input id="imgWidth" type="number" name="img_w" min="1" max="1024"{width_value} required>
                    </div>
                    <div class="form-group">
                        <label for="imgHeight">Image Height (Max 1024px)</label>
                        <input id="imgHeight" type="number" name="img_h" min="1" max="1024"{height_value} required>
                    </div>
                    <div class="form-group">
                        <label for="pixelWidth">Pixel Width (px)</label>
                        <input id="pixelWidth" type="number" name="px_w" min="0.01" step="0.01"{pixel_width_value} required>
                    </div>
                    <div class="form-group">
                        <label for="pixelHeight">Pixel Height (px)</label>
                        <input id="pixelHeight" type="number" name="px_h" min="0.01" step="0.01"{pixel_height_value} required>
                    </div>
                    <div class="form-group">
                        <label for="numColors">Number of Colors</label>
                        <input id="numColors" type="number" name="num_colors" min="1" max="256"{color_value} required>
                    </div>
                </div>
                <div class="actions">
                    <button class="submit-btn" id="submitButton" type="submit">Generate Pixel Art Comparisons</button>
                    <span class="tip">Auto-fills upon upload: original size (capped at 1024px), 1x1 pixel size, 5 colors. Only thumbnails are loaded by default. Click to view full image.</span>
                </div>
            </form>
        </section>
        {render_results_html(results)}
    </main>

        <div id="loadingOverlay" class="loading-overlay">
        <div class="loading-card">
            <div class="spinner"></div>
            <strong>Generating Pixel Art Comparisons</strong>
            <p id="loadingMessage">Generating results based on current parameters. Please wait.</p>
        </div>
    </div>

    <div id="imageModal" class="modal">
        <span class="close">&times;</span>
        <img class="modal-content" id="expandedImg" alt="Expanded view">
    </div>

    <script>
        const fileInput = document.getElementById("imageFile");
        const fileName = document.getElementById("fileName");
        const widthInput = document.getElementById("imgWidth");
        const heightInput = document.getElementById("imgHeight");
        const pixelWidthInput = document.getElementById("pixelWidth");
        const pixelHeightInput = document.getElementById("pixelHeight");
        const colorInput = document.getElementById("numColors");
        const uploadForm = document.querySelector(".upload-form");
        const originalPreview = document.getElementById("originalPreview");
        const originalPreviewImage = document.getElementById("originalPreviewImage");
        const loadingOverlay = document.getElementById("loadingOverlay");
        const loadingMessage = document.getElementById("loadingMessage");
        const activeSessionId = "{session_literal}";
        let sessionCleared = false;

        const navigationEntry = performance.getEntriesByType("navigation")[0];
        if (activeSessionId && navigationEntry && (navigationEntry.type === "reload" || navigationEntry.type === "back_forward")) {{
            window.location.replace("/");
        }}

        fileInput.addEventListener("change", function () {{
            const file = fileInput.files[0];
            if (!file) {{
                fileName.textContent = "No image selected";
                return;
            }}

            fileName.textContent = `Selected: ${{file.name}}`;
            const objectUrl = URL.createObjectURL(file);
            const preview = new Image();
            preview.onload = function () {{
                let w = preview.naturalWidth;
                let h = preview.naturalHeight;
                if (w > 1024 || h > 1024) {{
                    const scale = 1024 / Math.max(w, h);
                    w = Math.round(w * scale);
                    h = Math.round(h * scale);
                }}
                widthInput.value = w;
                heightInput.value = h;
                pixelWidthInput.value = "1";
                pixelHeightInput.value = "1";
                colorInput.value = "5";
                originalPreviewImage.src = objectUrl;
                originalPreviewImage.dataset.fullSrc = objectUrl;
                originalPreview.classList.add("is-visible");
            }};
            preview.src = objectUrl;
        }});

        uploadForm.addEventListener("submit", function (event) {{
            if (fileInput.files.length === 0) {{
                event.preventDefault();
                window.alert("Please upload an image first to generate pixel art comparisons.");
                return;
            }}
            const width = widthInput.value || "?";
            const height = heightInput.value || "?";
            const pixelWidth = pixelWidthInput.value || "?";
            const pixelHeight = pixelHeightInput.value || "?";
            const colors = colorInput.value || "?";
            loadingMessage.textContent = `Generating ${{width}}x${{height}} image, pixel size ${{pixelWidth}}x${{pixelHeight}}, ${{colors}} colors. Please wait.`;
            loadingOverlay.classList.add("is-visible");
        }});

        const modal = document.getElementById("imageModal");
        const expandedImg = document.getElementById("expandedImg");
        const closeButton = document.getElementsByClassName("close")[0];
        const images = document.querySelectorAll(".result-card img, .original-preview img");

        images.forEach(function (img) {{
            img.addEventListener("click", function () {{
                modal.style.display = "flex";
                expandedImg.src = this.dataset.fullSrc || this.src;
            }});
        }});

        closeButton.onclick = function () {{
            modal.style.display = "none";
        }};

        modal.onclick = function (event) {{
            if (event.target !== expandedImg) {{
                modal.style.display = "none";
            }}
        }};

        function clearActiveSession() {{
            if (!activeSessionId || sessionCleared) {{
                return;
            }}
            sessionCleared = true;
            const payload = new URLSearchParams({{ session_id: activeSessionId }});
            navigator.sendBeacon("/clear-session", payload);
        }}

        window.addEventListener("pagehide", clearActiveSession);
    </script>
</body>
</html>
"""
