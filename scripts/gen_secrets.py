#!/usr/bin/env python3
"""Генерирует секреты Clima и записывает их в .env.

Создаёт пару VAPID-ключей для Web Push, токен внутреннего планировщика и пароль PostgreSQL.
Уже заполненные значения не трогает (без --force). Запуск: `uv run python scripts/gen_secrets.py`
"""

import argparse
import base64
import secrets
import shutil
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def vapid_keypair() -> tuple[str, str]:
    """Возвращает (приватный, публичный) ключи в формате base64url, который принимает pywebpush."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64url(private), b64url(public)


def fill_env(path: Path, values: dict[str, str], force: bool) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    written: list[str] = []
    for index, line in enumerate(lines):
        key, sep, current = line.partition("=")
        if sep and key in values and (force or not current.strip()):
            lines[index] = f"{key}={values[key]}"
            written.append(key)
    missing = [key for key in values if key not in {line.partition("=")[0] for line in lines}]
    for key in missing:
        lines.append(f"{key}={values[key]}")
        written.append(key)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env", type=Path)
    parser.add_argument("--force", action="store_true", help="перезаписать уже заданные значения")
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="только вывести значения, файл не менять")
    args = parser.parse_args()

    private, public = vapid_keypair()
    values = {
        "CLIMA_VAPID_PRIVATE_KEY": private,
        "CLIMA_VAPID_PUBLIC_KEY": public,
        "CLIMA_SCHEDULER_TOKEN": secrets.token_urlsafe(32),
        # token_urlsafe даёт только A-Za-z0-9-_, поэтому пароль безопасно вставлять в URL подключения.
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    }
    if args.print_only:
        for key, value in values.items():
            print(f"{key}={value}")
        return 0

    if not args.env_file.exists():
        example = Path(".env.example")
        if not example.exists():
            print("Не найден ни .env, ни .env.example", file=sys.stderr)
            return 1
        shutil.copyfile(example, args.env_file)
    if args.force and any(
        line.startswith("POSTGRES_PASSWORD=") and line.partition("=")[2].strip()
        for line in args.env_file.read_text(encoding="utf-8").splitlines()
    ):
        # Пароль роли уже записан в том postgres при первом запуске: смена значения в .env
        # без смены пароля в самой базе лишила бы backend доступа. Поэтому --force его не трогает.
        del values["POSTGRES_PASSWORD"]
    written = fill_env(args.env_file, values, args.force)
    if written:
        print(f"{args.env_file}: записано {', '.join(written)}")
    else:
        print(f"{args.env_file}: все секреты уже заданы (используйте --force, чтобы заменить)")
    print("Важно: пересоздание VAPID-ключей отключает уже оформленные push-подписки.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
