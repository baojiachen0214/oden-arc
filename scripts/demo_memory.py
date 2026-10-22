#!/usr/bin/env python3
"""Synthetic scale/restart demonstration. Does NOT call or benchmark an AI model.

Output cards are intentionally simple programmatic fixtures to isolate scheduling,
cache invalidation, durability and prepared input volume from semantic quality.
"""
from __future__ import annotations
from datetime import datetime, timezone
import argparse
from pathlib import Path
import json
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from oden_arc.memory import Memory,compact
from oden_arc.common import json_bytes,write_new


def card_batch(batch):
    return {'lease':batch['lease'],'goal_rev':batch['goal_rev'],'results':[
        {'chunk_id':u['id'],'summary':u['text'].strip()[:100], 'room':'合成基准/条件',
         'keywords':['条件','测量','排除'], 'coverage':'read','unresolved':[],
         'claims':[{'text':u['text'].strip()[:180],'kind':'fact','quote':u['text'].strip()[:180],
                    'qualifiers':['合成调度测试，不是现实实验结论']}]} for u in batch['units']]}


def run(documents=120, sections=10):
    start=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='oden-scale-', dir=Path(tempfile.gettempdir()).resolve()) as tmp:
        base=Path(tmp); originals=base/'sources';originals.mkdir();work=base/'work'
        goal={'question':'保留所有合成资料的条件并测试断点恢复','purpose':'reference',
              'constraints':['不把合成卡片当真实AI理解结果'],'must_answer':['是否有资料被重复或遗漏处理？']}
        Memory.create(work,goal)
        inputs=[]
        for d in range(documents):
            path=originals/f'doc-{d:04d}.md'
            content='\n\n'.join(f'资料 {d} 第 {n} 项：在测试条件 C{n} 下记录指标 {d+n}；这是合成数值，不能当作生产测量。未给出的耗时保持未知，比较之前需对齐版本与分母。' for n in range(sections))
            path.write_text(content,encoding='utf8');inputs.append(path)
        seen=set();duplicates=0;initial_batches=0
        with Memory(work) as m:
            for p in inputs:m.ingest(p,p.stem)
            initial_units=m.counts()['units']
            while len(seen)<initial_units//2:
                batch=m.next_batch('initial',limit=8);initial_batches+=1
                for u in batch['units']:
                    duplicates+=int(u['id'] in seen);seen.add(u['id'])
                m.commit(card_batch(batch))
            # A worker obtained a batch but its output was never committed.
            abandoned=m.next_batch('interrupted',limit=8,ttl=30,now=time.time()-60)
            before_restart=len(seen)
        with Memory(work) as m:
            capsule=m.recover();recovery_bytes=len(compact(capsule).encode())
            recovered_abandoned=set();resumed_batches=0
            while True:
                batch=m.next_batch('resumed',limit=8)
                if not batch['units']:break
                resumed_batches+=1
                for u in batch['units']:
                    duplicates+=int(u['id'] in seen);seen.add(u['id'])
                    if u['id'] in {x['id'] for x in abandoned['units']}:recovered_abandoned.add(u['id'])
                m.commit(card_batch(batch))
            complete=m.counts()
            cache_hits=[m.ingest(p,p.stem)['changed'] for p in inputs]
            before_change=m.stats()
            changed=inputs[0];changed.write_text(changed.read_text()+'\n\n新增条件：正式准入仍需独立核验。')
            incremental=m.ingest(changed,changed.stem)
            stale_coverage=m.counts()
            m.backup(base/'snapshot')
            with Memory(base/'snapshot') as restored:backup_ok=restored.integrity()['ok']
        return {'executed_at_utc':datetime.now(timezone.utc).isoformat(),
                'kind':'synthetic scheduling/durability demonstration, no model calls',
                'documents':documents,'initial_units':initial_units,
                'committed_before_restart':before_restart,'uncommitted_units_at_interruption':len(abandoned['units']),
                'uncommitted_units_recovered':len(recovered_abandoned),
                'previously_committed_units_reemitted':duplicates,
                'all_original_units_committed':complete['done']==initial_units,
                'unchanged_sources_reparsed_or_reenqueued':sum(cache_hits),
                'recovery_capsule_utf8_bytes':recovery_bytes,'raw_source_bytes_in_recovery':0,
                'initial_batches':initial_batches,'resumed_batches':resumed_batches,
                'one_source_append':incremental,'pending_after_append':stale_coverage['pending'],
                'portable_backup_verified':backup_ok,'prepared_volume_before_append':before_change,
                'elapsed_seconds':round(time.perf_counter()-start,4),
                'claims_not_made':['No paid-token saving percentage measured.','No LLM factual accuracy or recall test.',
                                   'Crash may require regenerating uncommitted model output.']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--documents',type=int,default=120);p.add_argument('--sections',type=int,default=10);p.add_argument('--report',type=Path);a=p.parse_args()
    if not (1<=a.documents<=500 and 2<=a.sections<=50):p.error('documents 1..500 and sections 2..50')
    r=run(a.documents,a.sections)
    if a.report:write_new(a.report,json_bytes(r))
    print(json.dumps(r,ensure_ascii=False,indent=2))
    return 0 if r['all_original_units_committed'] and r['previously_committed_units_reemitted']==0 and r['portable_backup_verified'] else 1


if __name__=='__main__':raise SystemExit(main())
