# trackcheck 开发规则（固定）

本文件是**长期有效**的开发约束。改代码前先读一遍，改完对照检查。

---

## 1. ★ 双语同步（强制，最高优先级）

**改动任何"用户能看到的文字"时，中文与英文必须在同一次改动里一起改完。**

这条没有例外。不允许"先写中文，英文下次再补"——本项目已经因为漏英文返工过一次
（0.3.0 发布后 29% 的界面还是中文）。

### 文字存在哪里

| 位置 | 中文源 | 英文放哪 |
|---|---|---|
| 页面骨架 / JS 里拼的提示 | `ui.py`、`planui.py` 的字面量 | `i18n.py` 的 `WORDS` / `LABELS` / `PHRASES` / `JS_LITERALS` / `TR_EXTRA`，或 `i18n_bulk.py` 的 `BULK`（整句长文本一律放这里） |
| 帮助页正文 | `help_text.py` 的 `HELP_ZH` | 同文件的 `HELP_EN` |
| 「i」按钮的格式说明 | `plan.py` 的 `_SPEC_*` | `spec_text_en.py` 的 `SPEC_EN` |
| 模型清单（设置页） | `metainfo.py` 的 `note` / `label` | `i18n_bulk.py`（**键 = 中文原文，必须逐字节一致**） |
| 阵解目录 / 内置示例阵解 | `plan.py` 返回值 | `i18n_bulk.py`（同上） |
| 报告页 | `html_report.py` / `jobs.py` | `i18n_bulk.py` + `i18n.py` 的规则表 |
| 植物 / 僵尸 / 场地名 | 中文标识符 | `i18n.py` 的 `NAMES`（官方英文名） |

### 具体做法

1. **先在中文源里改**，把新句子整句抄下来。
2. **同一提交里**去 `i18n_bulk.py` 加/改对应键：键必须与中文**逐字节相同**
   （包括全角标点、`**粗体**` 标记、换行与缩进）。键对不上 → 英文界面会退回
   逐词替换，句子会被切碎（历史事故：`邻D6` → `邻Adjacent`）。
3. 中文原句**改了写法**时，必须**同步改 `i18n_bulk.py` 的键**；
   旧键留着不会报错，只会变成死词条——请一并删掉。
4. 新增植物 / 僵尸 → 第一时间补 `i18n.NAMES` 的官方英文名（**官方名，不用绰号**：
   曾哥 = Gloom-shroom、大喷 = Fume-shroom、冰车 = Zomboni）。
5. **改完必须跑检查**：

   ```
   python -m tools.trackcheck.check_i18n          # 列出缺英文的中文字串
   python -m tools.trackcheck.check_i18n --fix-hint
   ```

   退出码非 0 = 有缺项，不许提交。

### 不许做的事

- 用"逐词替换能拼出来"当理由跳过整句词条 —— 长句一律整句进 `BULK`。
- 把植物 / 僵尸名（回传服务器的标识符）翻译掉 —— 那是 `NAMES` 的展示层工作。
- 让 1~2 字的短词进 `WORDS`（会咬坏 `玉米炮` 之类的名字）；短词只放 `TR_EXTRA`，
  只允许整串精确查表。

---

## 2. 模型清单必须与引擎一致

`metainfo.py` 里的 `note` 是**对外承诺**："这个植物 / 僵尸 / 场地建模到什么程度"。
写之前先读 `data.py` 的 `PLANTS` / `ZOMB` / `FIELDS` 与 `engine.py` 的对应 tick，
**只描述代码真做了的事**：

- 常量写在 `data.py` 的，note 里就写那个值（不要凭记忆写文献值）。
- 结果导向的简化（`RESULT_ONLY`、`ICE_DELAY=0`、`COB_IGNORE_FUSE`）必须说清楚
  "本工具不计时延"，不能照抄原版数值。
- 一旦某机制从"不模拟"升级成"模拟"，note 必须同版本改掉（历史事故：
  保护伞 / 蹦极 / 投篮 早已实现，note 还写着"不模拟"）。

## 3. 版本号

- 对外测试版 `0.x`；同一次发布里的每处改动记 `0.x.n`（`0.x.0` = 该发布基线）。
- 打包时 `metainfo.VERSION`、`build_win.APP_VER`、`build_web.APP_VER` 一起改。
- 只有 `0.x` 才对外 release；`0.x.n` 是内部版本，不建 Release、不打 tag。

## 4. 验证

- 改动涉及模拟 → 跑四档基线（`python -m tools.trackcheck.run --tier <档> --seeds 20`），
  期望 **21.7 / 17.5 / 13.7 / 12.0 s**（中英一致）。
- 改动涉及界面 → 中英两版 `ui.page_html()` 都要能生成，英文版**可见中文应为 0 条**。
- 改动涉及打包 → `python -m tools.trackcheck.build_web` + `build_win` 都要重跑。
