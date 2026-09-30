#!/usr/bin/env python3
"""
Find, save and test the Jev key on THIS machine. The key never passes through the chat, and
nothing here prints it.

    python3 jev_key.py find                    # which provider has a key, and where (never the value)
    python3 jev_key.py guide openrouter        # where to get a key, and where it will end up
    python3 jev_key.py save openrouter         # a password box; the key goes into a .env file (0600)
    python3 jev_key.py save openrouter --env-file ./.env   # into a project .env instead (refused if git would commit it)
    python3 jev_key.py check openrouter        # one tiny Jev call (a fraction of a cent) to prove the key works

Where a key is looked for, in order: the process environment, ./.env, ~/.config/jev/.env, then
~/.config/jev-lead-score/.env (a shared location other Jev tools may use), so a key already saved
in either place is used as it is.

The local key runs the preview (check_local.py) and the smoke test, and build_workflow.py writes
the same key into each workflow's first step: Clay's CLI can neither create an HTTP connection
nor bind one to a step, so a Clay connection would mean the installer rewiring steps by hand.
"""
import argparse
import getpass
import html
import http.server
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import urllib.parse
import webbrowser

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import active_lib as L  # noqa: E402

WAIT_SECONDS = 600


def cmd_find(_a):
    found = {}
    for p in L.PROVIDERS:
        w = L.find_key(p)
        found[p] = None if not w else {"where": w[0], "variable": w[1]}
        if w:
            L.say("%s key: found (%s in %s)" % (L.PROVIDERS[p]["label"], w[1], w[0]))
        else:
            L.say("%s key: not found" % L.PROVIDERS[p]["label"])
    print(json.dumps({"keys": found}))


def cmd_guide(a):
    P = L.PROVIDERS[a.provider]
    L.say("1. Get a %s key: %s" % (P["label"], P["keys_at"]))
    L.say("2. On this machine the key goes in a .env file as one line:")
    L.say("     %s=<your key>" % P["env"])
    L.say("   The agent opens a password box that writes that line for you (jev_key.py save %s), into %s."
          % (a.provider, L.default_env_file()))
    L.say("3. When the workflow is built, the same key is written into its first step in Clay. Anyone in")
    L.say("   your Clay workspace who opens that workflow, or one of its runs, can read it. Rebuild to")
    L.say("   rotate it. (It moves to a Clay connection once Clay's CLI can create and attach one.)")


def ask_macos(label, where):
    text = ("Your %s API key goes here.\\n\\nGet one at: %s\\n\\nIt is saved to a .env file on this Mac only, "
            "and never shown in the chat." % (label, where))
    script = ('display dialog "%s" default answer "" with hidden answer with title "Save %s key" '
              'buttons {"Cancel", "Save"} default button "Save"' % (text.replace('"', "'"), label))
    r = subprocess.run(["osascript", "-e", script, "-e", "text returned of result"],
                       capture_output=True, text=True, timeout=WAIT_SECONDS)
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def ask_linux(label, where):
    if shutil.which("zenity"):
        cmd = ["zenity", "--password", "--title", "Save %s key" % label]
    elif shutil.which("kdialog"):
        cmd = ["kdialog", "--password", "Paste your %s key (get one at %s)." % (label, where),
               "--title", "Save %s key" % label]
    else:
        return False
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=WAIT_SECONDS)
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def ask_browser(label, where):
    """A one-field page on this machine only, with a one-time token in the path."""
    token = secrets.token_urlsafe(16)
    got, done = {}, threading.Event()

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            if self.path != "/" + token:
                self.send_response(404)
                self.end_headers()
                return
            self._send("""<!doctype html><meta name=viewport content="width=device-width">
<title>Save %(l)s key</title><body style="font:16px system-ui;max-width:32rem;margin:3rem auto;padding:0 1rem">
<h2>Save your %(l)s API key</h2><p>Get one at: %(w)s</p>
<form method=post><input name=k type=password autofocus required style="width:100%%;font-size:16px;padding:.5rem">
<p><button style="font-size:16px;padding:.5rem 1rem">Save</button></p></form>
<p style="color:#666">Saved to a .env file on this machine only, never shown in the chat.</p>""" % {
                "l": html.escape(label), "w": html.escape(where)})

        def do_POST(self):
            if self.path != "/" + token:
                self.send_response(404)
                self.end_headers()
                return
            n = int(self.headers.get("Content-Length") or 0)
            got["k"] = (urllib.parse.parse_qs(self.rfile.read(n).decode()).get("k") or [""])[0]
            self._send("<body style='font:16px system-ui;margin:3rem'><h2>Saved.</h2>You can close this tab.")
            done.set()

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    host, port = srv.server_address[0], srv.server_address[1]
    url = "".join(["http", "://", host, ":", str(port), "/", token])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    L.say("A page to paste the %s key into is open in your browser. If it did not open: %s" % (label, url))
    try:
        webbrowser.open(url)
    except Exception:
        pass
    done.wait(WAIT_SECONDS)
    srv.shutdown()
    return got.get("k")


