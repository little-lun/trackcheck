# -*- coding: utf-8 -*-
"""
winsetup.py —— 安装/卸载共用的 Windows 小工具

不引第三方库：弹窗用 ctypes 调 MessageBoxW，快捷方式用 PowerShell 的
WScript.Shell，卸载信息写 HKCU 的 Uninstall 键（所以**不需要管理员权限**，
也不会污染系统目录）。
"""

import ctypes
import os
import subprocess
import sys
import time
import urllib.request

APP_NAME = 'TrackCheck'
APP_TITLE = 'TrackCheck'
APP_VER = '0.2.3'
PUBLISHER = 'PVZ 生存无尽研究 · trackcheck'
EXE_NAME = 'TrackCheck.exe'
UNINST_NAME = 'Uninstall.exe'
URL = 'http://127.0.0.1:8765/'
REG_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\TrackCheck'

_NO_WINDOW = 0x08000000          # CREATE_NO_WINDOW


# ------------------------------------------------------------------ 弹窗
def info(text, title='%s %s' % (APP_TITLE, APP_VER)):
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)


def error(text, title='%s 安装程序' % APP_TITLE):
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)


def ask(text, title='%s %s' % (APP_TITLE, APP_VER)):
    """是 / 否"""
    return ctypes.windll.user32.MessageBoxW(None, text, title, 0x04 | 0x40) == 6


def ask3(text, title='%s %s' % (APP_TITLE, APP_VER)):
    """是 / 否 / 取消 → 'yes' / 'no' / 'cancel'（右上角 × 也算取消）"""
    r = ctypes.windll.user32.MessageBoxW(None, text, title, 0x03 | 0x40)
    return {6: 'yes', 7: 'no'}.get(r, 'cancel')


def pick_folder(initial=None, title='选择安装目录'):
    """
    Windows 原生"浏览文件夹"对话框（ctypes 调 shell32，不引第三方库）。

    用户取消 / 直接关窗 → 返回 None。
    ★ 一定要先 OleInitialize：SHBrowseForFolder 的新式界面要用 COM 单线程套间，
      否则弹出来的会是那种又老又小的树状框，或者干脆不响应。
    """
    import ctypes.wintypes as wt

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [('hwndOwner', wt.HWND), ('pidlRoot', ctypes.c_void_p),
                    ('pszDisplayName', ctypes.c_void_p),
                    ('lpszTitle', ctypes.c_void_p),
                    ('ulFlags', wt.UINT), ('lpfn', ctypes.c_void_p),
                    ('lParam', wt.LPARAM), ('iImage', ctypes.c_int)]

    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    try:
        ole32.OleInitialize(None)
    except Exception:                                        # noqa: BLE001
        pass

    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    shell32.SHParseDisplayName.argtypes = [wt.LPCWSTR, ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_void_p),
                                           wt.ULONG, ctypes.POINTER(wt.ULONG)]
    shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BROWSEINFO)]
    shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wt.LPWSTR]
    shell32.SHGetPathFromIDListW.restype = wt.BOOL

    root = ctypes.c_void_p()
    start = initial
    # ★ SHParseDisplayName 只认**已存在**的路径；默认安装目录通常还没建，
    #   所以要往上找一个存在的祖先，否则对话框会莫名其妙地开在"桌面/此电脑"。
    while start and not os.path.isdir(start):
        parent = os.path.dirname(start)
        if parent == start:
            start = None
            break
        start = parent
    if start:
        try:
            shell32.SHParseDisplayName(start, None, ctypes.byref(root), 0, None)
        except Exception:                                    # noqa: BLE001
            root = ctypes.c_void_p()

    shown = ctypes.create_unicode_buffer(260)
    title_p = ctypes.c_wchar_p(title)      # ★ 必须留引用，否则指针会被回收
    bi = BROWSEINFO()
    bi.hwndOwner = None
    bi.pidlRoot = root
    bi.pszDisplayName = ctypes.cast(shown, ctypes.c_void_p)
    bi.lpszTitle = ctypes.cast(title_p, ctypes.c_void_p)
    # RETURNONLYFSDIRS | EDITBOX | NEWDIALOGSTYLE（新式界面 + 可以直接粘贴/新建路径）
    bi.ulFlags = 0x0001 | 0x0010 | 0x0040
    bi.lpfn = None
    bi.lParam = 0
    bi.iImage = 0

    out = None
    pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))
    if pidl:
        buf = ctypes.create_unicode_buffer(1024)
        if shell32.SHGetPathFromIDListW(pidl, buf):
            out = buf.value
        ole32.CoTaskMemFree(ctypes.c_void_p(pidl))
    if root:
        ole32.CoTaskMemFree(root)
    return out


# ------------------------------------------------------------------ 路径
def install_dir():
    """默认安装目录（用户没改目录时用它）"""
    return os.path.join(os.environ.get('LOCALAPPDATA') or
                        os.path.expanduser('~'), 'Programs', APP_NAME)


