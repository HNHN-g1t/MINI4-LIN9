# -*- coding: utf-8 -*-
"""「作業ビュー」— 直近に触ったファイルと開いているウィンドウを、ブラウザで一覧プレビューする小道具。

    py recent_viewer.py                 # http://127.0.0.1:8780/ を開く
    py recent_viewer.py --root D:\\work  # 「最近更新」の探索先を足す
    py recent_viewer.py --port 9000 --no-open

3つのタブ（外部ライブラリなし・標準ライブラリのみ）
  開いているウィンドウ … 今開いているウィンドウの一覧とサムネイル（Windows。Linuxは wmctrl があれば一覧のみ）
  最近アクセス         … Windows の「最近使ったファイル」/ Linux の recently-used.xbel。
                         取れない環境では探索先のアクセス日時で代用する
  最近更新             … 探索先を歩いて、更新日時の新しい順に並べる
                         （既定: ドキュメント・デスクトップ・ダウンロード・このフォルダ）

カードを押すと右側に中身をプレビュー（画像・PDF・HTML・テキスト）。
127.0.0.1 にしか待ち受けず、操作できるのは一覧に出ているファイルだけ。
"""
import argparse
import ctypes
import glob
import io
import json
import mimetypes
import os
import secrets
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
import xml.etree.ElementTree as ET
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

IS_WIN = os.name == "nt"
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = secrets.token_hex(16)
LIMIT = 60                       # 1タブに出す件数
WALK_SECONDS = 4.0               # 「最近更新」の探索に使う時間の上限
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "AppData",
             "$RECYCLE.BIN", "System Volume Information", ".cache", ".npm"}
SKIP_SUFFIX = (".tmp", ".pyc", ".lnk", ".crdownload", ".part", ".swp")
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}
TEXT_EXT = {".txt", ".md", ".py", ".json", ".js", ".css", ".csv", ".log", ".bat", ".ps1",
            ".ini", ".yml", ".yaml", ".toml", ".xml", ".sh", ".ts", ".tsx", ".jsx"}
FRAME_EXT = {".pdf", ".html", ".htm"}

# 直近の一覧に出したファイル。/file と /api/open はここにあるものしか扱わない。
ALLOWED = set()
WINDOWS = {}                     # id -> 情報（フォーカス・サムネ用）
LOCK = threading.Lock()


# ───────────────────────── ファイル一覧 ─────────────────────────

def file_info(path, when=None):
    try:
        st = os.stat(path)
    except OSError:
        return None
    if not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    kind = ("img" if ext in IMG_EXT else "text" if ext in TEXT_EXT
            else "frame" if ext in FRAME_EXT else "other")
    return {"path": path, "name": os.path.basename(path),
            "dir": os.path.dirname(path), "ext": ext.lstrip(".") or "file",
            "size": st.st_size, "kind": kind,
            "time": when if when is not None else st.st_mtime,
            "mtime": st.st_mtime}


def default_roots():
    home = os.path.expanduser("~")
    roots = [os.path.join(home, n) for n in ("Documents", "Desktop", "Downloads", "ドキュメント", "デスクトップ", "ダウンロード")]
    roots.append(HERE)
    seen, out = set(), []
    for r in roots:
        r = os.path.normcase(os.path.abspath(r))
        if r not in seen and os.path.isdir(r):
            seen.add(r)
            out.append(r)
    return out


