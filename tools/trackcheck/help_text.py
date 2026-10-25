# -*- coding: utf-8 -*-
"""
help_text.py —— 帮助页正文（中 / 英两份）

★ 2026-10-24：帮助页原本写死在 `ui.py` 的 `PAGE` 里，双语化时抽出来，
  由 `ui.page_html()` 按当前语言挑一份塞进 `__HELPBODY__`。
  `__GLOSSARY__` 再由 `i18n.glossary_html()` 填（术语说明，两份各自本地化）。
"""

HELP_ZH = '''<div class="panel">__GLOSSARY__</div>
  <div class="panel">
    <div class="ptitle">怎么用（四步）</div>
    <div class="helpsec">
      <h3>① 阵容布置</h3>
      <p>先选<b>场地</b>（PE / FE / DE / NE / RE），起一个<b>阵型名</b>
      （格式 <code>[场地].名字</code>，<code>[场地].</code> 由 app 自动生成，只填后面的名字），
      再点格子把植物摆上去。
      每格可以设：主植物（含模仿者）、<b>是否套南瓜</b>、<b>是否搭梯</b>（必须先有南瓜）、
      <b>是否有睡莲/花盆</b>（水路、屋顶有东西时会自动锁上）。
      也可以在下面直接<b>粘贴 PvZ Tools 的阵型字符串</b>导入，或用「生成字符串」导出。</p>
      <h3>② 出怪沙盘</h3>
      <p>勾选这一关允许出现的僵尸，起个名字点「加入列表」。可以加多组（不同出怪组合）。</p>
      <h3>③ 阵解编辑</h3>
      <p>阵解 = 「节奏 + 每波做什么 + 全场判定 + 救场」。如果只想看自然输出能撑多久，
      这一步可以跳过（不选阵解就是"什么都不做"的空轨道）。
      所有出现 JSON 的地方都有一个小 <b>i</b>，点开能复制/下载格式说明 —— 直接交给 AI 生成阵解。</p>
      <p><b>轨道里只有两种操作</b>：<b>P</b>（玉米炮，不指定哪一门）和
      <b>种植物</b>（卡片）。轨道串认得
      <code>|</code>（换波）、<code>-</code>（同一波的第二个时机）、
      <code>/</code>（上下半场）、<code>~</code>（两套节奏摆动）；
      右边的「波长串」写 <code>(9,9,9,9)</code>，会自动校验波长和够不够炮 / 卡的 CD 转完。
      <b>单位自动识别</b>：默认按<b>秒</b>读；写成 <code>(875,875,875,850)</code> 这种
      明显是 <b>cs</b> 的数量级也会自动按 cs 读（= 8.75 / 8.75 / 8.75 / 8.5 秒）。
      想写死单位就带后缀：<code>875cs</code> / <code>8.75s</code>。</p>
      <h3>④ 运行与报告</h3>
      <p>点「开始模拟」。报告里有：波长、偏差、减速覆盖、存冰/阳光/补南瓜台账、
      逐波时间轴、轨道执行表；右上角可以下载 PDF。</p>
      <p class="hint">注意：本工具是<b>模型</b>，不是游戏本体。哪些植物/僵尸/场地建模到什么程度，
      见右上角齿轮里的「模型清单」。</p>
    </div>
  </div>

  <div class="panel">
    <div class="ptitle">使用示例：PE.电波钟无炮（C4io）</div>
    <div class="helpsec">
      <p>下面的示例<b>不在</b>主界面里，只是给你看"一个完整配置长什么样"。
      点按钮会把它载入到 ① 阵容布置 / ③ 阵解编辑 里，可以照着改。</p>
      <p><b>节奏</b>：C<sub>4</sub>io —— 4 拍循环 <code>N | AA′ | I | I</code>
      （N = 毁灭菇、A = 樱桃、A′ = 辣椒、I = 寒冰菇、a = 窝瓜、c = 垫材），常规波长 ≈ 15.4~15.9s。
      2016 年后的写法在两套命名方案下都叫 C4io（C 系未废止，归入 P 大类）。</p>
      <p><b>阵型要点</b>：6 行 9 列泳池；3/4 路是水路；3-2 / 3-3 / 4-3 / 5-3 是永久存冰位；
      2-7 / 5-7 是前场临时位；5-8 是主核坑。</p>
      <div class="row" style="margin-top:8px">
        <button id="help-load">载入示例阵容</button>
        <button id="help-plan">载入示例阵解</button>
        <button id="help-classic8">载入 PE.经典八炮（炮阵样板）</button>
 <button id="help-fe4">载入 FE.雾四炮（少炮重 IO 样板）</button>
        <span class="hint" id="help-msg"></span>
      </div>
      <h3>示例阵型字符串（PvZ Tools）</h3>
      <pre id="help-str">（点「载入示例阵容」后会自动填进 ①）</pre>
    </div>
  </div>
'''

