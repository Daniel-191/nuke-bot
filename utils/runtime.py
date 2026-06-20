import asyncio


# Tracks long-running background tasks so they can be cancelled.
active_tasks: dict[str, asyncio.Task] = {}
