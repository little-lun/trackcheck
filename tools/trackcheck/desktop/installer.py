# -*- coding: utf-8 -*-
"""
installer.py —— 安装程序（打包成 trackcheck-v0.1-setup.exe）

安装包本身是个自解压 exe：里面躺着 TrackCheck.exe 和 Uninstall.exe，
运行后把它们复制到**用户选的目录**（默认 `%LOCALAPPDATA%\\Programs\\TrackCheck\\`），
再建快捷方式、写"应用和功能"里的卸载条目。

★ 全程 HKCU + 用户目录，不要管理员权限。装到别的盘/别的目录也可以 ——
  卸载程序以自身位置为准（见 winsetup.app_dir），所以改装目录后照样能卸干净。

命令行：
    trackcheck-v0.1-setup.exe              正常安装（可改目录）
    trackcheck-v0.1-setup.exe /S           静默，装默认目录
    trackcheck-v0.1-setup.exe /S /D=D:\\Tools\\TrackCheck  静默，装指定目录
"""

import os
import shutil
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import winsetup as W          # noqa: E402

SILENT = any(a.lower() == '/s' for a in sys.argv[1:])


def forced_dir():
    """`/D=路径` 或 `--dir=路径`：指定了就不弹目录选择（原样使用，不追加子目录）"""
    for a in sys.argv[1:]:
        low = a.lower()
        for pre in ('/d=', '--dir=', '-d='):
            if low.startswith(pre):
                return W.clean_dir(a[len(pre):].strip('"'))
    return None


def choose_dir():
    """
    决定装到哪。返回 None = 用户放弃安装。

        默认目录 / 自己选一个 / 取消       三种回答

    ★ 已经装过 → 默认**原地升级**（同一个目录），不需要先卸载。
    """
    old = W.installed_dir()
    default = old or W.install_dir()
    force = forced_dir()
    if force:
        return force
    if SILENT:
        return default

    if old:
        r = W.ask3('检测到已安装 %s %s：\n%s\n\n'
                   '【是】原地升级到这一版（推荐，不用先卸载）\n'
                   '【否】换一个目录装（旧的留着手动删）\n'
                   '【取消】不装了'
                   % (W.APP_TITLE, W.installed_version() or '', old))
    else:
        r = W.ask3('要把 %s v%s 装到哪里？\n\n'
                   '默认：%s\n\n'
                   '　【是】装到默认目录\n'
                   '　【否】自己选一个目录\n'
                   '　【取消】不装了'
                   % (W.APP_TITLE, W.APP_VER, default))
    if r == 'yes':
        return default
    if r != 'no':
        return None

    picked = W.pick_folder(default, '选择 %s 的安装目录' % W.APP_TITLE)
    if not picked:
        return None
    if not os.access(picked, os.W_OK):
        # 装到 Program Files 之类的位置会写不进去，早点说清楚
        if not W.ask('%s 需要管理员权限才能写。\n\n'
                     '换个目录（比如 D:\\Tools）？' % picked):
            return None
        picked = W.pick_folder(picked, '换一个安装目录')
        if not picked:
            return None
    return W.normalize_dir(picked)


def install():
    payload = W.resource(W.EXE_NAME)
    payload_un = W.resource(W.UNINST_NAME)
    if not os.path.exists(payload) or not os.path.exists(payload_un):
        return W.error('安装包不完整（缺 %s / %s）。\n请重新下载。'
                       % (W.EXE_NAME, W.UNINST_NAME))

    folder = choose_dir()
    if not folder:
        return
    exe = os.path.join(folder, W.EXE_NAME)
    uninst = os.path.join(folder, W.UNINST_NAME)

    size_mb = os.path.getsize(payload) / 1048576.0
    if os.path.exists(exe):
        oldv = W.installed_version() or '（未知）'
        if not _maybe('检测到 %s 已经装在：\n%s\n\n版本 %s → %s\n\n'
                      '要覆盖安装（原地升级）吗？\n'
                      '　· 程序文件与卸载程序会被替换\n'
                      '　· 快捷方式、"应用和功能"条目会被重建\n'
                      '　· 存档（%%APPDATA%%\\TrackCheck\\plans）不受影响'
                      % (W.APP_TITLE, folder, oldv, W.APP_VER)):
            return
    else:
        if not _maybe('即将安装 %s v%s 到：\n\n%s\n\n'
                      '文件约 %.0f MB，不需要管理员权限。\n\n继续安装？'
                      % (W.APP_TITLE, W.APP_VER, folder, size_mb)):
            return

    W.kill_running()
    os.makedirs(folder, exist_ok=True)
    shutil.copy2(payload, exe)
    shutil.copy2(payload_un, uninst)

    W.make_shortcut(W.startmenu_link(), exe, folder, exe)
    if not SILENT:
        if W.ask('要不要在桌面放一个快捷方式？'):
            W.make_shortcut(W.desktop_link(), exe, folder, exe)
        else:
            W.remove_file(W.desktop_link())

    W.write_uninstall_entry(folder, W.dir_size_kb(folder))

    if SILENT:
        return
    if W.ask('安装完成，位置：\n%s\n\n现在就启动 %s 吗？\n'
             '（会在默认浏览器里打开出怪沙盘）' % (folder, W.APP_TITLE)):
        W.launch(exe)


def _maybe(text):
    return True if SILENT else W.ask(text)


if __name__ == '__main__':
    try:
        install()
    except Exception:                                        # noqa: BLE001
        W.error('安装失败：\n\n' + traceback.format_exc(limit=8))
