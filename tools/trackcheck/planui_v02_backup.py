# -*- coding: utf-8 -*-
"""
planui.py —— **阵解栏**的前端（HTML 片段 + JS）

为什么单独一个文件：`ui.PAGE` 已经很长了，阵解栏是独立一屏，
拆出来以后改它不会碰到出怪沙盘那些代码。

交互模型（刻意做得像积木编程）：

    波（一行）
      └ 候选 a（`when` 成立才用）→ 积木序列 → 每个积木带触发器
      └ 候选 b（兜底）…
    救场
      └ 规则（事件）→ 第 1 层积木 → 第 2 层…（上一层没落地就试下一层）

所有编辑都是"改状态再重画"：`PLAN.p` 是唯一的真相，事件用
`data-act` + `data-path` 做事件委托，路径形如 `waves.4.sets.0.ops.1.trig`。
"""

STYLE = r'''
.tabs{display:flex;gap:6px;margin:0 0 14px;border-bottom:1px solid #e2e8f0}
.tabs button{border:1px solid #e2e8f0;border-bottom:0;background:#fff;
 border-radius:8px 8px 0 0;padding:7px 15px;font-weight:600;color:#64748b;cursor:pointer}
.tabs button.on{background:#2563eb;border-color:#2563eb;color:#fff}
.pgrid{display:grid;grid-template-columns:200px 1fr;gap:12px;align-items:start}
.wlist{border:1px solid #e2e8f0;border-radius:8px;overflow:auto;max-height:560px}
.wrow{display:flex;gap:6px;align-items:center;padding:5px 8px;cursor:pointer;
 font-size:12px;border-bottom:1px solid #f1f5f9}
.wrow:hover{background:#f8fafc}
.wrow.on{background:#dbeafe}
.wrow .rw{color:#94a3b8;width:24px;flex:none}
.wrow .rr{font-size:10px;color:#475569;background:#f1f5f9;border-radius:4px;
 padding:0 4px;flex:none}
.wrow .rb{color:#94a3b8;margin-left:auto;font-size:10.5px}
.chip{display:inline-flex;gap:4px;align-items:center;border:1px solid #cbd5e1;
 background:#f8fafc;border-radius:6px;padding:2px 7px;font-size:12px;cursor:pointer;
 white-space:nowrap}
.chip:hover{border-color:#93c5fd}
.chip.on{border-color:#2563eb;background:#dbeafe}
.chip small{color:#94a3b8;font-size:10px}
.chip.warn{border-color:#fca5a5;background:#fef2f2}
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
.insp{border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;background:#f8fafc;
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
'''

MARKUP = r'''
<div id="planpage" style="display:none">
  <div class="panel">
    <div class="ptitle">阵解 · 基本信息</div>
    <div class="row" style="flex-wrap:wrap;gap:8px">
      <label class="hint">名称</label><input type="text" id="pl-name" style="width:180px">
      <label class="hint">节奏系</label><select id="pl-sys"></select>
      <label class="hint">节奏型</label><select id="pl-preset"></select>
      <label class="hint">拍</label><input type="text" id="pl-beats" style="width:170px"
        placeholder="N | AA' | I | I">
      <button class="primary" data-act="run">▶ 用这个阵解跑</button>
      <button class="ghost" data-act="validate">✓ 校验</button>
      <label class="hint" id="pl-open-lab" style="display:none">已保存</label>
      <select id="pl-open" style="display:none"></select>
      <button class="ghost" data-act="save">⌸ 保存</button>
      <button class="ghost" data-act="example">✦ 载入示例</button>
      <button class="ghost" data-act="export">⤓ 导出 JSON</button>
      <button class="ghost" data-act="import">⤒ 导入 JSON</button>
      <button class="ghost" data-act="reset">↺ 回到内置基线</button>
      <input type="file" id="pl-file" accept=".json,application/json" style="display:none">
    </div>
    <div class="hint" id="pl-note" style="margin-top:6px"></div>
  </div>

  <div class="panel">
    <div class="ptitle">表层阵解 · 轨道
      <span class="hint" style="font-weight:400">（每波一行；行内是候选兜底链，
        行首积木 = 刷怪即刻生效，后面的积木挂触发器）</span></div>
    <div class="pgrid">
      <div class="wlist" id="pl-waves"></div>
      <div id="pl-wavebox"></div>
    </div>
  </div>

  <div class="panel">
    <div class="ptitle">救场层
      <span class="hint" style="font-weight:400">（事件 → 多层兜底：上一层没落地就试下一层）</span></div>
    <div id="pl-rescue"></div>
  </div>

  <div class="panel">
    <div class="ptitle">校验</div>
    <div id="pl-issues" class="hint">点「校验」看看这份阵解有没有明显问题</div>
  </div>
</div>
'''

