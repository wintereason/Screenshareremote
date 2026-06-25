"""
ScreenShareRemote - PC Server  (fixed)
- Uses PIL.ImageGrab instead of mss  (no admin/permission issues on Windows)
- Serves each frame as a plain JPEG via /frame?t=<timestamp>
- Client JS polls /frame every 50ms  (Android WebView compatible - no MJPEG needed)
Run:  python server.py
"""

import io, os, socket, time
import pyautogui, qrcode
from flask import Flask, Response, jsonify, render_template_string, request
from PIL import ImageGrab, Image

# ── Config ────────────────────────────────────────────────────────────────────
PORT          = 8080
STREAM_FPS    = 15     # target FPS
STREAM_QUALITY= 55     # JPEG quality  (lower = faster transfer)
SCALE         = 0.5    # 0.5 = half resolution  (faster)
pyautogui.FAILSAFE = False

app = Flask(__name__)

# ── Screen capture (single frame) ─────────────────────────────────────────────
def grab_frame_bytes():
    img = ImageGrab.grab()                   # PIL.ImageGrab - no admin needed
    if SCALE != 1.0:
        img = img.resize(
            (int(img.width * SCALE), int(img.height * SCALE)),
            Image.BILINEAR
        )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=STREAM_QUALITY, optimize=False)
    return buf.getvalue()

def get_screen_size():
    img = ImageGrab.grab()
    return img.width, img.height

# ── HTML UI ───────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title>Screen Remote</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;display:flex;flex-direction:column;align-items:center;
     min-height:100vh;font-family:system-ui,sans-serif;overflow:hidden;touch-action:none}

#toolbar{position:fixed;top:0;left:0;right:0;height:46px;
  background:rgba(0,0,0,0.88);backdrop-filter:blur(12px);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 14px;z-index:100;border-bottom:1px solid rgba(255,255,255,0.07)}
#toolbar .title{color:#a5b4fc;font-size:13px;font-weight:700;letter-spacing:.04em}
.row{display:flex;align-items:center;gap:6px}

.tb-btn{background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);
  color:#a5b4fc;border-radius:8px;padding:5px 13px;font-size:12px;cursor:pointer;
  transition:background .15s}
.tb-btn:active{background:rgba(99,102,241,0.4)}
.tb-btn.on{background:rgba(239,68,68,0.2);border-color:rgba(239,68,68,0.45);color:#fca5a5}

#ping{font-size:11px;color:#4b5563}
#fps {font-size:11px;color:#4b5563}

/* hint bar */
#hint{position:fixed;top:46px;left:0;right:0;height:22px;
  background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;
  font-size:10px;color:#6b7280;letter-spacing:.03em;z-index:99;
  pointer-events:none}

#wrap{margin-top:68px;width:100vw;height:calc(100vh - 68px);
  display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}

#screen{max-width:100%;max-height:100%;object-fit:contain;
  display:block;-webkit-user-select:none;user-select:none}

#status{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
  color:#6b7280;font-size:14px;display:none}

/* ── Cursor overlay ── */
#cursor{
  position:fixed;
  width:22px;height:22px;
  pointer-events:none;
  z-index:500;
  transform:translate(-50%,-50%);
  display:none;
}
/* outer ring */
#cursor::before{
  content:'';position:absolute;inset:0;
  border-radius:50%;
  border:2px solid rgba(99,102,241,0.9);
  box-shadow:0 0 6px rgba(99,102,241,0.7),0 0 12px rgba(99,102,241,0.3);
  animation:cursorPulse 2s ease-in-out infinite;
}
/* inner dot */
#cursor::after{
  content:'';position:absolute;
  width:5px;height:5px;border-radius:50%;
  background:#a5b4fc;
  top:50%;left:50%;transform:translate(-50%,-50%);
  box-shadow:0 0 4px rgba(165,180,252,0.9);
}
/* click flash */
#cursor.clicking::before{
  background:rgba(99,102,241,0.35);
  animation:none;
}
/* move-only (double tap) flash */
#cursor.moving::before{
  border-color:rgba(34,197,94,0.9);
  box-shadow:0 0 6px rgba(34,197,94,0.7);
  animation:none;
}
/* right-click flash */
#cursor.rclicking::before{
  border-color:rgba(239,68,68,0.9);
  box-shadow:0 0 8px rgba(239,68,68,0.8);
  animation:none;
}
@keyframes cursorPulse{
  0%,100%{box-shadow:0 0 6px rgba(99,102,241,0.7),0 0 12px rgba(99,102,241,0.3)}
  50%     {box-shadow:0 0 10px rgba(99,102,241,0.9),0 0 20px rgba(99,102,241,0.5)}
}

