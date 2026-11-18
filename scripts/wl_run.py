"""wl_run.py —— 目录驱动 + 确认弹窗 + 复检

三处照抄 GitHub 项目：
  ① 完成判定   li.className.includes('course_disable')      (welearn-auto L433)
  ② 已提交判定 submit 按钮 display:none / submitinfo 文本     (welearn-auto L100-110)
  ③ 提交        点 Submit 后必须处理确认弹窗                   (welearn-auto L325/L340)
用法：
  python wl_run.py --scan          # 只列待做
  python wl_run.py --plan 5        # 做 5 节
  python wl_run.py --sco ITEM-xxx  # 做指定节点
"""
import json, os, re, sys, time, argparse, datetime, random
sys.path.insert(0, ".")
from wl_cdp import Mini

ROOT = os.path.dirname(os.path.abspath(__file__))
# 配置查找顺序：同目录 -> ../assets -> 上级目录
_cands = [
    os.path.join(ROOT, "wl_config.json"),
    os.path.join(ROOT, "..", "assets", "wl_config.json"),
    os.path.join(ROOT, "..", "wl_config.json"),
]
CFG_PATH = next((x for x in _cands if os.path.exists(x)), _cands[0])

def load_cfg():
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"cid": "2415", "classid": "783311", "debug_port": 9224,
                "units": [1,2,3,4], "stay_seconds": 60, "stay_jitter": 8,
                "skip_record": True, "max_sections": 200, "result_log": "wl_run_log.json"}

CFG = load_cfg()
CATALOG = CFG["catalog_url"].format(cid=CFG["cid"], classid=CFG["classid"])
LOG = os.path.join(ROOT, CFG.get("result_log", "wl_run_log.json"))
PORT = int(CFG.get("debug_port", 9224))

def log(m=""):
    line = f"[{datetime.datetime.now():%H:%M:%S}] {m}" if m else ""
    print(line, flush=True)
    try:
        d = json.load(open(LOG, encoding="utf-8")) if __import__("os").path.exists(LOG) else []
    except Exception:
        d = []
    d.append(line)
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- iframe 内脚本 ----------
JS_STATE = r"""(() => {
  const f = document.getElementById('contentFrame');
  if (!f) return JSON.stringify({ noFrame: 1 });
  let d, W;
  try { d = f.contentDocument; W = f.contentWindow; } catch (e) { return JSON.stringify({ noAccess: 1 }); }
  if (!d || !d.body) return JSON.stringify({ noBody: 1 });

  const subs = [...d.querySelectorAll('et-button,button,span,a')]
    .filter(e => /^Submit$/i.test((e.innerText || '').trim()));
  const vis = subs.find(e => W.getComputedStyle(e).display !== 'none' && e.offsetParent !== null);

  // ② 已提交判定（照抄 welearn-auto L100-110）
  const subBtn = d.querySelector('[data-controltype="submit"]');
  let submitted = false;
  if (subBtn && W.getComputedStyle(subBtn).display === 'none') submitted = true;
  const info = d.querySelector('[data-controltype="submitinfo"]');
  if (info && !/尚未提交/.test(info.textContent || '')) submitted = true;

  return JSON.stringify({
    hash: d.location.hash.split('?')[0],
    blank: d.querySelectorAll('et-blank').length,
    choice: d.querySelectorAll('et-choice').length,
    canSubmit: !!vis,
    submitted: submitted,
    score: [...d.querySelectorAll('[class*="score"]')].map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 2),
    head: (d.body.innerText || '').slice(0, 80).replace(/\n/g, ' | ')
  });
})()"""

