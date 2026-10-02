from pathlib import Path

TARGET = Path("Ask_MASTIC_V11_RENDER_SAFE/platform/index.html")
MARKER = "/* V11.1 restore analytics context bars */"

if TARGET.exists():
    try:
        html = TARGET.read_text(encoding="utf-8", errors="ignore")
        if MARKER not in html:
            css = r"""
<style>
/* V11.1 restore analytics context bars */
body.i360-onepage #i360 > .bi-context,
body.impact-onepage #impact > .bi-context{
  display:block !important;
  flex:0 0 auto !important;
  margin:6px 0 0 !important;
  border:1px solid #DCE4EC !important;
  border-radius:8px !important;
  background:#FFFFFF !important;
  overflow:hidden !important;
  box-shadow:none !important;
}
body.i360-onepage #i360 > .bi-context > summary,
body.impact-onepage #impact > .bi-context > summary{
  min-height:32px !important;
  padding:7px 11px !important;
  font-size:10px !important;
  line-height:1.2 !important;
  font-weight:700 !important;
  color:#17365D !important;
  background:#F8FAFC !important;
  cursor:pointer !important;
}
body.i360-onepage #i360 > .bi-context[open],
body.impact-onepage #impact > .bi-context[open]{
  max-height:32vh !important;
}
body.i360-onepage #i360 > .bi-context .bi-context-body,
body.impact-onepage #impact > .bi-context .bi-context-body{
  max-height:calc(32vh - 34px) !important;
  overflow:auto !important;
  padding:10px 12px !important;
}
body.i360-onepage #i360 > .bi-context .intelligence-card,
body.impact-onepage #impact > .bi-context .impact-signal{
  min-height:0 !important;
}
</style>
"""
            html = html.replace("</head>", css + "\n</head>", 1)
            TARGET.write_text(html, encoding="utf-8")
    except Exception:
        pass
