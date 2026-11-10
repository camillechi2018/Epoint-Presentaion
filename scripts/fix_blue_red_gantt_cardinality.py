"""Record source row cardinality for the P191 Gantt/table composition."""
import argparse,json
from pathlib import Path
from hashlib import sha256
from pptx import Presentation

def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);a=ap.parse_args()
    root=a.library.resolve();name='content-blue-191';base=root/'layouts'/name
    for theme in ('blue','red'):
        src=Presentation(root/'sources'/f'{theme}.pptx').slides[190]
        tables=[s.table for s in src.shapes if s.has_table]
        if len(tables)!=1 or len(tables[0].rows)!=7 or len(tables[0].columns)!=13:raise ValueError(f'{theme} source changed')
    touched={'catalog.json','review/curation-batch-02.json'}
    cp=root/'catalog.json';cat=json.loads(cp.read_text(encoding='utf-8-sig'))
    entry=next(e for e in cat['layouts'] if e['id']==name)
    entry.update(cardinality_policy='fixed_no_row_add_remove',batch_status='fixed_structure_reviewed_semantic_fill_pending',planned_count_tests=[6],
                 fixed_structure_evidence={'native_table_rows':7,'header_rows':1,'data_rows':6,'columns':13,
                    'reason':'Timeline bars and date labels are separate native shapes aligned to six table rows.'})
    dump(cp,cat)
    rp=base/'layout_rules.json';rule=json.loads(rp.read_text(encoding='utf-8-sig'))
    rule.update(cardinality_mode='fixed',source_count=6,supported_counts=[6],verified_counts=[],
                validation_status='fixed_structure_reviewed_semantic_fill_pending',reflow_status='not_applicable_fixed_gantt')
    dump(rp,rule);touched.add(rp.relative_to(root).as_posix())
    review=root/'review/curation-batch-02.json';record=json.loads(review.read_text(encoding='utf-8-sig'))
    row=next(x for x in record['layouts'] if x['layout_id']==name)
    row.update(planned_count_tests=[6],cardinality_decision='fixed_no_row_add_remove',
               validation_status='source_structure_reviewed_semantic_fill_pending',
               evidence={'native_table_rows':7,'header_rows':1,'data_rows':6,'columns':13})
    dump(review,record)
    manifest=root/'knowledge-manifest.json';m=json.loads(manifest.read_text(encoding='utf-8-sig'))
    for rel in touched:m['files'][rel]=sha256((root/rel).read_bytes()).hexdigest()
    dump(manifest,m)
if __name__=='__main__':main()
