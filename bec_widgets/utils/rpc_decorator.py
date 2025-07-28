def rpc_public(func):
    func.rpc_public = True  # Mark the function for later processing by the class decorator
    return func


def register_rpc_methods(cls):
    """
    Class decorator to scan for rpc_public methods and add them to USER_ACCESS.
    """
    if not hasattr(cls, "USER_ACCESS"):
        cls.USER_ACCESS = set()
    for name, method in cls.__dict__.items():
        if getattr(method, "rpc_public", False):
            cls.USER_ACCESS.add(name)
    return cls


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
