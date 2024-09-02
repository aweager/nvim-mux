#!/usr/bin/env python3

import asyncio
import logging
import os
import pathlib
import signal
from functools import partial
from sys import argv, stderr

import jrpc
from jrpc.client import unix_factory, unix_oneoff_factory
from jrpc.client_cache import ClientManager
from mux.rpc_processor import mux_rpc_processor
from reg.api import AddLinkParams, RegLink, RegMethod
from reg.rpc_processor import reg_rpc_processor
from result import Err, Ok, Result

from .errors import NvimLuaApiError
from .ext.api import SyncRegistersDownParams
from .ext.rpc_processor import NvimExtensionApiImpl, ext_rpc_processor
from .mux.impl import NvimMuxApiImpl
from .nvim_client import connect_to_nvim
from .reg.impl import NvimRegApiImpl

_LOGGER = logging.getLogger("nvim-mux-server")


async def run_mux_server(
    socket_path: pathlib.Path,
    term_future: asyncio.Future[int],
    parent_mux_instance: str | None,
    parent_mux_location: str | None,
    parent_reg_instance: str | None,
    parent_reg_registry: str | None,
) -> Result[int, NvimLuaApiError]:
    match await connect_to_nvim():
        case Ok(vim):
            pass
        case Err() as err:
            return err

    _LOGGER.info("Connected to nvim in daemon thread")

    mux_clients = ClientManager(unix_factory)
    reg_clients = ClientManager(unix_oneoff_factory)
    mux_impl = NvimMuxApiImpl(mux_clients, parent_mux_instance, parent_mux_location, vim)
    reg_impl = NvimRegApiImpl(vim, reg_clients, str(socket_path))
    ext_impl = NvimExtensionApiImpl(
        vim=vim,
        this_instance=str(socket_path),
        parent_mux_instance=parent_mux_instance,
        parent_mux_location=parent_mux_location,
        parent_reg_instance=parent_reg_instance,
        parent_reg_registry=parent_reg_registry,
        mux_clients=mux_clients,
        reg_clients=reg_clients,
    )

    connection_callback = jrpc.connection.client_connected_callback(
        mux_rpc_processor(mux_impl),
        reg_rpc_processor(reg_impl),
        ext_rpc_processor(ext_impl),
    )

    server = await asyncio.start_unix_server(connection_callback, path=socket_path)
    try:
        async with mux_clients, reg_clients:
            # TODO less hacky way of initial publish / sync
            async with asyncio.TaskGroup() as tg:
                tg.create_task(mux_impl.publish())
                tg.create_task(ext_impl.sync_registers_down(SyncRegistersDownParams()))
                if parent_reg_instance and parent_reg_registry:
                    tg.create_task(
                        reg_clients.with_client(
                            parent_reg_instance,
                            lambda client: client.notify(
                                RegMethod.ADD_LINK,
                                AddLinkParams(
                                    registry=parent_reg_registry,
                                    link=RegLink(
                                        instance=str(socket_path),
                                        registry="0",
                                    ),
                                ),
                            ),
                        )
                    )

            _LOGGER.info("Server started")
            try:
                await term_future
            finally:
                _LOGGER.info("Server shutting down")
                server.close()

            if term_future.done():
                return Ok(term_future.result())
            return Ok(0)
    finally:
        try:
            os.unlink(socket_path)
        except Exception:
            # swallow
            pass


_TERMINATING_SIGNALS = [
    signal.SIGTERM,
    signal.SIGINT,
    signal.SIGQUIT,
    signal.SIGHUP,
]


def _handle_terminating_signals(signal: int, future: asyncio.Future[int]):
    _LOGGER.info(f"Received {signal}, closing the server")
    future.set_result(signal)


async def main(
    socket_path: pathlib.Path,
    log_file: pathlib.Path,
    parent_mux_instance: str,
    parent_mux_location: str,
    parent_reg_instance: str,
    parent_reg_registry: str,
) -> int:
    logging.basicConfig(filename=log_file, level=logging.INFO)
    term_future: asyncio.Future[int] = asyncio.Future()
    for term_signal in _TERMINATING_SIGNALS:
        asyncio.get_running_loop().add_signal_handler(
            term_signal,
            partial(_handle_terminating_signals, signal=term_signal, future=term_future),
        )

    match await run_mux_server(
        socket_path=socket_path,
        term_future=term_future,
        parent_mux_instance=parent_mux_instance or None,
        parent_mux_location=parent_mux_location or None,
        parent_reg_instance=parent_reg_instance or None,
        parent_reg_registry=parent_reg_registry or None,
    ):
        case Ok(term_value):
            _LOGGER.info(f"Exiting safely with status {term_value}")
            return term_value
        case Err(lua_error):
            stderr.write(
                f"Failed to start nvim mux server! nvim connect failed with error {lua_error}"
            )
            _LOGGER.error(
                f"Failed to start nvim mux server! nvim connect failed with error {lua_error}"
            )
            return 1


if __name__ == "__main__":
    socket = pathlib.Path(argv[1])
    log_file = pathlib.Path(argv[2])
    parent_mux_instance = argv[3]
    parent_mux_location = argv[4]
    parent_reg_instance = argv[5]
    parent_reg_registry = argv[6]

    exit(
        asyncio.run(
            main(
                socket,
                log_file,
                parent_mux_instance,
                parent_mux_location,
                parent_reg_instance,
                parent_reg_registry,
            )
        )
    )
