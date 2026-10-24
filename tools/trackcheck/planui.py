# -*- coding: utf-8 -*-
"""
planui.py —— **阵解栏**的前端（HTML 片段 + JS）

交互模型（刻意像积木编程）：

    阵解库   多套阵解，可新建 / 复制 / 删除 / 保存 / 导出 / 导入
    选卡     10 个卡槽（含模仿者）—— 后面所有"种什么"只从这 10 张里选
    表层     每波一行；行内是候选兜底链；候选里是积木；积木带触发器
             批量：勾选波次 → 前移/后移、复制/粘贴/清空、撤销
    全场判定 持续判条件，成立就做
    简化救场 交资源 + 排优先级，内部决定打什么
    详细救场 事件 → 多层兜底（v0.2 的，保留）
    匹配     出怪组 ↔ 阵解

所有编辑都是"改状态再重画"：`PLAN.bank[active].plan` 是唯一真相，
事件用 `data-act` + `data-path` 做委托，路径形如 `waves.4.sets.0.ops.1.trig`。
"""

STYLE = r"""
.tabs{display:flex;gap:6px;margin:0 0 14px;border-bottom:1px solid #e2e8f0}
.tabs button{border:1px solid #e2e8f0;border-bottom:0;background:#fff;
 border-radius:8px 8px 0 0;padding:7px 15px;font-weight:600;color:#64748b;cursor:pointer}
.tabs button.on{background:#2563eb;border-color:#2563eb;color:#fff}
.pgrid{display:grid;grid-template-columns:210px 1fr;gap:12px;align-items:start}
.wlist{border:1px solid #e2e8f0;border-radius:8px;overflow:auto;max-height:600px}
.wrow{display:flex;gap:5px;align-items:center;padding:4px 6px;cursor:pointer;
 font-size:12px;border-bottom:1px solid #f1f5f9}
.wrow:hover{background:#f8fafc}
.wrow.on{background:#dbeafe}
.wrow.marked{background:#f0f9ff;box-shadow:inset 3px 0 0 #38bdf8}
.wrow.on.marked{background:#dbeafe;box-shadow:inset 3px 0 0 #2563eb}
.wrow .mk{width:14px;flex:none;cursor:pointer;accent-color:#2563eb}
.wrow .rw{color:#94a3b8;width:26px;flex:none}
.wrow .rr{font-size:10px;color:#475569;background:#f1f5f9;border-radius:4px;
 padding:0 4px;flex:none}
.wrow .rb{color:#94a3b8;margin-left:auto;font-size:10px}
.chip{display:inline-flex;gap:4px;align-items:center;border:1px solid #cbd5e1;
 background:#f8fafc;border-radius:6px;padding:2px 7px;font-size:12px;cursor:pointer;
 white-space:nowrap}
.chip:hover{border-color:#93c5fd}
.chip.on{border-color:#2563eb;background:#dbeafe}
.chip small{color:#94a3b8;font-size:10px}
.chip small.bid{color:#2563eb;font-family:ui-monospace,Consolas,monospace;
  background:#eff6ff;border-radius:3px;padding:0 2px}
.chip.no{border-color:#fecaca;background:#fef2f2;color:#b91c1c}
.arrow{color:#94a3b8;font-size:11px}
.set{border:1px dashed #cbd5e1;border-radius:8px;padding:6px 8px;margin-bottom:8px;
 background:#fcfdff}
.sethead{display:flex;gap:6px;align-items:center;font-size:11.5px;color:#475569;
 margin-bottom:5px;flex-wrap:wrap}
.chain{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.cond{display:inline-flex;flex-wrap:wrap;gap:3px;align-items:center;font-size:11.5px;
 background:#eef2ff;border:1px solid #c7d2fe;border-radius:6px;padding:2px 5px}
.cond select,.cond input{font-size:11px;padding:0 3px;border:1px solid #cbd5e1;
 border-radius:4px;background:#fff}
.insp{border:1px solid #e2e8f0;border-radius:8px;padding:9px 11px;background:#f8fafc;
 margin-top:8px}
.insp .row{margin-bottom:6px;font-size:12px}
.insp label{color:#475569;font-size:11.5px;margin-right:4px}
.mini2{font-size:11px;padding:1px 6px}
.lvl{border-left:3px solid #93c5fd;padding-left:8px;margin:6px 0}
.rule{border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;margin-bottom:8px;
 background:#fcfdff}
.rh{display:flex;gap:8px;align-items:center;font-size:12.5px;font-weight:600;color:#0f172a}
.rh .rid{color:#2563eb}
.issue{font-size:12px;padding:3px 0;border-bottom:1px dashed #f1f5f9}
.issue b{display:inline-block;min-width:44px}
.issue.err b{color:#b91c1c}.issue.warn b{color:#b45309}
.pltag{font-size:11px;background:#eef2ff;color:#3730a3;border-radius:4px;padding:1px 6px}
.jplan{font-size:11px;color:#334155;background:#eef2ff;border-radius:4px;padding:0 5px}
.jplan b{color:#1e3a8a}
.deck{display:flex;gap:6px;flex-wrap:wrap}
.deck .slot{display:flex;flex-direction:column;gap:2px;align-items:center}
.deck .slot b{font-size:10px;color:#94a3b8;font-weight:400}
.deck select{font-size:11.5px;max-width:86px}
.q i.info{display:inline-flex;align-items:center;justify-content:center;width:15px;
 height:15px;border-radius:50%;background:#e2e8f0;color:#475569;font-size:10px;
 font-style:normal;cursor:pointer;margin-left:4px;user-select:none}
.q i.info:hover{background:#2563eb;color:#fff}
.bank{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:12px}
.bank select{font-size:12px;max-width:180px}
.modwrap{position:fixed;inset:0;z-index:9998;background:rgba(15,23,42,.45);
 display:none;align-items:center;justify-content:center}
.modwrap.on{display:flex}
.mod{background:#fff;border-radius:10px;max-width:820px;width:92vw;max-height:84vh;
 display:flex;flex-direction:column;overflow:hidden}
.mod h3{margin:0;padding:12px 16px;font-size:14px;border-bottom:1px solid #e2e8f0}
.mod pre{flex:1;overflow:auto;margin:0;padding:12px 16px;font-size:11.5px;
 line-height:1.55;background:#f8fafc;white-space:pre-wrap;word-break:break-word}
.mod .foot{display:flex;gap:8px;justify-content:flex-end;padding:10px 16px;
 border-top:1px solid #e2e8f0}
.maptable{width:100%;border-collapse:collapse;font-size:12px}
.maptable th,.maptable td{border-bottom:1px solid #f1f5f9;padding:4px 6px;text-align:left}
.maptable select{font-size:11.5px}
"""
MARKUP = r"""
<div id="planpage" style="display:none">

  <div class="panel">
    <div class="ptitle">阵解库 · 多套阵解<i class="info" data-spec="plan"></i></div>
    <div class="bank">
      <select id="pl-bank"></select>
      <button class="ghost mini2" data-act="newPlan">＋ 新建</button>
      <button class="ghost mini2" data-act="dupPlan">⎘ 复制</button>
      <button class="ghost mini2" data-act="delPlan">✕ 删除</button>
      <span style="width:10px"></span>
      <button class="ghost mini2" data-act="save">⌸ 保存</button>
      <button class="ghost mini2" data-act="export">⤓ 导出本套</button>
      <button class="ghost mini2" data-act="import">⤒ 导入</button>
      <label class="hint" id="pl-saved-lab" style="display:none">已保存</label>
      <select id="pl-open" style="display:none"></select>
      <span style="width:10px"></span>
      <button class="ghost mini2" data-act="cfgExport">⤓ 导出全场配置</button>
      <button class="ghost mini2" data-act="cfgImport">⤒ 导入全场配置</button>
      <i class="info" data-spec="config"></i>
      <button class="ghost mini2" data-act="blank">＋ 空模板</button>
    </div>
    <div class="hint" id="pl-note" style="margin-top:6px"></div>
  </div>

  <div class="panel">
    <div class="ptitle">基本信息 · 节奏 · 快捷布置
      <i class="info" data-spec="spawnmech"></i>
      <span class="hint" style="font-weight:400">（i = 刷怪机制说明）</span>
      <i class="info" data-spec="resultonly"></i>
      <span class="hint" style="font-weight:400">（i = 建模原则：结果导向 / 哪些时延不计）</span></div>
    <div class="row" style="flex-wrap:wrap;gap:8px">
      <label class="hint">名称</label>
      <input type="text" id="pl-name" style="width:210px" placeholder="电波钟无炮">
      <label class="hint">节奏系</label><select id="pl-sys"></select>
      <label class="hint">节奏型</label><select id="pl-preset"></select>
      <span class="hint" id="pl-rhythm-info"></span>
      <label class="hint">轨道</label><input type="text" id="pl-beats" style="width:190px"
        placeholder="P|P|P|P">
      <label class="hint">波长串</label><input type="text" id="pl-gaps" style="width:150px"
        placeholder="(9,9,9,9)">
      <label class="hint" title="固定波长的阵，起手从连续节奏最快的点开始">起手拍</label>
      <input type="number" id="pl-start" min="0" style="width:56px" value="0">
      <span class="hint" id="pl-gaps-tip"></span>
      <button class="primary mini2" data-act="quick">⚡ 快捷布置阵解</button>
      <button class="ghost mini2" data-act="validate">✓ 校验</button>
    </div>
    <div class="hint" style="margin-top:4px">
      快捷布置只把「做什么」铺进常规波（20 波全填），落点 / 时机 / 兜底留给你填。<br>
      轨道认得 <code>|</code> 波次、<code>-</code> 同一波的第二个时机、<code>/</code> 上下半场、
      <code>~</code> 两套节奏摆动；波长串写 <code>(9,9,9,9)</code> 或 <code>(9|9|9|9)</code>。
    </div>
    <div class="hint" id="pl-spectrum" style="margin-top:6px"></div>
  </div>

  <div class="panel">
    <div class="ptitle">选卡 · 10 个卡槽<i class="info" data-spec="plan"></i></div>
    <div class="deck" id="pl-deck"></div>
    <div class="hint" style="margin-top:6px">
      下面所有"种什么"的选项都只从这 10 张里出。唤醒存冰 = 在某格<b>种咖啡豆</b>；
      补存冰 = 在某格<b>种寒冰菇</b>。
    </div>
  </div>

  <div class="panel">
    <div class="ptitle">表层阵解 · 轨道
      <span class="hint" style="font-weight:400">（每波一行；行内是候选兜底链，
        行首积木 = 刷怪即刻生效）</span></div>
    <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:8px">
      <span class="hint">批量：</span>
      <button class="ghost mini2" data-act="markAll">全选</button>
      <button class="ghost mini2" data-act="markInv">反选</button>
      <button class="ghost mini2" data-act="markNone">清空勾选</button>
      <span style="width:8px"></span>
      <button class="ghost mini2" data-act="shiftL">← 整体前移一位</button>
      <button class="ghost mini2" data-act="shiftR">整体后移一位 →</button>
      <span style="width:8px"></span>
      <button class="ghost mini2" data-act="copy">⎘ 复制</button>
      <button class="ghost mini2" data-act="paste">⎗ 粘贴</button>
      <button class="ghost mini2" data-act="clr">⌫ 清空</button>
      <button class="ghost mini2" data-act="undo">↶ 撤销</button>
      <span class="hint" id="pl-marks"></span>
    </div>
    <div class="pgrid">
      <div class="wlist" id="pl-waves"></div>
      <div id="pl-wavebox"></div>
    </div>
  </div>

  <div class="panel">
    <div class="ptitle">全场判定
      <span class="hint" style="font-weight:400">（持续判一个条件，成立就做。
        例：冰卡一好就补在空着的永久存冰位）</span><i class="info" data-spec="plan"></i></div>
    <div id="pl-globals"></div>
    <button class="ghost" data-act="addGlobal">+ 加一条全场判定</button>
  </div>

  <div class="panel">
    <div class="ptitle">简化救场
      <span class="hint" style="font-weight:400">（你只交资源 + 排优先级，打什么、打哪一路由内部决定）</span></div>
    <div id="pl-simple"></div>
  </div>

  <div class="panel">
    <div class="ptitle">详细救场
      <span class="hint" style="font-weight:400">（事件 → 多层兜底：上一层没落地就试下一层）</span></div>
    <div id="pl-rescue"></div>
    <button class="ghost" data-act="addRule">+ 加一条救场规则</button>
  </div>

  <div class="panel">
    <div class="ptitle">阵解 ↔ 出怪 匹配
      <span class="hint" style="font-weight:400">（左边是出怪沙盘里的列表，右边选它用哪套阵解）</span></div>
    <div id="pl-map"><div class="hint">出怪列表还是空的</div></div>
  </div>

  <div class="panel">
    <div class="ptitle">校验</div>
    <div id="pl-issues" class="hint">点「校验」看看这份阵解有没有明显问题</div>
  </div>
</div>

<div class="modwrap" id="pl-mod">
  <div class="mod">
    <h3 id="pl-mod-title">JSON 格式说明</h3>
    <pre id="pl-mod-body"></pre>
    <div class="foot">
      <button class="ghost mini2" data-act="specCopy">复制全文</button>
      <button class="ghost mini2" data-act="specDown">下载 .md</button>
      <button class="primary mini2" data-act="specClose">关闭</button>
    </div>
  </div>
</div>

<input type="file" id="pl-file" accept=".json,application/json" style="display:none">
<input type="file" id="pl-cfgfile" accept=".json,application/json" style="display:none">
"""
SCRIPT = r"""
<script>
/* ═══════════════════════════ 阵解栏 v0.3 ═══════════════════════════ */
const PLAN = {
  cat: null, bank: [], active: 0, undo: [], clip: null, spec: null,
  bclip: null,
  sel: { wave: 1, set: -1, block: -1, rule: -1, g: -1 },
  marks: new Set(),
};

function plP() { return PLAN.bank[PLAN.active].plan; }
function plBankId() { return PLAN.bank[PLAN.active].id; }
function plSnap() {
  PLAN.undo.push(JSON.stringify(plP()));
  if (PLAN.undo.length > 40) PLAN.undo.shift();
}
function plDeep(x) { return JSON.parse(JSON.stringify(x)); }
function plEsc(s) {
  return String(s === undefined || s === null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function plPath(root, path) {
  let o = root;
  for (const k of String(path || '').split('.').filter(x => x !== '')) o = o[k];
  return o;
}
function plSet(root, path, val) {
  const ks = String(path).split('.').filter(x => x !== '');
  let o = root;
  for (let i = 0; i < ks.length - 1; i++) {
    if (o[ks[i]] === undefined || o[ks[i]] === null)
      o[ks[i]] = /^\d+$/.test(ks[i + 1]) ? [] : {};
    o = o[ks[i]];
  }
  o[ks[ks.length - 1]] = val;
}
function plNum(path, key, val, w) {
  return '<input type="number" data-path="' + path + '" data-key="' + key +
    '" value="' + (val === null || val === undefined ? 0 : val) + '" style="width:' +
    (w || 62) + 'px">';
}
function plArr(path, key, val, w) {
  const s = Array.isArray(val) ? val.join(',') : (val === undefined || val === null ? '' : val);
  return '<input type="text" data-path="' + path + '" data-key="' + key +
    '" data-arr="1" value="' + plEsc(s) + '" style="width:' + (w || 84) + 'px">';
}
function plSel(path, key, val, opts) {
  return '<select data-path="' + path + '" data-key="' + key + '">' +
    opts.map(function (o) {
      const v = Array.isArray(o) ? o[0] : o, t = Array.isArray(o) ? o[1] : o;
      return '<option value="' + plEsc(v) + '"' +
        (String(v) === String(val) ? ' selected' : '') + '>' + plEsc(t) + '</option>';
    }).join('') + '</select>';
}

/* ---- 选卡 / 积木下拉：种植物类只给选卡里选中的植物 ---- */
const MIMIC_TAG = '模仿者';
function plCardOp(c) {
  c = String(c || '');
  return c.indexOf(MIMIC_TAG + ':') === 0 ? '模仿' + c.split(':')[1] : c;
}
function plDeckOps() {
  const out = [];
  (plP().deck || []).forEach(function (c) {
    const o = plCardOp(c);
    if (o && out.indexOf(o) < 0) out.push(o);
  });
  return out;
}
function plOps() {
  const allowed = plDeckOps();
  const ops = PLAN.cat.ops.filter(function (o) {
    // ★ 2026-10-22：P（玉米炮）永远可选 —— 它属于阵型，不属于选卡
    return o.group === '炮' || o.group === '特技' || allowed.indexOf(o.name) >= 0;
  });
  // 模仿了 OPS 里没有的植物 → 补一块（引擎未建模，校验会提示）
  allowed.forEach(function (o) {
    if (o.indexOf('模仿') === 0 && !PLAN.cat.ops.some(function (x) { return x.name === o; })) {
      ops.push({ name: o, group: '模仿', need_aim: false, aim_kind: 'cell', auto: true,
                 note: '引擎暂未建模这张模仿卡（写进阵解可以，跑起来会记未知卡片）' });
    }
  });
  return ops;
}
function plCardOpts() {
  const deck = (plP().deck || []).filter(Boolean);
  return deck.length ? deck : (PLAN.cat.default_deck || []);
}
/* 节奏命名：2021 传统 / 2026 新版 / 双轨 */
function plNaming() {
  return (typeof tcNaming === 'function') ? tcNaming() : 'both';
}
function plName(cell) {
  if (!cell) return '';
  const trad = cell.trad || '', now = cell.new || '';
  const n = plNaming();
  if (n === '2021') return trad || now;
  if (n === '2026') return now || trad;
  if (trad && now && trad !== now) return now + '（' + trad + '）';
  return now || trad;
}
function plPreset(id) {
  for (const r of (PLAN.cat.rhythms || [])) {
    for (const p of (r.presets || [])) if (p.id === id) return p;
  }
  return null;
}

/* 选中节奏型时，把它的**波长串**自动填进输入框（26 版速查表给的官方波长）。
   ★ 官方没给固定波长（C4io / S3 这类"看阵"的）→ **清空**并提示，
     不能留着上一个节奏型的旧值（用户会以为那是官方值）。
   用户口径：波长串是**可选**的，io 高的阵本来就难精确控波长。 */
function plFillGaps(q) {
  const g = (q && q.gaps) || [];
  const box = document.getElementById('pl-gaps');
  const tip = document.getElementById('pl-gaps-tip');
  const ok = g.length && !g.some(function (x) { return x === null || x === undefined; });
  if (box) box.value = ok ? ('(' + g.join(',') + ')') : '';
  if (tip) {
    tip.textContent = ok
      ? '官方波长 ' + g.join(' / ') + 's（循环 ' +
        (g.reduce(function (a, b) { return a + (+b || 0); }, 0)) + 's）'
      : '这个节奏型官方没给固定波长 —— 按实战填，留空就不校验';
  }
}
/* 节奏型下拉里的显示：`P3n ｜ 12,12,12` —— 一眼看到波长 */
function plPresetLabel(q) {
  const g = (q && q.gaps) || [];
  const ok = g.length && !g.some(function (x) { return x === null || x === undefined; });
  return plName(q) + (ok ? ' ｜ ' + g.join(',') : '');
}

const PL_CMP = ['>=', '<=', '>', '<', '=='];
const PL_STATE = [['ice_stock', '存冰数（场上有几颗寒冰菇）'], ['sun', '阳光'],
                  ['zombies_in_row', '本路僵尸数'], ['zombies_total', '场上僵尸数'],
                  ['wave_hp', '本波剩余血量'],
                  ['cobs_ready', '已装填完毕的玉米炮门数'],
                  ['front_x', '本路最靠前僵尸的 x（px）']];
const PL_DEFAULTS = {
  dist: { zombie: '任意', row: 6, col: 6, axis: 'x', cmp: '<=', value: 160 },
  state: { what: 'sun', cmp: '>=', value: 100 },
  card: { name: '寒冰菇', offset: 0 },
  card_ready: { card: '寒冰菇', offset: 0 },
  card_ready_within: { card: '樱桃', waves: 0.9 },
  plant_count: { plant: '寒冰菇', cmp: '>=', value: 1 },
  cell_is: { row: 3, col: 2, plant: '' },
  kernel_slack: { cmp: '>=', value: 0 },
  time: { at: 0 },
  after: { at: 0 },
  prev: { back: 1, target: 'set', set: 0, op: '辣椒', negate: false },
  zombie_in_window: { rows: [6, 5, 1], col: 6, window: [10, 75], min_hp: 500, zombie: '任意' },
  heavy_near_core: { rows: [6, 5, 2, 1], cells: 3 },
  cell_threat: { row: 2, col: 6, cells: 0 },
  wave: { from: 1, to: 20 },
};
function plFill(node, kind) {
  const d = PL_DEFAULTS[kind];
  if (!d) return;
  for (const k of Object.keys(d))
    if (node[k] === undefined || node[k] === null) node[k] = plDeep(d[k]);
}

/* ---- 条件编辑器（递归） ---- */
function plCond(c, path, kinds) {
  c = c || { kind: (kinds[0] || {}).kind || 'always' };
  const k = c.kind || 'always';
  const plants = PLAN.cat.cards.concat(['寒冰菇', '存冰', '忧郁菇', '冰瓜', '大喷菇']);
  let extra = '';
  if (k === 'card_ready' || k === 'card' || k === 'card_ready_within') {
    extra = plSel(path, 'card', c.card || c.name || '寒冰菇', plCardOpts())
      + (k === 'card_ready_within' ? plNum(path, 'waves', c.waves === undefined ? 0.9 : c.waves, 50)
        : plNum(path, 'offset', c.offset || 0, 50));
  } else if (k === 'plant_count' || k === 'ice_stock') {
    extra = plSel(path, 'plant', c.plant || '寒冰菇', Array.from(new Set(plants)))
      + plSel(path, 'cmp', c.cmp || '>=', PL_CMP) + plNum(path, 'value', c.value === undefined ? 1 : c.value, 50);
  } else if (k === 'cell_is') {
    extra = '<span class="hint">格</span>' + plNum(path, 'row', c.row || 3, 38) + '-'
      + plNum(path, 'col', c.col || 2, 38)
      + '<span class="hint">是</span>'
      + plSel(path, 'plant', c.plant || '', [['', '（空）']].concat(plants.map(function (x) { return [x, x]; })));
  } else if (k === 'kernel_slack') {
    extra = plSel(path, 'cmp', c.cmp || '>=', PL_CMP) + plNum(path, 'value', c.value || 0, 52);
  } else if (k === 'time' || k === 'after') {
    extra = plNum(path, 'at', c.at || 0, 62) + '<span class="hint">cs</span>';
  } else if (k === 'after_block') {
    // ★ 2026-10-23：定时 —— 距"某一块具体积木"（w3-1-1）生效后 N cs
    extra = '<span class="hint">距</span>'
      + '<input type="text" style="width:96px" value="' + plEsc(c.id || '') + '"'
      + ' data-act="setpath" data-path="' + path + '.id">'
      + '<span class="hint">生效后</span>' + plNum(path, 'delay', c.delay || 0, 62)
      + '<span class="hint">cs</span>';
  } else if (k === 'since') {
    // ★ 2026-10-22：跨波锚点 —— 距上次某个积木生效 N cs 之后
    extra = plSel(path, 'op', c.op || '玉米炮', (PLAN.cat.ops || []).map(function (o) { return [o.name, o.name]; }))
      + '<span class="hint">生效后</span>' + plNum(path, 'at', c.at || 8800, 62)
      + '<span class="hint">cs</span>';
  } else if (k === 'dist') {
    extra = plSel(path, 'zombie', c.zombie || '任意', ZOMBIES)
      + '<span class="hint">到</span>' + plNum(path, 'row', c.row || 6, 36) + '-'
      + plNum(path, 'col', c.col || 6, 36)
      + plSel(path, 'axis', c.axis || 'x', [['x', '水平'], ['row', '竖向']])
      + plSel(path, 'cmp', c.cmp || '<=', PL_CMP) + plNum(path, 'value', c.value === undefined ? 160 : c.value, 56)
      + '<span class="hint">px</span>';
  } else if (k === 'state') {
    extra = plSel(path, 'what', c.what || 'sun', PL_STATE)
      + ((c.what === 'zombies_in_row' || c.what === 'front_x')
         ? plNum(path, 'row', c.row || 6, 36) : '')
      + plSel(path, 'cmp', c.cmp || '>=', PL_CMP) + plNum(path, 'value', c.value || 0, 54);
  } else if (k === 'prev') {
    const tgt = c.target || 'set';
    extra = '<span class="hint">往前</span>' + plNum(path, 'back', c.back || 1, 40)
      + '<span class="hint">波</span>'
      + plSel(path, 'target', tgt, [['set', '选中的候选'], ['act', '真正打出的动作']])
      + (tgt === 'set' ? '<span class="hint">候选#</span>' + plNum(path, 'set', c.set === undefined ? 0 : c.set, 40) : '')
      + '<span class="hint">含</span>'
      + plSel(path, 'op', c.op || '', [['', '（任意）']].concat(PLAN.cat.ops.map(function (o) { return [o.name, o.name]; })))
      + '<label class="hint"><input type="checkbox" data-path="' + path +
        '" data-key="negate"' + (c.negate ? ' checked' : '') + '>取反</label>';
  } else if (k === 'zombie_in_window') {
    extra = '<span class="hint">路</span>' + plArr(path, 'rows', c.rows || [6, 5, 1], 74)
      + '<span class="hint">列</span>' + plNum(path, 'col', c.col || 6, 36)
      + '<span class="hint">窗口</span>' + plArr(path, 'window', c.window || [10, 75], 74)
      + '<span class="hint">hp≥</span>' + plNum(path, 'min_hp', c.min_hp || 0, 56)
      + plSel(path, 'zombie', c.zombie || '任意', ZOMBIES);
  } else if (k === 'heavy_near_core') {
    extra = '<span class="hint">路</span>' + plArr(path, 'rows', c.rows || [6, 5, 2, 1], 80)
      + '<span class="hint">≤</span>' + plNum(path, 'cells', c.cells === undefined ? 3 : c.cells, 40)
      + '<span class="hint">格</span>';
  } else if (k === 'cell_threat') {
    extra = '<span class="hint">格</span>' + plNum(path, 'row', c.row || 2, 36) + '-'
      + plNum(path, 'col', c.col || 6, 36)
      + '<span class="hint">≤</span>' + plNum(path, 'cells', c.cells === undefined ? 1 : c.cells, 40)
      + '<span class="hint">格</span>';
  } else if (k === 'wave') {
    extra = '<span class="hint">w</span>' + plNum(path, 'from', c.from || 1, 44)
      + '<span class="hint">~ w</span>' + plNum(path, 'to', c.to || 20, 44);
  } else if (k === 'all' || k === 'any' || k === 'not') {
    const subs = c.of || [];
    extra = '<div style="display:flex;flex-direction:column;gap:3px;width:100%">'
      + subs.map(function (sb, i) {
        return '<div style="display:flex;gap:4px;align-items:center">'
          + '<span class="hint">' + (k === 'not' ? '非' : '·') + '</span>'
          + plCond(sb, path + '.of.' + i, kinds)
          + '<button class="ghost mini2" data-act="delCond" data-path="' + path + '.of.' + i + '">✕</button></div>';
      }).join('')
      + '<div><button class="ghost mini2" data-act="addCond" data-path="' + path + '">+ 子条件</button></div></div>';
  }
  const list = kinds.map(function (g) { return [g.kind, g.label || g.kind]; });
  return '<span class="cond">' + plSel(path, 'kind', k, list) + extra + '</span>';
}

function plTrigLabel(t) {
  t = t || { kind: 'spawn' };
  if (!t.kind || t.kind === 'spawn') return '即刻';
  if (t.kind === 'time') return '波内' + (t.at || 0) + 'cs';
  if (t.kind === 'after') return '接上块+' + (t.at || 0) + 'cs';
  if (t.kind === 'card') return '等' + (t.name || '') + '好';
  if (t.kind === 'since') return '距' + (t.op || '上次') + '生效+' + (t.at || 0) + 'cs';
  if (t.kind === 'after_block') return '距 ' + (t.id || '?') + ' +' + (t.delay || 0) + 'cs';
  if (t.kind === 'dist') return '等到' + (t.zombie || '任意') + '距 ' + (t.row || '') + '-' + (t.col || '') + (t.cmp || '') + (t.value || '');
  if (t.kind === 'state') {
    const nm = { cobs_ready: '炮已装填门数', front_x: '本路最靠前 x',
                 zombies_in_row: '本路僵尸数', zombies_total: '场上僵尸数',
                 wave_hp: '本波剩余血量', ice_stock: '存冰数', sun: '阳光' };
    return '等到' + (nm[t.what] || t.what || '') + (t.row ? ('(' + t.row + '路)') : '')
      + (t.cmp || '>=') + (t.value === undefined ? '' : t.value);
  }
  if (t.kind === 'all') return '等全部';
  if (t.kind === 'any') return '等任一';
  if (t.kind === 'not') return '等非';
  return t.kind;
}
/* 积木里的 op 是**标识符**（回传给服务器），显示时要换成官方英文名 */
function plOp(n) { return (typeof window.tcShow === 'function') ? window.tcShow(n) : n; }
function plAimLabel(b) {
  const a = b.aim;
  const num = function (v) {
    const f = parseFloat(v);
    return isNaN(f) ? String(v) : ((f === Math.round(f)) ? String(Math.round(f))
                                                         : f.toFixed(1));
  };
  if (a === 'stock') return ' · 空存冰位';
  if (a === 'temp') return ' · 前场临时冰位';
  if (Array.isArray(a)) {
    // ★ 2026-10-24：拦截炮 / 分离炮动态落点 / 常规炮的滑动落点
    if (a[1] === 'imp') return ' · 拦截小鬼（动态）';
    if (a[1] === 'dyn') {
      // 行号在检查器里已经能看到，chip 上只显示打了哪几种僵尸
      const ks = (b.dyn_kinds || []).map(function (k) { return plOp(k); });
      return ' · 动态落点（' + (ks.join('/') || '—') + '）';
    }
    if (a[1] === 'front') return ' · 滑动落点';
    if (a[1] === 'threat') return ' · 滑动落点（优先威胁）';
    return ' ' + num(a[0]) + '-' + num(a[1]);
  }
  return '';
}
function plAutoBlockId(w, si, i) { return 'w' + w + '-' + (si + 1) + '-' + (i + 1); }
function plBlockChip(b, i, si, on, wave) {
  const deck = plP().deck || [];
  const key = (PLAN.cat.card_key || {})[b.op];
  const missing = key && deck.indexOf(b.op) < 0;
  const rep = b.repeat ? ' ↻' : '';
  const bid = b.id || plAutoBlockId(wave || '?', si, i);
  return '<span class="chip ' + (on ? 'on ' : '') + (missing ? 'no' : '') +
    '" data-act="selBlock" data-set="' + si + '" data-block="' + i + '">' +
    '<small class="bid" title="积木 ID（after_block 触发器靠它定位）">#' + plEsc(bid) + '</small> ' +
    plEsc(plOp(b.op)) + plEsc(plAimLabel(b)) + rep +
    '<small> ' + plEsc(plTrigLabel(b.trig)) + '</small></span>';
}
function plGateText(st) {
  const c = st.when || {};
  if (!c.kind || c.kind === 'always') return '总是';
  if (c.kind === 'card_ready') return '卡好：' + (c.card || '');
  if (c.kind === 'card_ready_within') return (c.card || '') + ' ' + (c.waves || 0.9) + ' 波内好';
  if (c.kind === 'plant_count') return (c.plant || '') + ' ' + (c.cmp || '>=') + ' ' + (c.value || 0);
  if (c.kind === 'cell_is') return c.row + '-' + c.col + '=' + (c.plant || '空');
  if (c.kind === 'kernel_slack') return '核坑有余量';
  if (c.kind === 'prev') return '上一波' + (c.target === 'act' ? '打了' : '选了') + (c.op || ('候选' + c.set));
  if (c.kind === 'all') return '全部满足';
  if (c.kind === 'any') return '任一满足';
  if (c.kind === 'not') return '取反';
  return c.kind;
}

"""
SCRIPT += r"""
/* ---------------- 渲染：阵解库 / 选卡 ---------------- */
function plRenderBank() {
  document.getElementById('pl-bank').innerHTML = PLAN.bank.map(function (b, i) {
    return '<option value="' + i + '"' + (i === PLAN.active ? ' selected' : '') + '>' +
      plEsc(plFull(b.plan)) + '</option>';
  }).join('');
}
function plRenderDeck() {
  const deck = plP().deck || [];
  const plants = PLAN.cat.plants || PLAN.cat.cards;
  // ★ 2026-10-24 用户：**已经被选走的植物不再出现在别的卡槽里**
  //   · 普通植物：别的槽已经选了它 → 这个槽不再显示这个选项
  //   · 模仿者：别的槽已经占了模仿者 → 这个槽不再显示「模仿者（模仿）」
  //   · 但"被模仿的植物"仍然可以当普通卡选（模仿者:寒冰菇 不占用 寒冰菇 这个名字）
  const usedPlain = {};          // 别的槽用掉的普通植物名
  let mimicTaken = false;
  deck.forEach(function (c, i) {
    if (!c) return;
    if (c.indexOf(MIMIC_TAG + ':') === 0) { mimicTaken = true; return; }
    if (c === MIMIC_TAG) { mimicTaken = true; return; }
    usedPlain[c] = i;
  });
  let h = '';
  for (let i = 0; i < 10; i++) {
    const cur = deck[i] || '';
    const mimic = cur.indexOf(MIMIC_TAG + ':') === 0 || cur === MIMIC_TAG;
    const target = cur.indexOf(MIMIC_TAG + ':') === 0 ? cur.split(':')[1] : '';
    const shown = cur;
    // 本槽自己占用的普通植物名（要保留在选项里）
    const own = (!mimic && cur) ? cur : '';
    h += '<div class="slot"><b>' + (i + 1) + '</b>'
      + '<select data-deck="' + i + '">'
      + '<option value=""' + (cur ? '' : ' selected') + '>（空）</option>'
      + plants.filter(function (c) {
          // 被别的槽选走的普通植物 → 不显示（自己这槽的除外）
          return c === own || usedPlain[c] === undefined;
        }).map(function (c) {
        return '<option value="' + plEsc(c) + '"' + (!mimic && shown === c ? ' selected' : '') + '>'
          + plEsc(c) + '</option>';
      }).join('')
      + (mimic || !mimicTaken
        ? '<option value="' + MIMIC_TAG + '"' + (mimic ? ' selected' : '') + '>'
          + MIMIC_TAG + '（模仿）</option>'
        : '')
      + '</select>'
      + (mimic
        ? '<select data-mimic="' + i + '">'
          + plants.map(function (c) {
            return '<option value="' + plEsc(c) + '"' + (target === c ? ' selected' : '') + '>'
              + plEsc(c) + '</option>';
          }).join('') + '</select>'
        : '')
      + '</div>';
  }
  document.getElementById('pl-deck').innerHTML = h;
}

/* ---------------- 渲染：波列表 ---------------- */
function plRenderWaveList() {
  const p = plP();
  document.getElementById('pl-waves').innerHTML = p.waves.map(function (row) {
    const ops = (row.sets || []).map(function (st) {
      return (st.ops || []).map(function (o) { return plOp(o.op); }).join('+');
    }).slice(0, 2).join(' / ');
    const mk = PLAN.marks.has(row.w);
    return '<div class="wrow' + (row.w === PLAN.sel.wave ? ' on' : '') + (mk ? ' marked' : '')
      + '" data-act="selWave" data-w="' + row.w + '">'
      + '<input class="mk" type="checkbox" data-mark="' + row.w + '"' + (mk ? ' checked' : '') + '>'
      + '<span class="rw">w' + row.w + '</span>'
      + '<span class="rr">' + plEsc(PLAN.cat.roles[String(row.w)] || '') + '</span>'
      + '<span style="color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
      + plEsc(ops || '—') + '</span>'
      + '<span class="rb">' + (row.sets || []).length + '</span></div>';
  }).join('');
  document.getElementById('pl-marks').textContent =
    PLAN.marks.size ? ('已勾选 ' + PLAN.marks.size + ' 波') : '';
}
function plMove(path, d) {
  const arr = plPath(plP(), path.replace(/\.[^.]+$/, ''));
  const i = +path.split('.').pop(), j = i + d;
  if (j < 0 || j >= arr.length) return;
  const t = arr[i]; arr[i] = arr[j]; arr[j] = t;
}
/* ★ 2026-10-24：候选**里面**的积木也能前后移动 / 复制粘贴 */
function plMoveBlock(path, d) {
  const p = plP();
  const arr = plPath(p, path.replace(/\.[^.]+$/, ''));
  const i = +path.split('.').pop(), j = i + d;
  if (j < 0 || j >= arr.length) return;
  const t = arr[i]; arr[i] = arr[j]; arr[j] = t;
  PLAN.sel.block = j;
}
function plRenumber(arr) {
  // ★ 2026-10-24：结构一变（增删 / 前后移 / 粘贴）就**整组重排** ID。
  //   ID 的语义就是波数-候选-序号，按位置重排最不容易出重名；
  //   不重排的话粘贴出来的块会和被复制的块撞名（after_block 就指错了）。
  const w = PLAN.sel.wave, si = Math.max(0, PLAN.sel.set);
  (arr || []).forEach(function (b, i) { b.id = plAutoBlockId(w, si, i); });
}

/* ---------------- 渲染：某一波 ---------------- */
function plRenderWave() {
  const p = plP();
  const idx = p.waves.findIndex(function (r) { return r.w === PLAN.sel.wave; });
  const box = document.getElementById('pl-wavebox');
  if (idx < 0) { box.innerHTML = '<div class="hint">左边选一波</div>'; return; }
  const row = p.waves[idx];
  const base = 'waves.' + idx;
  const sets = (row.sets || []).map(function (st, si) {
    const sp = base + '.sets.' + si;
    let chain = '';
    (st.ops || []).forEach(function (b, bi) {
      chain += plBlockChip(b, bi, si, PLAN.sel.set === si && PLAN.sel.block === bi, row.w)
        + '<button class="ghost mini2" data-act="delBlock" data-path="' + sp + '.ops.' + bi + '">✕</button>'
        + '<span class="arrow">→</span>';
    });
    return '<div class="set">'
      + '<div class="sethead"><b>候选 ' + (si + 1) + '</b><span class="hint">当</span>'
      + plCond(st.when, sp + '.when', PLAN.cat.gates)
      + '<span style="margin-left:auto"></span>'
      + '<button class="ghost mini2" data-act="upSet" data-path="' + sp + '">↑</button>'
      + '<button class="ghost mini2" data-act="downSet" data-path="' + sp + '">↓</button>'
      + '<button class="ghost mini2" data-act="delSet" data-path="' + sp + '">✕</button></div>'
      + '<div class="chain">' + chain
      + '<button class="ghost mini2" data-act="addBlock" data-path="' + sp + '.ops">+ 积木</button>'
      + '<button class="ghost mini2" data-act="addCob" data-path="' + sp + '.ops" title="直接放一块玉米炮（P 常规炮 + 滑动落点）">+ 炮</button>'
      + '<span class="hint" style="margin-left:8px">条件不成立就整组跳过、试下一个候选</span></div>'
      + plInspector(st, sp, si) + '</div>';
  }).join('');
  box.innerHTML = '<div style="margin-bottom:6px" class="hint">'
    + '第 w' + row.w + ' 波 · ' + plEsc(PLAN.cat.roles[String(row.w)] || '') + ' · '
    + '<input type="text" id="pl-wavenote" value="' + plEsc(row.note || '') + '" '
    + 'placeholder="这一波的备注（给人看的）" style="width:330px;font-size:11.5px">'
    + (row.role === '旗波' ? ' <span class="hint">旗波：快捷布置不会动它</span>' : '')
    + '</div>' + sets
    + '<button class="ghost" data-act="addSet" data-path="' + base + '.sets">+ 加一个候选（兜底）</button>';
}

function plAimEditor(bp, b) {
  const a = b.aim;
  let mode = 'none';
  if (a === 'stock') mode = 'stock';
  else if (a === 'temp') mode = 'temp';
  else if (Array.isArray(a) && a[1] === 'imp') mode = 'imp';
  else if (Array.isArray(a) && a[1] === 'dyn') mode = 'dyn';
  else if (Array.isArray(a) && (a[1] === 'front' || a[1] === 'threat')) mode = 'slide';
  else if (Array.isArray(a)) mode = 'cell';
  const arr = Array.isArray(a) ? a : [3, 2];
  const isCob = b.op === '玉米炮';
  const opts = [['none', '不给（默认策略）']];
  if (isCob) {
    opts.push(['slide', '滑动落点（按最靠前那只自动挑列）']);
    opts.push(['dyn', '分离炮动态落点（按僵尸种类 + 行，滑动找点）']);
    opts.push(['imp', '拦截动态落点（炸空中的小鬼）']);
  }
  opts.push(['cell', isCob ? '指定爆心（可带小数）' : '指定格子']);
  opts.push(['stock', '空着的永久存冰位'], ['temp', '前场临时冰位']);
  // 「分离炮动态落点」要选：行 + 打哪几种僵尸
  const dynRows = [1, 2, 3, 4, 5, 6].map(function (r) {
    return [String(r), String(r) + ' 路'];
  });
  const kinds = (PLAN.cat.kinds || []).map(function (k) { return [k, k]; });
  const picked = (b.dyn_kinds || []);
  return '<span data-aimmode="' + bp + '">'
    + '<select data-aim="' + bp + '">'
    + opts.map(function (o) {
        return '<option value="' + o[0] + '"' + (o[0] === mode ? ' selected' : '') + '>' + o[1] + '</option>';
      }).join('')
    + '</select> '
    + (mode === 'dyn'
      ? '<label style="margin-left:6px">行</label>'
        + '<select data-dynrow="' + bp + '">'
        + dynRows.map(function (o) {
            return '<option value="' + o[0] + '"'
              + (String(arr[0]) === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
          }).join('') + '</select>'
        + '<label style="margin-left:6px">打</label>'
        + '<select data-dynkind="' + bp + '" multiple size="1" '
        + 'style="min-width:96px;height:44px" title="可多选（Ctrl / Shift）">'
        + kinds.map(function (o) {
            return '<option value="' + plEsc(o[0]) + '"'
              + (picked.indexOf(o[0]) >= 0 ? ' selected' : '') + '>' + plEsc(o[1]) + '</option>';
          }).join('') + '</select>'
      : '')
    + (mode === 'cell'
      ? ('<input type="number" step="0.1" data-aimrc="' + bp + '" data-k="0" value="' + arr[0]
        + '" style="width:56px" title="行（可带一位小数）"> - '
        + '<input type="number" step="0.1" data-aimrc="' + bp + '" data-k="1" value="' + arr[1]
        + '" style="width:56px" title="列（可带一位小数）">')
      : '')
    + '</span>';
}

function plInspector(st, sp, si) {
  if (PLAN.sel.set !== si || PLAN.sel.block < 0) return '';
  const b = (st.ops || [])[PLAN.sel.block];
  if (!b) return '';
  const bp = sp + '.ops.' + PLAN.sel.block;
  const spec = PLAN.cat.ops.find(function (o) { return o.name === b.op; }) || {};
  const rep = b.repeat;
  const autoBid = plAutoBlockId(PLAN.sel.wave,
                                PLAN.sel.set, PLAN.sel.block);
  return '<div class="insp"><div class="row"><b>积木：' + plEsc(plOp(b.op)) + '</b>'
    + '<span class="hint">（' + plEsc(spec.note || '') + '）</span>'
    + '<label style="margin-left:12px">ID</label>'
    + '<input type="text" data-path="' + bp + '" data-key="id" value="'
    + plEsc(b.id || '') + '" placeholder="' + plEsc(autoBid)
    + '" style="width:96px;font-size:11.5px" '
    + 'title="唯一命名：波数-候选-序号；after_block 用它定位"></div>'
    + '<div class="row"><label>动作</label>'
    + plSel(bp, 'op', b.op, plOps().map(function (o) { return [o.name, o.name]; }))
    + (b.op === '玉米炮'
       ? '<label style="margin-left:10px">炮种</label>'
         + plSel(bp, 'cob', b.cob || 'P',
                 [['P', 'P 常规炮'], ['S', 'S 分离炮'], ['D', 'D 拦截炮']])
         + (b.cob === 'D'
            ? '<label style="margin-left:10px">拦截时机</label>'
              + plSel(bp, 'imp_when', b.imp_when || 'apex',
                      [['release', '投掷刚刚出手时'], ['apex', '飞行到最高点时'],
                       ['land', '小鬼将要落地时']])
              + '<label style="margin-left:10px">管哪几路</label>'
              + plSel(bp, 'imp_group', b.imp_group || 'low',
                      [['low', '1~3 路'], ['high', '4~6 路'], ['any', '全部']])
            : '')
       : '')
    + '<label style="margin-left:10px">落点</label>' + plAimEditor(bp, b) + '</div>'
    + '<div class="row"><label>触发器</label>'
    + plCond(b.trig || { kind: 'spawn' }, bp + '.trig', PLAN.cat.triggers) + '</div>'
    + '<div class="row"><label>循环</label>'
    + '<label class="hint"><input type="checkbox" id="pl-usep"' + (rep ? ' checked' : '') + '>启用</label>'
    + '每 <input type="number" id="pl-rep-every" value="' + ((rep && rep.every) || 100) + '" style="width:58px"> cs'
    + ' 共 <input type="number" id="pl-rep-times" value="' + (rep && rep.times != null ? rep.times : '') + '" style="width:50px" placeholder="∞"> 次'
    + '<span class="hint">（留空 = 一直循环）</span></div>'
    + '<div class="row"><button class="ghost mini2" data-act="delBlock" data-path="' + bp + '">删除这块</button>'
    + '<button class="ghost mini2" data-act="upBlock" data-path="' + bp + '">↑ 前移</button>'
    + '<button class="ghost mini2" data-act="downBlock" data-path="' + bp + '">↓ 后移</button>'
    + '<button class="ghost mini2" data-act="copyBlock" data-path="' + bp + '">⎘ 复制</button>'
    + '<button class="ghost mini2" data-act="pasteBlock" data-path="' + bp + '">⎗ 粘贴到此块后</button>'
    + '<button class="ghost mini2" data-act="selBlock" data-set="' + si + '" data-block="-1">收起</button></div></div>';
}

/* ---------------- 渲染：全场判定 ---------------- */
function plRenderGlobals() {
  const p = plP();
  const rules = p.globals || [];
  document.getElementById('pl-globals').innerHTML = rules.length ? rules.map(function (r, i) {
    const on = PLAN.sel.g === i;
    let chain = '';
    (r.ops || []).forEach(function (b, bi) {
      chain += '<span class="chip">' + plEsc(plOp(b.op)) + plEsc(plAimLabel(b)) + '</span>'
        + '<button class="ghost mini2" data-act="delGOp" data-path="globals.' + i + '.ops.' + bi + '">✕</button>';
    });
    return '<div class="rule"><div class="rh">'
      + '<input type="checkbox" data-g-en="' + i + '"' + (r.enabled !== false ? ' checked' : '') + '>'
      + '<input type="text" data-path="globals.' + i + '" data-key="id" value="' + plEsc(r.id || ('全场' + (i + 1))) + '" style="width:110px;font-size:12px">'
      + '<span class="hint" style="font-weight:400">' + plEsc(r.note || '') + '</span>'
      + '<span style="margin-left:auto"></span>'
      + '<button class="ghost mini2" data-act="selGlobal" data-g="' + i + '">' + (on ? '收起' : '编辑') + '</button>'
      + '<button class="ghost mini2" data-act="delGlobal" data-g="' + i + '">✕</button></div>'
      + (on ? '<div class="row" style="margin-top:6px"><label>条件</label>'
        + plCond(r.when || { kind: 'always' }, 'globals.' + i + '.when', PLAN.cat.gates)
        + '</div><div class="row"><label>做</label>' + chain
        + '<button class="ghost mini2" data-act="addGOp" data-path="globals.' + i + '.ops">+ 积木</button></div>'
        + '<div class="row"><label>每隔</label>' + plNum('globals.' + i, 'every', r.every === undefined ? 50 : r.every, 52)
        + '<span class="hint">cs 判一次 · 冷却</span>' + plNum('globals.' + i, 'cooldown', r.cooldown || 0, 52)
        + '<span class="hint">cs · 备注</span>'
        + '<input type="text" data-path="globals.' + i + '" data-key="note" value="' + plEsc(r.note || '') + '" style="width:220px;font-size:11.5px">'
        + '</div>' : '') + '</div>';
  }).join('') : '<div class="hint">还没有全场判定规则</div>';
}

/* ---------------- 渲染：简化救场 ---------------- */
const S_RES_DEFAULT = ['小喷菇', '花盆', '阳光菇', '胆小菇', '窝瓜', '樱桃', '辣椒', '咖啡豆'];
function plSResOptions(p) {
  const deck = (p.deck || []).filter(function (c) { return c !== '玉米炮'; });
  const list = deck.length ? deck : S_RES_DEFAULT;
  return list.map(function (c) {
    const v = plEsc(c);
    const t = plEsc(String(c).replace('模仿者:', '模仿'));
    return '<option value="' + v + '">' + t + '</option>';
  }).join('');
}
function plRenderSimple() {
  const p = plP();
  const s = p.rescue_simple || (p.rescue_simple = { enabled: true, resources: [], targets: [] });
  let res = '';
  (s.resources || []).forEach(function (b, i) {
    res += '<span class="chip">' + plEsc(plOp(b.op)) + plEsc(plAimLabel(b)) + '</span>'
      + '<button class="ghost mini2" data-act="delSRes" data-i="' + i + '">✕</button>';
  });
  const rows = (s.targets || []).map(function (t, i) {
    const pr = t.protect || {};
    return '<tr>'
      + '<td><input type="text" data-path="rescue_simple.targets.' + i + '" data-key="id" value="' + plEsc(t.id || '') + '" style="width:96px"></td>'
      + '<td>' + plNum('rescue_simple.targets.' + i + '.protect', 'row', pr.row || 1, 38) + '-'
      + plNum('rescue_simple.targets.' + i + '.protect', 'col', pr.col || 1, 38) + '</td>'
      + '<td>' + plNum('rescue_simple.targets.' + i, 'urgency_cells', t.urgency_cells === undefined ? 1 : t.urgency_cells, 44)
      + '<span class="hint">格</span></td>'
      + '<td>' + plNum('rescue_simple.targets.' + i, 'priority', t.priority === undefined ? 10 : t.priority, 48) + '</td>'
      + '<td>' + plNum('rescue_simple.targets.' + i, 'cooldown', t.cooldown === undefined ? 60 : t.cooldown, 48) + '</td>'
      + '<td><button class="ghost mini2" data-act="delSTgt" data-i="' + i + '">✕</button></td></tr>';
  }).join('');
  document.getElementById('pl-simple').innerHTML =
    '<div class="row"><label class="hint"><input type="checkbox" id="pl-simple-en"'
    + (s.enabled !== false ? ' checked' : '') + '>启用简化救场</label>'
    + '<span class="hint">' + plEsc(s.note || '') + '</span></div>'
    + '<div class="row" style="margin-top:6px"><label>救场资源</label>' + (res || '<span class="hint">（没有）</span>')
    + '<select id="pl-sres-sel">' + plSResOptions(p) + '</select>'
    + '<button class="ghost mini2" data-act="addSRes">+ 加资源</button></div>'
    + '<div class="hint" style="margin:6px 0">资源按顺序试：用不了（CD / 没位置）就换下一份。'
    + '列表来自「选卡」卡槽 —— 卡槽里没有的卡救场也用不出来。</div>'
    + '<table class="maptable"><tr><th>要保的</th><th>格子</th><th>急迫级</th><th>优先级</th><th>冷却cs</th><th></th></tr>'
    + (rows || '<tr><td colspan="6" class="hint">还没有要保护的目标</td></tr>') + '</table>'
    + '<button class="ghost mini2" data-act="addSTgt" style="margin-top:6px">+ 加要保护的植物</button>'
    + '<div class="hint" style="margin-top:4px">急迫级 = 僵尸距它还有几格就开始救（0 = 贴脸才救）；'
    + '优先级 = 都在危险里时谁先救（数值大的先）。</div>';
}

/* ---------------- 渲染：详细救场 ---------------- */
function plRenderRescue() {
  const p = plP();
  const rules = p.rescue || [];
  document.getElementById('pl-rescue').innerHTML = rules.length ? rules.map(function (r, ri) {
    const on = PLAN.sel.rule === ri;
    const levels = (r.levels || []).map(function (lv, li) {
      const ops = Array.isArray(lv) ? lv : (lv.ops || []);
      let chips = '';
      ops.forEach(function (b, bi) {
        chips += '<span class="chip">' + plEsc(plOp(b.op)) + plEsc(plAimLabel(b)) + '</span>'
          + '<button class="ghost mini2" data-act="delLevelOp" data-path="rescue.' + ri + '.levels.' + li + '.' + bi + '">✕</button>';
      });
      return '<div class="lvl"><span class="hint">第 ' + (li + 1) + ' 层</span>' + chips
        + '<button class="ghost mini2" data-act="addLevelOp" data-path="rescue.' + ri + '.levels.' + li + '">+ 积木</button></div>';
    }).join('');
    return '<div class="rule"><div class="rh"><span class="rid">' + plEsc(r.id || ('规则' + (ri + 1))) + '</span>'
      + '<span class="hint" style="font-weight:400">' + plEsc(r.note || '') + '</span>'
      + '<span style="margin-left:auto"></span>'
      + '<button class="ghost mini2" data-act="selRule" data-rule="' + ri + '">' + (on ? '收起' : '编辑') + '</button>'
      + '<button class="ghost mini2" data-act="delRule" data-rule="' + ri + '">✕</button></div>'
      + (on ? '<div class="row" style="margin-top:6px"><label>事件</label>'
        + plCond(r.event || { kind: 'always' }, 'rescue.' + ri + '.event', PLAN.cat.events)
        + '<label style="margin-left:10px">冷却</label>' + plNum('rescue.' + ri, 'cooldown', r.cooldown === undefined ? 30 : r.cooldown, 58)
        + '<span class="hint">cs</span></div>' + levels
        + '<button class="ghost mini2" data-act="addLevel" data-rule="' + ri + '">+ 再兜一层</button>' : '')
      + '</div>';
  }).join('') : '<div class="hint">还没有详细救场规则（简化救场已经能覆盖大部分场景）</div>';
}

/* ---------------- 渲染：匹配表 ---------------- */
function plRenderMap() {
  const box = document.getElementById('pl-map');
  const q = (typeof queue !== 'undefined' && Array.isArray(queue)) ? queue : [];
  if (!q.length) { box.innerHTML = '<div class="hint">出怪列表还是空的 —— 先去「出怪沙盘」加几组</div>'; return; }
  box.innerHTML = '<table class="maptable"><tr><th>出怪组</th><th>种类</th><th>次数</th><th>用哪套阵解</th></tr>'
    + q.map(function (it, i) {
      const opts = ['<option value="">（不绑阵解 · 空轨道）</option>'].concat(PLAN.bank.map(function (b) {
        return '<option value="' + plEsc(b.id) + '"' + (it.planId === b.id ? ' selected' : '') + '>'
          + plEsc(plFull(b.plan)) + '</option>';
      })).join('');
      return '<tr><td>' + plEsc(it.name || ('组' + (i + 1))) + '</td>'
        + '<td>' + (it.kinds || []).length + ' 种</td><td>' + (it.seeds || 1) + '</td>'
        + '<td><select data-map="' + i + '">' + opts + '</select></td></tr>';
    }).join('') + '</table>'
    + '<div class="hint" style="margin-top:4px">在「运行」标签页点开始，会按这张表给每组配上阵解。</div>';
}

"""
SCRIPT += r"""
/* ---------------- 总渲染 ---------------- */
/* ★ 2026-10-22 命名规则：`[场地].名字` 是**阵型**的名字（在「① 阵容布置」里填）；
   阵解只写自己的名字，不再自动加场地前缀。 */
function plBare(name) {
  var s = String(name === undefined || name === null ? '' : name).trim();
  if (s.charAt(0) === '[') {
    var i = s.indexOf('].');
    if (i > 0) return s.slice(i + 2).trim();
  }
  return s;
}
function plFull(p) {
  p = p || plP();
  return plBare(p.name) || '未命名阵解';
}

/* ★ 2026-10-22：波长串 `(9,9,9,9)` / `(9|9|9|9)`，以及简写/复写设置 */
function plGapsParse(text) {
  var s = String(text || '').trim().replace(/[()（）\[\]]/g, '')
    .replace(/[|｜/,，\s]+/g, ' ').trim();
  if (!s) return [];
  var out = [], cs = false;
  s.split(' ').forEach(function (t) {
    var v = parseFloat(t);
    if (!isNaN(v) && v > 0) { out.push(v); if (v >= 100) cs = true; }
  });
  if (cs) out = out.map(function (v) { return v / 100; });
  return out;
}
function plGapsText(g) {
  if (!g || !g.length) return '';
  return '(' + g.map(function (v) { return (Math.round(v * 100) / 100); }).join(',') + ')';
}
const PAIR_KEY = 'tc.pairmode';
function plPairMode() {
  var ok = (PLAN.cat && PLAN.cat.pair_modes || []).map(function (x) { return x.id; });
  var v = localStorage.getItem(PAIR_KEY);
  return ok.indexOf(v) >= 0 ? v : ((PLAN.cat && PLAN.cat.pair_default) || 'auto');
}
function plSetPairMode(v) {
  localStorage.setItem(PAIR_KEY, v);
  plSpectrumSoon();
  if (typeof renderSettings === 'function') renderSettings();
}
let plSpecTimer = null;
function plSpectrumSoon() {
  clearTimeout(plSpecTimer);
  plSpecTimer = setTimeout(plSpectrum, 260);
}
async function plSpectrum() {
  const box = document.getElementById('pl-spectrum');
  if (!box) return;
  const track = document.getElementById('pl-beats').value;
  const gaps = document.getElementById('pl-gaps').value;
  const d = await plPost('/api/plan/spectrum', { plan: plP(), track: track,
    gaps: gaps, n_cob: (typeof plCobCount === 'function') ? (plCobCount() || null) : null });
  if (!d || d.error || d.ok === false) {
    box.innerHTML = '<span style="color:#b91c1c">波长串读不出来：'
      + plEsc((d && d.error) || '') + '</span>';
    return;
  }
  if (!d.gaps || !d.gaps.length) {
    box.innerHTML = '<span class="hint">波长串（可选）：填了才会校验波长和够不够炮 / 卡的 CD 转完。'
      + 'IO 高的阵波长本来就难精确控制，可以不填。</span>';
    return;
  }
  const head = '波长和 <b>' + (Math.round(d.total * 100) / 100)
    + 's</b>　拍数 ' + d.beats + '　P ' + d.n_p + ' 发'
    + (d.unknown && d.unknown.length ? '　<span style="color:#b45309">不认识的记号：'
       + plEsc(d.unknown.join(' ')) + '</span>' : '');
  const cls = { bad: 'err', warn: 'warn', ok: 'ok' };
  const tag = { bad: '不可行', warn: '警告', ok: '通过' };
  box.innerHTML = head + (d.items || []).map(function (it) {
    return '<div class="issue ' + (cls[it.level] || 'ok') + '"><b>'
      + (tag[it.level] || it.level) + '</b> ' + plEsc(it.msg) + '</div>';
  }).join('');
}
function plRender() {
  if (!PLAN.bank.length) return;
  const p = plP();
  document.getElementById('pl-name').value = plBare(p.name);
  document.getElementById('pl-beats').value = (p.rhythm.beats || []).join(' | ');
  const gEl = document.getElementById('pl-gaps');
  if (gEl && document.activeElement !== gEl) gEl.value = plGapsText(p.rhythm.gaps);
  const stEl = document.getElementById('pl-start');
  if (stEl && document.activeElement !== stEl) stEl.value = (p.rhythm.start || 0);
  const gTip = document.getElementById('pl-gaps-tip');
  if (gTip) {
    const gg = p.rhythm.gaps || [];
    gTip.textContent = gg.length
      ? '循环 ' + gg.reduce(function (a, b) { return a + (+b || 0); }, 0) + 's（' + gg.length + ' 拍）'
      : '留空 = 不校验波长（io 高的阵本来难控）';
  }
  document.getElementById('pl-note').textContent = p.note || '';
  const sys = document.getElementById('pl-sys');
  sys.innerHTML = PLAN.cat.rhythms.map(function (r) {
    return '<option value="' + plEsc(r.system) + '"' + (r.system === p.rhythm.system ? ' selected' : '') + '>'
      + plEsc(plName(r.label)) + '</option>';
  }).join('');
  const cur = PLAN.cat.rhythms.find(function (r) { return r.system === p.rhythm.system; }) || { presets: [] };
  const pre = document.getElementById('pl-preset');
  pre.innerHTML = (cur.presets || []).length ? cur.presets.map(function (q) {
    return '<option value="' + plEsc(q.id) + '"' + (q.id === p.rhythm.id ? ' selected' : '') + '>'
      + plEsc(plPresetLabel(q)) + '</option>';
  }).join('') : '<option value="">（该系暂无预设）</option>';
  const info = document.getElementById('pl-rhythm-info');
  if (info) {
    const preset = plPreset(p.rhythm.id);
    info.textContent = [
      plName(cur.label) ? '系：' + plName(cur.label) : '',
      preset && preset.note ? '说明：' + preset.note : '',
      '命名方案：' + ({ '2021': '2021 传统', '2026': '2026 新版', 'both': '双轨' })[plNaming()],
    ].filter(Boolean).join('　·　');
  }
  plRenderBank(); plRenderDeck(); plRenderWaveList(); plRenderWave();
  plRenderGlobals(); plRenderSimple(); plRenderRescue(); plRenderMap();
  plSpectrumSoon();
}

/* ---------------- JSON 说明（i 按钮） ---------------- */
async function plSpec(what) {
  if (!PLAN.spec || !PLAN.spec[what]) {
    PLAN.spec = PLAN.spec || {};
    const r = await fetch('/api/spec?what=' + encodeURIComponent(what));
    PLAN.spec[what] = await r.text();
  }
  document.getElementById('pl-mod-title').textContent =
    ({ plan: '阵解 JSON 格式说明', spawn: '出怪列表 JSON 格式说明', config: '全场配置 JSON 格式说明' })[what] || 'JSON 格式说明';
  document.getElementById('pl-mod-body').textContent = PLAN.spec[what];
  document.getElementById('pl-mod').classList.add('on');
  document.getElementById('pl-mod').dataset.what = what;
}

document.addEventListener('click', function (e) {
  const inf = e.target.closest ? e.target.closest('i.info') : null;
  if (inf) { plSpec(inf.dataset.spec || 'plan'); return; }
});
document.getElementById('pl-mod').addEventListener('click', function (e) {
  const self = document.getElementById('pl-mod');
  if (e.target === self) { self.classList.remove('on'); return; }
  const b = e.target.closest ? e.target.closest('[data-act]') : null;
  if (!b) return;
  const a = b.dataset.act;
  const body = document.getElementById('pl-mod-body').textContent;
  if (a === 'specClose') self.classList.remove('on');
  else if (a === 'specCopy') {
    if (navigator.clipboard) navigator.clipboard.writeText(body).then(function () {
      b.textContent = '已复制'; setTimeout(function () { b.textContent = '复制全文'; }, 1200);
    }, function () { alert('复制失败，请手动选中'); });
    else alert('这个浏览器不让直接写剪贴板，请手动选中');
  } else if (a === 'specDown') {
    plDownload('trackcheck-json-' + (self.dataset.what || 'spec') + '.md', body);
  }
});

/* ---------------- 主事件：按钮 ---------------- */
const PL_ROOT = document.getElementById('planpage');
PL_ROOT.addEventListener('click', async function (e) {
  /* ★ 勾选框要先拦下来：它在一个 data-act="selWave" 的行里，
     不拦的话 click 会冒泡到行 → selWave → plRender() 整页重画，
     把刚打上的勾又抹掉（这就是"点了没反应"的原因）。 */
  const mkEl = e.target.closest ? e.target.closest('input[data-mark]') : null;
  if (mkEl) {
    const w = +mkEl.dataset.mark;
    if (mkEl.checked) PLAN.marks.add(w); else PLAN.marks.delete(w);
    plRenderWaveList();
    return;
  }
  const el = e.target.closest('[data-act]');
  if (!el) return;
  const act = el.dataset.act, path = el.dataset.path || '';
  // ★ 阵解库空的时候（理论上 boot 会给一套空模板）不要往下走，免得 plP() 抛错
  if (!PLAN.bank.length && act !== 'blank' && act !== 'newPlan'
      && act !== 'import' && act !== 'cfgImport') return;
  const p = plP();
  const H = {
    selWave: function () { PLAN.sel.wave = +el.dataset.w; PLAN.sel.set = -1; PLAN.sel.block = -1; },
    selBlock: function () { PLAN.sel.set = +el.dataset.set; PLAN.sel.block = +el.dataset.block; },
    selGlobal: function () { PLAN.sel.g = (PLAN.sel.g === +el.dataset.g ? -1 : +el.dataset.g); },
    selRule: function () { PLAN.sel.rule = (PLAN.sel.rule === +el.dataset.rule ? -1 : +el.dataset.rule); },
    addSet: function () { plSnap(); plPath(p, path).push({ when: { kind: 'always' }, ops: [] }); },
    delSet: function () { plSnap(); plPath(p, path.replace(/\.[^.]+$/, '')).splice(+path.split('.').pop(), 1); },
    upSet: function () { plSnap(); plMove(path, -1); },
    downSet: function () { plSnap(); plMove(path, +1); },
    addBlock: function () {
      plSnap();
      // ★ 2026-10-24：默认动作必须**是下拉里真的能选到的**那个 ——
      //   以前选卡为空时会塞一块"寒冰菇"，但下拉里根本没有这一项（选卡外的植物不列出），
      //   于是这块积木的动作显示为空。
      const list = plOps();
      const pick = list.find(function (o) { return o.group !== '炮'; }) || list[0]
        || { name: '寒冰菇' };
      const arr = plPath(p, path);
      const first = pick.name;
      const si = +(path.split('.')[3]) || 0;
      arr.push({ op: first, aim: null, trig: { kind: 'spawn' } });
      plRenumber(arr);
    },
    // ★ 2026-10-24 用户报的 bug：炮操作类以前只能靠「快捷布置阵解」生成，手放不了。
    //   这里给一个专门的「+ 炮」按钮：直接放一块正常的 P（常规炮、滑动落点）。
    addCob: function () {
      plSnap();
      const arr = plPath(p, path);
      const si = +(path.split('.')[3]) || 0;
      arr.push({ op: '玉米炮', cob: 'P', aim: [2, 'front'],
                 trig: { kind: 'spawn' } });
      plRenumber(arr);
      PLAN.sel.set = si;
      PLAN.sel.block = arr.length - 1;
    },
    // ★ 2026-10-24：积木的**前后移动 / 复制 / 粘贴**（和候选的 ↑↓ / 复制粘贴对齐）
    upBlock: function () {
      plSnap(); plMoveBlock(path, -1);
      plRenumber(plPath(p, path.replace(/\.[^.]+$/, '')));
    },
    downBlock: function () {
      plSnap(); plMoveBlock(path, +1);
      plRenumber(plPath(p, path.replace(/\.[^.]+$/, '')));
    },
    copyBlock: function () {
      const b = plPath(p, path);
      PLAN.bclip = JSON.parse(JSON.stringify(b || {}));
      delete PLAN.bclip.id;                       // 粘贴时重新分配唯一 ID
      plRender();
    },
    pasteBlock: function () {
      if (!PLAN.bclip) { alert('剪贴板是空的（先点一块积木「复制」）'); return; }
      plSnap();
      const arr = plPath(p, path.replace(/\.[^.]+$/, ''));
      const at = +path.split('.').pop();
      const nb = JSON.parse(JSON.stringify(PLAN.bclip));
      delete nb.id;
      arr.splice(at + 1, 0, nb);
      plRenumber(arr);
      PLAN.sel.block = at + 1;
      plRender();
    },
    delBlock: function () {
      plSnap();
      const arr = plPath(p, path.replace(/\.[^.]+$/, ''));
      arr.splice(+path.split('.').pop(), 1);
      plRenumber(arr);
      PLAN.sel.block = -1;
    },
    addCond: function () {
      plSnap();
      const c = plPath(p, path);
      if (!['all', 'any', 'not'].includes(c.kind)) {
        const prev = plDeep(c);
        for (const k of Object.keys(c)) delete c[k];
        c.kind = 'all'; c.of = [prev];
      } else { c.of = c.of || []; c.of.push({ kind: 'card_ready', card: '寒冰菇' }); }
    },
    delCond: function () {
      plSnap();
      plPath(p, path.replace(/\.of\.\d+$/, '')).of.splice(+path.split('.').pop(), 1);
    },
    addGlobal: function () {
      plSnap();
      p.globals = p.globals || [];
      p.globals.push({ id: '全场' + (p.globals.length + 1), enabled: true, every: 50, cooldown: 0,
        when: { kind: 'card_ready', card: '寒冰菇' },
        ops: [{ op: '寒冰菇', aim: 'stock', trig: { kind: 'spawn' } }] });
      PLAN.sel.g = p.globals.length - 1;
    },
    delGlobal: function () { plSnap(); p.globals.splice(+el.dataset.g, 1); PLAN.sel.g = -1; },
    addGOp: function () { plSnap(); plPath(p, path).push({ op: '寒冰菇', aim: 'stock', trig: { kind: 'spawn' } }); },
    delGOp: function () { plSnap(); plPath(p, path.replace(/\.[^.]+$/, '')).splice(+path.split('.').pop(), 1); },
    addSRes: function () {
    plSnap();
    const sel = document.getElementById('pl-sres-sel');
    p.rescue_simple.resources.push({ op: (sel && sel.value) || '小喷菇', aim: null });
  },
    delSRes: function () { plSnap(); p.rescue_simple.resources.splice(+el.dataset.i, 1); },
    addSTgt: function () {
      plSnap();
      p.rescue_simple.targets.push({ id: '目标' + (p.rescue_simple.targets.length + 1),
        protect: { row: 1, col: 5 }, urgency_cells: 1, priority: 10, cooldown: 60 });
    },
    delSTgt: function () { plSnap(); p.rescue_simple.targets.splice(+el.dataset.i, 1); },
    addRule: function () {
      plSnap();
      p.rescue = p.rescue || [];
      p.rescue.push({ id: '规则' + (p.rescue.length + 1), cooldown: 30,
        event: { kind: 'zombie_in_window', rows: [6, 5, 1], col: 6, window: [10, 75], min_hp: 500, zombie: '任意' },
        levels: [[{ op: '小喷菇', aim: null }]] });
      PLAN.sel.rule = p.rescue.length - 1;
    },
    delRule: function () { plSnap(); p.rescue.splice(+el.dataset.rule, 1); PLAN.sel.rule = -1; },
    addLevel: function () { plSnap(); p.rescue[+el.dataset.rule].levels.push([{ op: '窝瓜', aim: null }]); },
    addLevelOp: function () {
      plSnap();
      const lv = plPath(p, path);
      (Array.isArray(lv) ? lv : (lv.ops = lv.ops || [])).push({ op: '窝瓜', aim: null });
    },
    delLevelOp: function () { plSnap(); plPath(p, path.replace(/\.[^.]+$/, '')).splice(+path.split('.').pop(), 1); },
    validate: function () { return plValidate(); },
    quick: function () { return plQuick(); },
    save: function () { return plSave(); },
    export: function () { plDownload(plFull(p) + '.json', JSON.stringify(p, null, 2)); },
    import: function () { document.getElementById('pl-file').click(); },
    cfgExport: function () { return plCfgExport(); },
    cfgImport: function () { document.getElementById('pl-cfgfile').click(); },
    example: async function () {
      if (!confirm('载入示例会新增一套阵解，继续？')) return;
      plAddBank(await plExampleRaw());
    },
    reset: function () { alert('主界面不再内置基线阵解；示例请在「帮助」里载入'); },
    blank: async function () { plAddBank(await plTemplateRaw(), '新建阵解'); },
    newPlan: function () { plAddBank(JSON.parse(JSON.stringify(plP())), '新阵解'); },
    dupPlan: function () { plAddBank(JSON.parse(JSON.stringify(plP())), (plP().name || '阵解') + ' 副本'); },
    delPlan: function () {
      if (PLAN.bank.length <= 1) { alert('至少留一套阵解'); return; }
      if (!confirm('删除这套阵解？')) return;
      PLAN.bank.splice(PLAN.active, 1);
      PLAN.active = 0;
    },
    markAll: function () { p.waves.forEach(function (r) { PLAN.marks.add(r.w); }); },
    markInv: function () {
      const keep = new Set();
      p.waves.forEach(function (r) { if (!PLAN.marks.has(r.w)) keep.add(r.w); });
      PLAN.marks = keep;
    },
    markNone: function () { PLAN.marks = new Set(); },
    shiftL: function () { return plBatch('shift', -1); },
    shiftR: function () { return plBatch('shift', +1); },
    copy: function () {
      const rows = [];
      p.waves.forEach(function (r) {
        if (PLAN.marks.has(r.w)) rows.push({ sets: plDeep(r.sets || []), note: r.note || '' });
      });
      if (!rows.length) { alert('先勾选要复制的波次'); return; }
      PLAN.clip = rows;
      alert('已复制 ' + rows.length + ' 波');
    },
    paste: function () { return plBatch('paste'); },
    clr: function () { return plBatch('clear'); },
    undo: function () {
      if (!PLAN.undo.length) { alert('没有可撤销的操作'); return; }
      PLAN.bank[PLAN.active].plan = JSON.parse(PLAN.undo.pop());
    },
    specCopy: function () {
      const t = document.getElementById('pl-mod-body').textContent;
      navigator.clipboard.writeText(t).then(function () { alert('已复制'); },
        function () { alert('复制失败，请手动选中'); });
    },
    specDown: function () {
      plDownload('trackcheck-json-' + (document.getElementById('pl-mod').dataset.what || 'spec') + '.md',
        document.getElementById('pl-mod-body').textContent);
    },
    specClose: function () { document.getElementById('pl-mod').classList.remove('on'); },
  };
  if (H[act]) { await H[act](); plRender(); }
});

/* ---------------- 主事件：改值 ---------------- */
PL_ROOT.addEventListener('change', async function (e) {
  const el = e.target;
  if (el.dataset.mark) {
    const w = +el.dataset.mark;
    if (el.checked) PLAN.marks.add(w); else PLAN.marks.delete(w);
    return plRenderWaveList();
  }
  if (el.dataset.deck !== undefined) {
    plSnap();
    const p = plP(), i = +el.dataset.deck;
    let v = el.value;
    const deck = p.deck.slice();
    const prev = deck[i] || '';
    if (v === MIMIC_TAG) {
      // 选「模仿者」→ 默认模仿上一张的植物（没有就寒冰菇）
      const guess = (prev.split(':')[1]) || plCardOp(deck[0] || '') || '寒冰菇';
      v = MIMIC_TAG + ':' + (PLAN.cat.plants.indexOf(guess) >= 0 ? guess : '寒冰菇');
    }
    if (!v) deck.splice(i, 1);
    else if (deck[i] !== undefined) deck[i] = v;
    else deck.push(v);
    p.deck = deck.filter(Boolean).slice(0, 10);
    return plRender();
  }
  if (el.dataset.mimic !== undefined) {
    plSnap();
    const p = plP(), i = +el.dataset.mimic;
    p.deck[i] = MIMIC_TAG + ':' + el.value;
    return plRender();
  }
  if (el.dataset.map !== undefined) {
    const i = +el.dataset.map;
    if (typeof queue !== 'undefined' && queue[i]) {
      queue[i].planId = el.value || null;
      return plRenderMap();
    }
    return;
  }
  if (el.dataset.aim !== undefined) {
    plSnap();
    const bp = el.dataset.aim, b = plPath(plP(), bp);
    const v = el.value;
    if (v === 'imp') {
      // ★ 2026-10-24 拦截炮：动态落点 + 条件触发器
      b.cob = 'D';
      b.aim = [2, 'imp'];
      b.imp_group = b.imp_group || 'low';
      b.imp_when = b.imp_when || 'apex';
      b.trig = { kind: 'imp', group: b.imp_group, when: b.imp_when };
    } else if (v === 'dyn') {
      // ★ 2026-10-24 分离炮动态落点：炮种变 S，落点 = [行, "dyn"] + 打哪几种僵尸
      b.cob = 'S';
      b.aim = [2, 'dyn'];
      if (!(b.dyn_kinds || []).length) b.dyn_kinds = ['冰车'];
      delete b.imp_group; delete b.imp_when;
    } else if (v === 'slide') {
      b.aim = [2, 'front'];
      if (b.cob === 'D') b.cob = 'P';
      if (b.aim && b.aim[1] !== 'dyn') delete b.dyn_kinds;
    } else {
      b.aim = (v === 'cell') ? [3, 2] : (v === 'none' ? null : v);
      if (v !== 'dyn') delete b.dyn_kinds;
    }
    return plRender();
  }
  if (el.dataset.dynrow !== undefined) {
    plSnap();
    const b = plPath(plP(), el.dataset.dynrow);
    if (!Array.isArray(b.aim)) b.aim = [2, 'dyn'];
    b.aim[0] = +el.value;
    return plRender();
  }
  if (el.dataset.dynkind !== undefined) {
    plSnap();
    const b = plPath(plP(), el.dataset.dynkind);
    b.dyn_kinds = Array.from(el.selectedOptions || [])
      .map(function (o) { return o.value; });
    return plRender();
  }
  if (el.dataset.aimrc !== undefined) {
    const bp = el.dataset.aimrc, b = plPath(plP(), bp);
    if (!Array.isArray(b.aim)) b.aim = [3, 2];
    const raw = parseFloat(el.value);
    if (!isNaN(raw)) b.aim[+el.dataset.k] = Math.round(raw * 10) / 10;
    return plRender();
  }
  if (el.dataset.gEn !== undefined) {
    plSnap();
    plP().globals[+el.dataset.gEn].enabled = el.checked;
    return;
  }
  if (el.id === 'pl-simple-en') {
    plSnap(); plP().rescue_simple.enabled = el.checked; return;
  }
  if (el.id === 'pl-sys') {
    plSnap();
    const p = plP(), s = PLAN.cat.rhythms.find(function (x) { return x.system === el.value; });
    p.rhythm.system = el.value;
    if (s && s.presets && s.presets.length) {
      p.rhythm.id = s.presets[0].id;
      p.rhythm.name = s.presets[0].id;
      p.rhythm.beats = s.presets[0].beats.slice();
      plFillGaps(s.presets[0]);
    }
    return plRender();
  }
  if (el.id === 'pl-preset') {
    plSnap();
    const p = plP(), q = plPreset(el.value);
    p.rhythm.id = el.value;
    p.rhythm.name = el.value;
    if (q) { p.rhythm.beats = q.beats.slice(); plFillGaps(q); }
    return plRender();
  }
  if (el.id === 'pl-bank') { PLAN.active = +el.value; PLAN.marks = new Set(); return plRender(); }
  if (el.id === 'pl-open') {
    if (!el.value) return;
    const r = await fetch('/api/plan/load?name=' + encodeURIComponent(el.value));
    const d = await r.json();
    if (d && d.waves) plAddBank(d);
    else alert('读取失败：' + (d.error || '未知'));
    el.value = '';
    return;
  }
  if (el.id === 'pl-usep') {
    plSnap();
    const b = plSelBlock(plP());
    if (b) { if (el.checked) b.repeat = { every: 100, times: null }; else delete b.repeat; }
    return plRender();
  }
  if (el.dataset.path) {
    const p = plP();
    let v = el.value;
    if (el.type === 'checkbox') v = el.checked;
    else if (el.dataset.arr) v = String(el.value).split(/[,，\s]+/).filter(Boolean).map(Number);
    else if (el.type === 'number') v = (el.value === '' ? null : +el.value);
    if (el.dataset.key === 'kind') plSnap();
    plSet(p, el.dataset.path + (el.dataset.key ? '.' + el.dataset.key : ''), v);
    if (el.dataset.key === 'kind') plFill(plPath(p, el.dataset.path), v);
    // ★ 2026-10-24：**手放炮积木**——动作切成玉米炮时，给它一套能直接用的默认值
    //   （炮种 P、滑动落点）。切走时把炮专用字段清掉，免得留在卡上被当成炮。
    if (el.dataset.key === 'op') {
      const b = plPath(p, el.dataset.path);
      if (b) {
        if (b.op === '玉米炮') {
          b.cob = b.cob || 'P';
          if (!Array.isArray(b.aim)) b.aim = [2, 'front'];
        } else {
          delete b.cob; delete b.imp_group; delete b.imp_when;
          delete b.dyn_kinds;
        }
      }
      return plRender();
    }
    // ★ 2026-10-24 炮种 / 拦截参数改动 → 同步触发器（拦截炮是条件触发，不是定时）
    if (['cob', 'imp_when', 'imp_group'].includes(el.dataset.key)) {
      const b = plPath(p, el.dataset.path);
      if (b && b.op === '玉米炮') {
        if (b.cob === 'D') {
          b.imp_group = b.imp_group || 'low';
          b.imp_when = b.imp_when || 'apex';
          if (!Array.isArray(b.aim) || b.aim[1] !== 'imp') b.aim = [2, 'imp'];
          b.trig = { kind: 'imp', group: b.imp_group, when: b.imp_when };
        } else if (Array.isArray(b.aim) && b.aim[1] === 'imp') {
          b.aim = null;
          if ((b.trig || {}).kind === 'imp') b.trig = { kind: 'spawn' };
        }
      }
      return plRender();
    }
    if (['kind', 'op', 'what', 'row', 'cmp', 'value', 'card', 'name', 'at', 'zombie',
         'axis', 'waves', 'offset', 'target', 'back', 'set', 'negate', 'plant', 'col'].includes(el.dataset.key))
      return plRender();
  }
});

PL_ROOT.addEventListener('input', function (e) {
  const el = e.target;
  if (el.id === 'pl-name') { plP().name = plBare(el.value); plRenderBank(); return; }
  if (el.id === 'pl-beats') {
    plP().rhythm.beats = el.value.split('|').map(function (s) { return s.trim(); }).filter(Boolean);
    plSpectrumSoon();
    return;
  }
  if (el.id === 'pl-gaps') {
    plP().rhythm.gaps = plGapsParse(el.value);
    plSpectrumSoon();
    return;
  }
  if (el.id === 'pl-wavenote') {
    const p = plP();
    const row = p.waves.find(function (r) { return r.w === PLAN.sel.wave; });
    if (row) { row.note = el.value; plRenderWaveList(); }
    return;
  }
  if (el.id === 'pl-rep-every' || el.id === 'pl-rep-times') {
    const b = plSelBlock(plP());
    if (!b) return;
    b.repeat = b.repeat || { every: 100, times: null };
    if (el.id === 'pl-rep-every') b.repeat.every = +el.value || 100;
    else b.repeat.times = (el.value === '' ? null : +el.value);
  }
});
function plSelBlock(p) {
  const row = p.waves.find(function (r) { return r.w === PLAN.sel.wave; });
  if (!row) return null;
  const st = (row.sets || [])[PLAN.sel.set];
  if (!st) return null;
  return (st.ops || [])[PLAN.sel.block] || null;
}

"""
SCRIPT += r"""
/* ---------------- 服务端动作：校验 / 快捷布置 / 批量 / 保存 ---------------- */
async function plPost(url, body) {
  const r = await fetch(url, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return r.json();
}
async function plValidate() {
  const d = await plPost('/api/plan/validate', { plan: plP() });
  const box = document.getElementById('pl-issues');
  if (!d.issues || !d.issues.length) {
    box.innerHTML = '<span style="color:#059669">✓ 没发现问题</span>';
    return;
  }
  box.innerHTML = d.issues.map(function (x) {
    return '<div class="issue ' + (x.lv === 'error' ? 'err' : 'warn') + '"><b>'
      + (x.lv === 'error' ? '错误' : '提示') + '</b>'
      + '<span class="pltag">' + plEsc(x.where) + '</span> ' + plEsc(x.msg) + '</div>';
  }).join('');
}
async function plQuick() {
  const track = document.getElementById('pl-beats').value;
  const gaps = document.getElementById('pl-gaps').value;
  const startEl = document.getElementById('pl-start');
  const start = startEl ? (+startEl.value || 0) : 0;
  if (!track.trim()) { alert('先填轨道，比如 P|P|P|P 或 N|AA\'|I|I'); return; }
  if (!confirm(['会把 20 波（含旗波）的候选整组替换成轨道的动作。',
      gaps.trim() ? '填了波长串 → 具备运算量的操作会按「距上一波 +波长」**定时**。'
                  : '没填波长串 → 时机留空。',
      '同时会**按阵型自动选卡 + 自动填救场**。继续？'].join('\n'))) return;
  plSnap();
  // ★ 2026-10-24：把**阵型**一起发给后端 —— 旗波要不要冰杀蹦极、炮打哪两路、
  //   自动选卡与自动救场都要看阵型结构（"阵型结构决定"是用户的原话）。
  const kinds = (typeof sel !== 'undefined' && sel) ? Array.from(sel) : [];
  const d = await plPost('/api/plan/quick', { plan: plP(), track: track,
    pair: plPairMode(), gaps: gaps, start: start,
    array: (typeof LY !== 'undefined' ? LY.array : null),
    field: (typeof LY !== 'undefined' ? LY.field : null),
    kinds: kinds });
  if (d.error) { alert('失败：' + d.error); return; }
  PLAN.bank[PLAN.active].plan = d.plan;
  const inf = d.info || {};
  const lines = [['已布置 ', String(d.filled), ' 波（起手第 ', String(start), ' 拍）',
    gaps.trim() ? '，并按波长定时' : ''].join('')];
  if ((inf.deck_added || []).length) { lines.push('', '自动选卡：'); lines.push(...inf.deck_added); }
  if (inf.rescue) lines.push('', '自动救场：要保 ' + inf.rescue.n + ' 格，资源 '
    + (inf.rescue.ash_txt || '—') + ' / ' + (inf.rescue.pads_txt || '—'));
  if ((inf.hints || []).length) lines.push('', '提示：', ...inf.hints);
  if ((inf.warnings || []).length) lines.push('', '注意：', ...inf.warnings);
  alert(lines.join('\n'));
  plRender();
  plSpectrumSoon();
}
async function plBatch(op, delta) {
  const marks = Array.from(PLAN.marks);
  if (!marks.length) { alert('先勾选波次（左边每行的小方框）'); return; }
  if (op === 'paste' && !PLAN.clip) { alert('剪贴板是空的（先勾选并「复制」）'); return; }
  plSnap();
  const d = await plPost('/api/plan/batch', { plan: plP(), waves: marks, op: op,
    delta: delta || 0, data: { rows: PLAN.clip || [] } });
  if (d.error) { alert('失败：' + d.error); return; }
  PLAN.bank[PLAN.active].plan = d.plan;
  // 平移后保留勾选，方便连着挪；粘贴/清空后清掉，避免误操作
  if (op === 'paste' || op === 'clear') PLAN.marks = new Set();
}
async function plSave() {
  const p = plP();
  const d = await plPost('/api/plan/save', { name: plFull(p), plan: p });
  if (d.ok) { alert('已存到：' + d.path); await plListSaved(); }
  else alert('保存失败：' + (d.error || '未知'));
}
async function plListSaved() {
  try {
    const d = await (await fetch('/api/plan/list')).json();
    const names = d.names || [];
    const sel = document.getElementById('pl-open');
    if (!names.length) { sel.style.display = 'none'; return; }
    sel.innerHTML = '<option value="">（打开已保存）</option>'
      + names.map(function (n) { return '<option value="' + plEsc(n) + '">' + plEsc(n) + '</option>'; }).join('');
    sel.style.display = '';
    document.getElementById('pl-saved-lab').style.display = '';
  } catch (e) { /* 网页版没有磁盘 */ }
}

/* ---------------- 全场配置 ---------------- */
function plDownload(name, text) {
  const blob = new Blob([text], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
}
function plCfgExport() {
  const q = (typeof queue !== 'undefined' && Array.isArray(queue)) ? queue : [];
  const cfg = {
    format: 'trackcheck-config/1',
    spawns: q.map(function (it) {
      return { name: it.name, kinds: it.kinds, seeds: it.seeds, planId: it.planId || null };
    }),
    plans: PLAN.bank.map(function (b) { return { id: b.id, name: plFull(b.plan), plan: b.plan }; }),
  };
  plDownload('trackcheck-config.json', JSON.stringify(cfg, null, 2));
}
document.getElementById('pl-cfgfile').addEventListener('change', function (ev) {
  const f = ev.target.files && ev.target.files[0];
  if (!f) return;
  const rd = new FileReader();
  rd.onload = function () {
    let d;
    try { d = JSON.parse(rd.result); } catch (err) { alert('不是合法 JSON：' + err.message); return; }
    if (d.format && d.format.indexOf('trackcheck-plan') === 0) { plAddBank(d); return; }
    if (!d.plans && !d.spawns) { alert('不是全场配置（缺 plans / spawns）'); return; }
    PLAN.bank = [];
    (d.plans || []).forEach(function (x) {
      PLAN.bank.push({ id: x.id || ('p' + (PLAN.bank.length + 1)), plan: x.plan || x });
    });
    if (!PLAN.bank.length) { alert('配置里没有阵解'); return; }
    PLAN.active = 0;
    if (Array.isArray(d.spawns) && typeof queue !== 'undefined') {
      queue.length = 0;
      d.spawns.forEach(function (s) {
        queue.push({ name: s.name, kinds: s.kinds || [], seeds: s.seeds || 1, planId: s.planId || null });
      });
      if (typeof renderQueue === 'function') renderQueue();
    }
    PLAN.marks = new Set();
    plRender();
    alert('已导入 ' + PLAN.bank.length + ' 套阵解、' + ((d.spawns || []).length) + ' 组出怪');
  };
  rd.readAsText(f, 'utf-8');
  ev.target.value = '';
});
document.getElementById('pl-file').addEventListener('change', function (ev) {
  const f = ev.target.files && ev.target.files[0];
  if (!f) return;
  const rd = new FileReader();
  rd.onload = function () {
    try {
      const d = JSON.parse(rd.result);
      if (d && d.plans) {
        (d.plans || []).forEach(function (x) { plAddBank(x.plan || x); });
      } else plAddBank(d.plan || d);
    } catch (err) { alert('不是合法的阵解 JSON：' + err.message); }
  };
  rd.readAsText(f, 'utf-8');
  ev.target.value = '';
});

/* ---------------- 阵解库 ---------------- */
function plAddBank(plan, name) {
  if (!plan || !plan.waves) { alert('不是阵解'); return; }
  if (!PLAN.cat) { plBoot(); return; }        // catalog 还没到 → 先 boot，用户再点一次
  plan = JSON.parse(JSON.stringify(plan));
  if (name) plan.name = plBare(name);
  PLAN.bank.push({ id: 'p' + Date.now().toString(36) + PLAN.bank.length, plan: plan });
  PLAN.active = PLAN.bank.length - 1;
  PLAN.marks = new Set();
  plRender();
}

/* ---------------- 标签页 / 启动 ---------------- */
function plEnterPlan() {
  if (!PLAN.cat) return plBoot();
  plRenderMap();
}
/* 「① 阵容布置」换了场地 → 阵解的 field 跟着走 */
function plSetField(code) {
  if (typeof PLAN === 'undefined' || !PLAN.cat || !PLAN.bank.length) return;
  const p = plP();
  if (p && p.field !== code) { p.field = code; try { plRender(); } catch (e) {} }
}
function plTab(which) {
  if (typeof tcTab === 'function') return tcTab(which);
  plEnterPlan();
}
for (const b of document.querySelectorAll('.tabs button')) b.onclick = function () { plTab(b.dataset.tab); };
const gearEl = document.getElementById('gear');
if (gearEl) gearEl.onclick = function () { plTab('settings'); };

async function plBoot() {
  const [cat, tpl] = await Promise.all([
    fetch('/api/plan/catalog').then(function (r) { return r.json(); }),
    fetch('/api/plan/template').then(function (r) { return r.json(); }),
  ]);
  PLAN.cat = cat;
  window.ZOMBIES = cat.zombies;
  // ★ v0.2.2：阵解库**从一套空模板开始** —— 主界面不再内置 PE.电波钟无炮 的阵解。
  //   示例在「帮助」页，点了才载入（见 plAddExamplePlan）。
  PLAN.bank = [{ id: 'p0', plan: tpl }];
  PLAN.active = 0;
  plRender();
  plListSaved();
}

/* 「帮助」页用：把 PE.电波钟无炮 的示例阵解载入阵解库 */
async function plAddExamplePlan() {
  const def = await fetch('/api/plan/default').then(function (r) { return r.json(); });
  if (!PLAN.cat) { await plBoot(); }
  PLAN.bank.push({ id: 'ex' + Date.now(), plan: def });
  PLAN.active = PLAN.bank.length - 1;
  plRender();
  return def.name || '示例阵解';
}

/* 给「运行」标签页用：把阵解绑到出怪组上 */
function plExampleRaw() {
  return fetch('/api/plan/example').then(function (r) { return r.json(); });
}
function plTemplateRaw() {
  return fetch('/api/plan/template').then(function (r) { return r.json(); });
}

function plPlanById(id) {
  const b = PLAN.bank.find(function (x) { return x.id === id; });
  return b ? b.plan : null;
}
</script>
"""