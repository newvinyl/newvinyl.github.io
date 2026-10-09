#!/usr/bin/env python3
"""Showcase-Video für Instagram: echte Bildschirmaufnahme der Live-Seite (Handy-Format),
Platte für Platte, mit den echten Hörproben als Ton. Kein Hochglanz, harte Schnitte.

Ablauf: Startseite → Cover antippen (Musik) → nochmal tippen (nächster Track) → + Bag →
weiterscrollen, nächste Platte → More (Cover dreht) → Check out → Bag → Backup → Endkarte.

Läuft in GitHub Actions (braucht Zugriff auf monthlyvinyl.net und die Shop-Server).
Ausgabe: <WORK>/showcase_<yymmdd>.mp4 (+ .jpg Poster), JSON auf stdout.
"""
import datetime as dt, json, os, subprocess, sys, tempfile, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import digs  # fetch, decode, pick_start, SR

SITE = os.environ.get("SHOWCASE_SITE", "https://monthlyvinyl.net")
WORK = os.environ.get("SHOWCASE_WORK") or tempfile.mkdtemp()
SR = digs.SR
VW, VH, DSF = 405, 720, 1080 / 405          # 9:16, ergibt 1080×1920

INIT = r"""
(()=>{
  const css=`#__cap{position:fixed;left:16px;right:16px;top:64px;z-index:9999;pointer-events:none;display:flex;justify-content:center}
  #__cap span{background:#0d0d0d;color:#ecebe7;font:500 13px/1.35 "JetBrains Mono",ui-monospace,monospace;padding:6px 9px;border:1px solid #3c4046;letter-spacing:.02em}
  #__cap[hidden]{display:none}
  .__tap{position:fixed;z-index:9998;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;border:2.5px solid #fff;background:rgba(255,255,255,.18);pointer-events:none;animation:__t .55s ease-out forwards}
  @keyframes __t{from{transform:scale(.6);opacity:1}to{transform:scale(1.25);opacity:0}}`;
  const boot=()=>{if(document.getElementById("__cap"))return;const st=document.createElement("style");st.textContent=css;document.head.appendChild(st);
    const c=document.createElement("div");c.id="__cap";c.hidden=true;c.innerHTML="<span></span>";document.body.appendChild(c)};
  window.__caption=t=>{boot();const c=document.getElementById("__cap");c.querySelector("span").textContent=t||"";c.hidden=!t};
  addEventListener("pointerdown",e=>{const d=document.createElement("div");d.className="__tap";d.style.left=e.clientX+"px";d.style.top=e.clientY+"px";document.body.appendChild(d);setTimeout(()=>d.remove(),700)},true);
  if(document.readyState!=="loading")boot();else addEventListener("DOMContentLoaded",boot);
})();
"""

PICK = r"""
(()=>{const out=[];const g=document.querySelector('#feed .grid');if(!g)return out;
 g.querySelectorAll('.card').forEach(c=>{const i=+c.dataset.i,r=RECS[i],img=c.querySelector('.front img');
  if(!img||!img.complete||img.naturalWidth<280)return;
  out.push({i,n:r.tracks.length,u:r.tracks.map(t=>t.u).slice(0,2),shop:r.main.S.shop,g:(r.main.g||'').split(/[\/·]/)[0].trim(),a:r.main.a,t:r.main.t})});
 return out})()
"""

def log(*a):
    print(*a, file=sys.stderr, flush=True)

def load_audio(url, n):
    p = os.path.join(WORK, "s%d.mp3" % n)
    open(p, "wb").write(digs.fetch(url, timeout=90))
    a = digs.decode(p)
    if len(a) < SR * 12:
        raise RuntimeError("too short")
    return a

def choose(cands):
    """A (mind. 2 Tracks) + B + C, möglichst verschiedene Shops und Genres."""
    audio = {}
    def ok(url):
        if url in audio:
            return True
        try:
            a = load_audio(url, len(audio))
            audio[url] = (a, digs.pick_start(a))
            return True
        except Exception as e:
            log("audio fail", url, e)
            return False
    A = next((c for c in cands if c["n"] >= 2 and ok(c["u"][0]) and ok(c["u"][1])), None)
    if not A:
        raise SystemExit("no record with two playable tracks")
    rest, picks = [c for c in cands if c["i"] != A["i"]], [A]
    for c in rest:
        if len(picks) == 3:
            break
        if any(c["shop"] == p["shop"] and c["g"] == p["g"] for p in picks):
            continue
        if ok(c["u"][0]):
            picks.append(c)
    if len(picks) < 3:
        raise SystemExit("not enough records")
    return picks, audio

