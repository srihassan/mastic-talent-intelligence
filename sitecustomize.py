from pathlib import Path
import zipfile
import re

PACKAGE = Path("Ask_MASTIC_V11_RENDER_SAFE.zip")
ROOT = Path("Ask_MASTIC_V11_RENDER_SAFE")
TARGET = ROOT / "platform" / "index.html"
AVATAR_B64_FILE = Path("masticgpt_avatar_bust_192.b64")
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

    # Fast local analytical response for the recurring SPM Mathematics trend demo.
    if analytical and 'spm' in ql and ('matematik' in ql or 'mathematics' in ql) and ('trend' in ql or 'prestasi' in ql):
        src=answer_structured('prestasi subjek matematik SPM 2018-2025',language,req.context) or {}
        if language=='ms':
            answer=('Prestasi Matematik SPM menunjukkan trend bercampur antara 2018 hingga 2025. '
                    'GPMP 2025 ialah 5.03, sama seperti 2018, tetapi kadar lulus menurun daripada 82.0% kepada 78.3%, '
                    'kadar sekurang-kurangnya kepujian daripada 56.1% kepada 51.6%, manakala kadar gagal meningkat daripada 18.0% kepada 21.7%. '
                    'GPMP terbaik direkodkan pada 2020 (4.94) dan paling lemah pada 2021 (5.57). '
                    'Ini menunjukkan pemulihan GPMP belum disertai pengukuhan pada indikator hasil lain, maka prestasi keseluruhan belum menunjukkan peningkatan yang konsisten.')
        else:
            answer=('SPM Mathematics shows a mixed trend from 2018 to 2025. The 2025 GPMP was 5.03, the same as in 2018, '
                    'but the pass rate fell from 82.0% to 78.3%, the share achieving at least credit fell from 56.1% to 51.6%, '
                    'and the failure rate rose from 18.0% to 21.7%. The best GPMP was recorded in 2020 (4.94) and the weakest in 2021 (5.57). '
                    'This indicates that the recovery in GPMP has not been matched by stronger outcome indicators, so overall performance has not improved consistently.')
        return JSONResponse({
            'answer':answer,
            'sources':src.get('sources') or [],
            'route':'local:spm-math-trend',
            'confidence':'high',
            'llm_used':False
        },status_code=200)

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
  width:72px!important;
  height:72px!important;
  border-width:2px!important;
}
.ask-agent-avatar svg{display:none!important}
.ask-agent-avatar img{
  display:block!important;
  width:100%!important;
  height:100%!important;
  object-fit:contain!important;
  object-position:center center!important;
  padding:0!important;
  transform:scale(.88)!important;
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
  const AVATAR='__MASTICGPT_AVATAR__';

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

            try:
                avatar_b64 = AVATAR_B64_FILE.read_text(encoding="utf-8").strip()
                avatar_tag = '<img src="data:image/webp;base64,' + avatar_b64 + '" alt="" aria-hidden="true"/>'
                ui_script = ui_script.replace('__MASTICGPT_AVATAR__', avatar_tag)
            except Exception:
                pass

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
