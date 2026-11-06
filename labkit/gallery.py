"""図ギャラリー（reports/figure_gallery.html）と解析ビューア（reports/analyses_viewer.html）を作る。

どちらも analyses/ の manifest.json・notes.md・out/ を読むだけで、解析フォルダは動かさない。
画像は相対パスで参照するので、Finder から HTML を開けばそのまま表示される（ネット接続は不要）。

    labkit gallery           # 二つとも作り直す
"""
from __future__ import annotations

import csv
import html
import json
import os
import re

from . import analysis as _an

IMG_EXT = (".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp")


def _lineage_key(ana_id: str) -> str:
    """ana-20250914-ppp-avrami-2 → ppp-avrami（日付と版番号を外した名前）。"""
    s = re.sub(r"^ana-\d{8}-", "", ana_id)
    return re.sub(r"-\d+$", "", s)


def _ledger_rows(root: str) -> dict:
    p = os.path.join(root, "ledger.csv")
    if not os.path.exists(p):
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {r["meas_id"]: r for r in csv.DictReader(f)}


def collect(root: str) -> dict:
    ledger = _ledger_rows(root)
    items = _an.list_all(root)
    # 系統: supersedes の連なりと、同じ名前（-2, -3 …の版）を一つにまとめる
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    by_key: dict[str, str] = {}
    for A in items:
        find(A.ana_id)
        k = _lineage_key(A.ana_id)
        if k in by_key:
            union(A.ana_id, by_key[k])
        else:
            by_key[k] = A.ana_id
        s = A.manifest.get("supersedes")
        if s:
            union(A.ana_id, s)

    superseded_by = {}
    for A in items:
        s = A.manifest.get("supersedes")
        if s:
            superseded_by[s] = A.ana_id

    analyses, figures = [], []
    for A in items:
        m = A.manifest
        rel_dir = os.path.relpath(A.dir, root).replace(os.sep, "/")
        ext = m.get("external_dir")
        notes = ""
        if os.path.exists(A.notes_path):
            with open(A.notes_path, encoding="utf-8") as f:
                notes = f.read()
        fig_dirs = [(A.out_dir, rel_dir + "/out")]
        if ext:
            fig_dirs.append((os.path.join(root, *ext.split("/")), ext))
        figs = []
        for absdir, reldir in fig_dirs:
            if not os.path.isdir(absdir):
                continue
            for dp, dns, fns in os.walk(absdir):
                dns[:] = sorted(d for d in dns if not d.startswith((".", "__")))
                for fn in sorted(fns):
                    if fn.lower().endswith(IMG_EXT):
                        r = os.path.relpath(os.path.join(dp, fn), absdir).replace(os.sep, "/")
                        stem = os.path.splitext(os.path.join(dp, fn))[0]
                        pdf = stem + ".pdf"
                        figs.append({
                            "src": "../" + reldir + "/" + r,
                            "name": r,
                            "pdf": ("../" + reldir + "/" + os.path.splitext(r)[0] + ".pdf") if os.path.exists(pdf) else "",
                        })
        s = m.get("inputs_summary", {})
        created = (m.get("created") or "")[:10]
        rec = {
            "id": A.ana_id,
            "created": created,
            "status": m.get("status", ""),
            "question": m.get("question", ""),
            "procedure": m.get("procedure", ""),
            "params": m.get("params", {}),
            "results": m.get("results"),
            "samples": s.get("samples", []),
            "instr": s.get("instr", []),
            "inputs": [{"id": i, **{k: ledger.get(i, {}).get(k, "") for k in
                                    ("date", "sample", "thermal_history", "path", "status")}}
                       for i in m.get("inputs", [])],
            "supersedes": m.get("supersedes") or "",
            "superseded_by": superseded_by.get(A.ana_id, ""),
            "based_on": m.get("based_on") or "",
            "lineage": find(A.ana_id),
            "dir": "../" + (ext or rel_dir),
            "notes": notes,
            "figs": figs,
        }
        analyses.append(rec)
        for i, fg in enumerate(figs):
            figures.append({**fg, "ana": A.ana_id, "status": rec["status"], "samples": rec["samples"],
                            "created": created, "question": rec["question"]})
    return {"analyses": analyses, "figures": figures}


