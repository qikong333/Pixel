import cgi
import http.server
import socketserver
import threading
import time
import uuid
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import generate


PORT = 8082
DIRECTORY = str(generate.PROJECT_DIR)
MEDIA_TTL_SECONDS = 10 * 60


def parse_positive_int(raw_value: str, field_name: str) -> int:
    value = int(raw_value)
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return value


def parse_positive_float(raw_value: str, field_name: str) -> float:
    value = float(raw_value)
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return value


def parse_optional_positive_int(raw_value: str, default: int, field_name: str) -> int:
    if raw_value.strip() == "":
        return default
    return parse_positive_int(raw_value, field_name)


def parse_optional_positive_float(raw_value: str, default: float, field_name: str) -> float:
    if raw_value.strip() == "":
        return default
    return parse_positive_float(raw_value, field_name)


@dataclass
class MediaSession:
    created_at: float
    assets: dict[str, tuple[str, bytes]] = field(default_factory=dict)


class InMemoryMediaStore:
    def __init__(self, ttl_seconds: int = MEDIA_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, MediaSession] = {}
        self._lock = threading.Lock()

    def cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                session_id
                for session_id, session in self._sessions.items()
                if now - session.created_at > self.ttl_seconds
            ]
            for session_id in expired:
                self._sessions.pop(session_id, None)

    def create_session(self, assets: list[tuple[str, str, bytes]]) -> tuple[str, dict[str, str]]:
        self.cleanup()
        session_id = uuid.uuid4().hex
        session_assets: dict[str, tuple[str, bytes]] = {}
        urls: dict[str, str] = {}
        for asset_key, mime_type, payload in assets:
            media_id = uuid.uuid4().hex
            session_assets[media_id] = (mime_type, payload)
            urls[asset_key] = f"/media/{session_id}/{media_id}"
        with self._lock:
            self._sessions[session_id] = MediaSession(created_at=time.time(), assets=session_assets)
        return session_id, urls

    def get_asset(self, session_id: str, media_id: str) -> tuple[str, bytes] | None:
        self.cleanup()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return session.assets.get(media_id)

    def delete_session(self, session_id: str) -> bool:
        self.cleanup()
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


MEDIA_STORE = InMemoryMediaStore()


class PixelateHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def _send_html_response(self, html_content: str, status_code: int = 200) -> None:
        payload = html_content.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(payload)

    def _send_binary_response(self, payload: bytes, content_type: str, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_headers_only(self, content_type: str, content_length: int, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

    def _read_request_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            return b""
        return self.rfile.read(content_length)

    def _handle_media_request(self, headers_only: bool = False) -> bool:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/media/"):
            return False

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 3:
            self.send_error(404, "Not Found")
            return True

        _, session_id, media_id = parts
        asset = MEDIA_STORE.get_asset(session_id, media_id)
        if asset is None:
            self.send_error(404, "Asset expired, please generate again.")
            return True

        mime_type, payload = asset
        try:
            if headers_only:
                self._send_headers_only(mime_type, len(payload))
            else:
                self._send_binary_response(payload, mime_type)
        except (BrokenPipeError, ConnectionResetError):
            return True
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            try:
                self._send_html_response(generate.render_index_html())
            except (BrokenPipeError, ConnectionResetError):
                return
            return
        if self._handle_media_request(headers_only=False):
            return
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            html_content = generate.render_index_html().encode("utf-8")
            try:
                self._send_headers_only("text/html; charset=utf-8", len(html_content))
            except (BrokenPipeError, ConnectionResetError):
                return
            return
        if self._handle_media_request(headers_only=True):
            return
        try:
            super().do_HEAD()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):
        if self.path == "/clear-session":
            try:
                raw_body = self._read_request_body()
                params = parse_qs(raw_body.decode("utf-8")) if raw_body else {}
                session_id = (params.get("session_id") or [""])[0].strip()
                if session_id:
                    MEDIA_STORE.delete_session(session_id)
                self.send_response(204)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                return
            return

        if self.path != "/generate":
            self.send_error(404, "Not Found")
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                },
            )

            image_field = form["image_file"] if "image_file" in form else None
            if image_field is None or not getattr(image_field, "filename", ""):
                raise ValueError("Please upload an image first.")

            file_bytes = image_field.file.read()
            if not file_bytes:
                raise ValueError("Uploaded image is empty, please select again.")

            default_width, default_height = generate.get_image_dimensions_from_bytes(file_bytes)
            img_w = parse_optional_positive_int(form.getfirst("img_w", ""), default_width, "Image Width")
            img_h = parse_optional_positive_int(form.getfirst("img_h", ""), default_height, "Image Height")
            
            if img_w > 1024 or img_h > 1024:
                raise ValueError("Image dimension (width or height) cannot exceed 1024px. Please adjust the size.")

            px_w = parse_optional_positive_float(
                form.getfirst("px_w", ""),
                generate.DEFAULT_PIXEL_SIZE,
                "Pixel Width",
            )
            px_h = parse_optional_positive_float(
                form.getfirst("px_h", ""),
                generate.DEFAULT_PIXEL_SIZE,
                "Pixel Height",
            )
            num_colors = parse_optional_positive_int(
                form.getfirst("num_colors", ""),
                generate.DEFAULT_NUM_COLORS,
                "Number of Colors",
            )

            print(
                f"\n[Server] Received generation request: file={image_field.filename}, size={img_w}x{img_h}, "
                f"pixel grid={px_w}x{px_h}, colors={num_colors}"
            )

            payload = generate.generate_result_payload(
                file_bytes=file_bytes,
                filename=image_field.filename,
                target_size=(img_w, img_h),
                pixel_w=px_w,
                pixel_h=px_h,
                num_colors=num_colors,
            )
            del file_bytes
            import gc
            gc.collect()

            assets = [("original", payload["original_image_mime"], payload["original_image_bytes"])]
            for index, result in enumerate(payload["results"]):
                assets.append((f"result_{index}", result["full_image_mime"], result["full_image_bytes"]))
            session_id, media_urls = MEDIA_STORE.create_session(assets)
            for index, result in enumerate(payload["results"]):
                result["full_url"] = media_urls[f"result_{index}"]
            html_content = generate.render_index_html(
                form_values={
                    "img_w": img_w,
                    "img_h": img_h,
                    "px_w": px_w,
                    "px_h": px_h,
                    "num_colors": num_colors,
                },
                results=payload["results"],
                original_preview_url=payload["original_preview_url"],
                original_full_url=media_urls["original"],
                session_id=session_id,
            )
            self._send_html_response(html_content)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            form_values = {}
            for key in ("img_w", "img_h", "px_w", "px_h", "num_colors"):
                try:
                    value = form.getfirst(key, "") if "form" in locals() else ""
                except Exception:
                    value = ""
                if value != "":
                    form_values[key] = value
            try:
                self._send_html_response(
                    generate.render_index_html(
                        form_values=form_values,
                        error_message=str(exc),
                    ),
                    status_code=400,
                )
            except (BrokenPipeError, ConnectionResetError):
                return


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ReusableTCPServer(("", PORT), PixelateHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        print("You can open your browser to upload images and generate pixel art.")
        httpd.serve_forever()
