#!/usr/bin/env python3

import asyncio
import logging
import os
import pathlib
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from sys import argv, stderr

import jrpc
from jrpc.client import ClientManager
from jrpc_router.client_factory import connect_to_router
from reg.api import AddLinkParams, RegLink, RegMethod, RemoveLinkParams
from result import Err, Ok, Result

from nvim_mux.nvim_api import Empty

from .data import ParentInfo, ParentMux, ParentReg
from .errors import NvimLuaApiError
from .ext.api import SyncRegistersDownParams
from .ext.impl import NvimExtensionApiImpl
from .mux.impl import NvimMuxApiImpl
from .nvim_client import connect_to_nvim
from .reg.impl import NvimRegApiImpl

_LOGGER = logging.getLogger("nvim-mux-server")


@asynccontextmanager
async def link_to_reg_parent(
    this_instance: str,
    reg_clients: ClientManager,
    parent_reg: ParentReg | None,
) -> AsyncIterator[None]:
    if not parent_reg:
        yield
        return

    async with reg_clients.client(parent_reg.instance) as client:
        try:
            await client.notify(
                RegMethod.ADD_LINK,
                AddLinkParams(
                    registry=parent_reg.registry,
                    link=RegLink(
                        instance=this_instance,
                        registry="0",
                    ),
                ),
            )
            yield
        finally:
            await client.notify(
                RegMethod.REMOVE_LINK,
                RemoveLinkParams(
                    registry=parent_reg.registry,
                    link=RegLink(
                        instance=this_instance,
                        registry="0",
                    ),
                ),
            )


async def run_mux_server(
    socket_path: pathlib.Path,
    mux_service_name: str,
    reg_service_name: str,
    term_future: asyncio.Future[int],
    router_socket: str,
    parent_info: ParentInfo,
) -> Result[int, NvimLuaApiError]:
    match await connect_to_nvim():
        case Ok(vim):
            pass
        case Err() as err:
            return err

    _LOGGER.info("Connected to nvim in daemon thread")

    match await connect_to_router(router_socket):
        case Ok(router):
            pass
        case Err(e):
            msg = f"Failed to connect to router at {router_socket}: {e}"
            _LOGGER.error(msg)
            stderr.write(msg)
            return Ok(1)

    mux_clients = ClientManager(router.service_factory)
    reg_clients = ClientManager(router.service_oneoff_factory)

    mux_impl = NvimMuxApiImpl(
        vim=vim,
        clients=mux_clients,
        parent_mux=parent_info.parent_mux,
    )
    reg_impl = NvimRegApiImpl(
        vim=vim,
        this_instance=reg_service_name,
        clients=reg_clients,
    )
    ext_impl = NvimExtensionApiImpl(
        vim=vim,
        this_reg_instance=reg_service_name,
        mux_clients=mux_clients,
        reg_clients=reg_clients,
        parent_info=parent_info,
    )

    connection_callback = jrpc.connection.client_connected_callback(
        mux_impl.method_set(),
        reg_impl.method_set(),
        ext_impl.method_set(),
    )

    server = await asyncio.start_unix_server(connection_callback, path=socket_path)
    try:
        async with (
            router,
            mux_clients,
            reg_clients,
            router.active_service(mux_service_name, str(socket_path)),
            router.active_service(reg_service_name, str(socket_path)),
            link_to_reg_parent(reg_service_name, reg_clients, parent_info.parent_reg),
        ):
            # TODO less hacky way of initial publish / sync
            async with asyncio.TaskGroup() as tg:
                tg.create_task(mux_impl.publish())
                tg.create_task(ext_impl.sync_registers_down(SyncRegistersDownParams()))
                tg.create_task(vim.call_no_error("mark_loaded", Empty))

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
    mux_service_name: str,
    reg_service_name: str,
    log_file: pathlib.Path,
    router_socket: str,
    parent_mux_instance: str,
    parent_mux_location: str,
    parent_reg_instance: str,
    parent_reg_registry: str,
) -> int:
    logging.basicConfig(filename=log_file, level=logging.WARNING)

    term_future: asyncio.Future[int] = asyncio.Future()
    for term_signal in _TERMINATING_SIGNALS:
        asyncio.get_running_loop().add_signal_handler(
            term_signal,
            partial(_handle_terminating_signals, signal=term_signal, future=term_future),
        )

    parent_mux = (
        ParentMux(parent_mux_instance, parent_mux_location)
        if parent_mux_instance and parent_mux_location
        else None
    )
    parent_reg = (
        ParentReg(parent_reg_instance, parent_reg_registry)
        if parent_reg_instance and parent_reg_registry
        else None
    )

    match await run_mux_server(
        socket_path=socket_path,
        mux_service_name=mux_service_name,
        reg_service_name=reg_service_name,
        term_future=term_future,
        router_socket=router_socket,
        parent_info=ParentInfo(parent_mux, parent_reg),
    ):
        case Ok(term_value):
            _LOGGER.info(f"Exiting safely with status {term_value}")
            return term_value
        case Err(lua_error):
            msg = f"Failed to start nvim mux server! nvim connect failed with error {lua_error}"
            stderr.write(msg)
            _LOGGER.error(msg)
            return 1


if __name__ == "__main__":
    (
        _,
        socket,
        mux_service_name,
        reg_service_name,
        log_file,
        router_socket,
        parent_mux_instance,
        parent_mux_location,
        parent_reg_instance,
        parent_reg_registry,
    ) = argv

    exit(
        asyncio.run(
            main(
                socket_path=pathlib.Path(socket),
                mux_service_name=mux_service_name,
                reg_service_name=reg_service_name,
                log_file=pathlib.Path(log_file),
                router_socket=router_socket,
                parent_mux_instance=parent_mux_instance,
                parent_mux_location=parent_mux_location,
                parent_reg_instance=parent_reg_instance,
                parent_reg_registry=parent_reg_registry,
            )
        )
    )
