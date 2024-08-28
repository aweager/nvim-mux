from jrpc.service import JsonRpcProcessor, MethodSet, TypedMethodHandler

from nvim_mux.mux.impl import NvimMuxApiImpl

from .api import NvimExtensionMethod


def ext_rpc_processor(mux_impl: NvimMuxApiImpl) -> JsonRpcProcessor:
    handlers: list[TypedMethodHandler] = [
        TypedMethodHandler(NvimExtensionMethod.PUBLISH_TO_PARENT, mux_impl.publish_to_parent),
    ]
    return MethodSet({m.descriptor.name: m for m in handlers})
