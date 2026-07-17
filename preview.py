"""零依赖预览服务器。

当 Streamlit 依赖尚未安装时，可运行 `py preview.py` 预览第一版页面。
"""

from __future__ import annotations

import http.server
import socketserver
import webbrowser
from pathlib import Path


PORT = 8501
PROJECT_DIR = Path(__file__).resolve().parent


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main() -> None:
    handler = http.server.SimpleHTTPRequestHandler
    with ReusableTCPServer(("127.0.0.1", PORT), handler) as server:
        url = f"http://127.0.0.1:{PORT}/preview.html"
        print(f"ReviewScope AI preview is running: {url}")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nPreview stopped.")


if __name__ == "__main__":
    # SimpleHTTPRequestHandler 从当前目录提供文件，因此切换到项目目录。
    import os

    os.chdir(PROJECT_DIR)
    main()