SCRIPT = r'''
<script>
/* ════════════════════════════════ 阵解栏 ════════════════════════════════ */
const PLAN = { cat: null, p: null, sel: { wave: 1, set: -1, block: -1, rule: 0 }, dirty: false };

const PL_CARDS = ['核', '模仿核', '樱桃', '辣椒', '冰', '模仿冰', '窝瓜', '垫材', '垫材2',
                  '南瓜', '大蒜', '大喷菇'];
const PL_CMP = ['>=', '<=', '>', '<', '=='];
const PL_STATE = [['ice_stock', '存冰数'], ['sun', '阳光'], ['zombies_in_row', '本路僵尸数'],
                  ['zombies_total', '场上僵尸数'], ['wave_hp', '本波剩余血量']];

function plPath(root, path) {
  let o = root;
  for (const k of String(path || '').split('.').filter(x => x !== '')) o = o[k];
  return o;
}
function plSet(root, path, val) {
  const ks = String(path).split('.').filter(x => x !== '');
  let o = root;
  for (let i = 0; i < ks.length - 1; i++) {
    const k = ks[i];
    if (o[k] === undefined || o[k] === null) o[k] = /^\d+$/.test(ks[i + 1]) ? [] : {};
    o = o[k];
  }
  o[ks[ks.length - 1]] = val;
  PLAN.dirty = true;
}
function plEsc(s) {
  return String(s === undefined || s === null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function plNum(path, key, val, w) {
  return `<input type="number" data-path="${path}" data-key="${key}" value="${val ?? 0}"
    style="width:${w || 64}px">`;
}
function plArr(path, key, val, w) {
  let s = val;
  if (Array.isArray(val)) s = val.join(',');
  return `<input type="text" data-path="${path}" data-key="${key}" data-arr="1"
    value="${plEsc(s === undefined || s === null ? '' : s)}" style="width:${w || 90}px">`;
}
function plSel(path, key, val, opts) {
  return `<select data-path="${path}" data-key="${key}">` + opts.map(o => {
    const [v, t] = Array.isArray(o) ? o : [o, o];
    return `<option value="${plEsc(v)}" ${String(v) === String(val) ? 'selected' : ''}>${plEsc(t)}</option>`;
  }).join('') + '</select>';
}

const PL_DEFAULTS = {
  dist: { zombie: '任意', ref: { row: 6, col: 6 }, axis: 'x', cmp: '<=', value: 160 },
  state: { what: 'ice_stock', cmp: '>=', value: 1 },
  card: { name: '核', offset: 0 },
  card_ready: { card: '核', offset: 0 },
  card_ready_within: { card: '樱桃', waves: 0.9 },
  ice_stock: { cmp: '>=', value: 1 },
  kernel_slack: { cmp: '>=', value: 0 },
  time: { at: 0 },
  after: { at: 0 },
  zombie_in_window: { rows: [6, 5, 1], col: 6, window: [10, 75], min_hp: 500, zombie: '任意' },
  heavy_near_core: { rows: [6, 5, 2, 1], cells: 3 },
  wave: { from: 1, to: 20 },
  prev: { back: 1, target: 'set', set: 0, op: '辣椒', negate: false },
};
function plFillDefaults(node, kind) {
  const d = PL_DEFAULTS[kind];
  if (!d) return;
  for (const k of Object.keys(d)) {
    if (node[k] === undefined || node[k] === null) {
      node[k] = JSON.parse(JSON.stringify(d[k]));
    }
  }
}

/* ---------------- 条件 / 触发器编辑器（递归） ---------------- */
function condHTML(c, path, kinds) {
  c = c || { kind: (kinds[0] && kinds[0].kind) || 'always' };
  const k = c.kind || 'always';
  let extra = '';
  if (k === 'card_ready' || k === 'card' || k === 'card_ready_within') {
    extra = plSel(path, 'card', c.card || c.name || '核', PL_CARDS)
          + (k === 'card_ready_within'
             ? plNum(path, 'waves', c.waves ?? 0.9, 52)
             : plNum(path, 'offset', c.offset ?? 0, 52));
  } else if (k === 'ice_stock' || k === 'kernel_slack' || k === 'state') {
    if (k === 'state') extra = plSel(path, 'what', c.what || 'ice_stock', PL_STATE)
                              + (c.what === 'zombies_in_row' ? plNum(path, 'row', c.row ?? 6, 40) : '');
    extra += plSel(path, 'cmp', c.cmp || '>=', PL_CMP) + plNum(path, 'value', c.value ?? 1, 52);
  } else if (k === 'time' || k === 'after') {
    extra = plNum(path, 'at', c.at ?? 0, 64) + '<span class="hint">cs</span>';
  } else if (k === 'dist') {
    extra = plSel(path, 'zombie', c.zombie || '任意', ZOMBIES)
          + '<span class="hint">相对</span>'
          + plNum(path + '.ref', 'row', (c.ref || {}).row ?? 6, 40) + '-'
          + plNum(path + '.ref', 'col', (c.ref || {}).col ?? 6, 40)
          + plSel(path, 'axis', c.axis || 'x', [['x', '水平'], ['row', '竖向']])
          + plSel(path, 'cmp', c.cmp || '<=', PL_CMP) + plNum(path, 'value', c.value ?? 160, 60)
          + '<span class="hint">px</span>';
  } else if (k === 'zombie_in_window') {
    extra = '<span class="hint">路</span>' + plArr(path, 'rows', c.rows || [6, 5, 1], 80)
          + '<span class="hint">6 列窗口</span>'
          + plArr(path, 'window', c.window || [10, 75], 70)
          + '<span class="hint">hp≥</span>' + plNum(path, 'min_hp', c.min_hp ?? 500, 60)
          + plSel(path, 'zombie', c.zombie || '任意', ZOMBIES);
  } else if (k === 'heavy_near_core') {
    extra = '<span class="hint">路</span>' + plArr(path, 'rows', c.rows || [6, 5, 2, 1], 80)
          + '<span class="hint">≤</span>' + plNum(path, 'cells', c.cells ?? 3, 44)
          + '<span class="hint">格</span>';
  } else if (k === 'wave') {
    extra = '<span class="hint">从 w</span>' + plNum(path, 'from', c.from ?? 1, 48)
          + '<span class="hint">到 w</span>' + plNum(path, 'to', c.to ?? 20, 48);
  } else if (k === 'prev') {
    const target = c.target || 'set';
    extra = '<span class="hint">回看</span>' + plNum(path, 'back', c.back ?? 1, 44)
          + '<span class="hint">波</span>'
          + plSel(path, 'target', target, [['set', '选中的候选'], ['act', '真正打出的动作']])
          + (target === 'set'
             ? '<span class="hint">候选 #</span>' + plNum(path, 'set', c.set ?? 0, 44)
             : '')
          + '<span class="hint">含</span>'
          + plSel(path, 'op', c.op || '辣椒', [['', '（任意）']].concat(PLAN.cat.ops.map(o => [o.name, o.name])))
          + `<label class="hint"><input type="checkbox" data-path="${path}" data-key="negate"
               ${c.negate ? 'checked' : ''}>取反（没发生）</label>`;
  } else if (k === 'all' || k === 'any' || k === 'not') {
    const subs = (c.of || []);
    extra = '<div style="display:flex;flex-direction:column;gap:3px;width:100%">'
      + subs.map((sb, i) => `<div style="display:flex;gap:4px;align-items:center">
          <span class="hint">${k === 'not' ? '非' : '·'}</span>
          ${condHTML(sb, path + '.of.' + i, kinds)}
          <button class="ghost mini2" data-act="delCond" data-path="${path}.of.${i}">✕</button>
        </div>`).join('')
      + `<div><button class="ghost mini2" data-act="addCond" data-path="${path}">+ 子条件</button></div>`
      + '</div>';
  }
  const list = kinds.map(g => [g.kind, g.label || g.kind]);
  return `<span class="cond">${plSel(path, 'kind', k, list)}${extra}</span>`;
}

function gateLabel(st) {
  const c = st.when || { kind: 'always' };
  if (!c.kind || c.kind === 'always') return '总是';
  if (c.kind === 'card_ready') return `卡好：${c.card || c.name}`;
  if (c.kind === 'card_ready_within') return `${c.card || c.name} ${c.waves ?? 0.9} 波内好`;
  if (c.kind === 'ice_stock') return `存冰 ${c.cmp || '>='} ${c.value ?? 1}`;
  if (c.kind === 'kernel_slack') return '核坑有余量';
  if (c.kind === 'all') return '全部满足';
  if (c.kind === 'any') return '任一满足';
  if (c.kind === 'not') return '取反';
  return c.kind;
}
function trigLabel(t) {
  t = t || { kind: 'spawn' };
  if (!t.kind || t.kind === 'spawn') return '即刻';
  if (t.kind === 'time') return `${t.at ?? 0}cs`;
  if (t.kind === 'after') return `+${t.at ?? 0}cs`;
  if (t.kind === 'card') return `卡好:${t.name || t.card}`;
  if (t.kind === 'dist') return `距离${t.zombie || '任意'}${t.cmp || '<='}${t.value ?? ''}`;
  if (t.kind === 'state') return `场况${t.what || ''}${t.cmp || ''}${t.value ?? ''}`;
  return t.kind;
}
function blockLabel(b) {
  const op = b.op || '?';
  let aim = '';
  if (Array.isArray(b.aim)) aim = ` ${b.aim[0]}-${b.aim[1]}`;
  else if (b.aim && b.aim.rows) aim = ` 路${b.aim.rows.join('/')}`;
  const rep = b.repeat ? ` ↻/${b.repeat.every || 100}cs` : '';
  return `${op}${aim}<small> ${trigLabel(b.trig)}${rep}</small>`;
}

/* ---------------- 渲染 ---------------- */
function plRender() {
  const p = PLAN.p;
  if (!p) return;
  document.getElementById('pl-name').value = p.name || '';
  document.getElementById('pl-beats').value = (p.rhythm.beats || []).join(' | ');
  document.getElementById('pl-note').textContent = p.note || '';
  const sys = document.getElementById('pl-sys');
  sys.innerHTML = PLAN.cat.rhythms.map(r =>
    `<option value="${r.system}" ${r.system === p.rhythm.system ? 'selected' : ''}>${r.label}</option>`).join('');
  const cur = PLAN.cat.rhythms.find(r => r.system === p.rhythm.system) || { presets: [] };
  const pre = document.getElementById('pl-preset');
  pre.innerHTML = (cur.presets || []).map(q =>
    `<option value="${q.name}" ${q.name === p.rhythm.name ? 'selected' : ''}>${q.name}</option>`).join('')
    || '<option value="">（该系暂无预设）</option>';

  document.getElementById('pl-waves').innerHTML = (p.waves || []).map(row => {
    const n = (row.sets || []).length;
    const ops = (row.sets || []).flatMap(st => (st.ops || []).map(o => o.op)).join('·');
    return `<div class="wrow ${row.w === PLAN.sel.wave ? 'on' : ''}"
      data-act="selWave" data-w="${row.w}">
      <span class="rw">w${row.w}</span><span class="rr">${plEsc(row.role || '')}</span>
      <span style="color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
        ${plEsc(ops || '—')}</span>
      <span class="rb">${n} 候选</span></div>`;
  }).join('');

  plRenderWave();
  plRenderRescue();
}

function plRenderWave() {
  const p = PLAN.p;
  const row = (p.waves || []).find(r => r.w === PLAN.sel.wave);
  const box = document.getElementById('pl-wavebox');
  if (!row) { box.innerHTML = '<div class="hint">左边选一波</div>'; return; }
  const base = `waves.${(p.waves || []).indexOf(row)}`;

  const sets = (row.sets || []).map((st, si) => {
    const sp = `${base}.sets.${si}`;
    const blocks = (st.ops || []).map((b, bi) => {
      const bp = `${sp}.ops.${bi}`;
      const on = PLAN.sel.block === bi && PLAN.sel.set === si;
      return `<span class="chip ${on ? 'on' : ''}" data-act="selBlock" data-set="${si}" data-block="${bi}">
          ${blockLabel(b)}</span>
        <button class="ghost mini2" data-act="delBlock" data-path="${bp}">✕</button>
        <span class="arrow">→</span>`;
    }).join('');
    return `<div class="set">
      <div class="sethead">
        <b>候选 ${si + 1}</b>
        <span class="hint">当</span> ${condHTML(st.when, sp + '.when', PLAN.cat.gates)}
        <span style="margin-left:auto"></span>
        <button class="ghost mini2" data-act="upSet" data-path="${sp}">↑</button>
        <button class="ghost mini2" data-act="downSet" data-path="${sp}">↓</button>
        <button class="ghost mini2" data-act="delSet" data-path="${sp}">✕</button>
      </div>
      <div class="chain">${blocks}
        <button class="ghost mini2" data-act="addBlock" data-path="${sp}.ops">+ 积木</button>
        <span class="hint" style="margin-left:8px">条件不成立就整组跳过、试下一个候选</span>
      </div>
      ${plInspector(st, sp, si)}
    </div>`;
  }).join('');

  // 救场积木也用同一个 inspector，这里只画轨道
  box.innerHTML = `<div style="margin-bottom:6px" class="hint">
      第 w${row.w} 波 · ${plEsc(row.role || '')} · <input type="text" id="pl-wavenote"
      value="${plEsc(row.note || '')}" placeholder="这一波的备注（给人看的）"
      style="width:340px;font-size:11.5px"></div>`
    + sets
    + `<button class="ghost" data-act="addSet" data-path="${base}.sets">+ 加一个候选（兜底）</button>`;
}

function plInspector(st, sp, si) {
  if (PLAN.sel.set !== si || PLAN.sel.block < 0) return '';
  const b = (st.ops || [])[PLAN.sel.block];
  if (!b) return '';
  const bp = `${sp}.ops.${PLAN.sel.block}`;
  const spec = PLAN.cat.ops.find(o => o.name === b.op) || {};
  const aim = Array.isArray(b.aim) ? b.aim : [1, 9];
  const hasAim = !!b.aim;
  const rep = b.repeat || null;
  return `<div class="insp">
    <div class="row"><b>积木属性</b>
      <span class="hint">（${plEsc(spec.note || '')}）</span></div>
    <div class="row">
      <label>动作</label>${plSel(bp, 'op', b.op, PLAN.cat.ops.map(o => [o.name, o.name]))}
      <label style="margin-left:10px">落点</label>
      <label class="hint"><input type="checkbox" id="pl-hasaim" ${hasAim ? 'checked' : ''}>指定</label>
      <input type="number" data-path="${bp}.aim" data-key="0" value="${aim[0]}" style="width:44px"
        ${hasAim ? '' : 'disabled'}> -
      <input type="number" data-path="${bp}.aim" data-key="1" value="${aim[1]}" style="width:44px"
        ${hasAim ? '' : 'disabled'}>
    </div>
    <div class="row"><label>触发器</label>
      ${condHTML(b.trig || { kind: 'spawn' }, bp + '.trig', PLAN.cat.triggers)}</div>
    <div class="row"><label>循环</label>
      <label class="hint"><input type="checkbox" id="pl-usep" ${rep ? 'checked' : ''}>启用</label>
      每 <input type="number" id="pl-rep-every" value="${(rep || {}).every || 100}" style="width:60px"> cs
      共 <input type="number" id="pl-rep-times" value="${(rep || {}).times ?? ''}" style="width:52px"
        placeholder="∞"> 次
      <span class="hint">（留空 = 一直循环到 this 波结束）</span>
    </div>
    <div class="row">
      <button class="ghost mini2" data-act="delBlock" data-path="${bp}">删除这块</button>
      <button class="ghost mini2" data-act="selBlock" data-set="${si}" data-block="-1">收起</button>
    </div>
  </div>`;
}

function plRenderRescue() {
  const p = PLAN.p;
  const rules = p.rescue || [];
  document.getElementById('pl-rescue').innerHTML = rules.map((r, ri) => {
    const on = PLAN.sel.rule === ri;
    const levels = (r.levels || []).map((lv, li) => {
      const ops = (Array.isArray(lv) ? lv : (lv.ops || []));
      const chips = ops.map((b, bi) => {
        const bp = `rescue.${ri}.levels.${li}.${bi}`;
        return `<span class="chip">${blockLabel(b)}</span>
          <button class="ghost mini2" data-act="delLevelOp" data-path="${bp}">✕</button>`;
      }).join('');
      return `<div class="lvl"><span class="hint">第 ${li + 1} 层</span>
        ${chips}<button class="ghost mini2" data-act="addLevelOp"
          data-path="rescue.${ri}.levels.${li}">+ 积木</button></div>`;
    }).join('');
    return `<div class="rule">
      <div class="rh"><span class="rid">${plEsc(r.id || ('规则' + (ri + 1)))}</span>
        <span class="hint" style="font-weight:400">${plEsc(r.note || '')}</span>
        <span style="margin-left:auto"></span>
        <button class="ghost mini2" data-act="selRule" data-rule="${ri}">${on ? '收起' : '编辑'}</button>
        <button class="ghost mini2" data-act="delRule" data-rule="${ri}">✕</button></div>
      ${on ? `<div class="row" style="margin-top:6px">
          <label>事件</label>${condHTML(r.event || { kind: 'always' }, 'rescue.' + ri + '.event', EVENT_KINDS(r))}
          <label style="margin-left:10px">冷却</label>
          ${plNum('rescue.' + ri, 'cooldown', r.cooldown ?? 30, 64)}<span class="hint">cs</span>
        </div>
        ${levels}
        <button class="ghost mini2" data-act="addLevel" data-rule="${ri}">+ 再兜一层</button>` : ''}
    </div>`;
  }).join('') + `<button class="ghost" data-act="addRule">+ 加一条救场规则</button>`;
}

function EVENT_KINDS() {
  return [
    { kind: 'zombie_in_window', label: '僵尸进入窗口' },
    { kind: 'heavy_near_core', label: '重甲逼近 CORE' },
    { kind: 'bare_core_threat', label: '裸 CORE 要被砸' },
    { kind: 'ice_stock', label: '存冰数' },
    { kind: 'wave', label: '波次区间' },
    { kind: 'always', label: '总是' },
  ];
}

/* ---------------- 事件 ---------------- */
const PL = document.getElementById('planpage');

PL.addEventListener('click', async e => {
  const el = e.target.closest('[data-act]');
  if (!el) return;
  const act = el.dataset.act;
  const p = PLAN.p;
  const path = el.dataset.path || '';
  const A = {
    selWave: () => { PLAN.sel.wave = +el.dataset.w; PLAN.sel.set = -1; PLAN.sel.block = -1; },
    selBlock: () => { PLAN.sel.set = +el.dataset.set; PLAN.sel.block = +el.dataset.block; },
    addSet: () => { plPath(p, path).push({ when: { kind: 'always' }, ops: [] }); },
    delSet: () => { const arr = plPath(p, path.replace(/\.[^.]+$/, ''));
                    arr.splice(+path.split('.').pop(), 1); },
    upSet: () => { plMove(path, -1); },
    downSet: () => { plMove(path, +1); },
    addBlock: () => { plPath(p, path).push({ op: '存冰', aim: null,
                       trig: { kind: 'spawn' } }); },
    delBlock: () => { const arr = plPath(p, path.replace(/\.[^.]+$/, ''));
                      arr.splice(+path.split('.').pop(), 1); PLAN.sel.block = -1; },
    addCond: () => { const c = plPath(p, path);
                     if (!c.of) c.of = [];
                     if (!['all', 'any', 'not'].includes(c.kind)) {
                       const prev = Object.assign({}, c);
                       for (const k of Object.keys(c)) delete c[k];
                       c.kind = 'all'; c.of = [prev];
                     } else c.of.push({ kind: 'card_ready', card: '核' }); },
    delCond: () => { const parent = plPath(p, path.replace(/\.of\.\d+$/, ''));
                     parent.of.splice(+path.split('.').pop(), 1); },
    selRule: () => { PLAN.sel.rule = (PLAN.sel.rule === +el.dataset.rule ? -1 : +el.dataset.rule); },
    addRule: () => { p.rescue = p.rescue || [];
                     p.rescue.push({ id: '规则' + (p.rescue.length + 1), note: '',
                       event: { kind: 'zombie_in_window', rows: [6, 5, 1], col: 6,
                                window: [10, 75], min_hp: 500, zombie: '任意' },
                       cooldown: 30, levels: [[{ op: '垫材', aim: null }]] });
                     PLAN.sel.rule = p.rescue.length - 1; },
    delRule: () => { p.rescue.splice(+el.dataset.rule, 1); PLAN.sel.rule = -1; },
    addLevel: () => { const r = p.rescue[+el.dataset.rule];
                      r.levels = r.levels || []; r.levels.push([{ op: '窝瓜', aim: null }]); },
    addLevelOp: () => { const lv = plPath(p, path);
                        (Array.isArray(lv) ? lv : (lv.ops = lv.ops || [])).push({ op: '窝瓜', aim: null }); },
    delLevelOp: () => { const arr = plPath(p, path.replace(/\.[^.]+$/, ''));
                        arr.splice(+path.split('.').pop(), 1); },
    validate: () => plValidate(),
    run: () => plRun(),
    save: () => plSave(),
    export: () => plExport(),
    import: () => document.getElementById('pl-file').click(),
    reset: async () => {
      if (!confirm('回到内置基线（当前编辑会丢）？')) return;
      const r = await fetch('/api/plan/default');
      PLAN.p = await r.json(); PLAN.dirty = false; plRender();
    },
    example: async () => {
      if (PLAN.dirty && !confirm('载入示例会覆盖当前编辑，继续？')) return;
      const r = await fetch('/api/plan/example');
      PLAN.p = await r.json(); PLAN.dirty = false;
      PLAN.sel = { wave: 5, set: -1, block: -1, rule: 0 };
      plRender();
    },
  };
  if (A[act]) { await A[act](); plRender(); }
});

PL.addEventListener('change', async e => {
  const el = e.target;
  if (el.id === 'pl-file') return;
  if (el.id === 'pl-open') {
    if (!el.value) return;
    const r = await fetch('/api/plan/load?name=' + encodeURIComponent(el.value));
    const p = await r.json();
    if (p && p.waves) {
      PLAN.p = p; PLAN.dirty = false;
      PLAN.sel = { wave: 1, set: -1, block: -1, rule: 0 };
      plRender();
    } else alert('读取失败：' + (p.error || '未知'));
    return;
  }
  if (el.id === 'pl-sys') {
    PLAN.p.rhythm.system = el.value;
    const s = PLAN.cat.rhythms.find(x => x.system === el.value);
    if (s && s.presets && s.presets.length) {
      PLAN.p.rhythm.name = s.presets[0].name;
      PLAN.p.rhythm.beats = s.presets[0].beats.slice();
    }
    return plRender();
  }
  if (el.id === 'pl-preset') {
    const s = PLAN.cat.rhythms.find(x => x.system === PLAN.p.rhythm.system) || {};
    const q = (s.presets || []).find(x => x.name === el.value);
    PLAN.p.rhythm.name = el.value;
    if (q) PLAN.p.rhythm.beats = q.beats.slice();
    return plRender();
  }
  if (el.id === 'pl-hasaim') {
    const path = e.target.closest('.insp').querySelector('input[data-key="0"]').dataset.path;
    const b = plPath(PLAN.p, path.split('.aim')[0]);
    b.aim = el.checked ? [1, 9] : null;
    return plRender();
  }
  if (el.id === 'pl-usep') {
    const b = PLAN.selBlockObj();
    if (!b) return;
    if (el.checked) b.repeat = { every: 100, times: null };
    else delete b.repeat;
    return plRender();
  }
  if (el.dataset.path) {
    const v0 = el.value;
    let v = v0;
    if (el.type === 'checkbox') {
      v = el.checked;
    } else if (el.dataset.arr) {
      v = v0.split(/[,，\s]+/).filter(Boolean).map(Number);
    } else if (el.type === 'number') {
      v = (v0 === '' ? null : +v0);
    }
    if (el.tagName === 'SELECT' && ['kind'].includes(el.dataset.key)
        && ['all', 'any', 'not'].includes(v0)) {
      const node = plPath(PLAN.p, el.dataset.path);
      if (!node.of) { const prev = Object.assign({}, node);
        for (const k of Object.keys(node)) delete node[k];
        node.kind = v0; node.of = v0 === 'not' ? [prev] : [prev]; }
    }
    plSet(PLAN.p, el.dataset.path + (el.dataset.key ? '.' + el.dataset.key : ''), v);
    if (el.dataset.key === 'kind') plFillDefaults(plPath(PLAN.p, el.dataset.path), v0);
    if (['kind', 'op', 'what', 'row', 'cmp', 'value', 'card', 'name', 'at',
         'zombie', 'axis', 'waves', 'offset', 'target', 'back', 'set',
         'negate'].includes(el.dataset.key)) return plRender();
    PLAN.dirty = true;
  }
});

PL.addEventListener('input', e => {
  const el = e.target;
  if (el.id === 'pl-name') { PLAN.p.name = el.value; PLAN.dirty = true; return; }
  if (el.id === 'pl-beats') {
    PLAN.p.rhythm.beats = el.value.split('|').map(s => s.trim()).filter(Boolean);
    PLAN.dirty = true; return;
  }
  if (el.id === 'pl-wavenote') {
    const row = (PLAN.p.waves || []).find(r => r.w === PLAN.sel.wave);
    if (row) { row.note = el.value; PLAN.dirty = true; }
    return;
  }
  if (el.id === 'pl-rep-every' || el.id === 'pl-rep-times') {
    const b = PLAN.selBlockObj();
    if (!b) return;
    b.repeat = b.repeat || { every: 100, times: null };
    if (el.id === 'pl-rep-every') b.repeat.every = +el.value || 100;
    else b.repeat.times = el.value === '' ? null : +el.value;
    PLAN.dirty = true;
  }
});

PLAN.selBlockObj = function () {
  const p = PLAN.p;
  const row = (p.waves || []).find(r => r.w === PLAN.sel.wave);
  if (!row) return null;
  const st = (row.sets || [])[PLAN.sel.set];
  if (!st) return null;
  return (st.ops || [])[PLAN.sel.block] || null;
};

function plMove(path, d) {
  const arr = plPath(PLAN.p, path.replace(/\.[^.]+$/, ''));
  const i = +path.split('.').pop(), j = i + d;
  if (j < 0 || j >= arr.length) return;
  const t = arr[i]; arr[i] = arr[j]; arr[j] = t;
}

/* ---------------- 校验 / 保存 / 跑 ---------------- */
async function plValidate() {
  const r = await fetch('/api/plan/validate', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan: PLAN.p }) });
  const d = await r.json();
  const box = document.getElementById('pl-issues');
  if (!d.issues || !d.issues.length) {
    box.innerHTML = '<span style="color:#059669">✓ 没发现问题</span>';
    return;
  }
  box.innerHTML = d.issues.map(x =>
    `<div class="issue ${x.lv === 'error' ? 'err' : 'warn'}">
      <b>${x.lv === 'error' ? '错误' : '提示'}</b>
      <span class="pltag">${plEsc(x.where)}</span> ${plEsc(x.msg)}</div>`).join('');
}

async function plSave() {
  const r = await fetch('/api/plan/save', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: PLAN.p.name, plan: PLAN.p }) });
  const d = await r.json();
  if (d.ok) { PLAN.dirty = false; alert('已存到：' + d.path); }
  else alert('保存失败：' + (d.error || '未知'));
}

function plExport() {
  const blob = new Blob([JSON.stringify(PLAN.p, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (PLAN.p.name || '阵解') + '.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

document.getElementById('pl-file').addEventListener('change', ev => {
  const f = ev.target.files && ev.target.files[0];
  if (!f) return;
  const rd = new FileReader();
  rd.onload = () => {
    try {
      const d = JSON.parse(rd.result);
      PLAN.p = d.plan || d;
      PLAN.sel = { wave: 1, set: -1, block: -1, rule: 0 };
      plRender();
    } catch (err) { alert('不是合法的阵解 JSON：' + err.message); }
  };
  rd.readAsText(f, 'utf-8');
  ev.target.value = '';
});

/* 用当前阵解跑：沿用「出怪沙盘」里勾好的出怪与次数 */
function plRun() {
  const kinds = [...sel];
  if (!kinds.length) {
    alert('先去「出怪沙盘」勾一份出怪 —— 阵解要有出怪才能跑');
    return;
  }
  const seeds = Math.max(1, Math.min(30, +document.getElementById('seeds').value || 1));
  queue.push({ name: (PLAN.p.name || '阵解') + ' · 试跑', kinds, seeds,
               plan: JSON.parse(JSON.stringify(PLAN.p)) });
  renderQueue();
  plTab('spawn');
  document.getElementById('start').click();
}

/* ---------------- 切换标签页 ---------------- */
function plTab(which) {
  const spawn = document.getElementById('tab-spawn');
  const planp = document.getElementById('planpage');
  spawn.style.display = which === 'spawn' ? '' : 'none';
  planp.style.display = which === 'plan' ? '' : 'none';
  for (const b of document.querySelectorAll('.tabs button')) {
    b.classList.toggle('on', b.dataset.tab === which);
  }
  if (which === 'plan' && !PLAN.p) plBoot();
}
for (const b of document.querySelectorAll('.tabs button')) {
  b.onclick = () => plTab(b.dataset.tab);
}

async function plBoot() {
  const [cat, def] = await Promise.all([
    fetch('/api/plan/catalog').then(r => r.json()),
    fetch('/api/plan/default').then(r => r.json()),
  ]);
  PLAN.cat = cat;
  window.ZOMBIES = cat.zombies;
  PLAN.p = def;
  plRender();
  // 桌面版有 plans/ 目录：列出已保存的阵解（网页版是空列表，就不显示这个下拉）
  try {
    const d = await fetch('/api/plan/list').then(r => r.json());
    const names = d.names || [];
    if (names.length) {
      const sel = document.getElementById('pl-open');
      sel.innerHTML = '<option value="">（打开已保存）</option>'
        + names.map(n => `<option value="${plEsc(n)}">${plEsc(n)}</option>`).join('');
      sel.style.display = '';
      document.getElementById('pl-open-lab').style.display = '';
    }
  } catch (e) { /* 网页版忽略 */ }
}
</script>
'''
