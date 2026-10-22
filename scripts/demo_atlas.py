#!/usr/bin/env python3
"""Fully local synthetic demonstration, including a live evidence-bound map.

Writes to a NEW user-selected directory. Includes private-style memory snapshots
of SYNTHETIC text only. Does not run a model, renderer or the ODEN application.
"""
from datetime import datetime, timezone
import argparse
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from oden_arc import __version__
from oden_arc.atlas import Atlas
from oden_arc.memory import Memory
from oden_arc.native import compile_plan, validate_delivery
from oden_arc.common import exclusive_directory, json_bytes, write_new


def run(output:Path):
    with exclusive_directory(output) as out:
        originals=out/'originals';originals.mkdir()
        work=out/'work'
        Memory.create(work,{'purpose':'decide','question':'这项合成测试能否说明冷启动达标？'})
        rows=[('trial','Falcon 在热启动合成测试中达到目标延迟。'),
              ('condition','该记录没有测量冷启动、网络耗时或生产负载，不能据此认定整体达标。'),
              ('irrelevant','另一份合成库存记录有17箱物品，入库日期为2026-10-20。')]
        cards={}
        with Memory(work) as memory:
            atlas=Atlas(memory)
            for key,body in rows:
                p=originals/(key+'.txt');p.write_text(body,encoding='utf8')
                memory.ingest(p,key)
                b=memory.next_batch('synthetic-fixture');u=b['units'][0]
                card={'chunk_id':u['id'],'summary':body,'room':'示例/准入','keywords':[],
                      'claims':[{'text':body,'kind':'fact','quote':body,'qualifiers':['纯合成示例，非实际产品性能']}],
                      'coverage':'read','unresolved':[]}
                memory.commit({'lease':b['lease'],'goal_rev':b['goal_rev'],'results':[card]})
                cards[key]=atlas._card(u['id'])
            a,b=cards['trial'],cards['condition']
            atlas.annotate({'chunk_id':a['chunk_id'],'card_hash':a['card_hash'],
                'facets':{'memory_class':'record','aliases':['启动表现'],'scope':'仅热启动；合成记录'}})
            atlas.link({'source':a['chunk_id'],'source_hash':a['card_hash'],
                        'target':b['chunk_id'],'target_hash':b['card_hash'],
                        'kind':'qualifies','reason':'明确限定同一记录的测试范围，结论不可去掉限定。'})
            atlas.session('demo-context')
            request={'queries':['启动表现'],'mode':'delta','session':'demo-context','epoch':1}
            first=atlas.context(request)
            # This deterministic host retains first in memory; it is NOT an AI-read assertion.
            atlas.acknowledge(first['packet_id'],'demo-context',1)
            delta=atlas.context(request)
            atlas.session('demo-context',reset=True)
            reset=atlas.context({**request,'epoch':2})
            plan={'plan_version':'1.0','document_id':'context-atlas-demo','title':'冷启动仍待验证（合成）',
                  'goal':{'purpose':'decide','question':'这项合成测试能否说明冷启动达标？'},
                  'sources':[],'assets':[],'cross_links':[],
                  'nodes':[{'id':'root','parent_id':None,'label':'只能支持热启动结论，冷启动仍未知',
                            'role':'root','support':'structure'},
                           {'id':'decision','parent_id':'root','label':'热启动达到合成目标；不覆盖冷启动、网络与生产负载',
                            'role':'conclusion','support':'inference','source_refs':[]},
                           {'id':'action','parent_id':'root','label':'下一步：补测缺失场景，再判断是否达标',
                            'role':'action','support':'structure'}],
                  'extensions':{'memory_bindings':{'version':'1.0','workspace_id':memory.get('workspace_id'),
                                  'goal_rev':memory.get('goal_rev'),'nodes':{'decision':[]}}}}
            for i,key in enumerate(('trial','condition')):
                c=cards[key];sid=f's{i}'
                plan['sources'].append({'id':sid,'title':key,'kind':'text','status':'read',
                    'coverage':'全部合成文本；不是AI语义理解实测','sha256':c['source_sha256'],
                    'uri':f'originals/{key}.txt'})
                plan['nodes'][1]['source_refs'].append({'source_id':sid,'locator':'全文','quote':c['summary']})
                plan['extensions']['memory_bindings']['nodes']['decision'].append({
                    'chunk_id':c['chunk_id'],'card_hash':c['card_hash'],'plan_source_id':sid,'placement':'label'})
            write_new(out/'plan.json',json_bytes(plan))
            write_new(out/'context-full.json',json_bytes(first))
            write_new(out/'context-delta.json',json_bytes(delta))
            write_new(out/'context-after-reset.json',json_bytes(reset))
        compiled=compile_plan(plan,out,out/'delivery',memory_workspace=work)
        verification=validate_delivery(out/'delivery')
        report={'version':__version__,'executed_at_utc':datetime.now(timezone.utc).isoformat(),
                'synthetic':True,'model_api_calls':0,'raw_cards':len(cards),
                'retrieved_cards':len(first['cards']),'delta_cards':len(delta['cards']),
                'delta_references':len(delta['held_references']),'after_reset_cards':len(reset['cards']),
                'compile_ok':compiled['ok'],'delivery_valid':verification['ok'],
                'native_runtime_observed':False,'semantic_truth_verified_by_code':False,
                'note':'One conclusion node intentionally binds two cards; the map is not a card dump.'}
        write_new(out/'demonstration.json',json_bytes(report))
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    print(json.dumps(run(a.out),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
