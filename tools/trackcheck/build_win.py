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
    python -m tools.trackcheck.build_win                   # 内部版：只打 exe（不含安装包）
    python -m tools.trackcheck.build_win --release         # 正式发布：再加安装包 + 合并更新日志
    python -m tools.trackcheck.build_win --only app        # 只打主程序
    python -m tools.trackcheck.build_win --only setup      # 只打安装包（要 exe 已在）

★ 2026-10-24 用户定的轻量化规则：
  **没有 release 的内部版本只出 html + exe，不生成 setup 安装包**；
  正式 release 时才把这一段所有 `0.x.n` 的更新日志**合并**成一份发布说明，
  再打安装包（这样安装包里带的日志是"一个发布"的完整说明，不是逐条碎片）。
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
APP_VER = '0.3.11'
APP_PKG = '0.3'          # 文件名只到 0.x（0.x.n 是同一发布里的改动计数）
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
    """主程序：内部版本输出 `TrackCheck-<完整版本号>.exe`

    ★ 2026-10-25 用户：内部版本用完整版本号命名；安装包只在 release 时生成、只用发布版本号。
    """
    print('① 主程序 TrackCheck-%s.exe …' % APP_VER, flush=True)
    name = 'TrackCheck-%s' % APP_VER
    out = pyi(os.path.join(DESK, 'launcher.py'), name,
              hidden=['tools.trackcheck.app', 'tools.trackcheck.jobs',
                      'tools.trackcheck.ui', 'tools.trackcheck.webbridge',
                      'tools.trackcheck.plan', 'tools.trackcheck.planui',
                      'tools.trackcheck.metainfo', 'tools.trackcheck.fields',
                      'tools.trackcheck.layout'])
    print('   %.1f MB' % (os.path.getsize(out) / 1048576.0), flush=True)
    return out


def build_uninstaller():
    print('② 卸载程序 Uninstall-%s.exe …' % APP_VER, flush=True)
    name = 'Uninstall-%s' % APP_VER
    out = pyi(os.path.join(DESK, 'uninstaller.py'), name,
              hidden=['winsetup'])
    print('   %.1f MB' % (os.path.getsize(out) / 1048576.0), flush=True)
    return out


def build_installer(app_exe, un_exe):
    """安装包：只在 release 时打，文件名只用**发布版本号**（`trackcheck-v0.3-setup.exe`）

    ★ 2026-10-25：主程序/卸载程序在 dist 里是按完整版本号命名的
      （`TrackCheck-0.3.8.exe`），但安装进去的目录里应该还是 `TrackCheck.exe` /
      `Uninstall.exe`，所以这里先复制成标准名再喂给 installer.py。
    """
    print('③ 安装程序 trackcheck-v%s-setup.exe …（内部版本 %s）' % (APP_PKG, APP_VER), flush=True)
    tmp = os.path.join(WORK, 'payload')
    os.makedirs(tmp, exist_ok=True)
    a = shutil.copy2(app_exe, os.path.join(tmp, 'TrackCheck.exe'))
    u = shutil.copy2(un_exe, os.path.join(tmp, 'Uninstall.exe'))
    out = pyi(os.path.join(DESK, 'installer.py'), 'trackcheck-v%s-setup' % APP_PKG,
              add=[(a, '.'), (u, '.')], hidden=['winsetup'])
    print('   %.1f MB' % (os.path.getsize(out) / 1048576.0), flush=True)
    return out


def write_docs():
    """顺手放一份"怎么分发"的说明到 dist/，方便直接压缩发出去"""
    src = os.path.join(ROOT, 'tools', 'trackcheck', '发布说明.md')
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(DIST, '发布说明.md'))