def _write(path: str, template: str, data: dict, title: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8") as f:
        f.write(template.replace("__TITLE__", html.escape(title)).replace("__DATA__", payload))


def build(root: str | None = None, quiet: bool = False) -> list[str]:
    from .build_ledger import find_project_root, load_config
    root = os.path.abspath(root or find_project_root())
    name = load_config(root).get("name") or os.path.basename(root)
    data = collect(root)
    reports = os.path.join(root, "reports")
    g = os.path.join(reports, "figure_gallery.html")
    v = os.path.join(reports, "analyses_viewer.html")
    _write(g, GALLERY_HTML, data, "%s — 図ギャラリー" % name)
    _write(v, VIEWER_HTML, data, "%s — 解析ビューア" % name)
    if not quiet:
        print("図ギャラリー: %d 枚 -> %s" % (len(data["figures"]), g))
        print("解析ビューア: %d 件 -> %s" % (len(data["analyses"]), v))
    return [g, v]


_CSS = r"""
:root{--bg:#f5f8f7;--card:#fff;--fg:#16232a;--mut:#5a6b72;--rule:#d3dedb;--acc:#1462a8;
--used:#2f8f6b;--tried:#1462a8;--rej:#b8452a;--wash:#eef3f1;
font-family:"Hiragino Sans","Yu Gothic",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#11191c;--card:#172226;--fg:#e2ebe8;--mut:#97a9ae;--rule:#2c3b40;
--acc:#6ea9e3;--used:#5ec49c;--tried:#6ea9e3;--rej:#e2795d;--wash:#0d1416;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-size:14px;line-height:1.6}
a{color:var(--acc)}code,.mono{font-family:Menlo,Consolas,monospace;font-size:12px}
header{padding:14px 20px;border-bottom:1px solid var(--rule);display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
header h1{font-size:17px;margin:0}
.chip{border:1px solid var(--rule);background:var(--card);color:var(--fg);border-radius:999px;padding:1px 10px;cursor:pointer;font:inherit;font-size:12.5px}
.chip.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.st{font-size:11px;border-radius:3px;padding:0 6px;border:1px solid currentColor}
.st-used{color:var(--used)}.st-tried{color:var(--tried)}.st-rejected{color:var(--rej)}
input,select{font:inherit;padding:3px 8px;border:1px solid var(--rule);border-radius:4px;background:var(--card);color:var(--fg)}
"""

GALLERY_HTML = r"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title><style>""" + _CSS + r"""
.bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.bar b{font-size:12px;color:var(--mut);margin-right:2px}
main{padding:16px 20px}.grp h2{font-size:14px;margin:22px 0 8px;color:var(--mut);border-bottom:1px solid var(--rule)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.fig{background:var(--card);border:1px solid var(--rule);border-radius:6px;overflow:hidden;display:flex;flex-direction:column}
.fig img{width:100%;aspect-ratio:4/3;object-fit:contain;background:#fff;cursor:zoom-in;display:block}
.fig .m{padding:6px 8px;font-size:12px;display:grid;gap:2px}.fig .q{color:var(--mut)}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;flex-direction:column;align-items:center;justify-content:center;padding:16px;z-index:9}
#lb.on{display:flex}#lb img{max-width:96vw;max-height:80vh;background:#fff}#lb .cap{color:#eee;font-size:13px;margin-top:10px;text-align:center;max-width:90vw}
#lb .cap a{color:#9cc7ff}.empty{color:var(--mut);padding:40px 0}
</style></head><body>
<header><h1>__TITLE__</h1>
<div class="bar" id="fs"><b>試料</b></div><div class="bar" id="fst"><b>状態</b></div>
<div class="bar"><b>月</b><select id="fm"><option value="">すべて</option></select></div>
<div class="bar"><b>まとめ</b><select id="fg"><option value="date">日付</option><option value="ana">解析</option><option value="sample">試料</option></select></div>
<input id="fq" type="search" placeholder="語句で絞る（解析ID・問い・ファイル名）" size="30">
<span class="mono" id="cnt"></span></header>
<main id="main"></main>
<div id="lb" role="dialog" aria-modal="true"><img id="lbi" alt=""><div class="cap" id="lbc"></div></div>
<script>
const D=__DATA__;const F=D.figures;const st={sample:'',status:'',month:'',q:'',group:'date'};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function chips(id,key,vals){const el=document.getElementById(id);['',...vals].forEach(v=>{const b=document.createElement('button');b.className='chip'+(v===''?' on':'');b.textContent=v||'すべて';b.onclick=()=>{st[key]=v;[...el.querySelectorAll('.chip')].forEach(x=>x.classList.toggle('on',x===b));draw()};el.appendChild(b)})}
chips('fs','sample',[...new Set(F.flatMap(f=>f.samples))].sort());
chips('fst','status',[...new Set(F.map(f=>f.status))].sort());
[...new Set(F.map(f=>f.created.slice(0,7)))].sort().reverse().forEach(m=>{const o=document.createElement('option');o.value=o.textContent=m;fm.appendChild(o)});
fm.onchange=()=>{st.month=fm.value;draw()};fg.onchange=()=>{st.group=fg.value;draw()};fq.oninput=()=>{st.q=fq.value.toLowerCase();draw()};
let shown=[];
function draw(){shown=F.filter(f=>(!st.sample||f.samples.includes(st.sample))&&(!st.status||f.status===st.status)&&(!st.month||f.created.startsWith(st.month))&&(!st.q||(f.ana+' '+f.question+' '+f.name).toLowerCase().includes(st.q)));
cnt.textContent=shown.length+' / '+F.length+' 枚';const g={};
shown.forEach((f,i)=>{const ks=st.group==='date'?[f.created]:st.group==='ana'?[f.ana]:(f.samples.length?f.samples:['（試料なし）']);ks.forEach(k=>(g[k]=g[k]||[]).push(i))});
const keys=Object.keys(g).sort();if(st.group==='date')keys.reverse();
main.innerHTML=keys.length?keys.map(k=>'<section class="grp"><h2>'+esc(k)+'</h2><div class="grid">'+g[k].map(i=>{const f=shown[i];return '<div class="fig"><img loading="lazy" src="'+esc(f.src)+'" alt="'+esc(f.name)+'" data-i="'+i+'"><div class="m"><span>'+esc(f.name)+'</span><a class="mono" href="analyses_viewer.html#'+esc(f.ana)+'">'+esc(f.ana)+'</a><span class="q">'+esc(f.question)+'</span><span><span class="st st-'+esc(f.status)+'">'+esc(f.status)+'</span> '+(f.pdf?'<a href="'+esc(f.pdf)+'">PDF</a>':'')+'</span></div></div>'}).join('')+'</div></section>').join(''):'<p class="empty">図がありません。解析の out/ に PNG か SVG を保存して labkit gallery を回してください。</p>';
main.querySelectorAll('img').forEach(im=>im.onclick=()=>open_(+im.dataset.i))}
let cur=-1;function open_(i){cur=(i+shown.length)%shown.length;const f=shown[cur];lbi.src=f.src;lbc.innerHTML=esc(f.name)+' · <a href="analyses_viewer.html#'+esc(f.ana)+'">'+esc(f.ana)+'</a><br>'+esc(f.question)+' <span class="mono">('+(cur+1)+'/'+shown.length+'　← → で送る、Esc で閉じる)</span>';lb.classList.add('on')}
lb.onclick=e=>{if(e.target===lb)lb.classList.remove('on')};
addEventListener('keydown',e=>{if(!lb.classList.contains('on'))return;if(e.key==='Escape')lb.classList.remove('on');if(e.key==='ArrowRight')open_(cur+1);if(e.key==='ArrowLeft')open_(cur-1)});
draw();
</script></body></html>"""

VIEWER_HTML = r"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title><style>""" + _CSS + r"""
.wrap{display:grid;grid-template-columns:340px minmax(0,1fr);min-height:calc(100vh - 56px)}
@media (max-width:800px){.wrap{grid-template-columns:1fr}}
aside{border-right:1px solid var(--rule);padding:10px 12px;overflow:auto;max-height:calc(100vh - 56px)}
aside details{margin:2px 0}aside summary{cursor:pointer;font-weight:700;padding:3px 0}
.lin{margin:4px 0 8px 10px;padding-left:8px;border-left:2px solid var(--rule)}
.lin .lk{font-size:11.5px;color:var(--mut)}
.it{display:block;padding:2px 6px;border-radius:4px;text-decoration:none;color:var(--fg);font-size:12.5px}
.it:hover{background:var(--wash)}.it.cur{background:var(--fg);color:var(--bg)}
.it.rejected{text-decoration:line-through;opacity:.7}
section#d{padding:16px 24px;min-width:0}section#d h2{font-size:16px;margin:4px 0 8px}
table{border-collapse:collapse;font-size:12.5px;width:100%}td,th{border-bottom:1px solid var(--rule);padding:4px 8px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:400;white-space:nowrap}.tw{overflow-x:auto}
pre{background:var(--wash);border:1px solid var(--rule);border-radius:4px;padding:10px;white-space:pre-wrap;font-size:12.5px}
.figs{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}.figs img{width:100%;background:#fff;border:1px solid var(--rule)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 14px;margin:8px 0}dt{color:var(--mut)}dd{margin:0;min-width:0;overflow-wrap:anywhere}
</style></head><body>
<header><h1>__TITLE__</h1><input id="q" type="search" placeholder="解析IDや問いで絞る" size="28"><a href="figure_gallery.html">図ギャラリーへ</a><span class="mono" id="cnt"></span></header>
<div class="wrap"><aside id="tree"></aside><section id="d"><p>左の木から解析を選んでください。</p></section></div>
<script>
const D=__DATA__;const A=D.analyses;const byId=Object.fromEntries(A.map(a=>[a.id,a]));
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function tree(f){const g={};A.filter(a=>!f||(a.id+' '+a.question).toLowerCase().includes(f)).forEach(a=>{(a.samples.length?a.samples:['（試料なし）']).forEach(s=>{g[s]=g[s]||{};(g[s][a.lineage]=g[s][a.lineage]||[]).push(a)})});
cnt.textContent=A.length+' 件';
tree_.innerHTML=Object.keys(g).sort().map(s=>'<details open><summary>'+esc(s)+' <span class="mono">('+Object.values(g[s]).flat().length+')</span></summary>'+Object.values(g[s]).sort((x,y)=>x[0].created<y[0].created?1:-1).map(L=>{L.sort((x,y)=>x.id<y.id?-1:1);return '<div class="lin"><div class="lk">'+esc(L[L.length-1].question.slice(0,40))+'</div>'+L.map(a=>'<a class="it '+esc(a.status)+'" href="#'+esc(a.id)+'">'+esc(a.id.replace(/^ana-/,''))+' <span class="st st-'+esc(a.status)+'">'+esc(a.status)+'</span></a>').join('')+'</div>'}).join('')+'</details>').join('')||'<p>解析がまだありません。</p>';mark()}
const tree_=document.getElementById('tree');
function kv(o){if(!o||typeof o!=='object')return esc(o??'');return '<dl>'+Object.entries(o).map(([k,v])=>'<dt>'+esc(k)+'</dt><dd class="mono">'+esc(typeof v==='object'?JSON.stringify(v):v)+'</dd>').join('')+'</dl>'}
function link(id){return id?'<a class="mono" href="#'+esc(id)+'">'+esc(id)+'</a>':'—'}
function show(id){const a=byId[id];if(!a)return;
d.innerHTML='<h2>'+esc(a.id)+' <span class="st st-'+esc(a.status)+'">'+esc(a.status)+'</span></h2><p>'+esc(a.question)+'</p>'+
'<dl><dt>作成</dt><dd>'+esc(a.created)+'</dd><dt>手順</dt><dd class="mono">'+esc(a.procedure)+'</dd><dt>前の版</dt><dd>'+link(a.supersedes)+'</dd><dt>次の版</dt><dd>'+link(a.superseded_by)+'</dd><dt>元にした解析</dt><dd>'+link(a.based_on)+'</dd><dt>フォルダ</dt><dd><a class="mono" href="'+esc(a.dir)+'">'+esc(a.dir.replace(/^\.\.\//,''))+'</a></dd></dl>'+
'<h3>パラメータ</h3>'+kv(a.params)+'<h3>結果</h3>'+kv(a.results)+
(a.figs.length?'<h3>図</h3><div class="figs">'+a.figs.map(f=>'<a href="'+esc(f.src)+'"><img loading="lazy" src="'+esc(f.src)+'" alt="'+esc(f.name)+'"></a>').join('')+'</div>':'')+
'<h3>入力の測定（'+a.inputs.length+'）</h3><div class="tw"><table><tr><th>meas_id</th><th>日付</th><th>試料</th><th>熱履歴</th><th>状態</th><th>ファイル</th></tr>'+a.inputs.map(i=>'<tr><td class="mono">'+esc(i.id)+'</td><td>'+esc(i.date)+'</td><td>'+esc(i.sample)+'</td><td class="mono">'+esc(i.thermal_history)+'</td><td>'+esc(i.status)+'</td><td>'+(i.path?'<a class="mono" href="../'+esc(i.path)+'">'+esc(i.path.split('/').pop())+'</a>':'台帳に無い')+'</td></tr>').join('')+'</table></div>'+
'<h3>notes.md</h3><pre>'+esc(a.notes)+'</pre>';mark()}
function mark(){const h=decodeURIComponent(location.hash.slice(1));tree_.querySelectorAll('.it').forEach(x=>x.classList.toggle('cur',x.getAttribute('href')==='#'+h))}
q.oninput=()=>tree(q.value.toLowerCase());addEventListener('hashchange',()=>show(decodeURIComponent(location.hash.slice(1))));
tree('');if(location.hash)show(decodeURIComponent(location.hash.slice(1)));
</script></body></html>"""
