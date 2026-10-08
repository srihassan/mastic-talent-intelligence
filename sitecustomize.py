from pathlib import Path
import zipfile
import re

PACKAGE = Path("Ask_MASTIC_V11_RENDER_SAFE.zip")
ROOT = Path("Ask_MASTIC_V11_RENDER_SAFE")
TARGET = ROOT / "platform" / "index.html"
MARKER = "/* V11.1 restore analytics context bars */"

# The latest presentation ZIP stores platform/backend/etc at ZIP root.
# Render's existing build/start commands expect them inside Ask_MASTIC_V11_RENDER_SAFE/.
# Bootstrap that expected folder before the build command continues.
try:
    if PACKAGE.exists() and not TARGET.exists():
        ROOT.mkdir(exist_ok=True)
        with zipfile.ZipFile(PACKAGE, "r") as zf:
            zf.extractall(ROOT)
except Exception:
    pass

# Preserve the i-360 / Kajian Impak analytical-context bars in one-page mode.
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
        html = html.replace(
            "Jawapan tidak dapat dijana. Pastikan Ollama dan backend Ask MASTIC sedang berjalan.",
            "MASTICgpt tidak dapat menjana jawapan buat masa ini. Sila cuba semula sebentar lagi."
        )
        TARGET.write_text(html, encoding="utf-8")
    except Exception:
        pass


# Emergency resilience patch: answer structured questions locally so Ask MASTIC
# does not depend on a second sleeping Render service during a live demo.
APP = ROOT / "backend" / "app.py"
ASK_MARKER = "# V11.3 robust Ask MASTIC routing"
if APP.exists():
    try:
        app_text = APP.read_text(encoding="utf-8", errors="ignore")
        if ASK_MARKER not in app_text:
            new_health = """# V11.3 robust Ask MASTIC routing
@app.get('/api/health')
def stable_health_proxy():
    return JSONResponse({'ok':True,'service_up':True,'mode':'local-management-first-with-synthesis-fallback'},status_code=200)


@app.post('/api/ask')
def stable_ask_proxy(req:AskRequest):
    q=req.question.strip()
    if not q:
        raise HTTPException(400,'Question is empty.')

    language=_resolve_language(q,req.language)
    ql=q.lower()
    analytical_terms=(
        'insight','insights','kenapa','mengapa','implikasi','risiko','rumusan',
        'apa maksud','apakah maksud','apa yang perlu','perlu diberi perhatian',
        'banding','perbandingan','hubungan','kaitkan','gabungkan','strategik',
        'management','pengurusan','trend','corak','apa yang boleh disimpulkan'
    )
    analytical=is_analytical(q) or any(term in ql for term in analytical_terms)
    structured=answer_structured(q,language,req.context)

    # Fast factual route.
    if structured and structured.get('answer') and not analytical:
        payload=dict(structured)
        payload.setdefault('confidence','high')
        payload['llm_used']=False
        payload['route']='local:factual:'+str(payload.get('route','structured'))
        return JSONResponse(payload,status_code=200)

    # Management-grade local synthesis for E&E mismatch questions.
    if analytical and ('e&e' in ql or 'elektrik' in ql or 'elektronik' in ql) and (
        'mismatch' in ql or 'ketidaksepadanan' in ql or 'padanan' in ql
    ):
        ee=answer_structured('permintaan dan penawaran bakat E&E',language,req.context) or {}
        mm=answer_structured('ketidaksepadanan graduan',language,req.context) or {}
        ee_ans=str(ee.get('answer') or '').strip()
        mm_ans=str(mm.get('answer') or '').strip()
        if language=='ms':
            answer=(
                'Implikasi utamanya ialah isu bakat E&E tidak boleh dilihat sebagai isu jumlah bekalan semata-mata. '
                + (mm_ans + ' ' if mm_ans else '')
                + (ee_ans + ' ' if ee_ans else '')
                + 'Walaupun unjuran agregat boleh menunjukkan lebihan, sebahagian pekerjaan khusus masih berisiko defisit. '
                'Ini menunjukkan jurang utama ialah kesepadanan bidang, pekerjaan dan kemahiran. '
                'Bagi pengurusan, keutamaan bukan sekadar menambah bilangan graduan, tetapi menumpukan intervensi kepada pekerjaan yang kritikal, '
                'memperkukuh padanan graduan–pekerjaan dan memastikan kemahiran yang dibangunkan selari dengan keperluan industri.'
            )
        else:
            answer=(
                'The key implication is that E&E talent should not be treated as a simple total-supply problem. '
                + (mm_ans + ' ' if mm_ans else '')
                + (ee_ans + ' ' if ee_ans else '')
                + 'Even where the aggregate projection shows a surplus, specific occupations can still face deficits. '
                'The central issue is therefore alignment across fields of study, occupations and skills. '
                'For management, the priority is not merely to increase graduate numbers, but to target critical occupations, improve graduate-to-job matching '
                'and align skills development with industry demand.'
            )
        return JSONResponse({
            'answer':answer,
            'sources':_merge_sources(ee.get('sources'),mm.get('sources')),
            'route':'local:management-synthesis',
            'confidence':'high',
            'llm_used':False
        },status_code=200)

    # Try richer upstream synthesis, but never let it hold the live demo for long.
    try:
        upstream_payload=req.model_dump()
        upstream_payload['question']=q
        r=http_requests.post(STABLE_ASK_MASTIC+'/api/ask',json=upstream_payload,timeout=12)
        if r.ok:
            try:
                payload=r.json()
                ans=str(payload.get('answer') or '').strip()
                if ans:
                    payload['route']='synthesis:'+str(payload.get('route','upstream'))
                    return JSONResponse(payload,status_code=200)
            except Exception:
                pass
    except Exception:
        pass

    # Deterministic analytical fallback for other questions.
    try:
        pack=build_evidence_pack(q,req.context)
        evidence_text=pack.get('text') or ''
        if evidence_text:
            draft=_draft_for(q,pack,None,True if analytical else False,False,language)
            return JSONResponse({
                'answer':draft or evidence_text,
                'sources':pack.get('sources') or [],
                'route':'local:analytical-fallback' if analytical else 'local:evidence-fallback',
                'confidence':'medium',
                'llm_used':False
            },status_code=200)
    except Exception:
        pass

    if structured and structured.get('answer'):
        payload=dict(structured)
        payload.setdefault('confidence','medium')
        payload['llm_used']=False
        payload['route']='local:last-resort:'+str(payload.get('route','structured'))
        return JSONResponse(payload,status_code=200)

    return JSONResponse({
        'answer':'MASTICgpt tidak dapat menjana jawapan buat masa ini. Sila cuba semula sebentar lagi.',
        'sources':[],
        'route':'local:unavailable',
        'confidence':'low',
        'llm_used':False
    },status_code=200)
"""

            # Replace the original hosted proxy routes regardless of timeout values.
            route_pattern = re.compile(
                r"@app\.get\('/api/health'\)\s*def stable_health_proxy\(\):.*?"
                r"@app\.post\('/api/ask'\)\s*def stable_ask_proxy\(req:AskRequest\):.*?"
                r"raise HTTPException\(503,f'Ask MASTIC stable backend belum memberi respons: \{exc\}'\)",
                re.S
            )
            app_text, n = route_pattern.subn(new_health, app_text, count=1)
            if n:
                APP.write_text(app_text, encoding="utf-8")
    except Exception:
        pass


