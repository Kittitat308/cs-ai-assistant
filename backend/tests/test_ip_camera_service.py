import unittest
from unittest.mock import patch

from app.services.ip_camera_service import IPCameraError, IPCameraService


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "image/jpeg"):
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit: int) -> bytes:
        return self.body


class IPCameraServiceTests(unittest.TestCase):
    def test_base_ipv4_url_uses_shot_endpoint(self):
        url = IPCameraService.build_snapshot_url("http://192.168.0.11:8080")

        self.assertEqual(url, "http://192.168.0.11:8080/shot.jpg")

    def test_existing_snapshot_path_is_preserved(self):
        url = IPCameraService.build_snapshot_url(
            "http://192.168.0.11:8080/custom.jpg"
        )

        self.assertEqual(url, "http://192.168.0.11:8080/custom.jpg")

    def test_empty_or_non_ipv4_url_is_rejected(self):
        invalid_urls = (
            "",
            "not-a-url",
            "http://camera.local:8080",
            "http://[::1]:8080",
            "http://192.168.0.11:not-a-port",
        )

        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(IPCameraError):
                IPCameraService.build_snapshot_url(url)

    @patch("app.services.ip_camera_service.urlopen")
    def test_fetch_snapshot_returns_image(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(b"jpeg-data")

        image, content_type = IPCameraService.fetch_snapshot(
            "http://192.168.0.11:8080"
        )

        self.assertEqual(image, b"jpeg-data")
        self.assertEqual(content_type, "image/jpeg")

    @patch("app.services.ip_camera_service.urlopen")
    def test_non_image_response_is_rejected(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(b"html", "text/html")

        with self.assertRaises(IPCameraError):
            IPCameraService.fetch_snapshot("http://192.168.0.11:8080")


if __name__ == "__main__":
    unittest.main()
