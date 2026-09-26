import ipaddress
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen


class IPCameraError(RuntimeError):
    pass


class IPCameraService:
    SNAPSHOT_PATH = "/shot.jpg"
    MAX_IMAGE_BYTES = 10 * 1024 * 1024
    TIMEOUT_SECONDS = 3.0

    @classmethod
    def build_snapshot_url(cls, configured_url: str) -> str:
        value = configured_url.strip()

        if not value:
            raise IPCameraError("IP camera URL is empty")

        parsed = urlparse(value)

        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise IPCameraError("IP camera URL is invalid")

        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError as error:
            raise IPCameraError("IP camera host must be an IPv4 address") from error

        if address.version != 4:
            raise IPCameraError("IP camera host must be an IPv4 address")

        try:
            parsed.port
        except ValueError as error:
            raise IPCameraError("IP camera port is invalid") from error

        path = parsed.path

        if path in {"", "/"}:
            path = cls.SNAPSHOT_PATH

        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                path,
                "",
                parsed.query,
                "",
            )
        )

    @classmethod
    def fetch_snapshot(cls, configured_url: str) -> tuple[bytes, str]:
        snapshot_url = cls.build_snapshot_url(configured_url)
        request = Request(
            snapshot_url,
            headers={
                "Accept": "image/jpeg,image/png,image/*",
                "User-Agent": "CS-AI-Assistant/1.0",
            },
        )

        try:
            with urlopen(request, timeout=cls.TIMEOUT_SECONDS) as response:
                content_type = response.headers.get(
                    "Content-Type",
                    "",
                ).split(";", 1)[0].strip().lower()
                image = response.read(cls.MAX_IMAGE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise IPCameraError("IP camera is unavailable") from error

        if not content_type.startswith("image/"):
            raise IPCameraError("IP camera did not return an image")

        if not image or len(image) > cls.MAX_IMAGE_BYTES:
            raise IPCameraError("IP camera image is empty or too large")

        return image, content_type


ip_camera_service = IPCameraService()