# MASTICGPT_UI_V1
# UI-only refresh for the chatbot. Dashboard modules, data and backend logic remain unchanged.
UI_MARKER = '<style id="masticgpt-ui-v1">'
if TARGET.exists():
    try:
        html = TARGET.read_text(encoding="utf-8", errors="ignore")
        # Refresh any earlier MASTICgpt UI injection so the latest UI is applied deterministically.
        html = re.sub(r'<style id="masticgpt-ui-v1">.*?</style>', '', html, flags=re.S)
        html = re.sub(r'<script id="masticgpt-ui-v1-script">.*?</script>', '', html, flags=re.S)
        html = re.sub(r'<div class="mgpt-disclaimer-backdrop" id="mgptDisclaimer".*?</div>\s*</div>', '', html, count=1, flags=re.S)
        if UI_MARKER not in html:
            ui_css = r"""
<style id="masticgpt-ui-v1">
/* MASTICgpt UI v1 — chatbot only */
.ask-mastic-btn{
  min-width:148px!important;
  padding:9px 14px 9px 9px!important;
  gap:9px!important;
  background:#0B2E63!important;
  border:1px solid rgba(255,255,255,.18)!important;
  box-shadow:0 12px 28px rgba(11,46,99,.24)!important;
}
.ask-mastic-btn:hover{background:#103E76!important}
.ask-agent-name{
  font-size:12.6px!important;
  font-weight:800!important;
  letter-spacing:.01em!important;
}
.ask-agent-avatar{
  overflow:hidden!important;
  background:#EAF1F8!important;
  border:2px solid rgba(255,255,255,.88)!important;
  box-shadow:0 4px 12px rgba(8,32,68,.18)!important;
}
.ask-agent-avatar.large{
  width:60px!important;
  height:60px!important;
  border-width:2px!important;
}
.ask-agent-avatar svg{display:none!important}
.ask-agent-avatar img{
  display:block!important;
  width:100%!important;
  height:100%!important;
  object-fit:contain!important;
  object-position:center center!important;
  padding:1px!important;
  border-radius:50%!important;
}

.ask-drawer{
  width:min(455px,96vw)!important;
  right:-485px!important;
  background:#F6F8FB!important;
  border-left:1px solid #D7E1EA!important;
  box-shadow:-18px 0 42px rgba(7,31,70,.18)!important;
}
.ask-drawer.open{right:0!important}
.ask-drawer-head{
  padding:15px 16px!important;
  background:#0B2E63!important;
  align-items:center!important;
  border-bottom:1px solid rgba(255,255,255,.10)!important;
}
.ask-head-brand{gap:12px!important;align-items:center!important}
.ask-head-copy h3{
  font-size:22px!important;
  line-height:1.1!important;
  font-weight:820!important;
  margin:0!important;
  letter-spacing:.005em!important;
}
.ask-head-copy p,.ask-head-status{display:none!important}
.ask-head-actions{display:flex;align-items:center;gap:8px}
.ask-minimize,.ask-close{
  width:34px!important;
  height:34px!important;
  border-radius:10px!important;
  border:1px solid rgba(255,255,255,.16)!important;
  background:rgba(255,255,255,.10)!important;
  color:#fff!important;
  display:grid!important;
  place-items:center!important;
  cursor:pointer!important;
  font-size:18px!important;
  font-weight:600!important;
  transition:.16s ease!important;
}
.ask-minimize:hover,.ask-close:hover{
  background:rgba(255,255,255,.18)!important;
  transform:none!important;
}

.ask-thread{
  padding:18px 16px 16px!important;
  background:#F7F9FC!important;
  gap:13px!important;
}
.ask-msg{
  font-size:12.4px!important;
  line-height:1.62!important;
  padding:13px 15px!important;
  border-radius:17px!important;
  max-width:89%!important;
}
.ask-msg.assistant{
  background:#FFFFFF!important;
  border:1px solid #DCE5ED!important;
  border-top-left-radius:17px!important;
  box-shadow:0 5px 14px rgba(16,42,67,.05)!important;
}
.ask-msg.user{
  background:#0B2E63!important;
  border-top-right-radius:17px!important;
  box-shadow:0 7px 16px rgba(11,46,99,.14)!important;
}
.ask-source-card{
  margin-top:11px!important;
  background:#FAFCFE!important;
  border:1px solid #D9E4EF!important;
  border-radius:12px!important;
  padding:10px 11px!important;
}
.ask-source-card strong{
  font-size:10.5px!important;
  color:#294E75!important;
  text-transform:none!important;
  letter-spacing:.01em!important;
  font-weight:800!important;
}
.doc-action-btn{
  border-radius:9px!important;
  background:#fff!important;
  color:#264D75!important;
  border-color:#D4E0EB!important;
}
.ask-input-row{
  gap:9px!important;
  padding:12px 14px 14px!important;
  background:#fff!important;
  border-top:1px solid #DFE7EF!important;
  box-shadow:0 -4px 14px rgba(16,42,67,.035)!important;
}
.ask-input-row input{
  height:46px!important;
  border-radius:23px!important;
  padding:0 17px!important;
  background:#FBFCFE!important;
  border:1px solid #CAD6E2!important;
  font-size:12.5px!important;
}
.ask-input-row button{
  height:46px!important;
  min-width:98px!important;
  border-radius:23px!important;
  padding:0 20px!important;
  background:#0B2E63!important;
  font-size:12.5px!important;
  box-shadow:0 7px 16px rgba(11,46,99,.16)!important;
}
.ask-backdrop.open{background:rgba(6,28,60,.28)!important}

/* Disclaimer shown before first chatbot use in each browser session */
.mgpt-disclaimer-backdrop{
  position:fixed;
  inset:0;
  z-index:4000;
  background:rgba(7,25,52,.54);
  display:none;
  align-items:center;
  justify-content:center;
  padding:20px;
}
.mgpt-disclaimer-backdrop.open{display:flex}
.mgpt-disclaimer{
  position:relative;
  width:min(510px,94vw);
  background:#fff;
  border-radius:18px;
  box-shadow:0 24px 64px rgba(6,25,55,.28);
  padding:26px 28px 24px;
  color:#172B41;
}
.mgpt-disclaimer h3{
  margin:0 0 14px;
  font-size:22px;
  color:#0B2E63;
  font-weight:820;
}
.mgpt-disclaimer p{
  margin:0;
  color:#344B63;
  font-size:14px;
  line-height:1.6;
}
.mgpt-disclaimer-check{
  display:flex;
  align-items:flex-start;
  gap:10px;
  margin:20px 0 18px;
}
.mgpt-disclaimer-check input{
  width:17px;
  height:17px;
  margin-top:2px;
  accent-color:#0B2E63;
  flex:0 0 auto;
}
.mgpt-disclaimer-check label{
  font-size:13.2px;
  line-height:1.45;
  color:#263D55;
  cursor:pointer;
}
.mgpt-disclaimer-proceed{
  width:100%;
  height:48px;
  border:0;
  border-radius:12px;
  background:#0B2E63;
  color:#fff;
  font-size:14px;
  font-weight:800;
  cursor:pointer;
  transition:.16s ease;
}
.mgpt-disclaimer-proceed:hover:not(:disabled){background:#123F78}
.mgpt-disclaimer-proceed:disabled{
  background:#C6D3E0;
  color:#F7F9FB;
  cursor:not-allowed;
}
.mgpt-disclaimer-dismiss{
  position:absolute;
  right:14px;
  top:12px;
  border:0;
  background:transparent;
  color:#718399;
  font-size:24px;
  line-height:1;
  cursor:pointer;
  padding:4px;
}
.mgpt-disclaimer-dismiss:hover{color:#0B2E63}

@media(max-width:600px){
  .mgpt-disclaimer{padding:24px 20px 20px;border-radius:16px}
  .mgpt-disclaimer h3{font-size:20px}
  .mgpt-disclaimer p{font-size:13.2px}
  .ask-drawer{width:100vw!important}
  .ask-head-copy h3{font-size:21px!important}
}
</style>
"""

            ui_modal = r"""
<div class="mgpt-disclaimer-backdrop" id="mgptDisclaimer" aria-hidden="true">
  <div class="mgpt-disclaimer" role="dialog" aria-modal="true" aria-labelledby="mgptDisclaimerTitle">
    <button class="mgpt-disclaimer-dismiss" id="mgptDisclaimerDismiss" type="button" aria-label="Tutup">×</button>
    <h3 id="mgptDisclaimerTitle">Penafian</h3>
    <p>Jawapan yang dijana melalui MASTICgpt adalah berasaskan data dan dokumen yang tersedia dalam platform ini. Dapatan dan tafsiran yang diberikan adalah untuk tujuan rujukan awal dan masih tertakluk kepada semakan lanjut. Sila hubungi pihak berkaitan sekiranya penjelasan lanjut diperlukan.</p>
    <div class="mgpt-disclaimer-check">
      <input id="mgptDisclaimerCheck" type="checkbox"/>
      <label for="mgptDisclaimerCheck">Saya telah membaca, memahami dan bersetuju dengan penafian di atas.</label>
    </div>
    <button class="mgpt-disclaimer-proceed" id="mgptDisclaimerProceed" type="button" disabled>Teruskan</button>
  </div>
</div>
"""

            ui_script = r"""
<script id="masticgpt-ui-v1-script">
(function(){
  const AVATAR='<img src="data:image/webp;base64,UklGRr4hAABXRUJQVlA4WAoAAAAQAAAAnwAAnwAAQUxQSM0JAAABDAVt2zAJf9jdZRARE8Cr6sZ24hRMnFMvrOCmXLg8oXSjesSmHXHB9IWxF25UJ1pZw7bNkCTr/eLL8axt27Zt27Zt27Zte3tt27bVmIyIL/I9mp3qqKg9fyNiAujU1h5JkqowtNXIGkAD2Eg0lOawEhhvvEEw7oxVkdL7fhmh5devP/2ImAD8Py3iVKuqqlTVyT8Opw6jqqryj0EUAIZOONsqm++85647bLb6QjOOh/8WdfIPwCmAadc4/80v/uRI/V/fvXDdwctPDACV62yiAky86z3f9ZIp+nrEiNrXtY8NSf74wF4LDgCg0rHEAVjgzM9JC96HEGOMZjHGGHxdB5Lh1UPnBlBJJxIHYNgGD0fShxhtFFMys1jXkbSndxwLqKTTiACDp1z5R2v1UekK3W/qAhZqIz/dZ3RAVDqIAJh0gZX2fIryALTRzGLw5NubTghAXcfA0OlXWXnL235lBXSHNbilZGahJn/q2m0iQKUDiKuGTzLNMsd39ZIBJIkOLKGhWYwkPzliGkALJ6oAxl77ko/I4KOhge/Ef5uvyU+OGAeuYKIOwKC59nyWZO2j2Ugc6ayaBd/w1ZWgUihRABOveczLNWkhmpmlBLjgk8zMAv/cFa5IosDYW13/BcnkQ+rvDclC7N0VrjyiwKSHfE626yqgQ3SzELgHtDQKTHbGD6T3Fc3jJYFLP6R6cbiiiGLQzt+wqaOZVjdIwi0FvjC6SEEcsNjzpI9mlnI0zz3gyqEY7YzEOqaULLU3E6H5eCJIKSrM0EULlgo4MrPA7UULoZjra46IqX8tytjMPO8G1EkBFCt/x9qsn/bjENOvK1UAtO0qfLFWQKFhBWBBgpp6nzt+WYVoe1XYqZWCJiGEHORAjGR8aFXASRtV2MBqYepML4u+9uTjSwLSNor1awN0Kj0GTIm+9wxnDoW0iWKZ7hR1Ir2xj3pmPvCyMUTawmGKbxlSDnIdiYXw7c4DnbSByNjPMVjLAPxYEswwSiOx0Ly7JtpAnLuKPlkSeBBsHkYpmSWzZIFdE0Oiib58a28Mo2mPp8Xgd4fLTfGpXRWQHBhu2MxassCXhkHycpj7PxVAktYUBwJASpYiVxTNSmTQPVYAeaMYeLGWzPMKuKwclv2jVtDWM3BQJ6bfZ4PLSXErixwBAgADeXSnUNcCuwY4yUcxT59Vj6gzAugBLgyS1TwGmo3DPJ+moPhwA83euIGYnJmNdVwOmonITC8w2AFdgBkBmpMkJz34ynCRTLDKl9FSSGBNWggdbBNUeSg2YEhZ0l07NzZXiEgOIkOfZWwRS8o1Np9MBZeDYnPG1Fpgjmws2vLQHDDg9iZYFociMaDDKAXukoVg8pdZuCFwm428QpDFfL8wtkgLcMasy0NjQnLYhNFSa1nQcfJ4cxq4/nM4nT61FlCyS9b8sUAGInikH5Q1g9SbBQa/yNCpIheBZjDo+eRbFNjCDa3mehlAcPWX3U0u4HSs9fIUVP3nsOhVKXYk4w+/3gzXf4Bbyptlkqzxm/efQ44OM/emjpSavz5/IosKO7FOBTWL9O7VcBkormBtHSn1dW8G7T+Be4m+JNrHKPD9MUVyGOebJrSfzcQ1614SDjmM93kTU/uZxQt8BCJZVI8ztJ/Ccbtfs4DgoqYE4QHPWyHI0WGDYNYaHCCWuTDRN+JEuCwEk/7cjBLcPFFc8wJGPd9vBs1k8GsMfwd2RN8i6q/vzQKXBQT3jwqgkOxzHtTHHyfDIU+Hm+n/jgTKbFjfrpkQkoni9FGJDsHo1PZ9Agiy2ZLeOockVO2f96iQzwb0ZhxzIFDahxdFRut3FjPzvL9yktPKDJaeqMUwYnE45LQGQ+oooXl8oEhGTqaPqeVM4cecRTDbGoqMFfuk2CpmII/AJ8cSl5HiMIbUtEhzig0bIteBIl/FivQxtXwCHQNLkZ8PF8lHZOhbjbfW9QEJYk06eB6ECvlW+Ngutom7fGEXaDk0D40uko/gTxidolWwmkdDs3GY+n8qsGvrtvVbetlJNoqt2htPRVjNNytIPle26zROeBAuG+D5Vm48D1loPp9YXCaCoR+3eg7oSEuep6HKZuKfTzqUlGLzxkCRGA7T9NiTgZTMumeBC9M7gAXygDnAUqq5ITSGYKJfmpNIQw5mNTfNZ+hnA4mFrDvRc6V85LVWbnqaYDGGtBBcDDjc1R5Px2L6bapsKhzZ3tAikJmULPDNQZAgimXtsfQEPe+EIqhgjC+a2HFqHoEBuUBxLuuOE5tlUWU0l4/ZWBbG78eDywaKG+gzsTQCH4JKPk6m/ysGy0JpeO6LAchYsRPrOGr42DazEGZxbricUOFIWshCZj1zCxr50WBIVqLYJzKs7LUFwnleCEXmioWfZsjo9BgXyw8KHEvfIQJfHyDIXx1uZ90ZPPdG1QZwbqw3WZv9DzKz5pcJIO0Ah2m+5Aiz/0FinpdD0Z6KOb9jHf6H0jYzW6BtoJjxGdJ0NPs874dD2zrodh8mcgu2GLR94BwWiALO2e95GxzaWSp9pxUgqxj/nFnaC4ob2pWVmdU8ABXabX2VSASr+eJAlTYTDPurFSBKbPPsnh2Kdnf4aknZCP6+HBRtL/LubysJRR/50bxQFFBfPraMSH/1+FCUUGTYh00oz7NHzg44lFFxKOvCBN4BwAkK6WTyz1Isi9l8GOhQToftGa0kgddDUVKRIR80oSBm3dOKKwoUJ9AXxPM4KEqzaG3lqPx4dCeFEaluZsiCGhaDorQOc/UmkvA8GoryOtzKkoPn4wNUCqRyXSE8v54UDgV27skyRPtrAShKK1o54C3WBGLkaqhQVlc5ABhz4Z8azovG7TEARVUBMMkapzz9jTXp/GjNNqhQUhVghu3u+ZUkLY0iJ0SGDVChpA5Yo6uPtOt61AWAGbMYgd2roEJJBUs8TqbaVwDtUAzP7xdChZKqLmH0Ptr/1PGe786ECkWtcA17baQ6PvDJ8VGhqA4r/xKjWUpFCLx+CBRFFRnjc4ZUSs/TIA5ldVggBiuFpXpqURRWsT59ytT2Rb49RKQ0FQ7gFSVg4GUYoKVRXFKQ2LyyLKBaFsFTLGkkI7sWBuAKIhj7O9Y8UggMN68GOFcMhwVSJJGUvJGPLwyoK0SFLemVqkXvGe9cHHCuEOcWxv7bR9q5swAqrRMBICFEXmLIx6yOHHHDlIC2nWDiP2gZUS/av3sNh3P9kaViOcaUEtTL+MEagLZEcjqdviyaoJaavHVOiGtBvoIBbzOWCwuRI45wqLJ49XGY3ZuVheXa+MQccNIPrwPnCvuwTkXFMdbs3g2QNhF5iqF0Zj7x8iGQlu11mHmEWfks1rxmkJP+eB0AAFZQOCDKFwAA8FgAnQEqoACgAD5JHoxEIqGhFXqebCgEhLEAZ+0vLv9Nf0vm+Wh/H8DtXXl6OXeq39Df9n3AOed+5nqI/ZX9rveY9Fv+Y9QD+1f2vrNf3J9gD9r/Tk/c/4Qf6//wP229oH/19YBwrP8e/DPwv/xH4+/uB6u/j30T+c/MLlUddeZ/8q/GP7DzR8CfkLqF/kv9I/0XnyfL91/tf+o9BH22+w/8n7b/ii+K85/5z+/+wF+q/+q/Mv1nvCS83/2H2zfYF/N/7H/sP8n+VXyPf9f+k/Mr3K/nn+W/8v+m+A3+W/1n/kf338mPnS9o/7Z+zB+uDhZHvjOExIWCP+WeLt/rDTRqPLyKd/DVP902rFPeRFywPyhLKgqyFG7q6y5s7JurIw84Nlnkch8k3ypKJb5aL+uFt0qH3HA5npwgZR1DIjiew5z6ZoTrvvGpNURQhJiDL/Y1euR7rvn+/d84j1trGr4fDIHCGc2yiFimE7YFe5PM77kIXtqBd3MQ2zfNNuaJ6okaRjHy8t4jGMng2qZyJq1lpstq0GBR+1W1xSREJ98wqcVcq6IVNjW9IvpGGCjTs5yYqFqiF5zHmQRuNL9UnCqfC8QNZ1Nm04/QLtpnmaCW50w7nNI1D2zKkgCk/PYp6CmTgkCskxiUOlgSWtsxAzaOP2wXksBOwj9lpN5EqwYsWoElrgaYqW/oD6ndhvngo1XkxN3ZYwPSRQlt9EVCy5gFJc8zqxFa8jxBhmr5RiEZupCi47Dtk1zNM4yux0BSHvwYxAsnV5Dj58D+F1cL/FU3TujG88auA5kzwZqqCqnnBVxhy2HNLqP3BZM7eYirDf9ZyHt6HGw7nHG8zddhoS2N/xGBDDsH3Ir0DfioTSMJBwSdYnb6COqh/HK+yq0uPd56aEIkb1YDcejrWqw6LLaCei4L0y22C6g+gRh9ozC5LLagaBw8/z5JC3/DTjDAAP7/DWRH4/a0V/Rr+jhCz+SVkcvWNgJQSf7lrv0sAYMLDMdyQncCNUdIr3ziEYO86HUwjKCPuebFVc47QANO58EGKbwqsQFAthKbpfGPK0iTVyjaectmI8bcQ8jvUfzgGJc+suaKNMv50w92XFFXHOjh7oo3YvFUf5lU6hHhPFfK/ts3te1RseKiiLdjA2tQNozLX7nS3Qa8zzBG9ZlFwMknqbhRB6sZ2dBk4aENzsxclXtmSMD/NXeViAkmrxTTyeuhSnimIxF1HpWeSVapWQ4ac/+BUK6NArGfi7RZ6QI2gHsOakLRjvX3dHkxFok7VG9MWqexp90w8Yh4RN3il0epIQyZtT3guXxoIfrhpltEM7Q5TtogNVaEqzqFTkJ8rpcJw3LrWWyc34gMFkPQZ6xDOiF3tmcWchEnj79KbvqOxouwiuTYFEIeWSR68UmrlFCAArzlkR9u63IYFZi4AcYWEQ+EkTfeM2YHtErT5FpuAHlDUo25df/Ca394yY4wc094W2r+WRuJmlNjdacL/h5t1UZtjY8woT/xZrxqvCEtEBmcZD75SueHXsN4lHBkhmsY80hZOUpxYpIzbt+jzCBgqfmzWIHPtDnUt0eydCazJ7FDly1WXqdOMtDA/mtsnfx48IzC3012DgBMcqZ2EBkklF6cG9eN91+cGR4xe1v3VmAk05gaTe+kaarNMdwxBPBQDn05gDrYKG3YxTjCeVzZL4np24ZTAhwsdHwnplA2iM7LVH2YghuHCKJiyJ1sktgXsVmpGz2VCg6YoeMAR4jZZgBvgSuvHwNYL1H2AEt46lum/pG10GueP2uXGthC8a/XXP7lQpvncxPBTopudpwKF2niSrWvvdspFhj7x/0JDjmc9TVBZFez/leS49DddKyeuDG2SRcC8R5IYSX8J6EmrpyCiBhkeSoxi053aziN4bZwzwDOxEupWecGQmnx6anZAxPHmBh7IB/wfZzZtuY5ebBJsLXna2xDSqpLda6L4USDZrgQjzvpWbXiRDstD/V9/q8iGlQcTMoc4lig4fOLnpmZdRaXTrGW9fbAkVNRRIr8FInD5Mx4xVyYn9vSeFsVLhpdAS9IDvLQ0+0Vre04ujVwV6hwxbvy0Sps/rYkCWZN1uAHUlSSDw/E92QMyJiZpjh4A25+rtDV51afI4P8LiNtVqVIdK43SE22RbiSNeJMh1PsleDuGhOGWOL2OiQCBcm74dG5+niiv3fMC6pYL53yg9Wo6P3ojpBDNt4fyfgtP5gzfCP0yzHWn/iuUrgrNFtBZH6tMdakKmhRqnT4dyjAJanJrXtxz650RiSgR33tikI74bey6PutMclMHFpHZBLAE6hy92gzzSd/KJaH1UMZaDBD1T1f9lXlyElUOBYM/MNOMwL0TLGE9PmDg64oKzA50WZIJ/Af7hrAZUu04xZIIAIQjHX4XX41InJESTauVAKRr7M2LyI/cvESiny2TXR751i4HhvFceB9U8Usfb5mMrwsBhYgXwkvjQKpWp4jaKQibjb/nnPW8MvvVHiAc2sputcckjEtFoTRvefyMd4VQLkFk01IlvGswLBp/2G590lHzqSdUqpg8zJFgFQEGoGmuyfQl6WnO+qnZpFWsjkXs8K+H/G3HGh/uExgkF4VmmijJ2O/wC5U39UE8KZmSe2A0O4374M4pV0EzoyE9H4X6pkbeeNb3OVsOlwOg+L8a1jPmTtBbnoBT4b4lME/W4s5W4QBIw99T3OfKByLx3WXdZqeRTFCm4QYCRy/a33rQ7e2WyTTcxuj09GhfJSBvHSvjwpvcn/uf0d3YdZDSo9Lgx3NDQGoMzY6tLYXy0IElFAjjvUDr6E9kXn8T+NQT2veyqhwKkjt5F8rbJR4FsYAv0b4teMCoVf4UVfrHUi36K7m0g4IwYVwErGf45Slivsq6v+bN920fFMgO6myhMtoASfy0C/iHTIA7FiYafKpvGpLH2jiJdkN5NbDxOzgKcK+BcDpTl5cKwinRuRo0maK5g4NKBghVOfkbUx3gETfrDo5dgGph8dw5+3EPlphkZBvkpwCdIWy8+2P9GamcP4KYUdVOrCssrq+5G8FWkhX7QH14xYHMmRKB6d8CsLJJvZUQ8lHrwul00ZfBy7lt4lArePXfAPi87CWCxnjrzEEyDYvhnySUwXHXt9C7/YoDk1WHHWm0Bklyhz2pq1+POV1NiNlGq+EfzlsfGhylkELncYD4LUHjmYqjhVxJRmcZGcvIT9s69PQwaE/THYXUEIueJBwk8Ojh+li3UZg0CJ6ES3aoN8JZkGcJ1lQA8mGdFEqsj8PcWWLgkiJthqS/F4fH0kQLbC7cuPPpYnNsy64Zir4tfnrKKVscXQ+XIJdN8xSltiaH2rNaA0ppq7D1Mo9rXYgrQt0Vbt3/65qppZaK7RssEwhxV5/Zp9ul/su7OdlyboynA4OMCv5mn1cqVsDkuxlZcuACd/7GxFqJk+DJr/+4s4/T1BddPBjA350lRDfDzx/uqPh45EzaUHjZJmUgQAYv7PgwWh6cRAzW9pVCPhvc+UrfnGtLUkCPsaT7B9p87Wna+sHU+LiaFifgaqvUR6hG3rxs18iT1XRuzkVswpTeOcUokVO8oLpj2LLB5lmj/Ju8CdtXszanxUSxlTFFQrzQftUQGKENdK51T3/5wOC/g2+GWAR7exeT9fQM5whz1t6c5ljG/b17fBbiz77z0WexoJhDfyenTNmuo/XlPQ9Fr2IpR3a2i4lQ2YNnS7rilcNd7+GnwgySTAxbMxdpF+W5J18OH6TnUnyYJhCxD5K9badnRJ0LCcisPrXSEAwLrgSj3cCfYQ8PCgVVBQVa9wthN95s5a+AZ427c7GV82XrHx4P8U/mWGy85f2Cv6wSMG1YZSLiGCsWw2EDB6SXZ7OnCs8lntDLEkYr9/lLH9wp5zKjQq1nuLnHGmYH0wXu/qX7H73CFCVEYl52fV7GM2ZTj8zazT8cZufe7mOXBC8v5COHsiLxF/pL420o7AZgpsDQpJ0QoglCcI/R1OWhV9fL62HWBpmhwV0vAUrkzYaw+fTMUuqtthiE1jnsqCt9Da52uxHoW0UbiOxA59Hc8PduyJ7W8Zo0QMMcJ1EOW2axflOOOLKkSZGMU64S8k5EvtH+HH327qSXVcCwEQUYa3gPW5Nj9TmPhY9H70FwgOreqV+cB4MbZTI67Kgk61sEUWY3AIKPz9G7XWoM1ZlH1XTYfvUH7Dw6HlP8/gc+IwAsinL2xDyR1b3Fx7VJcerf1rtbX1ItPZzWA64w30Ml85pwx+K59j0mi9nIdAd/8Dx+m8DqSxXuW0ioSJ6TrOSm9LwtyuAYXu+Mpqzd3L1GXmh6JuVPlvX1kFX4KpAd30qwJ9XrFOtXLASVJM+8R3etzRPULPuPEw1wJqD61Fcpey/PfxicrGRTQI/jQFFe/5SK0Cpc7r5RPHe5/9tSPN1aFEJ+G1G32iBQWQS+mcKMUqcEgDr3AN8K9jWIepDLP/uBfWYK3OIBsp29X1iz2F4aU8qXQFtFiCpHyGFcVVe8Gg07cEjnNMwypf5PjbhgiVycUJIVm7Xwz0GOaLsaFp5dWRy+Z7vqKg2WRSK657+i/p1D6B+AmKnQpBdUXS8pdODT4T4ZHGigFPHvj1CIUYSlCRKz0OZlhvcdHRO9FvB/lyVn9HUhRuk0BNOZLWVQt+M9j1xOkOrOJFn7LXueNHarElehWC5w8AbxDdMMOegGfib5xFpDd3ONqWif67O1oc9H7jMijL7WPMCax7tc1Pw4Lequ0qiU6vZXXF5Y4zmVELqIZsyOVgFJZUmFcVgfPYwSRMA5V3LUpBuTY62AhUqzEYqvmcvBNvrugJCPf0AMN04Y9HSlRp6DyAdpTmsSbi1SlOinggNnRlvYyRgTFlHqGPbrnksHnRNVLAmlikAZ0dHi4d33wRUdyqX9n46ApWKz0iRT4fQ3hP7DRIpYjmAnqyVART85FW3rRF5H9FbNNE+zp9Idn72LR1bWVutMyBl/2iGaniUKhi0bncspsoE3VoIT4os44ZrX8SE/+EYzxzkzf3oJhwR+ZZTOfpRt98iMomffBgWD01BjoTKcWQokF6hh8B+delBhRT97codqXc4n7SeZ5FHLLXG7+9euMDtJ8GXEsO74oFAUz7dQKKZyl/8Y7Q/jg2M775zh/7bmPzu4DnKS82ZiCsFSpiSJyIpBbfwKQmA/xCRAgnTI9/Z+1p/KpDkq1AV8xk8yWOd1mv55z4aBMajFXt6ajY1ivLCmFcO+a+O6Kpn+9f6P/jSEx7ajTAGZeRi8QeaeB99uwnTDzumVqj4w1Nqy/nDMrdvTbxGHQLx3R8+dHYWfwu8g+FOAPuWOrVSJ5C1vyGNr45LG9d+jHCUKv6YGvY1SECyvEno7yP4mLTFeVaUT8zb6dxMzn8GjvkPDqj1wLHL1BbbaN2wb8AoN3x2/tlA6ou/IDNQPWkRC/tjqegSn4lZBP8Q7uJ8E69ZEirMMiYiQNLyxnGE//8gDflrIGDkA79/dWWfkcvHQez07aA6OXGIE8SKtKgG9XL1f8MmaGpqvs6ZQB8N2qYPLtZj6arEi1i3ueMH470NtqLjQkrRXXnEN/t7pXVBfUxoDPoR/4oxt79jz3+56mNMk+m8SMCeq1UGrEoRyEYAkmLOXj9UKeCu3KA2dfWoljLq31a1wT2WHv4gBrF34YzK4a0RBvB/KRfJ39vvyEi8PGEkEpdSk56OmsLu0gPDhnrlOMrH7twhjgGmnUrgiW9vTaU7PEeaapBAGc9qJxFrClAp8+Zqb1FgpxFirB5og+7pr2K3aDWhS4WSPk0ot8yAaW6DOEAunWHJLkc1F1DL505tECTWxHYchMX77D8VE0r2M3kPX0hdkeSbE31FJU75ii9ymHtAqcuxJ4S5QQEZAnaKnYlCp98EZXHYaxBZV50QrH21nZna56XVEACMUP3HF44+GxJsjBCUZG9OaRwt6Cc3E6cCcKOtNvZ1hOXtLLesijQY3yCK0/Hw9QizYMtRMCNeaZunREDj3WEWrmgfPwAXNE0/wfICt6IBFL/9TamzSnwF4YIp7izJ0GR0wh2BckTsIiTNXnPE+Q8IBnUrWu2GnhiKjTDzCxNLcUX+Qw4q2QYC9Mj55Bzf77qYjQfyGZIZaVbeSRAS75AVqdfSpqkpNOSKvJmQfVZOQPqzyh4xd/9jBbRNDU9nuFRTJtScUpGalrObN29W6dxcCifV5piRIrd8TcLMuUEkPAC6QTjg5jEv1WSXwQ8yLy9dfo1eNN0tuasIXHYgATLPTXplGV9sOO2DTAmz9aPJY3MHwah78rPMTBSILjAl1Xng+cNN6F9LRQp14V53zrJ/NTU1z3nRiOLFFjROnwAFJoqG/KOy84TEqUD3M2av+GA+5C37ki4tJCXxLtm1QizbFWDTyNj8m/J9DJDx4l4bDTR4ZKD92EozOPDYv//nLIsJEvfkqu/UOfjJAMVAEwUR1SmrqxFFp9iHmDZMWCZczzuC5PU2U2n5qaAH1HgdgnuU7kUtkwgmvCWr9Q6IDgA/7+DckC4C6ZJRORhIOAJob5Zp4N5iMGbLra1GMlKcn4/lQJEgqsCiYo/zxQcGqX4XlNNiYn1uqDjHJNjj5gBTNY5AOfTzRURL//kbH+igSiKzMIE66NLK/fmhY4UYhP5pQaCHJSQ1cyUL9ft5eJuTG1BXCAfnBI0wdHEahy3KZFkbR6ecZZ5bp3SBXMceruHMNr6JfENnsk8JO8wTtSfduMU0WFTPXGOR2v/BRUehE3SLTFj/jt6wztckm/sj92s1Pxd/aVJqCoNLcXhV6kd3HLvxNxnMKM6RgUmm9T8m2qgCoVNc14MnjDnWNsggbpFQ2BOW0nL1+/C3/q1Ztg5sPbSft0k0LQy8w3Fhn6GPl+YschRxxfs+ou7bgeyDNfqfxiE+0fPlE6z7lCxLQRYPvH9lR8175CQX5JPWNYYCQJPIq4ErZ6UybktSO6XBdw259/qdszJz/zEcO8p1NrJo5EKlUu+m4wkJHC8SHDs4ikQduo7GPVo1RDvPag+yALpIddtqXD2jcyXf8jyt8tdIgxYIIOnnxvUYo4aFlbAaysEc0FNM1q+aPKQQy8ypc1SDkS5RV+ZxMUYIpzYeNO0h0sSxxIC6pH31ldEf6hbN0TLQQ1/Y4CCchu0atFqNGe5lYO++U517sb1x34nh8L1XHv51rs0ipj+DI9MiI/oBrX6Dc4sMk3QJudF8m4D08Ix8j3cB5f5zmFNByR2VHpX+UnSrUcBlpJzW/umqeQLdeErewshV//SVl8V1QrAaoXMDKtfSHTYOGuUIoV+n5a/SEWqaCuDLqvDRbMdV8BWiHnppVS0qlOK/xM7Mr/sxjMIQpObzg32Pb715VfXy4gpntl7QxGvKia4KlZ/dL4umSIur/g9JmCwYsJ8q1EHhiUn/zaOXEABy0hKG5qTfadLWaAFM+Rc/8c+UqRvOM8ekLX7SPPvKehcUUIgQJWvqUq3wt4UWy8YEN05czO/dDMcipYTCdRh/tHmRHESXXSxVBAW1/yT/9BYRpZoFgrS0g+Uxtm3RYY6UhRuLqkMesqv6x9IKHhkD/KxtlJL7dih3FB+HdME2U+wQQVZcCbdliP/1JRoCca2e8wvUK6W81sxFT4xh8YsLSUcCKhWWHTtNDmY7fkjc0lDUJVRl2OdCXY26sWdNa1HsR8I8zelDVYaIjsPmAQ+73GxSz6H1bF5kOVVZj5MDSiLV6Necpy5sB+4cZB2jUCuoSTuAz8zr93hnXEFgAztZKXM98Xoa3EWAmartXjfQpNqQY0J7BjdLwSPNPhbSO4Iv2WVy26YHgs6KG+0Jg2ApD8yRtoExryndjFVcwM+PXsvQNV/Y7VBwQuJu2sWQRnh5NV4bDfmPW85bgHRudKXPePbf/wS3RcLS7BzJ8Vvss70z0mhz2Ub7k5ahIvTLO/utWOOlchYcuav48EZxnEDFrXH4YRpq7Sc+EPVRcYrZM536niAvVEjhD8PSLaPJvnL7LqZCMh/B8BgWjmBsuv6A3ZQIxGHfylTcOm2AFWUdgujRY3eKbQwUevmrUPPna4n2pxcRMtYj63VeByWFIuQ2cu8w03/1ieq5/ByIZSCi6OPAOM+k8IWewAAA" alt="" aria-hidden="true"/>';

  function renameSources(){
    document.querySelectorAll('#askThread .ask-source-card strong').forEach(function(el){
      if(/rujukan|reference/i.test(el.textContent||'')) el.textContent='Sumber Rujukan';
    });
  }

  function applyUI(){
    document.querySelectorAll('.ask-agent-avatar').forEach(function(el){ el.innerHTML=AVATAR; });
    document.querySelectorAll('.ask-agent-name').forEach(function(el){ el.textContent='MASTICgpt'; });

    const title=document.querySelector('#askDrawer .ask-head-copy h3');
    if(title) title.textContent='MASTICgpt';

    const sub=document.querySelector('#askDrawer .ask-head-copy p');
    if(sub) sub.remove();

    const welcome=document.querySelector('#askThread .ask-msg.assistant');
    if(welcome){
      welcome.textContent='Hai, saya MASTICgpt. Tanya saya tentang data dan analitik bakat STEM.';
      welcome.setAttribute('data-langtext-ms','Hai, saya MASTICgpt. Tanya saya tentang data dan analitik bakat STEM.');
      welcome.setAttribute('data-langtext-en',"Hi, I'm MASTICgpt. Ask me about STEM talent data and analytics.");
    }

    const head=document.querySelector('#askDrawer .ask-drawer-head');
    const close=document.getElementById('askClose');
    if(head && close && !document.getElementById('askMinimize')){
      const actions=document.createElement('div');
      actions.className='ask-head-actions';

      const min=document.createElement('button');
      min.className='ask-minimize';
      min.id='askMinimize';
      min.type='button';
      min.setAttribute('aria-label','Minimize');
      min.textContent='—';

      close.parentNode.insertBefore(actions,close);
      actions.appendChild(min);
      actions.appendChild(close);

      min.addEventListener('click',function(){
        if(typeof setAskOpen==='function') setAskOpen(false);
      });
    }
    renameSources();
  }

  function showDisclaimer(){
    const modal=document.getElementById('mgptDisclaimer');
    if(!modal) return;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden','false');
    setTimeout(function(){ document.getElementById('mgptDisclaimerCheck')?.focus(); },30);
  }

  function hideDisclaimer(){
    const modal=document.getElementById('mgptDisclaimer');
    if(!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden','true');
  }

  document.addEventListener('DOMContentLoaded',function(){
    applyUI();

    const btn=document.getElementById('askMasticBtn');
    const modal=document.getElementById('mgptDisclaimer');
    const check=document.getElementById('mgptDisclaimerCheck');
    const proceed=document.getElementById('mgptDisclaimerProceed');
    const dismiss=document.getElementById('mgptDisclaimerDismiss');

    check?.addEventListener('change',function(){
      if(proceed) proceed.disabled=!check.checked;
    });

    proceed?.addEventListener('click',function(){
      if(!check?.checked) return;
      try{ sessionStorage.setItem('masticgpt_disclaimer_ack','true'); }catch(e){}
      hideDisclaimer();
      if(typeof setAskOpen==='function') setAskOpen(true);
    });

    dismiss?.addEventListener('click',hideDisclaimer);

    modal?.addEventListener('click',function(e){
      if(e.target===modal) hideDisclaimer();
    });

    /* Capture phase prevents the existing open handler until disclaimer is acknowledged. */
    btn?.addEventListener('click',function(e){
      let acknowledged=false;
      try{ acknowledged=sessionStorage.getItem('masticgpt_disclaimer_ack')==='true'; }catch(err){}
      if(!acknowledged){
        e.preventDefault();
        e.stopImmediatePropagation();
        showDisclaimer();
      }
    },true);

    const observer=new MutationObserver(renameSources);
    const thread=document.getElementById('askThread');
    if(thread) observer.observe(thread,{childList:true,subtree:true});
  });
})();
</script>
"""

            # Server-side branding so there is no visible flicker before JS runs.
            html = html.replace('<span class="ask-agent-name">Ask MASTIC</span>', '<span class="ask-agent-name">MASTICgpt</span>')
            html = html.replace('<h3>Ask MASTIC</h3>', '<h3>MASTICgpt</h3>')
            html = html.replace(
                'Tanya soalan berkaitan SPM, E&E Supply & Demand, Graduate Mismatch atau STI Foresight.',
                'Hai, saya MASTICgpt. Tanya saya tentang data dan analitik bakat STEM.'
            )
            html = html.replace(
                'Ask MASTIC tidak dapat menjana jawapan buat masa ini. Sila cuba semula sebentar lagi.',
                'MASTICgpt tidak dapat menjana jawapan buat masa ini. Sila cuba semula sebentar lagi.'
            )

            html = html.replace("</head>", ui_css + "\n</head>", 1)
            html = html.replace("</body>", ui_modal + "\n" + ui_script + "\n</body>", 1)
            TARGET.write_text(html, encoding="utf-8")
    except Exception:
        pass
