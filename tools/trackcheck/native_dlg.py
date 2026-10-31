# -*- coding: utf-8 -*-
"""
native_dlg.py —— Windows 原生「打开 / 另存为」对话框（纯 ctypes，无第三方依赖）

为什么不用 pywebview 的 `create_file_dialog`：
  ★ 2026-10-31 实测：页面里一旦调用 `window.pywebview.api.*`，pythonnet 会在
    .NET 线程里回调 Python，**把解释器卡死**（之后连 HTTP 服务都不响应了）。
    这条桥太脆，所以改成"页面 → HTTP → Python → 原生对话框"，
    全程走已经验证过的 HTTP 通路，桌面版 / 网页版共用一套前端代码。

只依赖 comdlg32 的 GetOpenFileNameW / GetSaveFileNameW，任何 Windows 都有。
"""

import ctypes
import os
from ctypes import wintypes as W

OFN_OVERWRITEPROMPT = 0x00000002
OFN_HIDEREADONLY = 0x00000004
OFN_PATHMUSTEXIST = 0x00000800
OFN_FILEMUSTEXIST = 0x00001000
OFN_NOCHANGEDIR = 0x00000008

MAX_PATH = 32768


class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ('lStructSize', W.DWORD), ('hwndOwner', W.HWND),
        ('hInstance', W.HINSTANCE), ('lpstrFilter', W.LPCWSTR),
        ('lpstrCustomFilter', W.LPWSTR), ('nMaxCustFilter', W.DWORD),
        ('nFilterIndex', W.DWORD), ('lpstrFile', W.LPWSTR),
        ('nMaxFile', W.DWORD), ('lpstrFileTitle', W.LPWSTR),
        ('nMaxFileTitle', W.DWORD), ('lpstrInitialDir', W.LPCWSTR),
        ('lpstrTitle', W.LPCWSTR), ('Flags', W.DWORD),
        ('nFileOffset', W.WORD), ('nFileExtension', W.WORD),
        ('lpstrDefExt', W.LPCWSTR), ('lCustData', W.LPARAM),
        ('lpfnHook', ctypes.c_void_p), ('lpTemplateName', W.LPCWSTR),
        ('pvReserved', ctypes.c_void_p), ('dwReserved', W.DWORD),
        ('FlagsEx', W.DWORD),
    ]


def _filter(pairs):
    """[('文本/JSON', '*.json;*.txt'), ('所有文件', '*.*')] → 双 \\0 结尾的过滤器串"""
    out = []
    for label, pat in pairs:
        out.append('%s\0%s' % (label, pat))
    return '\0'.join(out) + '\0\0'


def _owner():
    """找一个可见的顶层窗口当 owner，让对话框居中在应用窗口上"""
    try:
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        if hwnd:
            return hwnd
    except Exception:                                        # noqa: BLE001
        pass
    return None


def open_file(initial_dir=None, title='打开',
              types=(('文本/JSON', '*.json;*.txt'), ('所有文件', '*.*'))):
    """弹「打开」→ 返回 (路径, 文本)；用户取消返回 (None, None)"""
    buf = ctypes.create_unicode_buffer(MAX_PATH)
    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    ofn.hwndOwner = _owner()
    ofn.lpstrFilter = _filter(types)
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.cast(buf, ctypes.c_wchar_p)
    ofn.nMaxFile = MAX_PATH
    ofn.lpstrInitialDir = initial_dir
    ofn.lpstrTitle = title
    ofn.Flags = (OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR
                 | OFN_HIDEREADONLY)
    if not ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
        return None, None
    path = buf.value
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return path, f.read()
    except OSError:
        return path, None


def save_file(name, initial_dir=None, title='另存为',
              types=(('文本/JSON', '*.json;*.txt'), ('所有文件', '*.*')),
              default_ext='json'):
    """弹「另存为」→ 返回路径；取消返回 None"""
    buf = ctypes.create_unicode_buffer(MAX_PATH)
    buf.value = name or 'trackcheck.json'
    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    ofn.hwndOwner = _owner()
    ofn.lpstrFilter = _filter(types)
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.cast(buf, ctypes.c_wchar_p)
    ofn.nMaxFile = MAX_PATH
    ofn.lpstrInitialDir = initial_dir
    ofn.lpstrTitle = title
    ofn.lpstrDefExt = default_ext
    ofn.Flags = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR
    if not ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn)):
        return None
    return buf.value


def write_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text or '')
    return path


def write_bytes(path, data):
    with open(path, 'wb') as f:
        f.write(data)
    return path


def open_folder(path):
    try:
        os.startfile(path)                                  # noqa: S606
        return True
    except OSError:
        return False
