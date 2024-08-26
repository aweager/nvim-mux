#!/usr/bin/env python3

import asyncio
import logging
import pathlib
from asyncio import Server
from sys import argv, stderr
from typing import assert_never

import jrpc
from jrpc.client import JsonRpcClient
from mux.rpc_processor import mux_rpc_processor
from result import Err, Ok, Result

from .errors import NvimLuaApiError
from .extension_rpc_processor import ext_rpc_processor
from .nvim_client import connect_to_nvim
from .nvim_model import NvimMuxApiImpl

_LOGGER = logging.getLogger("nvim-mux-server")


async def start_mux_server(
    socket_path: pathlib.Path,
    parent_mux_instance: str | None,
    parent_mux_location: str | None,
) -> Result[Server, NvimLuaApiError]:
    match await connect_to_nvim():
        case Ok(client):
            pass
        case Err() as err:
            return err

    _LOGGER.info("Connected to nvim in daemon thread")

    parent_mux_client: JsonRpcClient | None = None
    if parent_mux_instance and parent_mux_location:
        reader, writer = await asyncio.open_unix_connection(parent_mux_instance)
        parent_mux_client = jrpc.client.wrap_streams(reader, writer)

    impl = NvimMuxApiImpl(parent_mux_client, parent_mux_location, client)
    connection_callback = jrpc.connection.client_connected_callback(
        mux_rpc_processor(impl),
        ext_rpc_processor(impl),
    )

    # TODO less hacky way of initial publish
    await impl._publish()
    return Ok(await asyncio.start_unix_server(connection_callback, path=socket_path))


async def main(
    socket_path: pathlib.Path,
    log_file: pathlib.Path,
    parent_mux_instance: str | None,
    parent_mux_location: str | None,
) -> int:
    logging.basicConfig(filename=log_file, level=logging.DEBUG)

    server_result = await start_mux_server(socket_path, parent_mux_instance, parent_mux_location)
    match server_result:
        case Ok(server):
            _LOGGER.info("Server started")
            await server.wait_closed()
            return 0
        case Err(lua_error):
            stderr.write(
                f"Failed to start nvim mux server! nvim connect failed with error {lua_error}"
            )
            return 1
        case _:
            assert_never(server_result)


if __name__ == "__main__":
    socket = pathlib.Path(argv[1])
    log_file = pathlib.Path(argv[2])
    parent_mux_instance: str | None = None
    parent_mux_location: str | None = None
    if len(argv) >= 5:
        parent_mux_instance = argv[3]
        parent_mux_location = argv[4]

    exit(asyncio.run(main(socket, log_file, parent_mux_instance, parent_mux_location)))
