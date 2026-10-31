import io

import pytest
from PIL import Image

from app.api_errors import ApiError
from app.images import MAX_LONG_EDGE, validate_and_prepare

LIMIT = 5 * 1024 * 1024


def make_image(
    fmt: str = "JPEG", size: tuple[int, int] = (200, 100), mode: str = "RGB", **save_kwargs: object
) -> bytes:
    color = (255, 0, 0, 128) if mode == "RGBA" else (255, 0, 0)
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def test_jpeg_accepted() -> None:
    result = validate_and_prepare(make_image("JPEG"), LIMIT)
    assert result.media_type == "image/jpeg"
    assert (result.width, result.height) == (200, 100)
    assert Image.open(io.BytesIO(result.data)).format == "JPEG"


def test_png_accepted_and_converted_to_jpeg() -> None:
    result = validate_and_prepare(make_image("PNG"), LIMIT)
    assert Image.open(io.BytesIO(result.data)).format == "JPEG"


def test_png_transparency_is_flattened_on_white() -> None:
    data = make_image("PNG", size=(10, 10), mode="RGBA")
    result = validate_and_prepare(data, LIMIT)
    image = Image.open(io.BytesIO(result.data))
    assert image.mode == "RGB"


def test_pdf_rejected_with_accepted_formats_message() -> None:
    with pytest.raises(ApiError) as exc:
        validate_and_prepare(b"%PDF-1.7\n%fake pdf content", LIMIT)
    assert exc.value.status_code == 415
    assert exc.value.code == "unsupported_file_type"
    assert "JPEG" in exc.value.message and "PNG" in exc.value.message


def test_other_image_format_rejected() -> None:
    with pytest.raises(ApiError) as exc:
        validate_and_prepare(make_image("GIF"), LIMIT)
    assert exc.value.code == "unsupported_file_type"


def test_text_file_rejected() -> None:
    with pytest.raises(ApiError) as exc:
        validate_and_prepare(b"hello world", LIMIT)
    assert exc.value.code == "unsupported_file_type"


def test_oversized_file_rejected_with_limit_in_message() -> None:
    with pytest.raises(ApiError) as exc:
        validate_and_prepare(make_image("JPEG") + b"0" * 2048, 1024)
    assert exc.value.status_code == 413
    assert exc.value.code == "file_too_large"
    assert "1 KB" in exc.value.message


def test_limit_message_in_megabytes() -> None:
    big = b"0" * (LIMIT + 1)
    with pytest.raises(ApiError) as exc:
        validate_and_prepare(big, LIMIT)
    assert "5 MB" in exc.value.message


def test_truncated_image_reported_as_invalid() -> None:
    data = make_image("JPEG", size=(800, 800))
    with pytest.raises(ApiError) as exc:
        validate_and_prepare(data[: len(data) // 2], LIMIT)
    assert exc.value.code == "invalid_image"
    assert exc.value.status_code == 422


def test_large_image_downscaled_to_long_edge() -> None:
    result = validate_and_prepare(make_image("JPEG", size=(3200, 1600)), 50 * 1024 * 1024)
    assert max(result.width, result.height) == MAX_LONG_EDGE
    assert (result.width, result.height) == (1600, 800)


def test_small_image_not_upscaled() -> None:
    result = validate_and_prepare(make_image("JPEG", size=(300, 200)), LIMIT)
    assert (result.width, result.height) == (300, 200)


def test_exif_orientation_applied() -> None:
    img = Image.new("RGB", (200, 100), (0, 128, 0))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    result = validate_and_prepare(buf.getvalue(), LIMIT)
    assert (result.width, result.height) == (100, 200)
