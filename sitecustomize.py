from pathlib import Path
import zipfile

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
            "Ask MASTIC tidak dapat menjana jawapan buat masa ini. Sila cuba semula sebentar lagi."
        )
        TARGET.write_text(html, encoding="utf-8")
    except Exception:
        pass


# Emergency resilience patch: answer structured questions locally so Ask MASTIC
# does not depend on a second sleeping Render service during a live demo.
APP = ROOT / "backend" / "app.py"
ASK_MARKER = "# V11.2 local structured Ask MASTIC resilience"
if APP.exists():
    try:
        app_text = APP.read_text(encoding="utf-8", errors="ignore")
        if ASK_MARKER not in app_text:
            old_health = """@app.get('/api/health')
def stable_health_proxy():
    try:
        r=http_requests.get(STABLE_ASK_MASTIC+'/api/health',timeout=20)
        return JSONResponse(r.json(),status_code=r.status_code)
    except Exception as exc:
        return JSONResponse({'ok':False,'service_up':True,'upstream':'waking','error':str(exc)},status_code=200)


@app.post('/api/ask')
def stable_ask_proxy(req:AskRequest):
    try:
        r=http_requests.post(STABLE_ASK_MASTIC+'/api/ask',json=req.model_dump(),timeout=110)
        try:
            payload=r.json()
        except Exception:
            payload={'detail':r.text[:1000]}
        return JSONResponse(payload,status_code=r.status_code)
    except Exception as exc:
        raise HTTPException(503,f'Ask MASTIC stable backend belum memberi respons: {exc}')
"""
            new_health = """# V11.2 local structured Ask MASTIC resilience
@app.get('/api/health')
def stable_health_proxy():
    return JSONResponse({'ok':True,'service_up':True,'mode':'evidence-ai-synthesis-with-local-fallback'},status_code=200)


@app.post('/api/ask')
def stable_ask_proxy(req:AskRequest):
    q=req.question.strip()
    if not q:
        raise HTTPException(400,'Question is empty.')

    language=_resolve_language(q,req.language)

    # 1) Classify the question before deciding whether a factual answer is enough.
    ql=q.lower()
    analytical_terms=(
        'insight','insights','kenapa','mengapa','implikasi','risiko','rumusan',
        'apa maksud','apakah maksud','apa yang perlu','perlu diberi perhatian',
        'banding','perbandingan','hubungan','kaitkan','gabungkan','strategik',
        'management','pengurusan','trend','corak','apa yang boleh disimpulkan'
    )
    analytical=is_analytical(q) or any(term in ql for term in analytical_terms)

    structured=answer_structured(q,language,req.context)

    # Straight factual questions remain fast and deterministic.
    if structured and structured.get('answer') and not analytical:
        payload=dict(structured)
        payload.setdefault('confidence','high')
        payload['llm_used']=False
        payload['route']='local:factual:'+str(payload.get('route','structured'))
        return JSONResponse(payload,status_code=200)

    # 2) Analytical questions should go through the richer synthesis layer first.
    # The previous hosted service contains the LLM synthesis path; this call is bounded
    # so a sleeping upstream cannot break the live demo.
    try:
        upstream_payload=req.model_dump()
        upstream_payload['question']=q
        r=http_requests.post(STABLE_ASK_MASTIC+'/api/ask',json=upstream_payload,timeout=45)
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

    # 3) Local analytical fallback: still interpret the evidence instead of returning
    # a single number. This keeps the chatbot useful even when the LLM service sleeps.
    try:
        if analytical and ('e&e' in ql or 'elektrik' in ql or 'elektronik' in ql) and (
            'mismatch' in ql or 'ketidaksepadanan' in ql or 'padanan' in ql
        ):
            ee=answer_structured('permintaan dan penawaran bakat E&E',language,req.context) or {}
            mm=answer_structured('ketidaksepadanan graduan',language,req.context) or {}
            ee_ans=str(ee.get('answer') or '').strip()
            mm_ans=str(mm.get('answer') or '').strip()
            parts=[]
            if language=='ms':
                parts.append('Isyarat utama ialah cabaran bakat E&E bukan semata-mata jumlah bekalan, tetapi sejauh mana bakat itu sepadan dengan pekerjaan dan keperluan industri.')
                if ee_ans:
                    parts.append(ee_ans)
                if mm_ans:
                    parts.append(mm_ans)
                parts.append('Secara pengurusan, lebihan pada peringkat agregat tidak boleh terus ditafsirkan sebagai isu bakat telah selesai. Tumpuan perlu diberi kepada pekerjaan yang masih berisiko defisit, padanan bidang–pekerjaan dan kemahiran yang diperlukan industri.')
            else:
                parts.append('The main signal is that the E&E talent challenge is not only about total supply, but whether talent is aligned with occupations and industry needs.')
                if ee_ans:
                    parts.append(ee_ans)
                if mm_ans:
                    parts.append(mm_ans)
                parts.append('From a management perspective, an aggregate surplus should not be interpreted as the talent issue being resolved. Attention should remain on occupations with projected deficits, field-to-job alignment and industry-relevant skills.')
            return JSONResponse({
                'answer':' '.join(parts),
                'sources':_merge_sources(ee.get('sources'),mm.get('sources')),
                'route':'local:management-fallback',
                'confidence':'high',
                'llm_used':False
            },status_code=200)

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

    return JSONResponse({
        'answer':'Ask MASTIC sedang menyambung semula perkhidmatan analitik. Sila cuba semula sebentar lagi.',
        'sources':[],
        'route':'local:service-warming',
        'confidence':'low',
        'llm_used':False
    },status_code=200)
"""
            if old_health in app_text:
                app_text = app_text.replace(old_health, new_health, 1)
                APP.write_text(app_text, encoding="utf-8")
    except Exception:
        pass
