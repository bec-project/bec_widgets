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
