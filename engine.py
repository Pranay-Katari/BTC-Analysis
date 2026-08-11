from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path

from .models import Analytics, LiveEvent


class AnalyticsProcess:
    def __init__(self, executable: Path):
        self.executable = executable
        self.process: asyncio.subprocess.Process | None = None
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        if not self.executable.exists():
            raise FileNotFoundError(
                f"C++ engine not found at {self.executable}; run cmake --build build"
            )
        await self._spawn()

    async def _spawn(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            str(self.executable),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def _exchange(self, payload: bytes) -> bytes:
        for attempt in range(2):
            process = self.process
            if process is None or process.returncode is not None:
                await self._spawn()
                process = self.process
            assert process and process.stdin and process.stdout
            try:
                process.stdin.write(payload)
                await process.stdin.drain()
                response = await process.stdout.readline()
                if response:
                    return response
            except (BrokenPipeError, ConnectionResetError, RuntimeError):
                pass
            await self._stop(process)
            self.process = None
            if attempt == 1:
                break
        raise RuntimeError("C++ analytics process did not return a response")

    async def analyze(self, event: LiveEvent) -> Analytics:
        async with self.lock:
            return Analytics.from_csv((await self._exchange(event.engine_line().encode())).decode())

    async def reset(self) -> None:
        async with self.lock:
            response = await self._exchange(b"reset\n")
            if response != b"reset\n":
                raise RuntimeError("C++ engine reset failed")

    async def close(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        await self._stop(process)

    async def _stop(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.terminate()
        await process.wait()
