#!/usr/bin/env python3
"""Baut /all/index.html aus index.html (27.11.26).

/all/ ist dieselbe Seite wie die Startseite, aber mit allen Tagen statt nur den letzten fünf.
So sieht sie immer gleich aus wie die Startseite. Nie /all/index.html von Hand ändern,
sondern index.html; build_static.py ruft dieses Skript am Ende auf.
Zusätzlich: Backup-Links (/all/#restore=MVR1…) aus dem Bag werden hier wiederhergestellt.
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESTORE = r"""<div class="rst" id="rst" hidden><div class="rpanel" role="dialog" aria-modal="true" aria-labelledby="rtitle">
  <b id="rtitle">Restore your data</b><p id="rtext"></p>
  <div class="rbtns"><button type="button" id="rno">Cancel</button><button type="button" id="rgo" class="go">Restore</button></div></div></div>
<style>
.rst{position:fixed;inset:0;z-index:60;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;padding:16px}
.rpanel{background:var(--bg);border:2px solid var(--white);max-width:420px;width:100%;padding:20px}
.rpanel b{display:block;font-size:20px;margin-bottom:8px}.rpanel p{color:var(--muted);line-height:1.45;margin:0 0 16px}
.rbtns{display:flex;gap:10px;justify-content:flex-end}
.rbtns button{all:unset;cursor:pointer;padding:10px 16px;border:2px solid var(--white);font-weight:700}
.rbtns .go{background:var(--yellow);color:var(--ink);border-color:var(--yellow)}
</style>
<script>
// Backup-Link aus dem Bag (/all/#restore=MVR1…): zusammenführen, nichts auf diesem Gerät wird gelöscht
(async()=>{const h=location.hash||"";if(!/^#restore=/.test(h))return;
  try{history.replaceState(null,"",location.pathname+location.search)}catch(e){}
  const S={get(k,d){try{const v=localStorage.getItem(k);return v?JSON.parse(v):d}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
  const box=document.getElementById("rst"),txt=document.getElementById("rtext"),go=document.getElementById("rgo"),no=document.getElementById("rno");
  const close=()=>{box.hidden=true};no.onclick=close;box.onclick=e=>{if(e.target===box)close()};
  const pl=(n,w)=>`${n} ${w}${n===1?"":"s"}`,arr=x=>Array.isArray(x)?x.filter(s=>typeof s==="string"):[];
  let d=null;
  try{const m=/MVR1(z?)\.([A-Za-z0-9_\-]+)/.exec(decodeURIComponent(h.slice(9)).replace(/\s+/g,""));if(!m)throw 0;
    let t=m[2].replace(/-/g,"+").replace(/_/g,"/");while(t.length%4)t+="=";const s=atob(t);let b=new Uint8Array(s.length);for(let i=0;i<s.length;i++)b[i]=s.charCodeAt(i);
    if(m[1])b=new Uint8Array(await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).arrayBuffer());
    d=JSON.parse(new TextDecoder().decode(b));if(!d||d.v!==1)throw 0}catch(e){d=null}
  box.hidden=false;
  if(!d){txt.textContent="This backup link seems incomplete or this browser can't read it. Open the full link in the latest Safari, Chrome or Firefox.";go.remove();no.textContent="Close";return}
  const nf=d.follow?arr(d.follow.a).length+arr(d.follow.l).length:0;
  txt.textContent=`This backup link${d.saved?" from "+d.saved:""} contains ${pl(arr(d.cart).length,"record")} in the bag, ${pl(arr(d.heard).length,"heard record")} and ${pl(nf,"follow")}. It is added to what's already in this browser. Nothing gets deleted.`;
  go.onclick=()=>{
    const cart=S.get("mvr-cart",[]),before=cart.length;arr(d.cart).forEach(k=>{if(!cart.includes(k))cart.push(k)});S.set("mvr-cart",cart);
    S.set("mvr-opened",[...new Set([...S.get("mvr-opened",[]),...arr(d.opened)])]);
    S.set("mvr-heard",[...new Set([...S.get("mvr-heard",[]),...arr(d.heard)])].slice(-3000));
    const f=S.get("mvr-follow",{a:[],l:[]});if(d.follow){arr(d.follow.a).forEach(x=>{if(!f.a.includes(x))f.a.push(x)});arr(d.follow.l).forEach(x=>{if(!f.l.includes(x))f.l.push(x)})}S.set("mvr-follow",f);
    const sh=S.get("mvr-ship",{});if(d.ship&&typeof d.ship==="object")Object.entries(d.ship).forEach(([k,v])=>{if(typeof v==="number"&&!(k in sh))sh[k]=v});S.set("mvr-ship",sh);
    if(typeof d.home==="string"&&d.home)S.set("mvr-home",d.home);
    if(typeof d.mail==="string"&&d.mail&&!S.get("mvr-mail",""))S.set("mvr-mail",d.mail);
    if(typeof track==="function")track("Backup restored");
    txt.textContent=`Welcome back. Added ${pl(cart.length-before,"record")} to your bag. Nothing on this device was removed.`;
    no.remove();go.textContent="Done";go.onclick=()=>location.reload()};
})();
</script>
"""


def sub1(s, old, new):
    if old not in s:
        raise SystemExit(f"make_all: Stelle nicht gefunden: {old[:60]!r}")
    return s.replace(old, new, 1)


def main():
    s = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    s = sub1(s, '<meta name="referrer" content="no-referrer">',
             '<meta name="referrer" content="no-referrer">\n<meta name="robots" content="noindex,follow">')
    s = re.sub(r"<title>.*?</title>", "<title>All records – Monthly Vinyl</title>", s, count=1, flags=re.S)
    # alle Tage statt nur die letzten fünf
    s = sub1(s, ".sort().reverse().slice(0,5);", ".sort().reverse();")
    # Archiv- und Backup-Links nicht auf sich selbst umleiten
    s = sub1(s, 'else if(/^#(archiv|restore=)/.test(location.hash))location.replace("/all/"+location.hash);', "")
    s = sub1(s, "New vinyl from <b", "All records from <b")
    # statische SEO-Liste gehört nur auf die Startseite (/all/ ist noindex)
    s = re.sub(r"<!--STATIC-->.*?<!--/STATIC-->", "", s, flags=re.S)
    s = sub1(s, "</body>", RESTORE + "</body>")
    os.makedirs(os.path.join(ROOT, "all"), exist_ok=True)
    open(os.path.join(ROOT, "all", "index.html"), "w", encoding="utf-8").write(s)
    print(f"all/index.html: {len(s)//1024} KB")


if __name__ == "__main__":
    main()
