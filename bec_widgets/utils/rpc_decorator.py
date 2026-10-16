import warnings


def rpc_timeout_hint(timeout: float | None):
    """
    Decorator to set a timeout for RPC methods.
    The actual implementation of timeout handling is within the cli module. This decorator
    is solely to inform the generate-cli command about the timeout value.
    """

    def decorator(func):
        func.__rpc_timeout__ = timeout  # Store the timeout value in the function
        return func

    return decorator


def rpc_timeout(timeout: float | None):
    """
    Deprecated alias of rpc_timeout_hint, kept so plugin widgets using the old name still work.
    """
    warnings.warn(
        "bec_widgets.utils.rpc_decorator.rpc_timeout is deprecated, use rpc_timeout_hint instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return rpc_timeout_hint(timeout)
