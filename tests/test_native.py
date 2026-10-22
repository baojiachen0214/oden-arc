from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from oden_arc.common import SkillError, digest, load_json, number, safe_link, safe_relative
from oden_arc.native import compile_plan, validate_delivery, validate_native
from oden_arc.plan import check_plan
from oden_arc.review import review_plan

ROOT = Path(__file__).resolve().parents[1]


def simple_plan():
    return {'plan_version': '1.0', 'document_id': 'test-doc', 'title': '合成测试',
            'goal': {'purpose': 'learn', 'question': '理解条件'},
            'sources': [], 'assets': [],
            'nodes': [{'id': 'root', 'parent_id': None, 'label': '条件必须保留', 'role': 'root', 'support': 'structure'},
                      {'id': 'n1', 'parent_id': 'root', 'label': '核心公式', 'role': 'mechanism', 'support': 'structure',
                       'body': [{'kind': 'equation', 'latex': r'y_t=\alpha x_t+(1-\alpha)y_{t-1}'}]},
                      {'id': 'n2', 'parent_id': 'root', 'label': '适用边界', 'role': 'constraint', 'support': 'structure'}],
            'cross_links': [{'id': 'link1', 'from': 'n1', 'to': 'n2', 'label': '受此条件限制'}]}


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name); self.plan = simple_plan()
    def tearDown(self): self.tmp.cleanup()
    def compile(self):
        return compile_plan(self.plan, self.base, self.base/'delivery')
    def test_editable_formula_and_link_label(self):
        r = self.compile()['native']
        self.assertEqual(r['editable_equations'], 1); self.assertEqual(r['canvas_links'], 1)
        self.assertEqual(r['semantic_nodes'], 3); self.assertEqual(r['native_nodes'], 4)
        self.assertFalse(r['native_runtime_observed'])
    def test_all_four_historical_plans_recompile(self):
        for folder in sorted((ROOT/'examples'/name for name in ('math','decision','action','crop'))):
            with self.subTest(folder=folder.name):
                p = load_json(folder/'plan.json')
                r = compile_plan(p, folder, self.base/folder.name, strict_review=True)
                self.assertTrue(r['ok']); self.assertFalse(r['semantic_truth_verified_by_compiler'])
    def test_relocated_delivery_independent_of_input_paths(self):
        source = ROOT/'examples/math'
        compile_plan(load_json(source/'plan.json'), source, self.base/'initial')
        shutil.move(str(self.base/'initial'), str(self.base/'moved'))
        self.assertTrue(validate_delivery(self.base/'moved')['ok'])
    def test_historical_crop_receipt_preserved_with_portable_resolution(self):
        source = ROOT/'examples/crop'
        original = load_json(source/'plan.json')
        compile_plan(original, source, self.base/'crop')
        copied = load_json(self.base/'crop/plan.json')['audit']['transformations'][0]
        self.assertEqual(copied['record'], original['audit']['transformations'][0]['record'])
        resolution = copied['source_resolution']
        self.assertEqual(resolution['scope'], 'delivery-relative')
        self.assertTrue(resolution['acquisition_path_is_historical'])
        raw = safe_relative(self.base/'crop', resolution['uri']).read_bytes()
        self.assertEqual(digest(raw), resolution['sha256'])
        shutil.move(str(self.base/'crop'), str(self.base/'crop-moved'))
        self.assertTrue(validate_delivery(self.base/'crop-moved')['ok'])
    def test_exclusive_output(self):
        self.compile(); before = (self.base/'delivery/plan.json').read_bytes()
        with self.assertRaises(SkillError): self.compile()
        self.assertEqual(before, (self.base/'delivery/plan.json').read_bytes())
    def test_hash_tampering_detected(self):
        self.compile(); f = self.base/'delivery/plan.json'; f.write_bytes(f.read_bytes()+b' ')
        with self.assertRaises(SkillError): validate_delivery(self.base/'delivery')
    def test_unknown_file_in_delivery_detected(self):
        self.compile(); (self.base/'delivery/unlisted.txt').write_text('added')
        with self.assertRaises(SkillError): validate_delivery(self.base/'delivery')
    def test_incomplete_marker_rejected(self):
        self.compile(); (self.base/'delivery/.incomplete').write_text('pending')
        with self.assertRaises(SkillError): validate_delivery(self.base/'delivery')
    def test_symlink_resource_rejected(self):
        (self.base/'data.txt').write_text('text'); (self.base/'link.txt').symlink_to(self.base/'data.txt')
        self.plan['assets'] = [{'id':'a','path':'link.txt','kind':'text'}]
        with self.assertRaises(SkillError): self.compile()
    def test_path_escape_rejected(self):
        for p in ('../private.txt','/etc/passwd','dir/../../x','C:\\test','file:///x'):
            with self.subTest(path=p), self.assertRaises(SkillError): safe_relative(self.base,p)
    def test_duplicate_node_rejected(self):
        self.plan['nodes'].append(deepcopy(self.plan['nodes'][0]))
        with self.assertRaises(SkillError): self.compile()
    def test_disconnected_cycle_rejected(self):
        self.plan['nodes'][1]['parent_id']='n2'; self.plan['nodes'][2]['parent_id']='n1'
        with self.assertRaises(SkillError): self.compile()
    def test_multiple_roots_rejected(self):
        self.plan['nodes'][1]['parent_id']=None
        with self.assertRaises(SkillError): self.compile()
    def test_missing_endpoint_rejected(self):
        self.plan['cross_links'][0]['to']='absent'
        with self.assertRaises(SkillError): self.compile()
    def test_invalid_numeric_types_are_expected_errors(self):
        for v in (True, None, '2', [], {}, float('nan'), float('inf'), 10**1000):
            with self.subTest(value=type(v).__name__), self.assertRaises(SkillError): number(v,'test',0,10)
    def test_unknown_plan_fields_rejected(self):
        self.plan['typo']=1
        with self.assertRaises(SkillError): self.compile()
    def test_resource_body_mix_rejected(self):
        (self.base/'data.txt').write_text('source'); self.plan['assets']=[{'id':'a','path':'data.txt','kind':'text'}]
        self.plan['nodes'][1]['asset_id']='a'
        with self.assertRaises(SkillError): self.compile()
    def test_resource_deduplication(self):
        (self.base/'data.txt').write_text('same bytes')
        self.plan['assets']=[{'id':i,'path':'data.txt','kind':'text'} for i in ('a','b')]
        self.plan['nodes'][0]['attachment_ids']=['a','b']
        r = self.compile()['native']; self.assertEqual(r['physical_assets'],1); self.assertEqual(r['aliases'],1)
    def test_changed_source_hash_rejected(self):
        (self.base/'source.txt').write_text('actual')
        self.plan['sources']=[{'id':'s','title':'s','kind':'text','status':'read','coverage':'all','uri':'source.txt','sha256':'0'*64}]
        with self.assertRaises(SkillError): self.compile()
    def test_unsafe_links(self):
        for link in ('javascript:alert(1)','file:///secret','https://user:pass@host/a','https://[bad', '//example.com'):
            with self.subTest(link=link), self.assertRaises(SkillError): safe_link(link)
    def test_markdown_remote_media_rejected(self):
        for payload in ('![x](https://example.com/x.png)', '![x][r]\n[r]: https://example.com/x.png', '<video src="https://example.com/v">'):
            (self.base/'data.md').write_text(payload)
            self.plan['assets']=[{'id':'a','path':'data.md','kind':'text'}]; self.plan['nodes'][0]['attachment_ids']=['a']
            with self.subTest(payload=payload), self.assertRaises(SkillError): self.compile()
    def test_unread_source_not_claimed_verified(self):
        p = ROOT/'examples/math/plan.json'; plan = load_json(p)
        plan['audit']['coverage']=[]
        r = review_plan(plan); self.assertTrue(r['errors']); self.assertFalse(r['semantic_truth_verified_by_checker'])
    def test_strict_requires_review(self):
        with self.assertRaises(SkillError): compile_plan(self.plan,self.base,self.base/'strict',strict_review=True)
    def test_native_parent_tamper_detected(self):
        self.compile(); p=self.base/'delivery/map.odenmap/map.json'; raw=load_json(p)
        raw['nodes'][1]['parentID']='missing'; p.write_text(json.dumps(raw))
        with self.assertRaises(SkillError): validate_native(p.parent)
    def test_unsupported_future_schema_rejected_without_downgrade(self):
        self.compile(); p=self.base/'delivery/map.odenmap/map.json'; raw=load_json(p)
        raw['schemaVersion']=999; p.write_text(json.dumps(raw))
        with self.assertRaises(SkillError): validate_native(p.parent)
    def test_duplicate_json_keys_not_silently_overwritten(self):
        p=self.base/'bad.json'; p.write_text('{"a":1,"a":2}')
        with self.assertRaises(SkillError): load_json(p)
    def test_wrong_node_types_are_expected_errors(self):
        for value in (None, 1, True, 'node', []):
            p = simple_plan(); p['nodes'][0]=value
            with self.subTest(value=value), self.assertRaises(SkillError): check_plan(p,self.base)


if __name__ == '__main__': unittest.main()
