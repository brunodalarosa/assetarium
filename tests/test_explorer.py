"""Explorer actions resolve exact original locations, including punctuation and Unicode."""
import os

import pytest

from local_asset_library import desktop, windows_shell


@pytest.mark.skipif(os.name != 'nt', reason='Windows Shell integration')
def test_folders_open_inside_and_files_are_selected(tmp_path, monkeypatch):
    folder = tmp_path / 'Holiday Kit, café (1)'
    folder.mkdir()
    file = folder / 'bench, été.obj'
    file.write_text('v 0 0 0')
    opened, selected = [], []
    monkeypatch.setattr(os, 'startfile', opened.append)
    monkeypatch.setattr(windows_shell, 'select_file', selected.append)
    desktop.show_in_explorer(folder)
    desktop.show_in_explorer(file)
    assert opened == [str(folder)]
    assert selected == [str(file)]
    with pytest.raises(FileNotFoundError):
        desktop.show_in_explorer(folder / 'gone.obj')
    assert len(opened) == len(selected) == 1


@pytest.mark.skipif(os.name != 'nt', reason='Windows Shell integration')
def test_native_shell_resolves_exact_unicode_file_and_reports_errors(tmp_path, monkeypatch):
    import ctypes
    target = tmp_path / 'Café, Holiday Kit (1).obj'
    target.write_text('v 0 0 0')
    native_loader = ctypes.WinDLL
    shell, ole = native_loader('shell32'), native_loader('ole32')
    shell.SHGetNameFromIDList.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetNameFromIDList.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    selected = []
    def select(item, count, children, flags):
        path = ctypes.c_void_p()
        assert shell.SHGetNameFromIDList(item, 0x80058000, ctypes.byref(path)) >= 0
        try:
            selected.append(ctypes.wstring_at(path))
        finally:
            ole.CoTaskMemFree(path)
        return 0
    class Shell:
        SHParseDisplayName = shell.SHParseDisplayName
        SHOpenFolderAndSelectItems = staticmethod(select)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda name, **kw: Shell() if name == 'shell32' else native_loader(name, **kw))
    windows_shell.select_file(str(target))
    assert selected == [str(target)]
    Shell.SHOpenFolderAndSelectItems = staticmethod(lambda *args: -2147467259)
    with pytest.raises(OSError, match='Windows could not show this file'):
        windows_shell.select_file(str(target))