JS_FILL = r"""(() => {
  const f = document.getElementById('contentFrame');
  const d = f.contentDocument, W = f.contentWindow;
  let rs; try { rs = W.angular.element(d.body).injector().get('$rootScope'); } catch (e) { return JSON.stringify({ err: 'no-root' }); }
  const seen = new Set(), blanks = [], choices = [];
  const walk = sc => { if (!sc) return;
    try { const o = sc.blank;  if (o && 'key' in o && !seen.has(o)) { seen.add(o); blanks.push(o); } } catch (e) {}
    try { const o = sc.choice; if (o && 'key' in o && !seen.has(o)) { seen.add(o); choices.push(o); } } catch (e) {}
    let c = sc.$$childHead; while (c) { walk(c); c = c.$$nextSibling; }
  };
  try { walk(rs); } catch (e) {}

  let bSet = 0, bNoKey = 0;
  blanks.forEach(b => {
    const k = Array.isArray(b.key) ? b.key : [b.key];
    const a = k.length ? String(k[0] ?? '').trim() : '';
    if (!a) { bNoKey++; return; }
    try { b.value = Array.isArray(b.value) ? [a] : a; bSet++; } catch (e) {}
  });
  let cSet = 0;
  choices.forEach(ch => {
    const k = Array.isArray(ch.key) ? ch.key : [ch.key];
    if (!k.length || k[0] === undefined) return;
    try { if (typeof ch.select === 'function') { ch.select(k[0]); cSet++; } else { ch.value = k.slice(); cSet++; } } catch (e) {}
  });
  try { rs.$apply(); } catch (e) {}
  return JSON.stringify({ blank: blanks.length, bSet, bNoKey, choice: choices.length, cSet });
})()"""

JS_SUBMIT = r"""(() => {
  const f = document.getElementById('contentFrame');
  const d = f.contentDocument, W = f.contentWindow;
  try { W.confirm = function () { return true; }; } catch (e) {}   // 照抄 auto-answer L400
  const subs = [...d.querySelectorAll('et-button,button,span,a')]
    .filter(e => /^Submit$/i.test((e.innerText || '').trim()));
  const vis = subs.find(e => W.getComputedStyle(e).display !== 'none' && e.offsetParent !== null);
  if (!vis) return 'no-submit';
  vis.click();
  return 'clicked';
})()"""

JS_CONFIRM = r"""(() => {
  const f = document.getElementById('contentFrame');
  const d = f.contentDocument, W = f.contentWindow;

  // 1 实测弹窗结构：.ng-confirm-box > .ng-confirm-title + button.btn.btn-primary「继续提交」
  const box = d.querySelector('.ng-confirm-box');
  if (box && box.offsetParent !== null) {
    const pri = box.querySelector('button.btn-primary, button[class*="primary"]');
    if (pri) {
      // 勾「以后不再提示」
      try {
        const cb = box.querySelector('input[type=checkbox]');
        if (cb && !cb.checked) cb.click();
      } catch (e) {}
      const t = (pri.innerText || '').trim();
      pri.click();
      return JSON.stringify({ hit: 'ng-confirm:' + t, done: true });
    }
    // 按钮是用 span 写的兜底
    const sp = [...box.querySelectorAll('button,span,a')]
      .find(e => /继续提交|确认提交|确定|确认/.test((e.innerText || '').trim()));
    if (sp) { sp.click(); return JSON.stringify({ hit: 'ng-confirm-span:' + (sp.innerText||'').trim(), done: true }); }
  }

  // 2 layui 旧弹层
  for (const sel of ['.layui-layer-btn0', '.layui-layer-btn a', '.layui-layer-btn button']) {
    const b = d.querySelector(sel);
    if (b && b.offsetParent !== null) {
      b.click(); return JSON.stringify({ hit: 'layui:' + sel, done: true });
    }
  }

  // 3 按文案优先级
  const PRIORITY = [/^继续提交$/, /^确认提交$/, /^确定$/, /^确认$/, /^是$/, /^提交$/, /^OK$/i, /^Yes$/i];
  const deny = /取消|关闭|Cancel/i;
  const cands = [...d.querySelectorAll('button,a,span,et-button')]
    .filter(e => e.offsetParent !== null && !/vjs-/.test((e.className || '').toString()))
    .filter(e => { const t = (e.innerText || '').trim(); return t && t.length <= 14 && !deny.test(t); });
  for (const re of PRIORITY) {
    const b = cands.find(e => re.test((e.innerText || '').trim()));
    if (b) { b.click(); return JSON.stringify({ hit: 'text:' + (b.innerText||'').trim(), done: true }); }
  }
  return JSON.stringify({ hit: [], done: false });
})()"""

JS_ANY_DIALOG = r"""(() => {
  const f = document.getElementById('contentFrame');
  const d = f.contentDocument;
  const layers = [...d.querySelectorAll('[class*="layer"],[class*="modal"],[class*="dialog"],[class*="popup"],[role="dialog"]')]
    .filter(e => e.offsetParent !== null)
    .map(e => ({ cls: (e.className || '').toString().slice(0, 50), t: (e.innerText || '').trim().slice(0, 90) }));
  return JSON.stringify(layers.slice(0, 5));
})()"""

