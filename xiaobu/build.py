"""Wrap app.html (the page body, also published as the claude.ai artifact) into a standalone PWA index.html."""
from pathlib import Path

HERE = Path(__file__).resolve().parent

HEAD = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#2c6e5f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="小步">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>
</head>
<body>
"""

TAIL = """<script>
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
</script>
</body>
</html>
"""


def main():
    body = (HERE / "app.html").read_text(encoding="utf-8")
    (HERE / "index.html").write_text(HEAD + body + TAIL, encoding="utf-8")
    print("wrote", HERE / "index.html")


if __name__ == "__main__":
    main()
