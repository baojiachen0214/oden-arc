#!/usr/bin/env python3
"""Reproducible retrieval-policy ablation with oracle/manual fixture annotations.

Not an LLM answer benchmark. Compares identical reviewed cards using (a) legacy
lexical API, (b) Atlas+aliases without links, (c) Atlas+aliases+critical links.
No model/network calls, no claim about billed-token savings or annotation cost.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from oden_arc.memory import Memory, compact
from oden_arc.atlas import Atlas
from oden_arc.common import json_bytes, write_new
from oden_arc import __version__


def run():
    with tempfile.TemporaryDirectory(prefix='oden-atlas-eval-', dir=Path(tempfile.gettempdir()).resolve()) as tmp:
        base = Path(tmp); work = base/'work'
        Memory.create(work, {'purpose':'decide','question':'Retrieve scoped synthetic evidence, without answering a real-world question.'})
        with Memory(work) as memory:
            atlas = Atlas(memory)
            cards = {}
            records = [
                ('literal','Birch specification records a 64 MB limit.'),
                ('price','Atlas license costs 30 USD per seat in this synthetic fixture.'),
                ('trial','Falcon passed the internal latency trial.'),
                ('caveat','The preceding observation excludes cold starts, networking and production traffic.'),
                ('claim','Cedar measured throughput was 800 records per second.'),
                ('conflict','The independent audit instead records only 320 records per second for the same run.'),
                ('old','ScheduleAlpha was due on 2026-10-23 at 09:00 +08:00.'),
                ('new','The authorized revision moves the deadline to 2026-10-24 at 09:00 +08:00; the prior date is superseded.'),
                ('memory','Helix-memory peak was 210 MiB, process scope only.'),
                ('speed','Helix-speed p95 was 80ms, measured over a different batch.'),
                ('formula','DecayBeta uses y[t]=a*x[t]+(1-a)*y[t-1].'),
                ('condition','The smoothing coefficient is restricted to 0<a<1 and the initialization must be specified.'),
            ]
            for i in range(80):
                records.append((f'noise{i}',f'Unrelated record Z{i:04d}: inventory item stored in warehouse W{i:04d}.'))
            for key, body in records:
                path = base/(key+'.txt'); path.write_text(body, encoding='utf8')
                memory.ingest(path,key)
                batch = memory.next_batch('fixture')
                u = batch['units'][0]
                result = {'chunk_id':u['id'], 'summary':body, 'room':'synthetic', 'keywords':[],
                    'claims':[{'text':body,'kind':'fact','quote':body,'qualifiers':['Synthetic fixture only.']}],
                    'coverage':'read','unresolved':[]}
                memory.commit({'lease':batch['lease'],'goal_rev':batch['goal_rev'],'results':[result]})
                cards[key]=atlas._card(u['id'])
            atlas.annotate({'chunk_id':cards['price']['chunk_id'], 'card_hash':cards['price']['card_hash'],
                            'facets':{'memory_class':'record','aliases':['采购费用'],'scope':'Per seat, USD, synthetic'}})
            for key in ('old','new'):
                atlas.annotate({'chunk_id':cards[key]['chunk_id'],'card_hash':cards[key]['card_hash'],
                    'facets':{'memory_class':'event','time_anchor':'2026-10-23' if key=='old' else '2026-10-24',
                              'event_state':'prior notice' if key=='old' else 'authorized update'}})
            cases = [
                ('literal', ['Birch'], ['literal']),
                ('cross_language_alias', ['采购费用'], ['price']),
                ('qualifier_without_shared_word', ['Falcon'], ['trial','caveat']),
                ('contradictory_evidence', ['Cedar'], ['claim','conflict']),
                ('temporal_revision', ['ScheduleAlpha'], ['old','new']),
                ('multi_facet', ['Helix-memory','Helix-speed'], ['memory','speed']),
                ('formula_preconditions', ['DecayBeta'], ['formula','condition']),
                ('unknown_abstention', ['QuasarUnobserved999'], []),
            ]
            out = {}
            for name, queries, required in cases:
                expected = {cards[k]['chunk_id'] for k in required}
                legacy = memory.cards(' '.join(queries), limit=8, budget=16000)
                no_links = atlas.context({'queries':queries,'max_cards':8,'budget_bytes':16000})
                out[name]={'queries':queries,'required_fixture_keys':required,'expected_count':len(expected),
                    'legacy_lexical':score(legacy,expected),
                    'atlas_aliases_only':score(no_links,expected)}
            for source,target,kind in [('trial','caveat','qualifies'),('claim','conflict','contradicts'),
                                       ('new','old','supersedes'),('formula','condition','requires')]:
                a,b=cards[source],cards[target]
                atlas.link({'source':a['chunk_id'],'source_hash':a['card_hash'],
                            'target':b['chunk_id'],'target_hash':b['card_hash'],
                            'kind':kind,'reason':'Manually supplied same-scope fixture relation.'})
            for name,queries,required in cases:
                expected={cards[k]['chunk_id'] for k in required}
                full=atlas.context({'queries':queries,'max_cards':8,'budget_bytes':16000})
                out[name]['atlas_with_links']=score(full,expected)
            session=atlas.session('actual-window-demo')
            request={'queries':['Falcon'],'mode':'delta','session':session['session'],'epoch':1,'budget_bytes':16000}
            first=atlas.context(request)
            unacked=atlas.context(request)
            atlas.acknowledge(first['packet_id'],session['session'],1)
            delta=atlas.context(request)
            reset=atlas.session(session['session'],reset=True)
            after_reset=atlas.context({**request,'epoch':reset['epoch']})
            low=atlas.context({'queries':['Falcon'],'max_cards':1})
            unaliased=atlas.context({'queries':['商业授权开支']})
            aggregate={}
            for mode in ('legacy_lexical','atlas_aliases_only','atlas_with_links'):
                positive=[x for x in out.values() if x['expected_count']]
                aggregate[mode]={
                    'positive_cases':len(positive),
                    'complete_evidence_bundles':sum(x[mode]['all_required_present'] for x in positive),
                    'required_cards_recalled':sum(x[mode]['required_present'] for x in positive),
                    'required_cards_total':sum(x['expected_count'] for x in positive),
                    'unknown_query_returns_no_evidence':out['unknown_abstention'][mode]['returned_count']==0,
                    'total_payload_bytes_all_cases':sum(x[mode]['payload_bytes'] for x in out.values())}
            return {'version':__version__,'executed_at_utc':datetime.now(timezone.utc).isoformat(),
                'scope':'Synthetic retrieval-policy ablation; oracle/manual aliases and edges; NOT a model answer benchmark.',
                'reviewed_cards':len(cards),'cases':out,'aggregate':aggregate,
                'context_reuse':{'first_packet_bytes':first['budget']['payload_bytes'],
                    'repeated_without_ack_bytes':unacked['budget']['payload_bytes'],
                    'acknowledged_delta_bytes':delta['budget']['payload_bytes'],
                    'delta_full_cards':len(delta['cards']),'delta_held_references':len(delta['held_references']),
                    'after_reset_full_cards':len(after_reset['cards']),
                    'after_reset_bytes':after_reset['budget']['payload_bytes'],
                    'compact_payload_reduction_fraction':round(1-delta['budget']['payload_bytes']/first['budget']['payload_bytes'],6)},
                'unannotated_paraphrase_control':{'query':'商业授权开支',
                    'expected_fixture':'price','expected_evidence_retrieved':cards['price']['chunk_id'] in {c['chunk_id'] for c in unaliased['cards']},
                    'state':unaliased['state'], 'note':'Known limitation: lexical matching cannot guarantee unannotated cross-language paraphrase recall.'},
                'insufficient_budget_behavior':{'max_cards':1,'returned_cards':len(low['cards']),
                    'state':low['state'],'blocked_groups':len(low['blocked_groups'])},
                'limitations':['Fixtures and annotations were authored by the implementer, not held-out user tasks.',
                    'Legacy comparator is the retained lexical API on identical current cards, not a separate executable v0.3 benchmark.',
                    'Annotation creation/verification cost is not measured and can outweigh retrieval savings on small tasks.',
                    'Bytes are actual compact JSON UTF-8 including newline, NOT billed model tokens.',
                    'No model API calls, answer accuracy scores, semantic-embedding benchmark or SOTA comparison.',
                    'Critical closure only covers explicitly recorded relations; unknown contradictions still require review.']}


def score(packet,expected):
    ids={c['chunk_id'] for c in packet['cards']}
    return {'required_present':len(ids&expected),'all_required_present':expected<=ids,
            'returned_count':len(ids),'extraneous_count':len(ids-expected),
            'payload_bytes':len(compact(packet).encode('utf8'))+1}


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path);a=p.parse_args()
    result=run()
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        write_new(a.out,json_bytes(result))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