JS_RECORD = r"""(() => {
  const f = document.getElementById('contentFrame');
  if (!f) return JSON.stringify({ noFrame: 1 });
  const d = f.contentDocument, W = f.contentWindow;
  const hits = [];
  // 1 自定义元素 / class
  const sel = ['et-record','et-recorder','et-speak','et-speaking','et-voice',
               '[class*="record"]','[class*="Record"]','[class*="recorder"]',
               '[class*="speak"]','[class*="Speak"]','[class*="voice"]','[class*="Voice"]',
               '[class*="microphone"]','[class*="mic-"]'];
  for (const q of sel) {
    const els = [...d.querySelectorAll(q)].filter(e => e.offsetParent !== null);
    if (els.length) hits.push({ sel: q, n: els.length,
      sample: (els[0].innerText || '').trim().slice(0, 40),
      cls: (els[0].className || '').toString().slice(0, 44) });
  }
  // 2 文本关键字
  const txt = (d.body.innerText || '');
  const kw = ['record', 'recording', '录音', '录制', '语音', '口语', '朗读', 'speak aloud',
              'read aloud', 'pronunciation practice', 'record your voice', 'microphone'];
  const matched = kw.filter(k => new RegExp(k, 'i').test(txt));
  // 3 MediaRecorder / getUserMedia 痕迹
  const hasMR = typeof W.MediaRecorder !== 'undefined';
  const mrUsed = !!W.__mrUsed;
  return JSON.stringify({
    hash: d.location.hash.split('?')[0],
    elements: hits,
    keywords: matched,
    mediaRecorder: hasMR,
    isRecord: hits.length > 0 || matched.length > 0
  });
})()"""

JS_TABS = r"""(() => {
  const d = document.getElementById('contentFrame').contentDocument;
  const tabs = [...d.querySelectorAll('span,li,div,a')].filter(e =>
    e.children.length === 0 && e.offsetParent !== null &&
    /^(I{1,3}|IV|V)\.$/.test((e.innerText || '').trim()));
  return JSON.stringify(tabs.map((e, i) => ({
    i, t: (e.innerText || '').trim(),
    cls: (e.className || '').toString().slice(0, 40),
    active: /active|on\b|cur|selected/i.test((e.className || '').toString())
  })));
})()"""

JS_CLICK_TAB = r"""(function(idx){
  const d = document.getElementById('contentFrame').contentDocument;
  const tabs = [...d.querySelectorAll('span,li,div,a')].filter(e =>
    e.children.length === 0 && e.offsetParent !== null &&
    /^(I{1,3}|IV|V)\.$/.test((e.innerText || '').trim()));
  const t = tabs[idx];
  if (!t) return 'no-tab';
  const target = (t.parentElement && t.parentElement.tagName === 'LI') ? t.parentElement : t;
  const r = target.getBoundingClientRect();
  const ev0 = { bubbles: true, cancelable: true, view: d.defaultView,
                clientX: Math.round(r.left + r.width / 2),
                clientY: Math.round(r.top + r.height / 2),
                button: 0, buttons: 1, detail: 1 };
  target.dispatchEvent(new MouseEvent('mousedown', ev0));
  target.dispatchEvent(new MouseEvent('mouseup', Object.assign({}, ev0, { buttons: 0 })));
  target.dispatchEvent(new MouseEvent('click', Object.assign({}, ev0, { buttons: 0 })));
  try { target.click(); } catch (e) {}
  return 'tab-clicked:' + t.innerText.trim();
})"""

JS_DIR = r"""(() => {
  // 目录全量叶子条目（含教师未开放的），按 DOM 顺序推单元号；
  // 只有带 SelectSCO 的 open 项才可能去刷；done 仍用 course_disable 判定
  const lis = [...document.querySelectorAll('li')]
    .filter(li => /courseware_list_1_4/.test((li.className || '').toString()));
  const rows = [];
  let unit = 0;
  for (const li of lis) {
    const cls = (li.className || '').toString();
    const a = li.querySelector('a');
    const on = a ? (a.getAttribute('onclick') || '') : '';
    const name = (li.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 42);
    if (/^01\.\s*Unit Goals/i.test(name)) unit += 1;
    const m = on.match(/SelectSCO\(['"]([^'"]+)/);
    rows.push({ sco: m ? m[1] : null, name: name, unit: unit,
                open: !!m, done: cls.includes('course_disable') });
  }
  return JSON.stringify(rows);
})()"""

