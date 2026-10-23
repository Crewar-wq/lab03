from pathlib import Path
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
IDEF=json.loads((ROOT/'model/idef0.json').read_text(encoding='utf-8'))
DATA=json.loads((ROOT/'model/entities.json').read_text(encoding='utf-8'))

class ModelChecks(unittest.TestCase):
    def test_required_levels(self):
        self.assertEqual(IDEF['context']['node'],'A-0')
        self.assertEqual([d['node'] for d in IDEF['diagrams']],['A0','A1','A2','A3','A4'])

    def test_top_level_function_count(self):
        self.assertTrue(3<=len(IDEF['diagrams'][0]['children'])<=6)

    def test_every_function_is_decomposed(self):
        self.assertEqual({c['id'] for c in IDEF['diagrams'][0]['children']},
                         {d['node'] for d in IDEF['diagrams'][1:]})
        for d in IDEF['diagrams'][1:]:self.assertGreaterEqual(len(d['children']),3)

    def test_context_balance(self):
        self.assertEqual(IDEF['context']['interface'],IDEF['diagrams'][0]['interface'])

    def test_all_icom_are_connected(self):
        for d in IDEF['diagrams']:
            codes={code for role in 'IOCM' for code in d['interface'][role]}
            self.assertEqual(codes,set(d['boundary']))
            children={c['id'] for c in d['children']}
            for code,targets in d['boundary'].items():
                self.assertTrue(targets,(d['node'],code))
                self.assertTrue(set(targets)<=children)

    def test_boundary_and_internal_balance_at_each_child(self):
        top=IDEF['diagrams'][0]
        for child in IDEF['diagrams'][1:]:
            expected={role:set() for role in 'IOCM'}
            for code,targets in top['boundary'].items():
                if child['node'] in targets:expected[code[0]].add(top['interface'][code[0]][code])
            for flow in top['flows']:
                if flow['from']==child['node']:expected['O'].add(flow['label'])
                if flow['to']==child['node']:expected[flow['role']].add(flow['label'])
            self.assertEqual(expected,{role:set(child['interface'][role].values()) for role in 'IOCM'},child['node'])

    def test_children_have_control_mechanism_input_and_output(self):
        for d in IDEF['diagrams']:
            for child in d['children']:
                roles={code[0] for code,targets in d['boundary'].items() if child['id'] in targets}
                for flow in d['flows']:
                    if flow['from']==child['id']:roles.add('O')
                    if flow['to']==child['id']:roles.add(flow['role'])
                self.assertEqual(roles,set('IOCM'),(d['node'],child['id']))

    def test_flow_endpoints_and_numbering(self):
        for d in IDEF['diagrams']:
            ids={c['id'] for c in d['children']}
            for i,f in enumerate(d['flows'],1):
                self.assertEqual(f['id'],f'F{i}')
                self.assertTrue(f['from'] in ids and f['to'] in ids)
                self.assertIn(f['role'],['I','C'])
                self.assertNotEqual(f['from'],f['to'])

    def test_native_drawio_has_six_editable_pages(self):
        tree=ET.parse(ROOT/'diagrams/idef0/library_idef0.drawio')
        diagrams=tree.getroot().findall('diagram')
        self.assertEqual([d.get('name') for d in diagrams],['A-0','A0','A1','A2','A3','A4'])
        for d in diagrams:
            self.assertIsNotNone(d.find('mxGraphModel/root'))
            self.assertGreater(len(d.findall('.//mxCell[@edge="1"]')),5)

    def test_svg_exports_contain_icom_names(self):
        for d in [IDEF['context']]+IDEF['diagrams']:
            tree=ET.parse(ROOT/'diagrams/idef0'/f"{d['node']}.svg")
            text=' '.join(tree.getroot().itertext())
            for role in 'IOCM':
                for code,label in d['interface'][role].items():
                    self.assertIn(code,text)
                    self.assertIn(label,' '.join(text.split()))

    def test_generated_sources_are_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            subprocess.run([sys.executable,str(ROOT/'scripts/build_diagrams.py'),'--output',str(out)],check=True,capture_output=True)
            for rel in ['idef0/library_idef0.drawio','er/library_er.puml']+[f'idef0/{n}.svg' for n in ['A-0','A0','A1','A2','A3','A4']]:
                self.assertEqual((out/rel).read_bytes(),(ROOT/'diagrams'/rel).read_bytes(),rel)

    def test_entity_count_and_primary_keys(self):
        self.assertEqual(len(DATA['entities']),16)
        self.assertTrue(12<=len(DATA['entities'])<=20)
        for e in DATA['entities']:
            self.assertGreaterEqual(len(e['attributes']),2)
            self.assertTrue(any('PK' in a['key'] for a in e['attributes']))

    def test_er_source_has_all_entities_and_cardinalities(self):
        source=(ROOT/'diagrams/er/library_er.puml').read_text(encoding='utf-8')
        for e in DATA['entities']:self.assertIn(f'as {e["name"]} {{',source)
        for r in DATA['relations']:
            self.assertIn(f'{r["parent"]} "{r["parent_cardinality"]}" -- "{r["child_cardinality"]}" {r["child"]}',source)
        self.assertEqual(len(DATA['relations']),19)

    def test_er_matches_actual_sqlite_tables_and_columns(self):
        db=sqlite3.connect(':memory:');db.executescript((ROOT/'schema/library.sql').read_text(encoding='utf-8'))
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables,{e['name'] for e in DATA['entities']})
        for e in DATA['entities']:
            columns={r[1]:r for r in db.execute(f'PRAGMA table_info("{e["name"]}")')}
            self.assertEqual(set(columns),{a['name'] for a in e['attributes']})
            for a in e['attributes']:
                self.assertEqual(columns[a['name']][2],a['type'])
                if 'PK' in a['key']:self.assertGreater(columns[a['name']][5],0)
        actual={(e['name'],r[3],r[2]) for e in DATA['entities'] for r in db.execute(f'PRAGMA foreign_key_list("{e["name"]}")')}
        self.assertEqual(actual,{(r['child'],r['foreign_key'],r['parent']) for r in DATA['relations']})

    def test_er_nullable_links_match_cardinality(self):
        for r in DATA['relations']:
            e=next(e for e in DATA['entities'] if e['name']==r['child'])
            a=next(a for a in e['attributes'] if a['name']==r['foreign_key'])
            self.assertEqual(a['nullable'],r['parent_cardinality']=='0..1')

    def test_er_svg_is_successful_render(self):
        tree=ET.parse(ROOT/'diagrams/er/library_er.svg')
        text=' '.join(tree.getroot().itertext())
        self.assertNotIn('Syntax Error',text)
        for e in DATA['entities']:self.assertIn(e['name'],text)
        self.assertIn('0..1',text)
        self.assertIn('1..*',text)

if __name__=='__main__':unittest.main()
