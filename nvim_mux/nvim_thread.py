import os
import pynvim
from queue import SimpleQueue
from dataclasses import dataclass
from threading import Thread
from typing import Any
from pynvim import Nvim
from result import Result, Ok, Err
from concurrent import futures
import logging

_LOGGER = logging.getLogger("nvim-thread")


@dataclass
class NvimWorkItem:
    lua: str
    args: list[Any]
    future: futures.Future[Result[Any, Exception]]


@dataclass
class NvimWrapper:
    vim: Nvim
    work_items: SimpleQueue[NvimWorkItem]

    def loop_forever(self) -> None:
        while True:
            work_item = self.work_items.get()
            self.execute_work_item(work_item)

    def execute_work_item(self, work_item: NvimWorkItem) -> None:
        _LOGGER.debug(f"Executing work item {work_item}")
        result: Result[Any, Exception]
        try:
            result = Ok(self.vim.exec_lua(work_item.lua, *work_item.args))
        except Exception as nvim_error:
            result = Err(nvim_error)

        work_item.future.set_result(result)
        _LOGGER.debug(f"Set result {result}")


def _thread_loop(queue: SimpleQueue[NvimWorkItem]) -> None:
    nvim_socket = os.environ["NVIM"]
    vim = Nvim.from_session(pynvim.socket_session(str(nvim_socket)))
    NvimWrapper(vim, queue).loop_forever()


def start_thread() -> SimpleQueue[NvimWorkItem]:
    queue: SimpleQueue[NvimWorkItem] = SimpleQueue()
    thread = Thread(target=_thread_loop, args=[queue], daemon=True)
    thread.start()
    return queue
