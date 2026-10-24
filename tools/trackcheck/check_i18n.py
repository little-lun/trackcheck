# -*- coding: utf-8 -*-
"""
check_i18n.py —— **双语同步**的自动检查（见 `AGENTS.md` 第 1 条）

做三件事：

1. 把**用户能看到的文字**从各处收集出来（模型清单 note / 阵解目录 / 内置示例阵解 /
   帮助页 / 格式说明 / 页面静态壳）。
2. 对每个含中文的串，问 `i18n.tr()`：英文界面下它会不会还是中文？
3. 有缺项就**列出并返回非 0 退出码**，方便接进提交前检查。

用法：

    python -m tools.trackcheck.check_i18n              # 只检查
    python -m tools.trackcheck.check_i18n -v           # 附带每个缺项的来源

设计取舍：
  · 只查"文字"，不查标识符（植物 / 僵尸 / 模仿者组合 —— 它们回传服务器，必须保持中文）。
  · 引用 `i18n_bulk.BULK` 里**已经不匹配的旧键**也会报出来（dead key），
    因为那通常是"中文改了、英文没跟着改"。
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.trackcheck import i18n as I18N      # noqa: E402

CJK = re.compile(r'[\u4e00-\u9fff]')
TEXT_KEYS = {'note', 'label', 'trad', 'new', 'group', 'reason', 'tier', 'hint',
             'title', 'text', 'desc', 'summary', 'msg', 'name', 'why'}


def _walk(obj, path='', out=None):
    """递归收集 (path, 字符串) —— 只收"显示字段"里的值"""
    out = out if out is not None else []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k in TEXT_KEYS:
                out.append(('%s/%s' % (path, k), v))
            else:
                _walk(v, '%s/%s' % (path, k), out)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _walk(v, '%s[%d]' % (path, i), out)
    return out


def _text_nodes(html):
    """HTML → 可见文本节点列表（跳过 `<script>` / `<style>` / `<code>` / `<pre>`）"""
    s = re.sub(r'<script[\s\S]*?</script>', ' ', html or '')
    s = re.sub(r'<style[\s\S]*?</style>', ' ', s)
    return [t.strip() for t in re.findall(r'>([^<>]+)<', s) if t.strip()]


def collect():
    """[(来源, 中文字串)] —— 需要 `i18n_bulk` 逐句翻译的结构化文案"""
    from tools.trackcheck import metainfo as MI
    from tools.trackcheck import plan as PL

    items = []
    items += _walk(MI.models(), 'metainfo')
    items += _walk(PL.catalog(), 'catalog')
    items += _walk(PL.default_dianbozhong(), 'default')
    for name in ('S3', 'P3n', 'C4io', 'N6s'):
        try:
            items += _walk(PL.example_fe4(name), 'fe4/%s' % name)
        except Exception:                                  # noqa: BLE001
            pass
    items += _walk(PL.example_classic8(), 'classic8')
    items += _walk(PL.example_split_aa(), 'split_aa')
    for f in ('PE', 'FE', 'DE', 'NE', 'RE'):
        items += _walk(PL.template(f), 'template/%s' % f)
    return items


def collect_en_bodies():
    """[(来源, 英文正文)] —— 手写英文，检查里**不许**有中文"""
    from tools.trackcheck import plan as PL
    from tools.trackcheck import help_text as HT
    from tools.trackcheck.spec_text_en import SPEC_EN

    out = [('help/HELP_EN', HT.HELP_EN)]
    for k, v in SPEC_EN.items():
        out.append(('spec_en/%s' % k, v))
    return out


def collect_zh_bodies():
    """[(来源, 中文原文)] —— 手写中文，用来对齐键与查死键"""
    from tools.trackcheck import plan as PL
    from tools.trackcheck import help_text as HT

    out = [('help/HELP_ZH', HT.HELP_ZH)]
    for what in ('plan', 'spawn', 'spawnmech', 'layout', 'resultonly', 'config'):
        out.append(('spec_zh/%s' % what, PL.spec_text(what)))
    return out


def dead_bulk_keys():
    """`BULK` 里那些在中文源（含页面 / JS 片段）里已经找不到的旧键"""
    from tools.trackcheck import i18n_bulk
    from tools.trackcheck import ui

    joined = '\n'.join([ui.page_html()] +
                       [s for _src, s in collect_zh_bodies()])
    dead = []
    for k in i18n_bulk.BULK:
        if k not in joined:
            dead.append(k)
    return dead


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('-v', '--verbose', action='store_true', help='打印每项来源')
    ap.add_argument('--fix-hint', action='store_true',
                    help='只打印"该往哪张表里加"')
    ap.add_argument('--dead', action='store_true', help='顺便报告 BULK 里的死键')
    a = ap.parse_args(argv)

    # ① 结构化文案：`tr()` 必须能给出纯英文
    I18N.set_lang('en')
    missing, seen = [], set()
    checked = 0
    for src, s in collect():
        if not s or not CJK.search(s):
            continue
        if I18N._is_identifier(s):
            continue                        # 植物 / 僵尸名 = 标识符，必须保持中文
        checked += 1
        got = I18N.tr(s)
        if CJK.search(got or ''):
            key = (s, got)
            if key in seen:
                continue
            seen.add(key)
            missing.append((src, s, got))
    # ② 手写英文正文：不许有中文
    bad_en = []
    for src, body in collect_en_bodies():
        for t in ([body] if len(body) < 400 else _text_nodes(body)):
            if CJK.search(t or '') and not I18N._is_identifier(t.strip()):
                bad_en.append((src, t.strip()))
    # ③ 英文页面的可见文本：不应有中文
    from tools.trackcheck import ui
    page_cjk = [t for t in _text_nodes(ui.page_html())
                if CJK.search(t) and not I18N._is_identifier(t)]
    I18N.set_lang('zh')

    if missing:
        print('✗ 英文界面下仍会显示中文的文案：%d 条' % len(missing))
        for src, s, got in missing:
            head = s.replace('\n', ' ')[:70]
            if a.fix_hint:
                print('  · [%s] %s' % (src, head))
                print('    → 往 i18n_bulk.BULK 加：%r' % s)
            elif a.verbose:
                print('  · [%s] %s' % (src, head))
                print('    现在会显示：%s' % (got or '')[:70].replace('\n', ' '))
            else:
                print('  · [%s] %s' % (src, head))
    if bad_en:
        print('✗ 手写英文正文里还有中文：%d 条' % len(bad_en))
        for src, t in bad_en:
            print('  · [%s] %s' % (src, t[:70].replace('\n', ' ')))
    if page_cjk:
        print('✗ 英文页面的可见文本里还有中文：%d 条' % len(page_cjk))
        for t in page_cjk[:20]:
            print('  · %s' % t[:70].replace('\n', ' '))

    dead = dead_bulk_keys() if a.dead else []
    if dead:
        print('\n⚠ BULK 里有 %d 条键在中文源里已经找不到（历史遗留的死键，'
              '不影响显示；要清理请手工核对）' % len(dead))
        for k in dead[:40]:
            print('  · %s' % k.replace('\n', ' ')[:70])

    if missing or bad_en or page_cjk:
        return 1
    print('✓ 双语同步检查通过（%d 条结构化文案 + %d 篇英文正文 + 整页可见文本）'
          % (checked, len(collect_en_bodies())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
