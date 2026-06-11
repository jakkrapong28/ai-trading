import asyncio
import logging
from typing import Set

logger = logging.getLogger("task-registry")

class TaskRegistry:
    """
    Tracks all background tasks to ensure graceful shutdown.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskRegistry, cls).__new__(cls)
            cls._instance.tasks: Set[asyncio.Task] = set()
        return cls._instance

    def register(self, coro, name: str = None) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def cancel_all(self):
        if not self.tasks:
            return
            
        logger.info(f"Cancelling {len(self.tasks)} background tasks...")
        for task in self.tasks:
            task.cancel()
            
        # Wait for all tasks to acknowledge cancellation
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("All background tasks cancelled and awaited.")

# Global singleton
registry = TaskRegistry()
