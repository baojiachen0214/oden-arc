import ast
import json
from pathlib import Path
import re
import tempfile
import unittest
from oden_arc.common import load_json, SkillError
from oden_arc.memory import Memory, check_goal
from oden_arc.plan import check_plan
from test_memory import result_for

ROOT=Path(__file__).resolve().parents[1]

class ReleaseTests(unittest.TestCase):
    def test_required_source_and_prompt_files_exist(self):
        for name in ('SKILL.md','README.md','src/oden_arc/native.py','src/oden_arc/memory.py','src/oden_arc/media.py',
                     'scripts/arc.py','scripts/arc_memory.py','scripts/arc_assets.py',
                     'prompts/01-intake.md','prompts/02-extract-batch.md','prompts/03-reconcile.md',
                     'prompts/04-compose.md','prompts/05-review.md','prompts/06-resume.md',
                     'schemas/map-plan.schema.json','schemas/memory-result.schema.json',
                     'src/oden_arc/atlas.py','src/oden_arc/evidence_gate.py','scripts/demo_atlas.py',
                     'references/context-atlas.md','docs/design/research.md'):
            with self.subTest(name=name):self.assertTrue((ROOT/name).is_file());self.assertGreater((ROOT/name).stat().st_size,50)
    def test_source_zip_roundtrip_preserves_empty_native_assets_directory(self):
        import importlib.util
        import zipfile
        from oden_arc.native import compile_plan, validate_delivery
        from oden_arc.common import json_bytes
        spec=importlib.util.spec_from_file_location('oden_repack',ROOT/'scripts/repack.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);tree=base/'source';tree.mkdir()
            compile_plan(load_json(ROOT/'assets/templates/minimal-plan.json'),ROOT/'assets/templates',tree/'examples/generated-fixture/minimal')
            manifest=tree/'FILE_MANIFEST.json';manifest.write_bytes(json_bytes({'test':True}))
            selected=module.files(tree);dirs=module.directories(tree)
            self.assertIn('examples/generated-fixture/minimal/map.odenmap/Assets',dirs)
            archive=base/'test.zip';module.write_archive(tree,selected,dirs,manifest,archive)
            with zipfile.ZipFile(archive) as z:z.extractall(base/'unpacked')
            delivery=base/'unpacked/oden-arc/examples/generated-fixture/minimal'
            self.assertTrue((delivery/'map.odenmap/Assets').is_dir())
            self.assertTrue(validate_delivery(delivery)['ok'])

    def test_skill_frontmatter_and_progressive_links(self):
        s=(ROOT/'SKILL.md').read_text()
        self.assertTrue(s.startswith('---\nname: oden-arc\n'))
        self.assertLess(len(s.splitlines()),500)
        for rel in re.findall(r'\]\(([^)]+)\)',s):
            with self.subTest(ref=rel):self.assertTrue((ROOT/rel).is_file())
    def test_all_python_source_parses(self):
        for file in ROOT.rglob('*.py'):
            if '__pycache__' in file.parts:continue
            with self.subTest(file=file.name):ast.parse(file.read_text(),filename=str(file))
    def test_minimal_template_compiler_contract(self):
        p=ROOT/'assets/templates/minimal-plan.json'
        self.assertEqual(len(check_plan(load_json(p),p.parent).levels),3)
    def test_json_schemas_accept_all_four_input_examples(self):
        try:import jsonschema
        except ImportError:self.skipTest('Optional jsonschema not installed; core validator remains authoritative')
        schema=load_json(ROOT/'schemas/map-plan.schema.json')
        jsonschema.Draft202012Validator.check_schema(schema)
        for folder in (ROOT/'examples'/name for name in ('math','decision','action','crop')):
            with self.subTest(folder=folder.name):jsonschema.validate(load_json(folder/'plan.json'),schema)
    def test_new_context_and_binding_schemas_are_valid(self):
        try: import jsonschema
        except ImportError: self.skipTest('Optional jsonschema not installed')
        for name in ('context-request','memory-bindings'):
            schema=load_json(ROOT/'schemas'/(name+'.schema.json'))
            jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(load_json(ROOT/'assets/templates/context-request.json'),
                            load_json(ROOT/'schemas/context-request.schema.json'))

    def test_unexpected_goal_types_fail_cleanly(self):
        for v in (None,[],{},True,1):
            with self.subTest(value=v),self.assertRaises(SkillError):check_goal({'question':'q','purpose':v})
    def test_memory_card_type_mutations_fail_without_committing(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);work=root/'w';source=root/'x.txt';source.write_text('Known fact under condition A.')
            Memory.create(work,{'question':'q','purpose':'learn'})
            with Memory(work) as m:
                m.ingest(source);b=m.next_batch('w');good=result_for(b)
                for bad in (None,[],{},False,3):
                    p=json.loads(json.dumps(good));p['results'][0]['coverage']=bad
                    with self.subTest(value=bad),self.assertRaises(SkillError):m.commit(p)
                self.assertEqual(m.counts()['done'],0);self.assertTrue(m.commit(good)['ok'])
    def test_queue_empty_does_not_mark_leased_work_complete(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);work=root/'w';source=root/'x.txt';source.write_text('Pending evidence')
            Memory.create(work,{'question':'q','purpose':'learn'})
            with Memory(work) as m:
                m.ingest(source);m.next_batch('worker1')
                q=m.next_batch('worker2');self.assertEqual(q['units'],[])
                self.assertTrue(q['empty_queue_is_not_completion'])
                self.assertFalse(m.counts()['all_in_scope_units_committed'])
    def test_search_index_has_deletion_key_index(self):
        with tempfile.TemporaryDirectory() as t:
            w=Path(t)/'w';Memory.create(w,{'question':'q'})
            with Memory(w) as m:
                plans=list(m.db.execute('EXPLAIN QUERY PLAN DELETE FROM search_terms WHERE chunk_id=? AND goal_rev=?',('x',1)))
                self.assertTrue(any('search_by_chunk' in r['detail'] for r in plans))

if __name__=='__main__':unittest.main()
