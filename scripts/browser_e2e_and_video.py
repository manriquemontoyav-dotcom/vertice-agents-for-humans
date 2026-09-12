#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

REQUIRED = ['READY','INTERRUPTED','COMMITTED','REPLAY_BLOCKED','MUTATION_BLOCKED','DENIED']

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024), b''): h.update(c)
    return h.hexdigest()

def wait_phase(page, phase: str):
    page.locator('#phase').wait_for(state='visible')
    page.wait_for_function("p => document.querySelector('#phase').textContent === p", arg=phase)

def api_state(page):
    return page.evaluate("async () => await (await fetch('/api/runtime/state')).json()")

def title_card(page, kicker, title, body, extra=''):
    html=f'''<!doctype html><html><head><meta charset="utf-8"><style>
    body{{margin:0;background:#071426;color:#fff;font-family:Arial,sans-serif;display:grid;place-items:center;height:100vh}}
    main{{width:1050px}}.k{{font-size:22px;letter-spacing:.16em;color:#90baff;text-transform:uppercase;font-weight:700}}
    h1{{font-size:58px;line-height:1.02;margin:18px 0}}p{{font-size:27px;line-height:1.35;color:#d6e2f5;max-width:1000px}}
    .chain{{font-family:monospace;font-size:23px;background:#0e223c;padding:22px;border-radius:14px;line-height:1.6}}
    .truth{{margin-top:28px;font-weight:700;font-size:20px;color:#9fe3bf}}
    </style></head><body><main><div class="k">{kicker}</div><h1>{title}</h1><p>{body}</p>{extra}</main></body></html>'''
    page.set_content(html)
    page.wait_for_timeout(1700)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--commit-sha', required=True)
    ap.add_argument('--source-archive', type=Path, required=True)
    ap.add_argument('--application-evidence', type=Path, required=True)
    ap.add_argument('--screenshots-dir', type=Path, required=True)
    ap.add_argument('--browser-evidence', type=Path, required=True)
    ap.add_argument('--video-dir', type=Path, required=True)
    ap.add_argument('--video-file', type=Path, required=True)
    ap.add_argument('--video-metadata', type=Path, required=True)
    args=ap.parse_args()
    args.screenshots_dir.mkdir(parents=True, exist_ok=True)
    args.video_dir.mkdir(parents=True, exist_ok=True)
    app_raw=args.application_evidence.read_bytes(); app=json.loads(app_raw)
    archive_sha=sha256(args.source_archive); app_sha=hashlib.sha256(app_raw).hexdigest()
    assert app['status']=='PASS' and app['runtime']=='REAL_STRANDS'
    assert app['source']['commit_sha']==args.commit_sha
    assert app['source']['archive_sha256']==archive_sha

    checks=[]
    def ck(name, ok, detail):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL','details':str(detail)})
        if not ok: raise AssertionError(f'{name}: {detail}')

    shots=[]; observed=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1280,'height':720}, record_video_dir=str(args.video_dir), record_video_size={'width':1280,'height':720})
        page=context.new_page(); video=page.video
        title_card(page,'Agents for Humans','VÉRTICE — The agent works. You decide.','A human-authority layer for consequential agent actions.')
        title_card(page,'Problem · Audience · Why it matters','Autonomy without blanket authority','Professionals need agents that can do reversible work autonomously, while consequential commitments remain bound to one exact human decision.')
        title_card(page,'Architecture','Exact-action authorization → constrained continuation','The decision is bound to the runtime action, consumed once, and proven against replay or mutation.', '<div class="chain">agent work → authority boundary → exact decision → human resolution → guarded continuation → SIMULATED effect → evidence</div><div class="truth">REAL_STRANDS · SIMULATED external effect · REPLAY explicitly tested</div>')

        page.goto(args.base_url, wait_until='networkidle')
        wait_phase(page,'READY'); s=api_state(page); observed.append('READY')
        ck('ready_state', s['phase']=='READY' and s['effect_count']==0, s)
        ck('ui_api_same_ready', page.locator('#phase').text_content()==s['phase'], 'DOM and API READY')

        page.locator('#start').click(); wait_phase(page,'INTERRUPTED'); s=api_state(page); observed.append('INTERRUPTED')
        ck('interrupt_real_strands', s['runtime']=='REAL_STRANDS' and s['phase']=='INTERRUPTED', s)
        ck('zero_effect_before_decision', s['effect_count']==0, s['effect_count'])
        ck('interrupt_visible', bool(page.locator('#interrupt').text_content()) and bool(page.locator('#actionHash').text_content()), 'interrupt and digest shown')
        f=args.screenshots_dir/'INTERRUPTED.png'; page.screenshot(path=str(f), full_page=True); shots.append(('INTERRUPTED',f))

        page.locator('#approve').click(); wait_phase(page,'COMMITTED'); s=api_state(page); observed.append('COMMITTED')
        ck('commit_once', s['effect_count']==1 and s['runtime']=='REAL_STRANDS', s)
        ck('receipt_visible', bool(s.get('receipt_id')) and page.locator('#receipt').text_content()==s.get('receipt_id'), s.get('receipt_id'))
        f=args.screenshots_dir/'COMMITTED.png'; page.screenshot(path=str(f), full_page=True); shots.append(('COMMITTED',f))

        page.locator('#replay').click(); page.locator('#proofMessage').filter(has_text='REPLAY SAFE').wait_for(); s=api_state(page); observed.append('REPLAY_BLOCKED')
        ck('replay_no_second_effect', s.get('replay_result')=='SAME_RECEIPT_NO_SECOND_EFFECT' and s['effect_count']==1, s)
        f=args.screenshots_dir/'REPLAY_BLOCKED.png'; page.screenshot(path=str(f), full_page=True); shots.append(('REPLAY_BLOCKED',f))

        page.locator('#tamper').click(); page.locator('#proofMessage').filter(has_text='MUTATION BLOCKED').wait_for(); s=api_state(page); observed.append('MUTATION_BLOCKED')
        ck('mutation_blocked', str(s.get('tamper_result','')).startswith('BLOCKED_8751:') and s['effect_count']==1, s)
        f=args.screenshots_dir/'MUTATION_BLOCKED.png'; page.screenshot(path=str(f), full_page=True); shots.append(('MUTATION_BLOCKED',f))

        page.locator('#reset').click(); wait_phase(page,'READY'); page.locator('#start').click(); wait_phase(page,'INTERRUPTED'); page.locator('#deny').click(); wait_phase(page,'DENIED'); s=api_state(page); observed.append('DENIED')
        ck('deny_zero_effect', s['phase']=='DENIED' and s['effect_count']==0 and s['runtime']=='REAL_STRANDS', s)
        ck('same_runtime_session', page.locator('#phase').text_content()==s['phase'] and page.locator('#truthRuntime').text_content()==s['runtime'], 'UI and API agree after same-session flow')
        f=args.screenshots_dir/'DENIED.png'; page.screenshot(path=str(f), full_page=True); shots.append(('DENIED',f))

        title_card(page,'Verified demo','Exact action. One authorization. One effect.','Replay does not create a second effect. A US$8,751 mutation is blocked. Denial produces zero effects.', '<div class="truth">REAL_STRANDS runtime · external business effect intentionally SIMULATED</div>')
        context.close(); browser.close()
        recorded=Path(video.path())

    args.video_file.parent.mkdir(parents=True, exist_ok=True)
    if args.video_file.exists(): args.video_file.unlink()
    shutil.move(str(recorded), args.video_file)
    ffprobe=shutil.which('ffprobe')
    if not ffprobe: raise SystemExit('ffprobe unavailable')
    duration=float(subprocess.check_output([ffprobe,'-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(args.video_file)],text=True).strip())
    ck('video_duration_under_5m', 0 < duration <= 300, duration)

    screenshot_entries=[]
    for label,path in shots:
        screenshot_entries.append({'label':label,'file':path.name,'sha256':sha256(path)})
    result={
      'schema':'vertice.browser-e2e.v1','scope':'BROWSER_APPLICATION_E2E','status':'PASS',
      'checks_passed':len(checks),'checks_total':len(checks),
      'source':{'commit_sha':args.commit_sha,'archive_sha256':archive_sha},
      'application_evidence_sha256':app_sha,'runtime':'REAL_STRANDS','same_runtime_session':True,
      'decision_actor':'OBSERVED_UI_CLICK_UNVERIFIED_ACTOR','external_effect':'SIMULATED',
      'observed_states':REQUIRED,'screenshots':screenshot_entries,'checks':checks
    }
    args.browser_evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    browser_sha=sha256(args.browser_evidence)
    video_meta={
      'schema':'vertice.video-freeze.v1','video_sha256':sha256(args.video_file),
      'source':{'commit_sha':args.commit_sha},'candidate_sha256':archive_sha,
      'application_evidence_sha256':app_sha,'browser_evidence_sha256':browser_sha,
      'duration_seconds':round(duration,3),'resolution':{'width':1280,'height':720},
      'truth_labels_visible':True,
      'sections':['problem','audience','why_it_matters','working_demo','architecture'],
      'language':'English','publication_status':'PRIVATE_CI_ARTIFACT_NOT_PUBLIC'
    }
    args.video_metadata.write_text(json.dumps(video_meta,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'browser':result,'video':video_meta},indent=2))

if __name__=='__main__': main()
