"""Аргументы командной строки и запуск event loop."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from people_monitor.app import run
from people_monitor.config import AppConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Уведомлять, когда очередь заполняет заданную область интереса."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="необязательный путь к env-файлу вместо .env",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="не обращаться к Telegram, а записывать уведомления в лог",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = (
        AppConfig.from_env(args.env_file)
        if args.env_file is not None
        else AppConfig.from_env()
    )
    logging.basicConfig(
        level=settings.runtime.log_level.value,
        format=settings.runtime.log_format,
    )
    asyncio.run(run(settings, dry_run=args.dry_run))
