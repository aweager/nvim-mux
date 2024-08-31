#!/usr/bin/env python3

import asyncio
import logging
import os
import pathlib
import signal
from asyncio import Server
from functools import partial
from sys import argv, stderr

import jrpc
from jrpc.client import JsonRpcClient, JsonRpcOneoffClient, unix_factory
from mux.rpc_processor import mux_rpc_processor
from reg.api import AddLinkParams, RegLink, RegMethod
from reg.rpc_processor import reg_rpc_processor
from result import Err, Ok, Result

from nvim_mux.ext.api import SyncRegistersDownParams

from .errors import NvimLuaApiError
from .ext.rpc_processor import NvimExtensionApiImpl, ext_rpc_processor
from .mux.impl import NvimMuxApiImpl
from .nvim_client import connect_to_nvim
from .reg.impl import NvimRegApiImpl

_LOGGER = logging.getLogger("nvim-mux-server")


async def start_mux_server(
    socket_path: pathlib.Path,
    parent_mux_instance: str | None,
    parent_mux_location: str | None,
    parent_reg_instance: str | None,
    parent_reg_registry: str | None,
) -> Result[Server, NvimLuaApiError]:
    match await connect_to_nvim():
        case Ok(vim):
            pass
        case Err() as err:
            return err

    _LOGGER.info("Connected to nvim in daemon thread")

    parent_mux_client: JsonRpcClient | None = None
    if parent_mux_instance and parent_mux_location:
        reader, writer = await asyncio.open_unix_connection(parent_mux_instance)
        parent_mux_client = jrpc.client.wrap_streams(reader, writer)

    mux_impl = NvimMuxApiImpl(parent_mux_client, parent_mux_location, vim)
    reg_impl = NvimRegApiImpl(vim, unix_factory, str(socket_path))
    ext_impl = NvimExtensionApiImpl(
        vim=vim,
        this_instance=str(socket_path),
        parent_mux_client=parent_mux_client,
        parent_mux_location=parent_mux_location,
        parent_reg_instance=parent_reg_instance,
        parent_reg_registry=parent_reg_registry,
        client_factory=unix_factory,
    )

    connection_callback = jrpc.connection.client_connected_callback(
        mux_rpc_processor(mux_impl),
        reg_rpc_processor(reg_impl),
        ext_rpc_processor(ext_impl),
    )

    # TODO less hacky way of initial publish / sync
    async with asyncio.TaskGroup() as tg:
        tg.create_task(mux_impl._publish())
        tg.create_task(ext_impl.sync_registers_down(SyncRegistersDownParams()))
        if parent_reg_instance and parent_reg_registry:
            tg.create_task(
                JsonRpcOneoffClient(parent_reg_instance, unix_factory).notify(
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

    return Ok(await asyncio.start_unix_server(connection_callback, path=socket_path))


_TERMINATING_SIGNALS = [
    signal.SIGTERM,
    signal.SIGINT,
    signal.SIGQUIT,
]


def _handle_terminating_signals(server: Server):
    server.close()


async def main(
    socket_path: pathlib.Path,
    log_file: pathlib.Path,
    parent_mux_instance: str,
    parent_mux_location: str,
    parent_reg_instance: str,
    parent_reg_registry: str,
) -> int:
    logging.basicConfig(filename=log_file, level=logging.INFO)

    match await start_mux_server(
        socket_path=socket_path,
        parent_mux_instance=parent_mux_instance or None,
        parent_mux_location=parent_mux_location or None,
        parent_reg_instance=parent_reg_instance or None,
        parent_reg_registry=parent_reg_registry or None,
    ):
        case Ok(server):
            for signal in _TERMINATING_SIGNALS:
                asyncio.get_running_loop().add_signal_handler(
                    signal, partial(_handle_terminating_signals, server=server)
                )
            _LOGGER.info("Server started")
            async with server:
                try:
                    await server.serve_forever()
                finally:
                    _LOGGER.info("Server shutting down")
                    os.unlink(socket_path)
            await server.wait_closed()
            return 0
        case Err(lua_error):
            stderr.write(
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
