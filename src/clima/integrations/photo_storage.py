"""Private local photo storage with user-scoped paths."""

from pathlib import Path
import secrets
import struct
import zlib

from clima.errors import NotFoundError, ValidationError


class PhotoStorage:
    MAX_PHOTO_BYTES = 5 * 1024 * 1024
    _image_types = (
        (b"\x89PNG\r\n\x1a\n", ".png"),
        (b"\xff\xd8\xff", ".jpg"),
        (b"GIF87a", ".gif"),
        (b"GIF89a", ".gif"),
    )

    def __init__(self, rootPath: str | Path = "uploads"):
        self.rootPath = Path(rootPath).expanduser().resolve()
        self.rootPath.mkdir(parents=True, exist_ok=True)

    def save(self, userId: int, photo: bytes) -> str:
        if not photo:
            raise ValidationError("Фото не должно быть пустым")
        if len(photo) > self.MAX_PHOTO_BYTES:
            raise ValidationError("Размер фотографии не должен превышать 5 МБ")
        suffix = self._imageSuffix(photo)
        user_dir = (self.rootPath / str(userId)).resolve()
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{secrets.token_hex(16)}{suffix}"
        path.write_bytes(photo)
        return path.relative_to(self.rootPath).as_posix()

    def delete(self, path: str) -> None:
        resolved = self._resolve(path)
        if not resolved.is_relative_to(self.rootPath):
            raise ValidationError("Некорректный путь к фотографии")
        resolved.unlink(missing_ok=True)

    def read(self, path: str) -> bytes:
        resolved = self._resolve(path)
        try:
            return resolved.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError("Фото не найдено") from error

    def belongsTo(self, userId: int, path: str) -> bool:
        resolved = self._resolve(path)
        user_root = (self.rootPath / str(userId)).resolve()
        return resolved.is_relative_to(user_root) and resolved.is_file()

    def deleteAllByUser(self, userId: int) -> None:
        user_dir = (self.rootPath / str(userId)).resolve()
        if user_dir.is_relative_to(self.rootPath) and user_dir.is_dir():
            for path in user_dir.iterdir():
                if path.is_file():
                    path.unlink()
            user_dir.rmdir()

    def _resolve(self, path: str) -> Path:
        candidate = Path(path)
        resolved = (candidate if candidate.is_absolute() else self.rootPath / candidate).resolve()
        if not resolved.is_relative_to(self.rootPath):
            raise ValidationError("Некорректный путь к фотографии")
        return resolved

    @classmethod
    def _imageSuffix(cls, photo: bytes) -> str:
        if photo.startswith(b"\x89PNG\r\n\x1a\n") and cls._validPng(photo):
            return ".png"
        if photo.startswith(b"\xff\xd8") and cls._validJpeg(photo):
            return ".jpg"
        if photo.startswith((b"GIF87a", b"GIF89a")) and cls._validGif(photo):
            return ".gif"
        if cls._validWebp(photo):
            return ".webp"
        raise ValidationError("Поддерживаются только PNG, JPEG, GIF и WebP изображения")

    @staticmethod
    def _validPng(photo: bytes) -> bool:
        offset = 8
        seen_header = seen_data = seen_end = False
        compressed = bytearray()
        while offset + 12 <= len(photo):
            length = struct.unpack(">I", photo[offset:offset + 4])[0]
            end = offset + 12 + length
            if length > 32 * 1024 * 1024 or end > len(photo):
                return False
            chunk_type = photo[offset + 4:offset + 8]
            chunk_data = photo[offset + 8:offset + 8 + length]
            expected_crc = struct.unpack(">I", photo[offset + 8 + length:end])[0]
            if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
                return False
            if chunk_type == b"IHDR":
                if seen_header or offset != 8 or length != 13:
                    return False
                width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
                if not width or not height or width > 20_000 or height > 20_000:
                    return False
                if bit_depth not in (1, 2, 4, 8, 16) or color_type not in (0, 2, 3, 4, 6):
                    return False
                seen_header = True
            elif chunk_type == b"IDAT":
                if not seen_header or seen_end:
                    return False
                seen_data = True
                compressed.extend(chunk_data)
            elif chunk_type == b"IEND":
                if length or not seen_data:
                    return False
                seen_end = True
                offset = end
                break
            elif not seen_header:
                return False
            offset = end
        if not seen_end or offset != len(photo):
            return False
        try:
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(compressed, 64 * 1024 * 1024)
            return decoder.eof and not decoder.unused_data and bool(decoded)
        except zlib.error:
            return False

    @staticmethod
    def _validJpeg(photo: bytes) -> bool:
        if len(photo) < 12 or not photo.endswith(b"\xff\xd9"):
            return False
        offset = 2
        has_frame = False
        while offset < len(photo) - 2:
            if photo[offset] != 0xFF:
                return False
            while offset < len(photo) and photo[offset] == 0xFF:
                offset += 1
            if offset >= len(photo):
                return False
            marker = photo[offset]
            offset += 1
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
                continue
            if offset + 2 > len(photo):
                return False
            length = struct.unpack(">H", photo[offset:offset + 2])[0]
            if length < 2 or offset + length > len(photo):
                return False
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
                if length < 8:
                    return False
                height, width = struct.unpack(">HH", photo[offset + 3:offset + 7])
                has_frame = width > 0 and height > 0
            if marker == 0xDA:
                return has_frame and photo.find(b"\xff\xd9", offset + length) == len(photo) - 2
            offset += length
        return False

    @staticmethod
    def _validGif(photo: bytes) -> bool:
        if len(photo) < 14 or photo[-1] != 0x3B:
            return False
        width, height = struct.unpack("<HH", photo[6:10])
        return width > 0 and height > 0 and b"\x2c" in photo[10:-1]

    @staticmethod
    def _validWebp(photo: bytes) -> bool:
        if len(photo) < 30 or photo[:4] != b"RIFF" or photo[8:12] != b"WEBP":
            return False
        declared_size = struct.unpack("<I", photo[4:8])[0] + 8
        if declared_size != len(photo):
            return False
        chunk = photo[12:16]
        chunk_size = struct.unpack("<I", photo[16:20])[0]
        return chunk in (b"VP8 ", b"VP8L", b"VP8X") and 20 + chunk_size <= len(photo)
