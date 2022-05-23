def serverClassFactory(serverIface):
    from .api import ReloadApi
    return ReloadApi(serverIface)
