import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import generate
import server


class GenerateInMemoryTests(unittest.TestCase):
    def test_server_optional_params_fall_back_to_image_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "input.png"
            Image.new("RGB", (37, 19), (1, 2, 3)).save(image_path)
            file_bytes = image_path.read_bytes()

            width, height = generate.get_image_dimensions_from_bytes(file_bytes)

            self.assertEqual(width, 37)
            self.assertEqual(height, 19)
            self.assertEqual(server.parse_optional_positive_int("", width, "Image Width"), 37)
            self.assertEqual(server.parse_optional_positive_int("", height, "Image Height"), 19)
            self.assertEqual(
                server.parse_optional_positive_float("", generate.DEFAULT_PIXEL_SIZE, "Pixel Width"),
                1.0,
            )
            self.assertEqual(
                server.parse_optional_positive_int("", generate.DEFAULT_NUM_COLORS, "Number of Colors"),
                5,
            )

    def test_render_index_without_results_has_upload_form_and_no_defaults(self) -> None:
        html = generate.render_index_html()

        self.assertIn('type="file"', html)
        self.assertIn('name="image_file"', html)
        self.assertNotIn("data:image/", html)
        self.assertNotIn('value="718"', html)
        self.assertNotIn('value="2959"', html)
        self.assertNotIn('value="5.0"', html)
        self.assertNotIn('value="5"', html)
        self.assertIn("loadingOverlay", html)
        self.assertIn("loadingMessage", html)
        self.assertIn("Generating results based on current parameters. Please wait.", html)
        self.assertIn("Only thumbnails are loaded by default. Click to view full image.", html)
        self.assertIn('const activeSessionId = "";', html)
        self.assertIn('navigator.sendBeacon("/clear-session", payload);', html)
        self.assertIn('autocomplete="off"', html)

    def test_generate_result_payload_embeds_thumbnails_and_omits_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"
            Image.new("RGB", (16, 16), (12, 34, 56)).save(image_path)
            file_bytes = image_path.read_bytes()

            payload = generate.generate_result_payload(
                file_bytes=file_bytes,
                filename="sample.png",
                target_size=(24, 24),
                pixel_w=4.0,
                pixel_h=4.0,
                num_colors=3,
            )
            for index, result in enumerate(payload["results"]):
                result["full_url"] = f"/media/session/result-{index}"
            html = generate.render_index_html(
                form_values={
                    "img_w": 24,
                    "img_h": 24,
                    "px_w": 4.0,
                    "px_h": 4.0,
                    "num_colors": 3,
                },
                results=payload["results"],
                original_preview_url=payload["original_preview_url"],
                original_full_url="/media/session/original",
            )

        self.assertIn("Style 4", html)
        self.assertIn("data:image/jpeg;base64,", html)
        self.assertIn('data-full-src="/media/session/original"', html)
        self.assertIn('data-full-src="/media/session/result-0"', html)
        self.assertIn("Only thumbnails are loaded by default. Click to view full image.", html)
        self.assertIn('download="Style-1.jpg"', html)
        self.assertIn("Download JPG", html)
        result_html = generate.render_index_html(
            form_values={},
            results=payload["results"],
            original_preview_url=payload["original_preview_url"],
            original_full_url="/media/session/original",
            session_id="session-123",
        )
        self.assertIn('const activeSessionId = "session-123";', result_html)
        self.assertIn('window.location.replace("/");', result_html)
        self.assertNotIn("data:image/svg+xml;base64,", html)
        self.assertNotIn("Download SVG", html)
        self.assertNotIn("output/", html)
        self.assertNotIn("uploads/", html)
        self.assertIn('alt="Original preview"', html)
        self.assertIn("full_image_bytes", payload["results"][0])

    def test_media_store_serves_and_expires_assets(self) -> None:
        store = server.InMemoryMediaStore(ttl_seconds=1)
        _, urls = store.create_session([("original", "image/jpeg", b"123")])
        parts = urls["original"].split("/")
        session_id = parts[-2]
        media_id = parts[-1]

        self.assertEqual(store.get_asset(session_id, media_id), ("image/jpeg", b"123"))

        store._sessions[session_id].created_at -= 2
        store.cleanup()
        self.assertIsNone(store.get_asset(session_id, media_id))

    def test_media_store_can_delete_session_immediately(self) -> None:
        store = server.InMemoryMediaStore(ttl_seconds=60)
        _, urls = store.create_session([("original", "image/jpeg", b"123")])
        parts = urls["original"].split("/")
        session_id = parts[-2]
        media_id = parts[-1]

        self.assertTrue(store.delete_session(session_id))
        self.assertIsNone(store.get_asset(session_id, media_id))
        self.assertFalse(store.delete_session(session_id))


if __name__ == "__main__":
    unittest.main()
