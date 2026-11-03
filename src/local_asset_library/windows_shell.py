"""Select a file through the Windows Shell without Explorer command-line parsing."""


def select_file(path):
    import ctypes
    from ctypes import wintypes

    shell = ctypes.WinDLL('shell32', use_last_error=True)
    ole = ctypes.WinDLL('ole32', use_last_error=True)
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    shell.SHParseDisplayName.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD, ctypes.c_void_p]
    shell.SHParseDisplayName.restype = ctypes.c_long
    shell.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD]
    shell.SHOpenFolderAndSelectItems.restype = ctypes.c_long

    def checked(result):
        if result < 0:
            raise OSError(f'Windows could not show this file in Explorer (0x{result & 0xffffffff:08X}): {path}')

    initialized = ole.CoInitializeEx(None, 2)
    # An existing COM apartment is usable too; only balance initialization we own.
    if initialized != -2147417850:  # RPC_E_CHANGED_MODE
        checked(initialized)
    item = ctypes.c_void_p()
    try:
        checked(shell.SHParseDisplayName(path, None, ctypes.byref(item), 0, None))
        checked(shell.SHOpenFolderAndSelectItems(item, 0, None, 0))
    finally:
        if item.value:
            ole.CoTaskMemFree(item)
        if initialized >= 0:
            ole.CoUninitialize()
