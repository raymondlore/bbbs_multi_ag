"""docs/ 마크다운을 외부 의존 없는 정적 HTML(_site/)로 변환한다."""
from __future__ import annotations

import html
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

# (출력 파일, 원본, 탭 이름)
PAGES: list[tuple[str, Path, str]] = [
    ("index.html", ROOT / "docs" / "plan.md", "계획"),
    ("api.html", ROOT / "docs" / "api.md", "API 계약서"),
    ("ux.html", ROOT / "docs" / "drafts" / "ux.md", "ux 초안"),
    ("architect.html", ROOT / "docs" / "drafts" / "architect.md", "architect 초안"),
    ("critic.html", ROOT / "docs" / "drafts" / "critic.md", "critic 검토"),
]

CSS = """
:root{--bg:#f7f8fa;--fg:#1b2430;--muted:#5b6675;--line:#dde2ea;--accent:#1f5fbf;--soft:#e6eefb;--code:#eef1f6}
@media (prefers-color-scheme:dark){:root{--bg:#12171e;--fg:#e4e9f0;--muted:#97a3b3;--line:#2c3644;--accent:#7fb0ff;--soft:#1f2c42;--code:#222b37;color-scheme:dark}}
body{background:var(--bg);color:var(--fg);margin:0;padding:24px max(16px,env(safe-area-inset-right,0px)) 64px max(16px,env(safe-area-inset-left,0px));
font:15px/1.7 "Pretendard","Noto Sans KR","Malgun Gothic",system-ui,sans-serif}
.wrap{max-width:780px;margin:0 auto}
nav{display:flex;flex-wrap:wrap;gap:4px;border-bottom:1px solid var(--line);margin-bottom:24px}
nav a{color:var(--muted);text-decoration:none;font-weight:600;font-size:14px;padding:10px 12px;border-bottom:2px solid transparent;margin-bottom:-1px}
nav a[aria-current=page]{color:var(--accent);border-bottom-color:var(--accent)}
h1{font-size:22px}h2{font-size:18px;margin-top:36px;padding-top:6px;border-top:1px solid var(--line)}h3{font-size:15px;color:var(--accent)}
p,li{max-width:68ch}a{color:var(--accent)}
code{font-family:ui-monospace,Consolas,monospace;font-size:.9em;background:var(--code);padding:1px 5px;border-radius:4px}
pre{background:var(--code);border:1px solid var(--line);border-radius:6px;padding:12px 14px;overflow-x:auto}
pre code{background:none;padding:0}
.t{overflow-x:auto}table{border-collapse:collapse;font-size:13.5px;min-width:100%}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{background:var(--soft)}
"""


def render(md_text: str) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    return body.replace("<table>", '<div class="t"><table>').replace("</table>", "</table></div>")


def page(title: str, body: str, current: str) -> str:
    links = "".join(
        f'<a href="{href}"{" aria-current=page" if href == current else ""}>{html.escape(name)}</a>'
        for href, _, name in PAGES
    )
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)} · 과제 게시판 MVP</title><style>{CSS}</style></head>"
        f'<body><div class="wrap"><nav>{links}</nav><main>{body}</main></div></body></html>'
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for out_name, src, tab in PAGES:
        text = src.read_text(encoding="utf-8")
        (OUT / out_name).write_text(page(tab, render(text), out_name), encoding="utf-8")
        print(f"built {out_name} <- {src.relative_to(ROOT)}")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")


if __name__ == "__main__":
    main()