def read_dir(m, sid, quiet=False):
    m.send("Page.navigate", {"url": CATALOG}, sid)
    time.sleep(8)
    rows = []
    for _ in range(8):
        r = m.ev(sid, JS_DIR)
        try:
            rows = json.loads(r) or []
        except Exception:
            rows = []
        if len(rows) >= 20:            # 目录已渲染到全量（140 节课程约 150+ 叶子）
            break
        time.sleep(2)
    return rows

def open_sco(m, sid, sco):
    ok = m.ev(sid, "(function(){const a=document.querySelector('a[onclick*=\"%s\"]'); if(a){a.click();return 1;} return 0;})()" % sco)
    if not ok:
        return False
    time.sleep(6)
    for _ in range(10):
        if m.ev(sid, "!!document.getElementById('contentFrame')"):
            return True
        time.sleep(2)
    return False

def do_tab_body(m, sid):
    """当前 tab 内：填 -> 提交 -> 确认"""
    sol = json.loads(m.ev(sid, JS_FILL) or "{}")
    log(f"      填: blank {sol.get('bSet')}/{sol.get('blank')} 无key={sol.get('bNoKey')} choice {sol.get('cSet')}/{sol.get('choice')}")
    if sol.get("bSet", 0) == 0 and sol.get("cSet", 0) == 0:
        return "no-answer"

    r = m.ev(sid, r"""(() => {
      const d = document.getElementById('contentFrame').contentDocument;
      const W = d.defaultView;
      try { W.confirm = () => true; } catch (e) {}
      // 真按钮：et-button 内部的 button[ng-click="btn.doAction()"]
      let btns = [...d.querySelectorAll('button[ng-click="btn.doAction()"], et-button > button, button')]
        .filter(e => /^Submit$/i.test((e.innerText || '').trim()))
        .filter(e => e.offsetParent !== null && W.getComputedStyle(e).display !== 'none');
      if (!btns.length) {
        // 回退：et-button / span
        btns = [...d.querySelectorAll('et-button,span.main.btn-group')]
          .filter(e => /^Submit$/i.test((e.innerText || '').trim()))
          .filter(e => e.offsetParent !== null);
      }
      if (!btns.length) return 'no-submit';
      const cy = W.innerHeight / 2;
      btns.sort((a, b) => Math.abs(a.getBoundingClientRect().top - cy) - Math.abs(b.getBoundingClientRect().top - cy));
      btns[0].scrollIntoView({ block: 'center' });
      btns[0].click();
      return 'clicked:' + btns[0].tagName + ':' + btns.length;
    })()""")
    if not str(r).startswith("clicked"):
        return "submit-fail"
    log(f"      submit: {r}")

    # 等弹窗出现（实测约 0.5-1.5 秒）
    c = None
    for _ in range(6):
        time.sleep(0.8)
        c = m.ev(sid, JS_CONFIRM)
        try:
            if json.loads(c).get("done"):
                break
        except Exception:
            pass
    log(f"      confirm: {c}")
    time.sleep(2.5)
    # 可能还有第二层
    c2 = m.ev(sid, JS_CONFIRM)
    log(f"      confirm2: {c2}")
    time.sleep(2)
    return "submitted"


def do_all_tabs(m, sid):
    """遍历本页所有 tab，每个 tab 填+提交"""
    tabs = []
    try:
        tabs = json.loads(m.ev(sid, JS_TABS) or "[]")
    except Exception:
        tabs = []
    if not tabs:
        log("      页内 tab: 无（单页处理）")
        return [do_tab_body(m, sid)]

    log(f"      页内 tab: {[t['t'] for t in tabs]}")
    out = []
    for i, t in enumerate(tabs):
        m.ev(sid, f"{JS_CLICK_TAB}({i})")
        time.sleep(2.5)
        log(f"      切到 {t['t']}")
        out.append(do_tab_body(m, sid))
        time.sleep(1.2)
    return out