def merged_changelog(pkg=None):
    """把 CHANGELOG 里属于**同一个 0.x 发布**的所有小节合并成一份发布说明

    ★ 2026-10-24 用户：内部版本只出 html+exe；到 release 时才合并更新日志、
      再打安装包（安装包里带的应该是"这一个发布"的完整说明）。
    """
    pkg = pkg or APP_PKG
    path = os.path.join(ROOT, 'CHANGELOG.md')
    if not os.path.exists(path):
        return ''
    with open(path, encoding='utf-8') as f:
        text = f.read()
    keep, hit = [], False
    for line in text.split('\n'):
        if line.startswith('## ['):
            hit = line.startswith('## [%s.' % pkg) or line.startswith('## [%s]' % pkg)
            if hit:
                keep.append(line)
            continue
        if hit:
            keep.append(line)
    body = '\n'.join(keep).strip()
    return ('# trackcheck v%s · 更新日志（%s 发布合并版）\n\n%s\n'
            % (pkg, pkg, body)) if body else ''


def write_release_notes():
    """release 专用：把 0.x.n 的日志合并成 dist/更新日志-v0.x.md"""
    body = merged_changelog()
    if not body:
        return None
    out = os.path.join(DIST, '更新日志-v%s.md' % APP_PKG)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(body)
    print('   合并更新日志 → %s（%d 字节）' % (os.path.basename(out), len(body)), flush=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=['app', 'uninst', 'setup', 'all'], default='all')
    ap.add_argument('--release', action='store_true',
                    help='正式发布：额外打 setup 安装包，并合并 0.x.n 的更新日志')
    a = ap.parse_args(argv)

    with open(VERFILE, 'w', encoding='utf-8') as f:
        f.write(version_txt())
    # ★ 2026-10-25：把版本号单点交给 winsetup（安装器 UI / 卸载条目都用它）
    with open(os.path.join(DESK, '_build_ver.py'), 'w', encoding='utf-8') as f:
        f.write('# 由 build_win.py 生成，勿手改\nVERSION = %r\n' % APP_VER)

    if a.only == 'app':
        build_app()
        return
    if a.only == 'uninst':
        build_uninstaller()
        return

    app_exe = os.path.join(DIST, 'TrackCheck.exe')
    un_exe = os.path.join(DIST, 'Uninstall.exe')
    if a.only in ('all', 'app') and (a.only == 'all' or not os.path.exists(app_exe)):
        app_exe = build_app()
    if a.only in ('all', 'uninst') and (a.only == 'all' or not os.path.exists(un_exe)):
        un_exe = build_uninstaller()

    do_setup = a.release or a.only == 'setup'
    if do_setup:
        if not (os.path.exists(app_exe) and os.path.exists(un_exe)):
            raise RuntimeError('打安装包需要 dist/ 里先有 TrackCheck.exe 和 Uninstall.exe')
        if a.release:
            write_release_notes()
        build_installer(app_exe, un_exe)
        write_docs()
    else:
        # ★ 内部版本：只出 html + exe，不生成安装包
        #   上一次 release 留下的 setup.exe 是**旧版本**的，留着容易误发 → 删掉
        stale = os.path.join(DIST, 'trackcheck-v%s-setup.exe' % APP_PKG)
        if os.path.exists(stale):
            os.remove(stale)
            print('   删掉上次 release 留下的旧安装包 %s'
                  % os.path.basename(stale), flush=True)
        # 旧命名（无版本号）的 exe 也清掉，免得和新的版本化产物混在一起
        for old in ('TrackCheck.exe', 'Uninstall.exe'):
            p_old = os.path.join(DIST, old)
            if os.path.exists(p_old):
                os.remove(p_old)
                print('   删掉旧命名的 %s' % old, flush=True)
        print('（内部版本：跳过 setup 安装包；要打安装包请加 --release）', flush=True)

    print('\n产物目录：%s' % DIST, flush=True)
    for n in sorted(os.listdir(DIST)):
        print('   %-34s %6.2f MB' % (n, os.path.getsize(os.path.join(DIST, n)) / 1048576.0))


if __name__ == '__main__':
    main()
