# -*- coding: utf-8 -*-
"""
build_win.py —— 打 Windows 版：主程序 exe + 安装程序 exe（内含卸载程序）

产物（都在 tools/trackcheck/dist/）：

    TrackCheck.exe              主程序（双击 → 起本地服务 → 打开浏览器）
    Uninstall.exe               卸载程序（安装时一起放进安装目录）
    trackcheck-v<版本>-setup.exe 安装程序（自解压：上面两个 exe 都在里面）

为什么"安装程序"是自己写的而不是 Inno Setup：
这台机器装不上 Inno Setup，而我们的需求很窄 —— 复制两个文件、建快捷方式、
写 HKCU 的卸载条目。用 PyInstaller 打一个自解压 exe 就够了，还不用管理员权限。
（`desktop/inno/trackcheck.iss` 里另留了一份 Inno Setup 脚本，将来想用正规
安装包时可以直接编译。）

用法：
    python -m tools.trackcheck.build_win              # 全打
    python -m tools.trackcheck.build_win --only app   # 只打主程序
"""

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESK = os.path.join(ROOT, 'tools', 'trackcheck', 'desktop')
DIST = os.path.join(ROOT, 'tools', 'trackcheck', 'dist')
WORK = os.path.join(ROOT, 'tools', 'trackcheck', 'build')
APP_VER = '0.2.30'
APP_PKG = '0.2'          # 文件名只到 0.x（0.x.n 是同一发布里的改动计数）
ICON = os.path.join(DESK, 'trackcheck.ico')
VERFILE = os.path.join(DESK, 'version_info.txt')

VERSION_TXT = '''VSVersionInfo(
  ffi=FixedFileInfo(filevers=%(ver_tuple)s, prodvers=%(ver_tuple)s,
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080404B0', [
      StringStruct('CompanyName', 'PVZ Endless Research'),
      StringStruct('FileDescription', 'TrackCheck - PVZ spawn simulator'),
      StringStruct('FileVersion', '%(ver4)s'),
      StringStruct('InternalName', 'TrackCheck'),
      StringStruct('OriginalFilename', 'TrackCheck.exe'),
      StringStruct('ProductName', 'TrackCheck'),
      StringStruct('ProductVersion', '%(ver)s')])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
'''


def version_txt():
    """版本资源跟 APP_VER 单点对齐 —— 以前写死过 0.1，升级时忘了改"""
    parts = [int(x) for x in APP_VER.split('.')] + [0, 0, 0, 0]
    v4 = '.'.join(str(x) for x in parts[:4])
    return VERSION_TXT % {'ver': APP_VER, 'ver4': v4,
                          'ver_tuple': '(%d, %d, %d, %d)' % tuple(parts[:4])}


# ------------------------------------------------------------------ 图标
def make_icon():
    """一个"沙盘格子"图标：深底 + 一排绿格子 + 一个橙色（冰车）格子"""
    if os.path.exists(ICON):
        return ICON
    from PIL import Image, ImageDraw
    S = 256
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, S - 8, S - 8], radius=44, fill=(15, 23, 42, 255))
    cols = [(74, 222, 128), (34, 197, 94), (22, 163, 74),
            (21, 128, 61), (249, 115, 22), (16, 185, 129)]
    x0, y0, cell, gap = 40, 74, 52, 12
    for i in range(3):
        for j in range(2):
            x = x0 + i * (cell + gap)
            y = y0 + j * (cell + gap)
            d.rounded_rectangle([x, y, x + cell, y + cell], radius=12,
                                fill=cols[(i * 2 + j) % len(cols)] + (255,))
    d.line([40, 190, S - 40, 190], fill=(148, 163, 184, 255), width=6)
    d.line([40, 190, 40 + 120, 190], fill=(59, 130, 246, 255), width=6)
    im.save(ICON, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    return ICON


# ------------------------------------------------------------------ PyInstaller
def pyi(script, name, add=(), hidden=(), extra=()):
    """跑一次 PyInstaller；add: [(源, 目标目录)]"""
    os.makedirs(DIST, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
           '--onefile', '--windowed',
           '--name', name,
           '--icon', make_icon(),
           '--paths', ROOT,
           '--paths', DESK,
           '--distpath', DIST,
           '--workpath', os.path.join(WORK, 'pyi'),
           '--specpath', WORK]
    if os.path.exists(VERFILE):
        cmd += ['--version-file', VERFILE]
    for h in hidden:
        cmd += ['--hidden-import', h]
    for src, dst in add:
        cmd += ['--add-data', '%s%s%s' % (src, os.pathsep, dst)]
    cmd += list(extra)
    cmd.append(script)
    print('  $', ' '.join(cmd[-6:]), flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    out = os.path.join(DIST, name + '.exe')
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError('PyInstaller 打包 %s 失败（退出码 %s）' % (name, r.returncode))
    return out


def build_app():
    print('① 主程序 TrackCheck.exe …', flush=True)
    out = pyi(os.path.join(DESK, 'launcher.py'), 'TrackCheck',
              hidden=['tools.trackcheck.app', 'tools.trackcheck.jobs',
                      'tools.trackcheck.ui', 'tools.trackcheck.webbridge',
                      'tools.trackcheck.plan', 'tools.trackcheck.planui',
                      'tools.trackcheck.metainfo', 'tools.trackcheck.fields',
                      'tools.trackcheck.layout'])
    print('   %.1f MB' % (os.path.getsize(out) / 1048576.0), flush=True)
    return out


def build_uninstaller():
    print('② 卸载程序 Uninstall.exe …', flush=True)
    out = pyi(os.path.join(DESK, 'uninstaller.py'), 'Uninstall',
              hidden=['winsetup'])
    print('   %.1f MB' % (os.path.getsize(out) / 1048576.0), flush=True)
    return out


def build_installer(app_exe, un_exe):
    print('③ 安装程序 trackcheck-v%s-setup.exe …（内部版本 %s）' % (APP_PKG, APP_VER), flush=True)
    out = pyi(os.path.join(DESK, 'installer.py'), 'trackcheck-v%s-setup' % APP_PKG,
              add=[(app_exe, '.'), (un_exe, '.')], hidden=['winsetup'])
    print('   %.1f MB' % (os.path.getsize(out) / 1048576.0), flush=True)
    return out


def write_docs():
    """顺手放一份"怎么分发"的说明到 dist/，方便直接压缩发出去"""
    src = os.path.join(ROOT, 'tools', 'trackcheck', '发布说明.md')
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(DIST, '发布说明.md'))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=['app', 'uninst', 'setup', 'all'], default='all')
    a = ap.parse_args(argv)

    with open(VERFILE, 'w', encoding='utf-8') as f:
        f.write(version_txt())

    if a.only == 'app':
        build_app()
        return
    if a.only == 'uninst':
        build_uninstaller()
        return

    app_exe = os.path.join(DIST, 'TrackCheck.exe')
    un_exe = os.path.join(DIST, 'Uninstall.exe')
    if a.only == 'all':
        app_exe = build_app()
        un_exe = build_uninstaller()
    build_installer(app_exe, un_exe)
    write_docs()
    print('\n产物目录：%s' % DIST, flush=True)
    for n in sorted(os.listdir(DIST)):
        print('   %-34s %6.2f MB' % (n, os.path.getsize(os.path.join(DIST, n)) / 1048576.0))


if __name__ == '__main__':
    main()