def cmd_save(a):
    P = L.PROVIDERS[a.provider]
    path = os.path.abspath(a.env_file) if a.env_file else L.default_env_file()
    if L.git_tracks_risk(path):
        L.fail("%s is inside a git repository and is not ignored, so a key written there could be committed "
               "(a .gitignore added later untracks nothing). Add .env to that repo's .gitignore first, or save "
               "to the default file (%s) by leaving out --env-file." % (path, L.default_env_file()), code=2)
    if a.terminal:
        value = getpass.getpass("Paste the %s key (hidden), then Enter: " % P["label"])
    elif a.browser:
        value = ask_browser(P["label"], P["keys_at"])
    elif sys.platform == "darwin" and shutil.which("osascript"):
        L.say("A password box for the %s key is open on your screen." % P["label"])
        value = ask_macos(P["label"], P["keys_at"])
    else:
        value = ask_linux(P["label"], P["keys_at"]) if sys.platform.startswith("linux") else False
        if value is False:
            value = ask_browser(P["label"], P["keys_at"])
    if not value or not value.strip():
        L.fail("No %s key was saved (cancelled, closed, or left empty)." % P["label"])
    L.write_env(path, P["env"], value)
    L.say("%s key saved as %s in %s (readable only by you). It was not shown here." % (P["label"], P["env"], path))
    w = L.find_key(a.provider)
    if w and os.path.abspath(w[0]) != path and w[0] != path:
        L.say("Note: a %s key in %s is honoured before this file, so that one is what gets used." % (P["label"], w[0]))


def cmd_check(a):
    P = L.PROVIDERS[a.provider]
    body = {"model": P["model"], "state": "The sky is blue.",
            "questions": {"ping": {"type": "noul", "instructions": "Does the text mention a colour?"}}}
    status, out = L.call_jev(a.provider, body)
    if status == 200 and isinstance(out, dict) and isinstance(out.get("answers"), dict):
        usage = out.get("usage") or {}
        L.say("%s key works: Jev (%s) answered. That call cost about $%.6f." % (
            P["label"], out.get("model") or P["model"],
            usage.get("cost") if usage.get("cost") is not None else
            (usage.get("input_tokens") or 0) * P["price_per_mtok"] / 1e6))
        print(json.dumps({"ok": True, "model": out.get("model")}))
        return
    meaning = {0: "could not reach %s (network)" % P["url"], 401: "the key was refused (wrong or revoked)",
               402: "the account has no credit", 403: "the key is not allowed to call this",
               429: "rate limited; try again shortly"}.get(status, "unexpected answer")
    print(json.dumps({"ok": False, "status": status}))
    L.fail("%s key check failed: HTTP %s, %s." % (P["label"], status, meaning), code=4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("find")
    for c in ("guide", "save", "check"):
        s = sub.add_parser(c)
        s.add_argument("provider", choices=sorted(L.PROVIDERS))
        if c == "save":
            s.add_argument("--env-file", help="write to this .env instead of the shared default")
            s.add_argument("--terminal", action="store_true", help="hidden prompt in a terminal instead of a box")
            s.add_argument("--browser", action="store_true", help="use a local page even where a dialog exists")
    a = ap.parse_args()
    {"find": cmd_find, "guide": cmd_guide, "save": cmd_save, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    main()
