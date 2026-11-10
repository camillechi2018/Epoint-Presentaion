"""Record P036/P110 as fixed chart compositions after source structure review."""
import argparse
import json
from hashlib import sha256
from pathlib import Path

PAGES = {36: 'four_kpi_four_charts_one_table', 110: 'dashboard_four_native_charts'}

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    root = args.library.resolve()
    catpath = root / 'catalog.json'
    cat = json.loads(catpath.read_text(encoding='utf-8-sig'))
    touched = {'catalog.json', 'review/curation-batch-02.json'}
    report_path = root / 'review/curation-batch-02.json'
    report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    for page, composition in PAGES.items():
        name = f'content-blue-{page:03d}'
        entry = next(x for x in cat['layouts'] if x['id'] == name)
        path = root / 'layouts' / name / 'bindings.json'
        binding = json.loads(path.read_text(encoding='utf-8-sig'))
        charts = binding['objects']['charts']
        expected_tables = 1 if page == 36 else 0
        if len(charts) != 4 or len(binding['objects']['tables']) != expected_tables:
            raise ValueError(f'{name}: chart/table structure changed')
        entry['cardinality_policy'] = 'fixed_no_module_add_remove'
        entry['batch_status'] = 'fixed_structure_reviewed_semantic_fill_pending'
        entry['planned_count_tests'] = [4]
        entry['fixed_structure_evidence'] = {
            'native_chart_count': 4, 'native_table_count': expected_tables,
            'reason': 'Chart modules have distinct roles and surrounding labels; removing a module needs a new designed layout.',
        }
        rules_path = root / 'layouts' / name / 'layout_rules.json'
        rules = json.loads(rules_path.read_text(encoding='utf-8-sig'))
        rules.update(cardinality_mode='fixed', source_count=4,
                     supported_counts=[4], verified_counts=[],
                     validation_status='fixed_structure_reviewed_semantic_fill_pending',
                     reflow_status='not_applicable_fixed_composition',
                     composition=composition)
        save(rules_path, rules)
        touched.add(rules_path.relative_to(root).as_posix())
        row = next(x for x in report['layouts'] if x['layout_id'] == name)
        row['planned_count_tests'] = [4]
        row['cardinality_decision'] = 'fixed_no_module_add_remove'
        row['validation_status'] = 'source_structure_reviewed_semantic_fill_pending'
        row['evidence'] = {'native_chart_count':4, 'native_table_count':expected_tables}
    save(catpath, cat)
    save(report_path, report)
    manifest_path = root / 'knowledge-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    for rel in touched:
        manifest['files'][rel] = sha256((root / rel).read_bytes()).hexdigest()
    save(manifest_path, manifest)

if __name__ == '__main__':
    main()