def scan_updated(roots, limit=LIMIT):
    """探索先を歩いて、更新日時の新しい順に返す。時間と深さに上限をかけて重くしない。"""
    deadline = time.time() + WALK_SECONDS
    found = {}
    for root in roots:
        base_depth = root.rstrip("\\/").count(os.sep)
        for cur, dirs, files in os.walk(root):
            if time.time() > deadline:
                break
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            if cur.count(os.sep) - base_depth >= 6:
                dirs[:] = []
            for fn in files:
                if fn.startswith(("~$", ".")) or fn.lower().endswith(SKIP_SUFFIX):
                    continue
                p = os.path.join(cur, fn)
                try:
                    found[p] = os.stat(p).st_mtime
                except OSError:
                    pass
    top = sorted(found.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [i for i in (file_info(p, t) for p, t in top) if i]


def _cstr(d, off, wide):
    if wide:
        end = off
        while end + 1 < len(d) and d[end:end + 2] != b"\0\0":
            end += 2
        return d[off:end].decode("utf-16-le", "replace")
    end = d.index(b"\0", off) if b"\0" in d[off:] else len(d)
    raw = d[off:end]
    for enc in ("cp932", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def lnk_target(path):
    """.lnk（ショートカット）の指す先を取り出す最小限のパーサ。COM を使わないので速い。"""
    try:
        with open(path, "rb") as f:
            d = f.read(65536)
        if len(d) < 76 or d[:4] != b"L\0\0\0":
            return None
        flags = struct.unpack_from("<I", d, 0x14)[0]
        off = 0x4C
        if flags & 1:                                    # HasLinkTargetIDList
            off += 2 + struct.unpack_from("<H", d, off)[0]
        if not flags & 2:                                # HasLinkInfo
            return None
        hdr = struct.unpack_from("<I", d, off + 4)[0]
        if not struct.unpack_from("<I", d, off + 8)[0] & 1:   # ローカルパスなし
            return None
        if hdr >= 0x24:
            base = _cstr(d, off + struct.unpack_from("<I", d, off + 28)[0], True)
            suf_o = struct.unpack_from("<I", d, off + 32)[0]
            suf = _cstr(d, off + suf_o, True) if suf_o else ""
        else:
            base = _cstr(d, off + struct.unpack_from("<I", d, off + 16)[0], False)
            suf_o = struct.unpack_from("<I", d, off + 24)[0]
            suf = _cstr(d, off + suf_o, False) if suf_o else ""
        return os.path.join(base, suf) if suf else base
    except (OSError, struct.error, ValueError):
        return None


def scan_accessed(roots, limit=LIMIT):
    """最近アクセスしたファイル。OSの履歴が読めればそれを、無ければアクセス日時で代用する。"""
    items = {}
    if IS_WIN:
        recent = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
        for lnk in glob.glob(os.path.join(recent, "*.lnk")):
            try:
                when = os.stat(lnk).st_mtime
            except OSError:
                continue
            tgt = lnk_target(lnk)
            if tgt and when > items.get(tgt, 0):
                items[tgt] = when
        source = "Windows の「最近使ったファイル」"
    else:
        xbel = os.path.expanduser("~/.local/share/recently-used.xbel")
        source = "recently-used.xbel"
        if os.path.isfile(xbel):
            try:
                for bm in ET.parse(xbel).getroot().iter("bookmark"):
                    href = urllib.parse.unquote(bm.get("href", ""))
                    if href.startswith("file://"):
                        ts = bm.get("visited") or bm.get("modified") or ""
                        try:
                            when = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
                        except ValueError:
                            when = 0
                        items[href[7:]] = max(when, items.get(href[7:], 0))
            except ET.ParseError:
                pass
    if not items:                                         # 代用：探索先のアクセス日時
        source = "アクセス日時（OSの履歴が無いため代用）"
        for root in roots:
            for cur, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
                for fn in files:
                    p = os.path.join(cur, fn)
                    try:
                        items[p] = os.stat(p).st_atime
                    except OSError:
                        pass
    top = sorted(items.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for p, t in top:
        i = file_info(p, t)
        if i and not i["name"].lower().endswith(SKIP_SUFFIX):
            out.append(i)
        if len(out) >= limit:
            break
    return out, source


# ───────────────────────── ウィンドウ一覧（Windows） ─────────────────────────

def _win_api():
    from ctypes import wintypes as w
    u, g, k = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
    H = ctypes.c_void_p
    u.GetDC.restype = H; u.GetDC.argtypes = [H]
    u.ReleaseDC.argtypes = [H, H]
    u.PrintWindow.argtypes = [H, H, w.UINT]
    u.GetWindowTextW.argtypes = [H, w.LPWSTR, ctypes.c_int]
    u.GetWindowTextLengthW.argtypes = [H]
    u.IsWindowVisible.argtypes = [H]
    u.IsIconic.argtypes = [H]
    u.GetWindowRect.argtypes = [H, ctypes.POINTER(w.RECT)]
    u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(w.DWORD)]
    u.GetWindowLongW.argtypes = [H, ctypes.c_int]
    u.ShowWindow.argtypes = [H, ctypes.c_int]
    u.SetForegroundWindow.argtypes = [H]
    g.CreateCompatibleDC.restype = H; g.CreateCompatibleDC.argtypes = [H]
    g.CreateCompatibleBitmap.restype = H; g.CreateCompatibleBitmap.argtypes = [H, ctypes.c_int, ctypes.c_int]
    g.SelectObject.restype = H; g.SelectObject.argtypes = [H, H]
    g.DeleteObject.argtypes = [H]
    g.DeleteDC.argtypes = [H]
    g.GetDIBits.argtypes = [H, H, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p, w.UINT]
    k.OpenProcess.restype = H; k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.QueryFullProcessImageNameW.argtypes = [H, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    k.CloseHandle.argtypes = [H]
    return w, u, g, k


def list_windows_win():
    w, u, g, k = _win_api()
    try:
        dwm = ctypes.windll.dwmapi
    except OSError:
        dwm = None
    out = []

    @ctypes.WINFUNCTYPE(w.BOOL, ctypes.c_void_p, w.LPARAM)
    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd) or u.GetWindowTextLengthW(hwnd) == 0:
            return True
        if u.GetWindowLongW(hwnd, -20) & 0x80:                      # ツールウィンドウ
            return True
        if dwm:                                                     # 別デスクトップ等で隠れた窓
            cloaked = ctypes.c_int(0)
            dwm.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), 14, ctypes.byref(cloaked), 4)
            if cloaked.value:
                return True
        buf = ctypes.create_unicode_buffer(512)
        u.GetWindowTextW(hwnd, buf, 512)
        title = buf.value
        if title == "Program Manager":
            return True
        pid = w.DWORD(0)
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        h = k.OpenProcess(0x1000, False, pid.value)                 # QUERY_LIMITED_INFORMATION
        if h:
            n = w.DWORD(1024)
            pb = ctypes.create_unicode_buffer(1024)
            if k.QueryFullProcessImageNameW(h, 0, pb, ctypes.byref(n)):
                exe = pb.value
            k.CloseHandle(h)
        out.append({"id": str(hwnd), "title": title, "app": os.path.splitext(os.path.basename(exe))[0],
                    "minimized": bool(u.IsIconic(hwnd)), "thumb": True})
        return True

    u.EnumWindows(cb, 0)
    return out


