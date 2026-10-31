"""Upload validation and image preparation for card photos.

The file type is decided from the file content, never from the client-supplied
content type or file name.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.api_errors import ApiError

ACCEPTED_FORMATS = {"JPEG", "PNG"}
ACCEPTED_MESSAGE = "Only JPEG and PNG images are accepted."
MAX_LONG_EDGE = 1600
MAX_PIXELS = 50_000_000
JPEG_QUALITY = 85


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    media_type: str
    width: int
    height: int


def _format_limit(max_bytes: int) -> str:
    mib = max_bytes / (1024 * 1024)
    return f"{mib:g} MB" if mib >= 1 else f"{max_bytes // 1024} KB"


def validate_and_prepare(data: bytes, max_bytes: int) -> PreparedImage:
    """Validate an uploaded card image and return a normalised, downscaled JPEG.

    Raises ApiError for oversized, unsupported (including PDF) and unreadable files.
    """
    if len(data) > max_bytes:
        raise ApiError(
            413,
            "file_too_large",
            f"The file is too large. The limit is {_format_limit(max_bytes)}.",
        )

    try:
        probe = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError):
        raise ApiError(415, "unsupported_file_type", ACCEPTED_MESSAGE) from None

    if probe.format not in ACCEPTED_FORMATS:
        raise ApiError(415, "unsupported_file_type", ACCEPTED_MESSAGE)
    if probe.width * probe.height > MAX_PIXELS:
        raise ApiError(422, "image_too_large", "The image dimensions are too large.")

    try:
        image = ImageOps.exif_transpose(probe)
        image.load()
    except (OSError, SyntaxError, ValueError):
        raise ApiError(422, "invalid_image", "The image file is damaged or unreadable.") from None

    image = _flatten_to_rgb(image)
    image.thumbnail((MAX_LONG_EDGE, MAX_LONG_EDGE), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return PreparedImage(out.getvalue(), "image/jpeg", image.width, image.height)


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")
