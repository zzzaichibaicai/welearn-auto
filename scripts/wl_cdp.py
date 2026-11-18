"""wl_cdp.py —— 最小 CDP 客户端，超时 60 秒，不依赖 cdp_harvest。"""
import json, time
import requests
import websocket


class Mini:
    def __init__(self, port=9224, timeout=60):
        v = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=10).json()
        self.ws = websocket.create_connection(v["webSocketDebuggerUrl"], timeout=timeout,
                                              suppress_origin=True)
        self.i = 0

    def send(self, method, params=None, session=None):
        self.i += 1
        msg = {"id": self.i, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.i:
                if "error" in r:
                    raise RuntimeError(f"{method}: {r['error']}")
                return r.get("result", {})

    def page(self, idx=0):
        ts = [t for t in self.send("Target.getTargets")["targetInfos"] if t.get("type") == "page"]
        if not ts:
            raise RuntimeError("无页面")
        return ts[idx]

    def attach(self, target_id):
        a = self.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        sid = a["sessionId"]
        self.send("Runtime.enable", {}, sid)
        self.send("Page.enable", {}, sid)
        return sid

    def ev(self, sid, expr, wait=False, timeout_ms=30000):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "awaitPromise": wait,
            "returnByValue": True, "timeout": timeout_ms
        }, sid)
        res = r.get("result", {})
        if res.get("subtype") == "error":
            return {"__error": res.get("description", "")[:300]}
        return res.get("value")

    def close(self):
        try: self.ws.close()
        except Exception: pass