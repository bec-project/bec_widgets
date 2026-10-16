def rpc_timeout(timeout: float | None):
    """
    Decorator to set a timeout for RPC methods.
    The actual implementation of timeout handling is within the cli module. This decorator
    is solely to inform the generate-cli command about the timeout value.
    """

    def decorator(func):
        func.__rpc_timeout__ = timeout  # Store the timeout value in the function
        return func

    return decorator