HELP_EN = '''<div class="panel">__GLOSSARY__</div>
  <div class="panel">
    <div class="ptitle">How to use (four steps)</div>
    <div class="helpsec">
      <h3>① Formation</h3>
      <p>Pick a <b>field</b> (PE / FE / DE / NE / RE), give the <b>formation a name</b>
      (the format is <code>[field].name</code>; the <code>[field].</code> part is
      generated automatically, you only type the name), then click cells to place
      plants. Each cell can carry: the plant itself (Imitator included),
      <b>Pumpkin</b>, <b>Ladder</b> (needs a Pumpkin first) and
      <b>Lily Pad / Flower Pot</b> (locked automatically on water and roof).
      You can also <b>paste a PvZ Tools formation string</b> below to import,
      or export one with “Generate string”.</p>
      <h3>② Spawn Sandbox</h3>
      <p>Tick the zombies allowed in this level, name the set and click
      “Add to queue”. Several sets can be queued.</p>
      <h3>③ Solution editor</h3>
      <p>A solution = “rhythm + what to do each wave + global checks + rescue”.
      If you only want to see how long passive damage holds, skip this step
      (no solution selected = an empty track that does nothing).
      Every JSON block has a small <b>i</b>; open it to copy/download the format
      spec — you can hand it straight to an AI to generate a solution.</p>
      <p><b>A track only has two kinds of operations</b>: <b>P</b> (Cob Cannon,
      no specific one named) and <b>plant</b> (cards). The track string understands
      <code>|</code> (next wave), <code>-</code> (a second group in the same wave),
      <code>/</code> (upper / lower half) and <code>~</code> (alternate two rhythms).
      The “wavelength list” on the right takes <code>(9,9,9,9)</code> and is
      validated against cob / card cooldowns automatically.
      <b>Units are detected automatically</b>: seconds by default; a list like
      <code>(875,875,875,850)</code> is recognised as <b>centiseconds</b>
      (= 8.75 / 8.75 / 8.75 / 8.5 s). To force a unit, add a suffix:
      <code>875cs</code> / <code>8.75s</code>.</p>
      <h3>④ Run &amp; report</h3>
      <p>Click “Start”. The report contains: wavelength, deviation, slow coverage,
      ice-bank / sun / pumpkin ledgers, a per-wave timeline and the track execution
      table; the PDF can be downloaded from the top right.</p>
      <p class="hint">Note: this is a <b>model</b>, not the game itself. See
      “Model list” in the gear menu for how deeply each plant / zombie / field
      is modeled.</p>
    </div>
  </div>

  <div class="panel">
    <div class="ptitle">Example: PE.C4io (Dianbozhong, no cob)</div>
    <div class="helpsec">
      <p>The example below is <b>not</b> part of the main UI — it just shows what a
      complete configuration looks like. The buttons load it into
      ① Formation / ③ Solution editor so you can edit from there.</p>
      <p><b>Rhythm</b>: C<sub>4</sub>io — a 4-beat cycle
      <code>N | AA′ | I | I</code> (N = Doom-shroom, A = Cherry Bomb,
      A′ = Jalapeno, I = Ice-shroom, a = Squash, c = padding plant); regular wavelength ≈ 15.4–15.9 s.
      Under both naming schemes the post-2016 name is still C4io
      (the C series is not obsolete; it belongs to the P family).</p>
      <p><b>Formation notes</b>: 6 rows × 9 columns pool; lanes 3/4 are water;
      3-2 / 3-3 / 4-3 / 5-3 are permanent ice slots; 2-7 / 5-7 are temporary front
      slots; 5-8 is the main Doom crater.</p>
      <div class="row" style="margin-top:8px">
        <button id="help-load">Load example formation</button>
        <button id="help-plan">Load example solution</button>
        <button id="help-classic8">Load PE.Classic 8 Cobs (cob-array template)</button>
 <button id="help-fe4">Load FE.Fog 4 Cobs (few-cob, IO-heavy template)</button>
        <span class="hint" id="help-msg"></span>
      </div>
      <h3>Example formation string (PvZ Tools)</h3>
      <pre id="help-str">(click “Load example formation” and it is filled into ①)</pre>
    </div>
  </div>
'''