def installed_dir():
    """
    已经装在哪（读 HKCU 卸载条目）。

    ★ 覆盖升级要用它当默认值：用户当初把程序装到 D:\\Tools\\TrackCheck，
      再双击新版 setup 时应该**升级到同一个目录**，而不是又装一份到默认位置。
    """
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            v, _ = winreg.QueryValueEx(k, 'InstallLocation')
            return v if v and os.path.isdir(v) else None
    except Exception:                                        # noqa: BLE001
        return None


def installed_version():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            v, _ = winreg.QueryValueEx(k, 'DisplayVersion')
            return v
    except Exception:                                        # noqa: BLE001
        return None


def app_dir():
    """
    已经装好的程序自己在哪个目录。

    ★ 用户可能改装到 D:\\Tools\\TrackCheck，卸载程序就在那个目录里 ——
      所以**以自身位置为准**，不能写死默认目录。
      开发态（没打包）才退回默认目录。
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return install_dir()


def clean_dir(path):
    """只做规范化（展开 ~ 与环境变量），不改路径本身 —— 给命令行 /D= 用"""
    return os.path.normpath(os.path.expandvars(os.path.expanduser(path or '')))


def normalize_dir(path):
    """
    把用户选的目录规整成"程序目录"：选了 D:\\Tools 就装到 D:\\Tools\\TrackCheck；
    选的就是 …\\TrackCheck 则原样用。
    """
    path = os.path.normpath(os.path.expandvars(os.path.expanduser(path or '')))
    if os.path.basename(path).lower() != APP_NAME.lower():
        path = os.path.join(path, APP_NAME)
    return path


def startmenu_link():
    return os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows',
                        'Start Menu', 'Programs', '%s.lnk' % APP_TITLE)


def desktop_link():
    return os.path.join(os.path.expanduser('~'), 'Desktop', '%s.lnk' % APP_TITLE)


def resource(name):
    """安装包内被打包进去的文件（开发态下就是同目录）"""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ------------------------------------------------------------------ 执行
def run_hidden(cmd):
    try:
        subprocess.run(cmd, creationflags=_NO_WINDOW, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:                                        # noqa: BLE001
        pass


def ps(script):
    run_hidden(['powershell', '-NoProfile', '-NonInteractive',
                '-WindowStyle', 'Hidden', '-Command', script])


def make_shortcut(link, target, workdir=None, icon=None):
    os.makedirs(os.path.dirname(link), exist_ok=True)
    parts = ['$s=(New-Object -ComObject WScript.Shell).CreateShortcut("%s");'
             % link,
             '$s.TargetPath="%s";' % target,
             '$s.IconLocation="%s";' % (icon or target)]
    if workdir:
        parts.append('$s.WorkingDirectory="%s";' % workdir)
    parts.append('$s.Save()')
    ps(''.join(parts))


def remove_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:                                        # noqa: BLE001
        pass


def kill_running():
    """先请它自己体面退出，再兜底强杀（安装/卸载都要先关掉，不然文件被占）"""
    try:
        urllib.request.urlopen(URL + 'api/quit', timeout=2).read()
        time.sleep(1.2)
    except Exception:                                        # noqa: BLE001
        pass
    run_hidden(['taskkill', '/F', '/IM', EXE_NAME, '/T'])


def launch(target):
    try:
        subprocess.Popen([target], cwd=os.path.dirname(target),
                         creationflags=_NO_WINDOW | 0x00000008,
                         close_fds=True)
    except Exception:                                        # noqa: BLE001
        os.startfile(target)                                 # noqa: S606


# ------------------------------------------------------------------ 注册表
def write_uninstall_entry(folder, size_kb):
    import winreg
    exe = os.path.join(folder, EXE_NAME)
    un = os.path.join(folder, UNINST_NAME)
    vals = [
        ('DisplayName', '%s v%s' % (APP_TITLE, APP_VER)),
        ('DisplayVersion', APP_VER),
        ('Publisher', PUBLISHER),
        ('DisplayIcon', exe),
        ('InstallLocation', folder),
        ('UninstallString', '"%s"' % un),
        ('QuietUninstallString', '"%s" /quiet' % un),
        ('InstallDate', time.strftime('%Y%m%d')),
    ]
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                            winreg.KEY_WRITE) as k:
        for name, val in vals:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, 'EstimatedSize', 0, winreg.REG_DWORD, int(size_kb))
        winreg.SetValueEx(k, 'NoModify', 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, 'NoRepair', 0, winreg.REG_DWORD, 1)


def remove_uninstall_entry():
    import winreg
    for root in (winreg.HKEY_CURRENT_USER,):
        try:
            winreg.DeleteKey(root, REG_KEY)
        except Exception:                                    # noqa: BLE001
            pass


def dir_size_kb(path):
    total = 0
    for base, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return max(1, total // 1024)
