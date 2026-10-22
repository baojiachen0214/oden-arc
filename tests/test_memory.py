from __future__ import annotations
import concurrent.futures
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from oden_arc.common import SkillError
from oden_arc.memory import Memory, compact, split_text

GOAL = {'question': '比较方案并保留条件', 'purpose': 'decide', 'must_answer': ['哪些条件不能省略？'], 'constraints': ['只用提供的材料']}


def result_for(batch):
    results = []
    for u in batch['units']:
        quote = u['text'][:160]
        r = {'chunk_id': u['id'], 'summary': '保留条件：'+quote[:80], 'room': '比较/边界',
             'keywords': ['性能', '限制', 'conditions'], 'coverage': 'read', 'unresolved': [],
             'claims': [{'text': quote or '视觉材料已检查（测试声明）', 'kind': 'fact' if quote else 'visual_observation',
                         'quote': quote, 'qualifiers': ['测试合成资料，不是现实结论']}]}
        if u['needs_visual']:
            r['visual_check'] = {'status': 'inspected', 'method': 'test fixture only', 'reason': 'Synthetic test declaration'}
        results.append(r)
    return {'lease': batch['lease'], 'goal_rev': batch['goal_rev'], 'results': results}


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base/'workspace'
        Memory.create(self.root, GOAL)
        self.source = self.base/'sample.md'
        self.source.write_text('第一段 性能：10 秒，条件 A。\n\n第二段 条件 B 下不可用。\n\n第三段 输入必须完整。\n\n第四段 仍需要验证。', encoding='utf-8')
        self.m = Memory(self.root)
        self.ingest = self.m.ingest(self.source, 'sample')

    def tearDown(self):
        self.m.db.close()
        self.tmp.cleanup()

    def finish(self):
        while True:
            b = self.m.next_batch('test')
            if not b['units']: break
            self.m.commit(result_for(b))

    def test_exclusive_init(self):
        with self.assertRaises(SkillError): Memory.create(self.root, GOAL)

    def test_unchanged_ingest_and_completed_work_not_reemitted(self):
        self.finish()
        r = self.m.ingest(self.source, 'sample')
        self.assertFalse(r['changed'])
        self.assertEqual(self.m.next_batch('test')['units'], [])
        self.assertEqual(self.m.counts()['done'], 4)

    def test_reopen_recovers_only_unfinished(self):
        b = self.m.next_batch('test', limit=1); self.m.commit(result_for(b))
        with Memory(self.root) as second:
            self.assertEqual(second.recover()['coverage']['done'], 1)
            ids = [u['id'] for u in second.next_batch('second')['units']]
            self.assertNotIn(b['units'][0]['id'], ids)

    def test_append_reuses_unchanged_analysis_but_invalidates_boundary(self):
        self.finish()
        self.source.write_text(self.source.read_text()+'\n\n新一段：不得把估算当测量。')
        r = self.m.ingest(self.source, 'sample')
        self.assertEqual(r['reused_analysis'], 3)
        self.assertEqual(r['new_analysis_tasks'], 2)

    def test_stale_source_commit_rejected(self):
        b = self.m.next_batch('test')
        self.source.write_text('已修改，新版本不能沿用旧结论。')
        self.m.ingest(self.source, 'sample')
        with self.assertRaises(SkillError): self.m.commit(result_for(b))
        self.assertEqual(self.m.counts()['done'], 0)

    def test_goal_change_reuses_bytes_not_old_decisions(self):
        b = self.m.next_batch('test'); self.m.set_goal({**GOAL, 'question': '学习而不是选择'})
        with self.assertRaises(SkillError): self.m.commit(result_for(b))
        self.assertEqual(self.m.cards()['cards'], [])
        self.assertEqual(len(self.m.next_batch('new')['units']), 4)

    def test_idempotent_commit(self):
        b = self.m.next_batch('test'); p = result_for(b)
        self.m.commit(p); replay = self.m.commit(p)
        self.assertTrue(replay['idempotent_replay'])
        self.assertEqual(self.m.counts()['done'], 4)
        p['results'][0]['summary'] = 'changed'
        with self.assertRaises(SkillError): self.m.commit(p)

    def test_batch_commit_atomic_on_invalid_evidence(self):
        b = self.m.next_batch('test'); p = result_for(b)
        p['results'][-1]['claims'][0]['quote'] = 'this does not occur in the source'
        with self.assertRaises(SkillError): self.m.commit(p)
        self.assertEqual(self.m.counts()['done'], 0)
        self.assertEqual(self.m.counts()['leased'], 4)

    def test_subset_cannot_silently_finish_batch(self):
        b = self.m.next_batch('test'); p = result_for(b); p['results'].pop()
        with self.assertRaises(SkillError): self.m.commit(p)

    def test_expired_lease_cannot_commit(self):
        b = self.m.next_batch('test', ttl=30, now=100)
        with self.assertRaises(SkillError): self.m.commit(result_for(b), now=131)
        b2 = self.m.next_batch('second', now=131)
        self.assertEqual({u['id'] for u in b['units']}, {u['id'] for u in b2['units']})

    def test_repeat_failures_block_and_explicit_retry_recovers(self):
        for n in range(3): self.m.next_batch('test', ttl=30, now=100+n*31)
        b = self.m.next_batch('test', now=200)
        self.assertFalse(b['units']); self.assertEqual(self.m.counts()['blocked'], 4)
        cid = self.m.status()['units'][0]['id']; self.m.retry(cid, 'Parser fixed; intentionally retry')
        self.assertEqual(len(self.m.next_batch('test')['units']), 1)

    def test_live_lease_renewal(self):
        b = self.m.next_batch('test')
        self.assertEqual(self.m.renew(b['lease'])['units'], 4)
        with self.assertRaises(SkillError): self.m.retry(b['units'][0]['id'], 'not allowed')

    def test_parallel_workers_do_not_receive_same_unit(self):
        def work(name):
            with Memory(self.root) as m: return m.next_batch(name, limit=2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a, b = list(pool.map(work, ['a','b']))
        self.assertFalse(set(u['id'] for u in a['units']) & set(u['id'] for u in b['units']))
        self.assertEqual(len(a['units'])+len(b['units']), 4)

    def test_budget_failure_does_not_lease(self):
        self.source.write_text('长'*3000); self.m.ingest(self.source, 'sample')
        with self.assertRaises(SkillError): self.m.next_batch('test', budget=1024)
        self.assertEqual(self.m.counts()['pending'], 1)
        self.assertEqual(self.m.counts()['leased'], 0)

    def test_source_deactivation_keeps_history(self):
        b = self.m.next_batch('test')
        self.m.remove_source(self.ingest['source_id'], 'withdrawn')
        with self.assertRaises(SkillError): self.m.commit(result_for(b))
        self.assertEqual(self.m.counts()['units'], 0)
        self.assertEqual(self.m.integrity()['verified_source_snapshots'], 1)

    def test_backup_restore_does_not_need_original_path(self):
        self.finish(); backup = self.base/'backup'; self.m.backup(backup)
        self.source.unlink()
        with Memory(backup) as restored:
            self.assertEqual(restored.counts()['done'], 4)
            restored.export_source(self.ingest['source_id'], self.base/'restored.md')
            self.assertEqual(restored.integrity()['verified_source_snapshots'], 1)
        self.assertIn('条件 B', (self.base/'restored.md').read_text())

    def test_backup_never_overwrites(self):
        self.m.backup(self.base/'backup')
        with self.assertRaises(SkillError): self.m.backup(self.base/'backup')

    def test_same_bytes_share_snapshot_not_semantics(self):
        r = self.m.ingest(self.source, 'another-logical-source')
        self.assertEqual(self.m.counts()['units'], 8)
        self.assertTrue(r['extraction_reused'])
        self.assertEqual(self.m.integrity()['verified_source_snapshots'], 1)

    def test_chinese_lexical_recall(self):
        self.finish(); r = self.m.cards(query='性能', budget=5000)
        self.assertTrue(r['cards']); self.assertLessEqual(len(compact(r).encode()), 5000)
        self.assertNotIn('body', r['cards'][0])

    def test_raw_reread_requires_reason_and_is_recorded(self):
        cid = next(iter(self.m.active()))
        with self.assertRaises(SkillError): self.m.read_chunk(cid, '')
        self.m.read_chunk(cid, '核对条件 A 的否定语句')
        self.assertEqual(self.m.stats()['prepared_payloads']['explicit_raw_read']['calls'], 1)

    def test_partial_review_cannot_claim_finished(self):
        b = self.m.next_batch('test'); p = result_for(b)
        p['results'][0]['coverage'] = 'partial'; p['results'][0]['unresolved'] = ['表格脚注还未检查']
        self.m.commit(p)
        self.assertFalse(self.m.counts()['all_in_scope_units_committed'])
        self.assertEqual(self.m.recover()['attention'][0]['status'], 'partial')

    def test_scope_exclusion_is_not_read(self):
        cid = next(iter(self.m.active())); r = self.m.exclude(cid, '用户明确排除附录')
        self.assertFalse(r['read']); self.assertEqual(self.m.counts()['excluded'], 1)

    def test_checkpoint_does_not_hide_corpus_change(self):
        self.m.checkpoint({'phase': 'read', 'next_actions': ['继续下一批'], 'pins': [next(iter(self.m.active()))]})
        self.assertFalse(self.m.recover()['checkpoint_stale'])
        self.source.write_text('Changed'); self.m.ingest(self.source, 'sample')
        self.assertTrue(self.m.recover()['checkpoint_stale'])

    def test_room_dependency_staleness(self):
        self.finish(); cards = self.m.cards()['cards']
        self.m.room_put({'path': '比较', 'summary': '有限条件下比较', 'dependencies': {c['chunk_id']: c['card_hash'] for c in cards}})
        self.assertFalse(self.m.recover()['room_summaries'][0]['stale'])
        self.source.write_text('Changed'); self.m.ingest(self.source, 'sample')
        r = self.m.recover()['room_summaries'][0]
        self.assertTrue(r['stale']); self.assertIsNone(r['summary'])

    def test_usage_receipts_are_idempotent_and_not_whole_host_total(self):
        r = {'receipt': 'call1', 'provider': 'synthetic-test', 'input_tokens': 100, 'output_tokens': 20, 'cached_input_tokens': 50}
        self.m.usage_add(r); self.m.usage_add(r)
        s = self.m.stats(); self.assertEqual(s['declared_input_tokens'], 100)
        self.assertFalse(s['whole_host_token_total_known'])
        with self.assertRaises(SkillError): self.m.usage_add({**r, 'output_tokens': 21})

    def test_source_symlink_refused(self):
        link = self.base/'link.md'; link.symlink_to(self.source)
        with self.assertRaises(SkillError): self.m.ingest(link)

    def test_corrupt_database_does_not_reset(self):
        bad = self.base/'broken'; bad.mkdir(); (bad/'memory.sqlite3').write_bytes(b'not a database')
        import sqlite3
        with self.assertRaises(sqlite3.DatabaseError): Memory(bad)
        self.assertEqual((bad/'memory.sqlite3').read_bytes(), b'not a database')

    def test_process_dies_mid_transaction_rolls_back(self):
        code = '''import sqlite3,os,sys
c=sqlite3.connect(sys.argv[1],isolation_level=None)
c.execute("BEGIN IMMEDIATE")
c.execute("UPDATE meta SET value='999' WHERE key='goal_rev'")
os._exit(91)
'''
        r = subprocess.run([sys.executable, '-c', code, str(self.root/'memory.sqlite3')])
        self.assertEqual(r.returncode, 91)
        with Memory(self.root) as reopened:
            self.assertEqual(reopened.get('goal_rev'), 1)
            self.assertTrue(reopened.integrity()['ok'])

    def test_external_units_require_version_and_visual_declarations(self):
        p = self.base/'scan.bin'; p.write_bytes(b'opaque synthetic')
        u = [{'text': '', 'locator': {'page': 1}, 'needs_visual': True}]
        with self.assertRaises(SkillError): self.m.ingest(p, 'scan', u)
        r = self.m.ingest(p, 'scan', u, 'human-image-v1')
        self.finish()
        self.assertEqual(self.m.counts()['done'], 5)

    def test_empty_pdf_text_cannot_be_claimed_text_only(self):
        p = self.base/'scan.bin'; p.write_bytes(b'opaque synthetic')
        self.m.ingest(p, 'scan', [{'text': '', 'locator': {'page': 1}, 'needs_visual': True}], 'visual-v1')
        b = self.m.next_batch('test', limit=10); payload = result_for(b)
        for c in payload['results']:
            if 'visual_check' in c: c['visual_check']['status'] = 'not_needed'
        with self.assertRaises(SkillError): self.m.commit(payload)

    def test_chunk_fences_and_large_fragments_are_explicit(self):
        raw = '# Title\n\n```py\na=1\n\nb=2\n```\n\n尾段'
        parts = split_text(raw, {'unit': 1})
        self.assertTrue(any('a=1\n\nb=2' in p['text'] for p in parts))
        large = split_text('x'*9000, {'unit': 1})
        self.assertEqual(len(large), 3)
        self.assertEqual(''.join(p['text'] for p in large), 'x'*9000)
        self.assertEqual(large[0]['fragment']['count'], 3)

    def test_recovery_does_not_emit_raw_corpus(self):
        self.finish(); r = self.m.recover()
        self.assertNotIn('第一段 性能', compact(r))
        self.assertEqual(self.m.stats()['prepared_payloads']['recovery_prepared']['raw_bytes'], 0)

    def test_repeated_paragraph_occurrences_remain_distinct(self):
        self.source.write_text(('相同句子。\n\n')*5)
        self.m.ingest(self.source, 'sample')
        self.assertEqual(self.m.counts()['units'], 5)
        self.assertEqual(len(self.m.active()), 5)

    def test_history_retained_after_explicit_reanalysis(self):
        self.finish(); cid = next(iter(self.m.active()))
        before = self.m.db.execute('SELECT COUNT(*) FROM card_history').fetchone()[0]
        self.m.retry(cid, '核对歧义')
        self.assertEqual(self.m.db.execute('SELECT COUNT(*) FROM card_history').fetchone()[0], before)
        self.assertEqual(self.m.counts()['pending'], 1)

    def test_card_corruption_is_reported_without_reset(self):
        self.finish()
        self.m.db.execute("UPDATE tasks SET result='{}' WHERE result IS NOT NULL")
        with self.assertRaises(SkillError): self.m.integrity()
        self.assertEqual(self.m.counts()['done'], 4)


if __name__ == '__main__': unittest.main()
