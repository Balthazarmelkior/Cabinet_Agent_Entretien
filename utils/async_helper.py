# utils/async_helper.py
"""Safe bridge from sync to async, handles existing event loops."""
import asyncio


def run_async(coro):
    """Run an async coroutine from sync context, safely handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context (FastAPI, Jupyter, etc.)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)