def png_encode(width, height, rgb):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 3)) + chunk(b"IEND", b""))


def capture_window_win(hwnd, max_w=480):
    """PrintWindow でウィンドウの中身を取り、max_w に間引いてPNGにする。最小化中は取れない。"""
    from ctypes import wintypes as w
    _, u, g, _ = _win_api()
    if u.IsIconic(hwnd):
        return None
    r = w.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    W, H = r.right - r.left, r.bottom - r.top
    if W < 8 or H < 8:
        return None
    sdc = u.GetDC(None)
    mdc = g.CreateCompatibleDC(sdc)
    bmp = g.CreateCompatibleBitmap(sdc, W, H)
    old = g.SelectObject(mdc, bmp)
    try:
        u.PrintWindow(hwnd, mdc, 2)                                  # PW_RENDERFULLCONTENT
        bi = struct.pack("<IiiHHIIiiII", 40, W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(W * H * 4)
        g.GetDIBits(mdc, bmp, 0, H, buf, bi, 0)
    finally:
        g.SelectObject(mdc, old)
        g.DeleteObject(bmp)
        g.DeleteDC(mdc)
        u.ReleaseDC(None, sdc)
    step = max(1, -(-W // max_w))
    ow, oh = len(range(0, W, step)), len(range(0, H, step))
    rows = []
    for y in range(0, H, step):
        row = buf.raw[y * W * 4:(y + 1) * W * 4]
        px = bytearray(ow * 3)
        px[0::3], px[1::3], px[2::3] = row[2::4][::step], row[1::4][::step], row[0::4][::step]
        rows.append(bytes(px))
    return png_encode(ow, oh, b"".join(rows))


def focus_window_win(hwnd):
    _, u, _, _ = _win_api()
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)                                        # SW_RESTORE
    return bool(u.SetForegroundWindow(hwnd))


def list_windows_linux():
    if not shutil.which("wmctrl"):
        return None
    try:
        text = subprocess.run(["wmctrl", "-l", "-p"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    out = []
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5 and parts[1] != "-1":
            out.append({"id": parts[0], "title": parts[4], "app": "", "minimized": False, "thumb": False})
    return out


def scan_windows():
    if IS_WIN:
        return list_windows_win(), ""
    wins = list_windows_linux()
    if wins is None:
        return [], "この環境ではウィンドウ一覧を取れません（Windows、または wmctrl のあるLinuxで動きます）"
    return wins, "wmctrl で取得（サムネイルはWindowsのみ）"


# ───────────────────────── サーバ ─────────────────────────

def preview_excerpt(path, n=1500):
    try:
        with open(path, "rb") as f:
            raw = f.read(n * 3)
    except OSError:
        return ""
    for enc in ("utf-8", "cp932"):
        try:
            return raw.decode(enc)[:n]
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")[:n]


def open_path(path, reveal):
    if IS_WIN:
        if reveal:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            os.startfile(path)                                       # noqa: S606（一覧内のパスのみ）
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, os.path.dirname(path) if reveal else path])


class Handler(BaseHTTPRequestHandler):
    roots = []

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        # DNS rebinding 対策：自分宛て以外のHostは受けない
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, "forbidden", "text/plain")
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            return self._send(200, PAGE.replace("__TOKEN__", TOKEN), "text/html; charset=utf-8")
        if u.path == "/api/windows":
            wins, note = scan_windows()
            with LOCK:
                WINDOWS.clear()
                WINDOWS.update({x["id"]: x for x in wins})
            return self._send(200, json.dumps({"items": wins, "note": note}, ensure_ascii=False))
        if u.path in ("/api/updated", "/api/accessed"):
            if u.path == "/api/updated":
                items, note = scan_updated(self.roots), "探索先: " + " / ".join(self.roots)
            else:
                items, note = scan_accessed(self.roots)
            for i in items:
                i["excerpt"] = preview_excerpt(i["path"], 240) if i["kind"] == "text" else ""
            with LOCK:
                ALLOWED.update(i["path"] for i in items)
            return self._send(200, json.dumps({"items": items, "note": note}, ensure_ascii=False))
        if u.path == "/api/text":
            p = q.get("p", [""])[0]
            if p not in ALLOWED:
                return self._send(404, "{}")
            return self._send(200, json.dumps({"text": preview_excerpt(p, 20000)}, ensure_ascii=False))
        if u.path == "/file":
            p = q.get("p", [""])[0]
            if p not in ALLOWED or not os.path.isfile(p):
                return self._send(404, "not found", "text/plain")
            ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
            if ctype == "text/html":                                  # 中身のスクリプトは動かさない
                extra = {"Content-Security-Policy": "sandbox; script-src 'none'"}
            else:
                extra = {"X-Content-Type-Options": "nosniff"}
            with open(p, "rb") as f:
                return self._send(200, f.read(30 * 1024 * 1024), ctype, extra)
        if u.path.startswith("/winthumb/") and IS_WIN:
            wid = u.path.rsplit("/", 1)[-1].split(".")[0]
            if wid not in WINDOWS:
                return self._send(404, "", "text/plain")
            try:
                png = capture_window_win(int(wid))
            except (OSError, ValueError, struct.error):
                png = None
            return self._send(200 if png else 404, png or b"", "image/png")
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Token") != TOKEN:
            return self._send(403, "forbidden", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        if self.path == "/api/open":
            p = body.get("p", "")
            if p not in ALLOWED:
                return self._send(404, "{}")
            open_path(p, bool(body.get("reveal")))
            return self._send(200, '{"ok":true}')
        if self.path == "/api/focus" and IS_WIN:
            wid = str(body.get("id", ""))
            ok = wid in WINDOWS and focus_window_win(int(wid))
            return self._send(200, json.dumps({"ok": bool(ok)}))
        self._send(404, "{}")


PAGE = r"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>作業ビュー</title>
<style>
:root{--bg:#f5f6f8;--surface:#fff;--ink:#1a2233;--ink2:#5a6478;--ink3:#8b93a5;--brand:#1256c4;--line:#e3e6ec;
font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#12151c;--surface:#1b2030;--ink:#e8ecf5;--ink2:#a6aec0;--ink3:#7a8398;--brand:#6aa0ff;--line:#2b3247}}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-size:14px;line-height:1.5;height:100vh;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--surface);border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:16px}
.tabs{display:flex;gap:4px}
.tab{border:0;background:none;color:var(--ink2);padding:7px 14px;font:inherit;font-weight:700;border-radius:6px;cursor:pointer}
.tab.on{background:var(--brand);color:#fff}
.tab .n{font-size:11px;margin-left:5px;opacity:.75}
input[type=search]{flex:1;min-width:140px;max-width:320px;margin-left:auto;padding:6px 10px;font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:6px}
button.ghost{border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:6px 12px;font:inherit;border-radius:6px;cursor:pointer}
.note{padding:6px 16px;font-size:12px;color:var(--ink3);word-break:break-all}
main{flex:1;display:flex;min-height:0}
#list{flex:1;overflow:auto;padding:4px 16px 24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;align-content:start;grid-auto-rows:max-content}
.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;overflow:hidden;cursor:pointer;display:flex;flex-direction:column}
.card:hover{border-color:var(--brand)}.card.sel{outline:2px solid var(--brand)}
.thumb{height:120px;background:var(--bg);display:flex;align-items:center;justify-content:center;overflow:hidden;color:var(--ink3);font-weight:700;font-size:20px}
.thumb img{width:100%;height:100%;object-fit:cover}
.thumb pre{width:100%;font-size:10px;line-height:1.35;color:var(--ink2);align-self:flex-start;padding:8px;white-space:pre-wrap;word-break:break-all;overflow:hidden;height:100%;font-weight:400;font-family:ui-monospace,Consolas,monospace}
.meta{padding:8px 10px}
.name{font-weight:700;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sub{font-size:11.5px;color:var(--ink3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.min{font-size:11px;color:var(--ink3)}
#pane{width:min(46%,560px);border-left:1px solid var(--line);background:var(--surface);display:none;flex-direction:column;min-width:0}
#pane.on{display:flex}
#pane .head{padding:12px 14px;border-bottom:1px solid var(--line)}
#pane .head .name{white-space:normal;word-break:break-all;font-size:14px}
#pane .acts{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
#body{flex:1;overflow:auto;padding:12px 14px;min-height:0}
#body img{max-width:100%}#body iframe{width:100%;height:100%;min-height:60vh;border:1px solid var(--line);background:#fff}
#body pre{white-space:pre-wrap;word-break:break-all;font:12px/1.5 ui-monospace,Consolas,monospace}
.empty{padding:40px 16px;color:var(--ink3)}
@media (max-width:760px){main{flex-direction:column}#pane{width:auto;border-left:0;border-top:1px solid var(--line);max-height:55vh}}
</style></head><body>
<header>
  <h1>作業ビュー</h1>
  <div class="tabs" id="tabs"></div>
  <input type="search" id="q" placeholder="名前・フォルダで絞り込み">
  <button class="ghost" id="reload">更新</button>
</header>
<div class="note" id="note"></div>
<main>
  <div id="list"></div>
  <aside id="pane"><div class="head"><div class="name" id="pname"></div><div class="sub" id="pdir"></div><div class="acts" id="pacts"></div></div><div id="body"></div></aside>
</main>
<script>
const TOKEN="__TOKEN__";
const TABS=[["windows","開いているウィンドウ"],["accessed","最近アクセス"],["updated","最近更新"]];
const st={tab:"windows",data:{},sel:null};
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const ago=t=>{const s=Date.now()/1000-t;if(s<60)return"たった今";if(s<3600)return Math.floor(s/60)+"分前";
 if(s<86400)return Math.floor(s/3600)+"時間前";if(s<86400*30)return Math.floor(s/86400)+"日前";return new Date(t*1000).toLocaleDateString("ja-JP")};
const size=n=>n<1024?n+" B":n<1048576?(n/1024).toFixed(1)+" KB":(n/1048576).toFixed(1)+" MB";
const fileUrl=p=>"/file?p="+encodeURIComponent(p);
const post=(u,b)=>fetch(u,{method:"POST",headers:{"X-Token":TOKEN},body:JSON.stringify(b)}).then(r=>r.json());

function renderTabs(){
  $("tabs").innerHTML=TABS.map(([k,l])=>{const d=st.data[k];
    return `<button class="tab${k===st.tab?" on":""}" data-k="${k}">${l}<span class="n">${d?d.items.length:""}</span></button>`}).join("");
  document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{st.tab=b.dataset.k;st.sel=null;closePane();load(st.tab)});
}
function thumb(it){
  if(st.tab==="windows")return it.thumb?`<img loading="lazy" src="/winthumb/${it.id}.png?t=${Date.now()}" alt="" onerror="this.replaceWith(document.createTextNode('${esc((it.app||"?").slice(0,3).toUpperCase())}'))">`:esc((it.app||"WIN").slice(0,3).toUpperCase());
  if(it.kind==="img"&&it.size<8e6)return`<img loading="lazy" src="${fileUrl(it.path)}" alt="">`;
  if(it.kind==="text"&&it.excerpt)return`<pre>${esc(it.excerpt)}</pre>`;
  return esc(it.ext.slice(0,4).toUpperCase());
}
function render(){
  renderTabs();
  const d=st.data[st.tab],q=$("q").value.trim().toLowerCase();
  $("note").textContent=d?d.note:"読み込み中…";
  if(!d){$("list").innerHTML="";return}
  const items=d.items.filter(i=>!q||(i.title||i.name||"").toLowerCase().includes(q)||(i.dir||i.app||"").toLowerCase().includes(q));
  if(!items.length){$("list").innerHTML='<div class="empty">該当なし</div>';return}
  $("list").innerHTML=items.map((it,n)=>{
    const win=st.tab==="windows",key=win?it.id:it.path;
    return`<div class="card${st.sel===key?" sel":""}" data-n="${n}"><div class="thumb">${thumb(it)}</div><div class="meta">
      <div class="name" title="${esc(win?it.title:it.name)}">${esc(win?it.title:it.name)}</div>
      <div class="sub">${win?esc(it.app)+(it.minimized?' <span class="min">（最小化中）</span>':""):esc(ago(it.time))+" ・ "+esc(size(it.size))}</div>
      ${win?"":`<div class="sub" title="${esc(it.dir)}">${esc(it.dir)}</div>`}</div></div>`}).join("");
  document.querySelectorAll(".card").forEach(c=>c.onclick=()=>select(items[+c.dataset.n]));
}
function closePane(){$("pane").classList.remove("on")}
async function select(it){
  const win=st.tab==="windows";st.sel=win?it.id:it.path;render();
  $("pane").classList.add("on");
  $("pname").textContent=win?it.title:it.name;
  $("pdir").textContent=win?it.app:it.dir;
  const body=$("body"),acts=$("pacts");
  if(win){
    acts.innerHTML=`<button class="ghost" id="a1">前面に出す</button>`;
    $("a1").onclick=async()=>{const r=await post("/api/focus",{id:it.id});if(!r.ok)alert("前面に出せませんでした（この環境では未対応かもしれません）")};
    body.innerHTML=it.thumb?`<img src="/winthumb/${it.id}.png?t=${Date.now()}" alt="" onerror="this.outerHTML='<div class=empty>プレビューを取れませんでした（最小化中など）</div>'">`:'<div class="empty">このウィンドウのプレビューは取れません</div>';
    return;
  }
  acts.innerHTML=`<button class="ghost" id="a1">開く</button><button class="ghost" id="a2">フォルダを開く</button>`;
  $("a1").onclick=()=>post("/api/open",{p:it.path});
  $("a2").onclick=()=>post("/api/open",{p:it.path,reveal:true});
  if(it.kind==="img")body.innerHTML=`<img src="${fileUrl(it.path)}" alt="">`;
  else if(it.kind==="frame")body.innerHTML=`<iframe sandbox src="${fileUrl(it.path)}"></iframe>`;
  else if(it.kind==="text"){body.innerHTML="<pre></pre>";
    const r=await (await fetch("/api/text?p="+encodeURIComponent(it.path))).json();body.firstChild.textContent=r.text||""}
  else body.innerHTML=`<div class="empty">${esc(it.ext.toUpperCase())} ・ ${esc(size(it.size))}<br>${esc(new Date(it.mtime*1000).toLocaleString("ja-JP"))} 更新<br>このファイル形式はプレビューできません。「開く」で既定のアプリが開きます。</div>`;
}
async function load(k){
  try{st.data[k]=await (await fetch("/api/"+k)).json()}catch(e){st.data[k]={items:[],note:"取得に失敗しました: "+e}}
  if(k===st.tab)render();else renderTabs();
}
$("q").oninput=render;$("reload").onclick=()=>load(st.tab);
render();TABS.forEach(([k])=>load(k));
setInterval(()=>{if(document.visibilityState==="visible"&&st.tab==="windows"&&!st.sel)load("windows")},15000);
</script></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="直近のファイルと開いているウィンドウをブラウザで一覧プレビューする")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--root", action="append", default=[], help="「最近更新」の探索先（複数可。指定すると既定に足す）")
    ap.add_argument("--no-open", action="store_true", help="ブラウザを自動で開かない")
    a = ap.parse_args()
    roots = default_roots()
    for r in a.root:
        r = os.path.abspath(os.path.expanduser(r))
        if os.path.isdir(r) and os.path.normcase(r) not in roots:
            roots.append(os.path.normcase(r))
    Handler.roots = roots
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = "http://127.0.0.1:%d/" % a.port
    print("作業ビュー: %s  （止めるときは Ctrl+C）" % url)
    for r in roots:
        print("  探索先:", r)
    if not a.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