def main():
    from playwright.sync_api import sync_playwright
    frames, events = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        ctx = b.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF, is_mobile=True, has_touch=True,
                            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=SITE)
        ctx.add_init_script(INIT)
        pg = ctx.new_page()
        pg.goto(SITE + "/", wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(4000)
        cands = pg.evaluate(PICK)
        log(len(cands), "candidates with loaded covers")
        picks, audio = choose(cands)
        A, B, C = picks
        log("picks", [(x["a"], x["t"], x["shop"]) for x in picks])

        cdp = ctx.new_cdp_session(pg)
        def on_frame(ev):
            n = len(frames)
            fp = os.path.join(WORK, "f%05d.jpg" % n)
            import base64
            open(fp, "wb").write(base64.b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], fp))
            try:
                cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:
                pass
        cdp.on("Page.screencastFrame", on_frame)
        def rec():
            try:
                cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": 1080, "maxHeight": 1920, "everyNthFrame": 1})
            except Exception as e:
                log("screencast", e)

        cap = lambda t="": pg.evaluate("t=>window.__caption&&window.__caption(t)", t)
        wait = pg.wait_for_timeout
        def tap(sel_or_loc, dy=0.5):
            loc = pg.locator(sel_or_loc) if isinstance(sel_or_loc, str) else sel_or_loc
            loc.scroll_into_view_if_needed()
            bb = loc.bounding_box()
            pg.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] * dy)
        card = lambda r: pg.locator('.card[data-i="%d"]' % r["i"])
        def started(url):
            off = audio[url][1]
            pg.evaluate("o=>{try{au.currentTime=o}catch(e){}}", off)
            events.append((time.time(), url, off))
        def scroll_to(r):
            pg.evaluate("i=>{const c=document.querySelector(`.card[data-i=\"${i}\"]`);const y=c.getBoundingClientRect().top+scrollY-60;scrollTo({top:y,behavior:'smooth'})}", r["i"])
            wait(1300)

        pg.evaluate("scrollTo(0,0)")
        rec(); wait(400)
        cap("new vinyl. every morning."); wait(2200)
        # A: antippen, Musik
        scroll_to(A)
        cap("tap the cover."); tap(card(A).locator(".front"), 0.42); started(A["u"][0]); wait(5200)
        cap("tap again. next track."); tap(card(A).locator(".front"), 0.42); started(A["u"][1]); wait(4600)
        cap("like it? bag it."); tap(card(A).locator(".front .add")); wait(1600)
        cap("")
        # B
        scroll_to(B)
        tap(card(B).locator(".front"), 0.42); started(B["u"][0]); wait(4400)
        tap(card(B).locator(".front .add")); wait(1200)
        # C: More
        scroll_to(C)
        tap(card(C).locator(".front"), 0.42); started(C["u"][0]); wait(3000)
        cap("flip it."); tap(card(C).locator(".front .more")); wait(2900)
        tap(card(C).locator(".backf .add")); wait(1300)
        cap("")
        # Check out
        tap("#mbag"); pg.wait_for_load_state("networkidle"); rec(); wait(600)
        cap("check out at the shop."); wait(2600)
        pg.evaluate("scrollTo({top:document.body.scrollHeight,behavior:'smooth'})"); wait(1500)
        cap("save your bag."); tap("#bsave"); wait(2000)
        cap("or just leave the tab open."); wait(2600)
        # Endkarte
        pg.set_content("""<html><body style="margin:0;background:#0d0d0d;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px">
          <div style="font:700 34px/1 'Helvetica Neue',Helvetica,'TeX Gyre Heros',Arial,sans-serif;color:#fbed4f;-webkit-text-stroke:.085em #fbed4f;paint-order:stroke fill;letter-spacing:-.008em">MONTHLY VINYL</div>
          <div style="font:500 14px 'JetBrains Mono',ui-monospace,monospace;color:#ecebe7;letter-spacing:.04em">monthlyvinyl.net</div>
          <div style="font:400 12px 'JetBrains Mono',ui-monospace,monospace;color:#a0a4a9">dig. bag. buy at the shop.</div></body></html>""")
        rec(); wait(4200)
        t_end = time.time()
        try:
            cdp.send("Page.stopScreencast")
        except Exception:
            pass
        b.close()

    if len(frames) < 20:
        raise SystemExit("screencast produced too few frames")
    frames.sort()
    t0 = frames[0][0]
    total = t_end - t0
    # Ton: jeweils ab dem Antippen der Hörprobe, harte Schnitte mit kurzer Blende, am Ende 2.5 s ausblenden
    n = int(total * SR)
    mix = np.zeros((n, 2), dtype="float32")
    for k, (tw, url, off) in enumerate(events):
        a = audio[url][0]
        s = max(0, int((tw - t0) * SR))
        e = int((events[k + 1][0] - t0) * SR) if k + 1 < len(events) else n
        seg = a[int(off * SR):int(off * SR) + (e - s)]
        if len(seg) < e - s:  # Hörprobe zu kurz: weiter vorne beginnen
            seg = a[max(0, len(a) - (e - s)):]
        seg = seg[:e - s].copy()
        f = min(len(seg), int(0.04 * SR))
        if f:
            seg[:f] *= np.linspace(0, 1, f)[:, None]
            seg[-f:] *= np.linspace(1, 0, f)[:, None]
        mix[s:s + len(seg)] += seg
    fo = int(2.5 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    peak = float(np.abs(mix).max() or 1)
    if peak > 0.97:
        mix *= 0.97 / peak
    raw = os.path.join(WORK, "mix.f32")
    mix.astype("<f4").tofile(raw)
    # Bild: Screencast-Frames mit echten Zeitabständen
    lst = os.path.join(WORK, "frames.txt")
    with open(lst, "w") as fh:
        for k, (ts, fp) in enumerate(frames):
            d = (frames[k + 1][0] if k + 1 < len(frames) else t_end) - ts
            fh.write("file '%s'\nduration %.4f\n" % (fp, max(d, 0.001)))
        fh.write("file '%s'\n" % frames[-1][1])
    ymd = dt.date.today().strftime("%y%m%d")
    out = os.path.join(WORK, "showcase_%s.mp4" % ymd)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", raw,
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x0d0d0d,fps=30,noise=alls=5:allf=t,format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k",
                    "-t", "%.2f" % total, "-movflags", "+faststart", out], check=True)
    poster = out.replace(".mp4", ".jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "8", "-i", out, "-frames:v", "1", "-q:v", "3", poster], check=True)
    print(json.dumps({"video": out, "poster": poster, "seconds": round(total, 1),
                      "records": [{"a": x["a"], "t": x["t"], "shop": x["shop"]} for x in picks]}))

if __name__ == "__main__":
    main()