/* keyboard overlay */
#kbdBox{display:none;position:fixed;bottom:0;left:0;right:0;
  background:rgba(8,8,18,0.97);border-top:1px solid rgba(99,102,241,0.25);
  padding:10px 14px 22px;z-index:200}
#kbdInput{width:100%;background:rgba(255,255,255,0.04);
  border:1px solid rgba(99,102,241,0.28);border-radius:10px;
  color:#e0e0e0;font-size:16px;padding:10px 14px;outline:none}
#kbdSend{margin-top:8px;width:100%;
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  border:none;border-radius:10px;color:#fff;font-size:15px;
  font-weight:700;padding:12px;cursor:pointer}

/* right-click ripple */
.ripple{position:fixed;width:44px;height:44px;border-radius:50%;
  background:rgba(239,68,68,0.45);pointer-events:none;z-index:300;
  transform:translate(-50%,-50%) scale(0);
  animation:rpl .4s ease-out forwards}
@keyframes rpl{to{transform:translate(-50%,-50%) scale(1.6);opacity:0}}

/* click tap visual */
.tapFlash{position:fixed;width:34px;height:34px;border-radius:50%;
  background:rgba(99,102,241,0.4);border:2px solid rgba(165,180,252,0.8);
  pointer-events:none;z-index:300;
  transform:translate(-50%,-50%) scale(0);
  animation:tapAnim .3s ease-out forwards}
@keyframes tapAnim{to{transform:translate(-50%,-50%) scale(1.4);opacity:0}}

/* move-only visual */
.moveFlash{position:fixed;width:28px;height:28px;border-radius:50%;
  background:rgba(34,197,94,0.35);border:2px solid rgba(74,222,128,0.8);
  pointer-events:none;z-index:300;
  transform:translate(-50%,-50%) scale(0);
  animation:tapAnim .3s ease-out forwards}
</style>
</head>
<body>

<div id="toolbar">
  <span class="title">Screen Remote</span>
  <div class="row">
    <span id="fps"></span>
    <span id="ping"></span>
    <button class="tb-btn" id="btnScroll" onclick="toggleScroll()">Scroll</button>
    <button class="tb-btn" onclick="toggleKbd()">KBD</button>
  </div>
</div>

<!-- hint strip -->
<div id="hint">1 tap = Click &nbsp;|&nbsp; 2 taps = Move only &nbsp;|&nbsp; Hold = Right-click &nbsp;|&nbsp; Drag = Move cursor</div>

<div id="wrap">
  <img id="screen" alt="">
  <div id="status">Connecting...</div>
</div>

<!-- cursor dot -->
<div id="cursor"></div>

<div id="kbdBox">
  <input id="kbdInput" type="text" placeholder="Type text to send..." autocomplete="off">
  <button id="kbdSend" onclick="sendText()">Send</button>
</div>

<script>
// ── Elements & state ──────────────────────────────────────────────────────────
const img      = document.getElementById('screen');
const statusEl = document.getElementById('status');
const pingEl   = document.getElementById('ping');
const fpsEl    = document.getElementById('fps');
const cursorEl = document.getElementById('cursor');

let screenW = 1920, screenH = 1080;
let scrollMode  = false;
let lastTouchY  = null;
let longTimer   = null;
let tapCount    = 0;
let tapTimer    = null;
let frameCount  = 0, lastFpsTime = Date.now();
let cursorFlashTimer = null;

// ── Screen size ───────────────────────────────────────────────────────────────
fetch('/info').then(r=>r.json()).then(d=>{screenW=d.width;screenH=d.height});

