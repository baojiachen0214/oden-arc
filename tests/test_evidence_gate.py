"""Live map/evidence gate tests; no claim about human semantic review."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from oden_arc.common import SkillError, load_json
from oden_arc.memory import Memory
from oden_arc.atlas import Atlas
from oden_arc.native import compile_plan, validate_delivery


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base/'memory'
        Memory.create(self.root, {'question': 'Which scope is supported?', 'purpose': 'decide'})
        self.m = Memory(self.root); self.a = Atlas(self.m)
        self.cards = []
        for name, body in [('trial', 'Falcon passed the warm-start trial.'),
                           ('scope', 'Cold starts and network time were not measured.')]:
            p = self.base/(name+'.txt'); p.write_text(body, encoding='utf8')
            self.m.ingest(p, name)
            batch = self.m.next_batch('test')
            u = batch['units'][0]
            card = {'chunk_id': u['id'], 'summary': body, 'room': 'Decision', 'keywords': [],
                    'claims': [{'kind': 'fact', 'text': body, 'quote': body, 'qualifiers': []}],
                    'coverage': 'read', 'unresolved': []}
            self.m.commit({'lease': batch['lease'], 'goal_rev': batch['goal_rev'], 'results': [card]})
            self.cards.append(self.a._card(u['id']))
        a,b = self.cards
        self.a.link({'source': a['chunk_id'], 'source_hash': a['card_hash'],
                     'target': b['chunk_id'], 'target_hash': b['card_hash'],
                     'kind': 'qualifies', 'reason': 'Same trial, missing cold-start coverage.'})
        self.plan = {'plan_version': '1.0', 'document_id': 'bound-plan', 'title': 'Warm-start only',
                     'goal': {'purpose': 'decide', 'question': 'Which scope is supported?'},
                     'sources': [], 'assets': [], 'cross_links': [],
                     'nodes': [{'id': 'root', 'parent_id': None, 'label': 'Warm-start only',
                                'role': 'root', 'support': 'structure'}],
                     'extensions': {'memory_bindings': {'version': '1.0',
                          'workspace_id': self.m.get('workspace_id'), 'goal_rev': 1, 'nodes': {}}}}
        for i, c in enumerate(self.cards):
            sid,nid = f's{i}',f'n{i}'
            self.plan['sources'].append({'id':sid, 'title':c['source_title'], 'kind':'text',
                'status':'read', 'coverage':'all synthetic text', 'sha256':c['source_sha256']})
            self.plan['nodes'].append({'id':nid, 'parent_id':'root', 'label':c['summary'],
                'role':'evidence', 'support':'fact', 'source_refs':[{'source_id':sid,'locator':'whole file'}]})
            self.plan['extensions']['memory_bindings']['nodes'][nid] = [{'chunk_id':c['chunk_id'],
                'card_hash':c['card_hash'], 'plan_source_id':sid, 'placement':'label'}]

    def tearDown(self):
        self.m.db.close(); self.tmp.cleanup()

    def emit(self, name='delivery'):
        return compile_plan(self.plan, self.base, self.base/name, memory_workspace=self.root)

    def test_bound_plan_compiles_with_auditable_snapshot(self):
        self.assertTrue(self.emit()['ok'])
        audit = load_json(self.base/'delivery/evidence-audit.json')
        self.assertEqual(audit['bound_cards'], 2)
        self.assertEqual(audit['critical_relations_checked'], 1)
        self.assertFalse(audit['semantic_truth_verified'])
        self.assertTrue(validate_delivery(self.base/'delivery')['ok'])

    def test_malformed_extensions_fail_cleanly(self):
        for value in (None, [], False, 3, 'bad'):
            self.plan['extensions'] = value
            with self.subTest(value=value), self.assertRaises(SkillError): self.emit()

    def test_binding_requires_explicit_workspace(self):
        with self.assertRaises(SkillError): compile_plan(self.plan, self.base, self.base/'bad')

    def test_wrong_workspace_rejected(self):
        self.plan['extensions']['memory_bindings']['workspace_id'] = 'another'
        with self.assertRaises(SkillError): self.emit()
        self.assertFalse((self.base/'delivery').exists())

    def test_stale_goal_rejected(self):
        self.plan['extensions']['memory_bindings']['goal_rev'] = 0
        with self.assertRaises(SkillError): self.emit()

    def test_stale_card_hash_rejected(self):
        self.plan['extensions']['memory_bindings']['nodes']['n0'][0]['card_hash'] = '0'*64
        with self.assertRaises(SkillError): self.emit()

    def test_source_hash_must_match_live_snapshot(self):
        self.plan['sources'][0]['sha256'] = '0'*64
        with self.assertRaises(SkillError): self.emit()

    def test_source_reference_required(self):
        self.plan['nodes'][1]['support'] = 'structure'
        self.plan['nodes'][1]['source_refs'] = []
        with self.assertRaises(SkillError): self.emit()

    def test_missing_binding_for_fact_rejected(self):
        del self.plan['extensions']['memory_bindings']['nodes']['n1']
        with self.assertRaises(SkillError): self.emit()

    def test_missing_critical_counterpart_rejected(self):
        self.plan['nodes'] = self.plan['nodes'][:-1]
        del self.plan['extensions']['memory_bindings']['nodes']['n1']
        with self.assertRaises(SkillError): self.emit()

    def test_qualifier_hidden_in_note_is_rejected(self):
        self.plan['nodes'][2]['note'] = self.plan['nodes'][2]['label']
        self.plan['extensions']['memory_bindings']['nodes']['n1'][0]['placement'] = 'note'
        with self.assertRaises(SkillError): self.emit()

    def test_qualifier_hidden_under_fold_is_rejected(self):
        self.plan['nodes'][1]['collapsed'] = True
        self.plan['nodes'][2]['parent_id'] = 'n0'
        with self.assertRaises(SkillError): self.emit()

    def test_many_cards_can_bind_one_visible_synthesis(self):
        refs = self.plan['extensions']['memory_bindings']['nodes']
        refs['n0'] += refs.pop('n1')
        self.plan['nodes'][1]['source_refs'] += self.plan['nodes'][2]['source_refs']
        self.plan['nodes'][1]['label'] = 'Warm-start trial passed; cold-start and network costs remain unknown'
        self.plan['nodes'] = self.plan['nodes'][:-1]
        self.assertTrue(self.emit()['ok'])

    def test_unsupported_placement_and_missing_body_rejected(self):
        for value in ('invented', 'body', 'resource', 'note'):
            self.plan['extensions']['memory_bindings']['nodes']['n0'][0]['placement'] = value
            with self.subTest(value=value), self.assertRaises(SkillError): self.emit()

    def test_withdrawn_counterevidence_blocks_export(self):
        self.m.remove_source(self.cards[1]['source_id'], 'retracted')
        with self.assertRaises(SkillError): self.emit()

    def test_snapshot_delivery_remains_readable_after_source_update(self):
        self.emit()
        self.m.remove_source(self.cards[0]['source_id'], 'new source expected')
        # Historical artifact validity is different from current evidence validity.
        self.assertTrue(validate_delivery(self.base/'delivery')['ok'])
        with self.assertRaises(SkillError): self.emit('new-delivery')

    def test_audit_tamper_detected(self):
        self.emit()
        p = self.base/'delivery/evidence-audit.json'
        p.write_text('{}')
        with self.assertRaises(SkillError): validate_delivery(self.base/'delivery')

    def test_plain_plan_cannot_silently_ignore_workspace(self):
        del self.plan['extensions']
        with self.assertRaises(SkillError): self.emit()

    def test_unread_source_declaration_conflicts_with_binding(self):
        self.plan['sources'][0]['status'] = 'unread'
        with self.assertRaises(SkillError): self.emit()


if __name__ == '__main__': unittest.main()