def do_one(m, sid, row):
    name, sco = row["name"], row["sco"]
    unit = row.get("unit")
    t0 = time.time()
    log(f"--- [U{unit}] {name}  {sco[:24]}")
    if not open_sco(m, sid, sco):
        return "open-fail"
    time.sleep(2)
    st = json.loads(m.ev(sid, JS_STATE) or "{}")
    log(f"    {st.get('hash')} blank={st.get('blank')} choice={st.get('choice')} "
        f"canSubmit={st.get('canSubmit')} submitted={st.get('submitted')} score={st.get('score')}")

    if st.get("submitted") or not st.get("canSubmit"):
        el = time.time() - t0
        if el < CFG.get("stay_seconds", 60):
            stay(int(CFG["stay_seconds"] - el), CFG.get("stay_jitter", 8))
        return "already-done"

    # 录音题 -> 跳过不写
    try:
        rec = json.loads(m.ev(sid, JS_RECORD) or "{}")
    except Exception:
        rec = {}
    if rec.get("isRecord") and CFG.get("skip_record", True):
        log(f"    录音题 -> 整页跳过  元件={[e['sel'] for e in rec.get('elements', [])][:3]}")
        el = time.time() - t0
        if el < CFG.get("stay_seconds", 60):
            stay(int(CFG["stay_seconds"] - el), CFG.get("stay_jitter", 8))
        return "skip-record"

    res = do_all_tabs(m, sid)
    log(f"    本页结果: {res}")

    el = time.time() - t0
    if el < CFG.get("stay_seconds", 60):
        stay(int(CFG["stay_seconds"] - el), CFG.get("stay_jitter", 8))

    if all(x == "no-answer" for x in res):
        return "no-answer"
    if all(x in ("no-answer", "submit-fail") for x in res):
        return "submit-fail"
    return "submitted"

def unit_of(rows):
    """单元号已在 JS_DIR 里按目录 DOM 顺序打好（含教师未开放条目），这里只做兜底"""
    if not any(r.get("unit") for r in rows):
        u = 0
        for r in rows:
            if re.match(r"^01\.\s*Unit Goals", r["name"]):
                u += 1
            r["unit"] = u or 1
    return rows


def stay(sec, jitter):
    """停留补足：保证本节总时长不少于 sec 秒"""
    if sec <= 0:
        return
    w = sec + random.randint(0, max(0, int(jitter)))
    log(f"    停留 {w}s（本节补足到 {sec}s+）")
    time.sleep(w)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--plan", type=int, default=0)
    ap.add_argument("--sco", type=str, default="")
    a = ap.parse_args()

    m = Mini(PORT, 45)
    p = m.page(0)
    sid = m.attach(p["targetId"])

    rows = read_dir(m, sid)
    rows = unit_of(rows)
    want = set(CFG.get("units") or [])
    opens = [r for r in rows if r.get("open")]
    todo = [r for r in opens if not r["done"] and (not want or r.get("unit") in want)]
    log(f"只做单元: {sorted(want) if want else '全部'}")
    log(f"目录: 叶子 {len(rows)} | 教师开放 {len(opens)} | 已完成 {len(opens)-len(todo)} | 待做 {len(todo)}")
    if a.scan:
        for i, r in enumerate(todo, 1):
            log(f"  {i:3}. [U{r.get('unit')}] {r['name']:40} {r['sco'][:30]}")
        m.close()
        return

    if a.sco:
        row = next((r for r in rows if r["sco"] == a.sco), None)
        if not row:
            log("找不到该 SCO")
            m.close()
            return
        r = do_one(m, sid, row)
        rows2 = read_dir(m, sid)
        now = next((x for x in rows2 if x["sco"] == a.sco), None)
        log(f"结果 {r} | 目录复检: {'DONE' if now and now['done'] else 'TODO'}")
        m.close()
        return

    stat = {}
    n = len(todo) if a.plan <= 0 else min(a.plan, len(todo))
    for i, row in enumerate(todo[:n], 1):
        log(f"[{i}/{n}]")
        r = do_one(m, sid, row)
        stat[r] = stat.get(r, 0) + 1
        # 复检
        rows2 = read_dir(m, sid)
        now = next((x for x in rows2 if x["sco"] == row["sco"]), None)
        ok = bool(now and now["done"])
        log(f"    目录复检: {'DONE ✓' if ok else 'TODO ✗'}")
        stat["verified" if ok else "not-verified"] = stat.get("verified" if ok else "not-verified", 0) + 1

    log("")
    log("===== 汇总 =====")
    for k, v in sorted(stat.items()):
        log(f"  {k:14} {v}")
    m.close()

if __name__ == "__main__":
    main()