// ── Frame polling ─────────────────────────────────────────────────────────────
const INTERVAL_MS = Math.round(1000 / {{ fps }});
function poll() {
  const t0  = Date.now();
  const tmp = new window.Image();
  tmp.onload = () => {
    img.src = tmp.src;
    statusEl.style.display = 'none';
    frameCount++;
    const now = Date.now();
    if (now - lastFpsTime >= 1000) {
      fpsEl.textContent = frameCount + 'fps';
      frameCount = 0; lastFpsTime = now;
    }
    setTimeout(poll, Math.max(0, INTERVAL_MS - (Date.now()-t0)));
  };
  tmp.onerror = () => {
    statusEl.style.display = 'block';
    statusEl.textContent   = 'Reconnecting...';
    setTimeout(poll, 1000);
  };
  tmp.src = '/frame?t=' + t0;
}
statusEl.style.display = 'block';
setTimeout(poll, 300);

// ── Cursor helpers ────────────────────────────────────────────────────────────
function moveCursor(cx, cy) {
  cursorEl.style.display = 'block';
  cursorEl.style.left    = cx + 'px';
  cursorEl.style.top     = cy + 'px';
}

function flashCursor(type, ms=280) {
  if (cursorFlashTimer) clearTimeout(cursorFlashTimer);
  cursorEl.classList.remove('clicking','moving','rclicking');
  cursorEl.classList.add(type);
  cursorFlashTimer = setTimeout(()=>{
    cursorEl.classList.remove(type);
  }, ms);
}

// ── Coordinate mapping ────────────────────────────────────────────────────────
function toPC(cx, cy) {
  const r = img.getBoundingClientRect();
  return {
    x: Math.max(0, Math.round((cx - r.left) / r.width  * screenW)),
    y: Math.max(0, Math.round((cy - r.top)  / r.height * screenH))
  };
}

// ── Send control ──────────────────────────────────────────────────────────────
function ctrl(action, extra={}) {
  const t0 = Date.now();
  fetch('/control',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({action,...extra})
  }).then(()=>{ pingEl.textContent = (Date.now()-t0)+'ms'; }).catch(()=>{});
}

// ── Tap system ────────────────────────────────────────────────────────────────
// 1 tap  = LEFT CLICK (does the work)
// 2 taps = MOVE ONLY  (just positions cursor, no click)
// hold   = RIGHT CLICK
// drag   = move cursor in real-time

function handleTaps(cx, cy) {
  const pc = toPC(cx, cy);
  tapCount++;
  clearTimeout(tapTimer);

  if (tapCount === 1) {
    tapTimer = setTimeout(()=>{
      if (tapCount === 1) {
        // Single tap → CLICK
        flashCursor('clicking');
        spawnVfx(cx, cy, 'tapFlash');
        ctrl('click', pc);
      }
      tapCount = 0;
    }, 280);

  } else if (tapCount >= 2) {
    // Double tap → MOVE ONLY, no click
    clearTimeout(tapTimer);
    tapCount = 0;
    flashCursor('moving');
    spawnVfx(cx, cy, 'moveFlash');
    ctrl('move', pc);
  }
}

// ── Touch events ──────────────────────────────────────────────────────────────
img.addEventListener('touchstart', e=>{
  e.preventDefault();
  const t = e.touches[0];
  moveCursor(t.clientX, t.clientY);
  if (scrollMode) { lastTouchY = t.clientY; return; }

  const pc = toPC(t.clientX, t.clientY);

  longTimer = setTimeout(()=>{
    longTimer = null;
    flashCursor('rclicking', 400);
    ripple(t.clientX, t.clientY);
    ctrl('right_click', pc);
    tapCount = 0;
    clearTimeout(tapTimer);
  }, 650);
}, {passive:false});

img.addEventListener('touchmove', e=>{
  e.preventDefault();
  if (longTimer) { clearTimeout(longTimer); longTimer = null; }
  const t = e.touches[0];
  moveCursor(t.clientX, t.clientY);

  if (scrollMode) {
    if (lastTouchY !== null) {
      const dy = lastTouchY - t.clientY;
      if (Math.abs(dy) > 2) {
        ctrl('scroll', {dy: Math.round(dy*0.06)});
        lastTouchY = t.clientY;
      }
    }
    return;
  }
  ctrl('move', toPC(t.clientX, t.clientY));
}, {passive:false});

