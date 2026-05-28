import asyncio
import httpx
from .modules import ALL_MODULES, SITE_NAMES


async def _run(client: httpx.AsyncClient, module, email: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        return await module(client, email)


async def hunt(email: str, modules=None, concurrency: int = 10, timeout: int = 12) -> list[dict]:
    if modules is None:
        modules = ALL_MODULES
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=5)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        limits=limits,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
    ) as client:
        tasks = [_run(client, m, email, sem) for m in modules]
        return await asyncio.gather(*tasks)


def hunt_sync(email: str, **kwargs) -> list[dict]:
    return asyncio.run(hunt(email, **kwargs))