img.addEventListener('touchend', e=>{
  e.preventDefault();
  if (longTimer) {
    clearTimeout(longTimer);
    longTimer = null;
    const t = e.changedTouches[0];
    moveCursor(t.clientX, t.clientY);
    if (!scrollMode) handleTaps(t.clientX, t.clientY);
  }
  if (scrollMode) { lastTouchY = null; }
}, {passive:false});

// ── UI helpers ────────────────────────────────────────────────────────────────
function toggleScroll() {
  scrollMode = !scrollMode;
  document.getElementById('btnScroll').classList.toggle('on', scrollMode);
}
function toggleKbd() {
  const b = document.getElementById('kbdBox');
  const v = b.style.display === 'block';
  b.style.display = v ? 'none' : 'block';
  if (!v) document.getElementById('kbdInput').focus();
}
function sendText() {
  const v = document.getElementById('kbdInput').value.trim();
  if (!v) return;
  ctrl('type', {text: v});
  document.getElementById('kbdInput').value = '';
}
document.getElementById('kbdInput').addEventListener('keydown', e=>{ if(e.key==='Enter') sendText(); });

function ripple(x, y) {
  const d = document.createElement('div'); d.className = 'ripple';
  d.style.left = x+'px'; d.style.top = y+'px';
  document.body.appendChild(d); setTimeout(()=>d.remove(), 500);
}
</script>
</body>
</html>
"""

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML, fps=STREAM_FPS)

@app.route("/frame")
def frame():
    """Single JPEG frame — client polls this repeatedly."""
    try:
        data = grab_frame_bytes()
        return Response(data, mimetype="image/jpeg",
                        headers={"Cache-Control": "no-store, no-cache, must-revalidate",
                                 "Pragma": "no-cache"})
    except Exception as e:
        return str(e), 500

@app.route("/info")
def info():
    w, h = get_screen_size()
    return jsonify(width=w, height=h)

@app.route("/control", methods=["POST"])
def control():
    data   = request.get_json(force=True)
    action = data.get("action", "")
    x, y   = data.get("x"), data.get("y")
    try:
        if   action == "move"         and x is not None: pyautogui.moveTo(x, y, duration=0)
        elif action == "click"        and x is not None: pyautogui.click(x, y)
        elif action == "double_click" and x is not None: pyautogui.doubleClick(x, y)
        elif action == "right_click"  and x is not None: pyautogui.rightClick(x, y)
        elif action == "scroll": pyautogui.scroll(-int(data.get("dy", 0)))
        elif action == "type":   pyautogui.typewrite(data.get("text", ""), interval=0.03)
        elif action == "key":    pyautogui.press(data.get("key", ""))
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
    return jsonify(ok=True)

# ── Startup ─────────────────────────────────────────────────────────────────────
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        return ip
    except: return "127.0.0.1"

def make_qr(url):
    qr = qrcode.QRCode(version=None,
                       error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=4)
    qr.add_data(url); qr.make(fit=True)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qrcode.png")
    qr.make_image(fill_color="black", back_color="white").save(path)
    return path

if __name__ == "__main__":
    ip  = get_local_ip()
    url = f"http://{ip}:{PORT}/"
    qr  = make_qr(url)

    print()
    print("=" * 50)
    print("  ScreenShareRemote Server  (FIXED)")
    print("=" * 50)
    print(f"  Server  : {url}")
    print(f"  QR file : {qr}")
    print("  Scan QR with the Android app to connect")
    print("=" * 50)
    print("  Tap           -> Click")
    print("  Double tap    -> Double click")
    print("  Long press    -> Right click")
    print("  Scroll button -> Scroll mode")
    print("  KBD button    -> Type text")
    print("=" * 50)
    print()

    try: os.startfile(qr)
    except: pass

    app.run(host="0.0.0.0", port=PORT, threaded=True, debug=False)
