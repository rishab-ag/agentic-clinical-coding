"""Input accounting tests; no expected clinical labels."""
import json

from app.ingestion import read_records


def test_txt_and_json_preserve_notes_order_and_metadata(tmp_path):
    path=tmp_path/"note.txt"
    path.write_text(" first line\nsecond line\n")
    records=read_records(path)
    assert len(records)==1 and records[0].note.text==path.read_text()
    path=tmp_path/"notes.json"
    original=[{"note_id":"b","text":"dummy B","metadata":{"keep":True}},{"note_id":"a","text":"dummy A"}]
    path.write_text(json.dumps(original))
    records=read_records(path)
    assert [r.note.note_id for r in records]==["b","a"]
    assert [r.original_record for r in records]==original


def test_jsonl_every_physical_line_and_collision_safe_stable_ids(tmp_path):
    path=tmp_path/"records.jsonl"
    path.write_text('\n'.join([json.dumps({"note_id":"record-000002","text":"dummy"}),
                             json.dumps({"note_id":"record-000002","text":"duplicate"}),
                             "", "{", "12", json.dumps({"text":None}), json.dumps({"text":""})])+"\n")
    records=read_records(path)
    assert len(records)==7
    assert len({r.note.note_id for r in records})==7
    assert [r.note.note_id for r in records]==[r.note.note_id for r in read_records(path)]
    assert records[1].original_record["note_id"]=="record-000002" and records[1].warnings
    assert all(r.errors for r in records[2:])


def test_bad_utf8_isolated_and_bytes_preserved(tmp_path):
    import base64
    path=tmp_path/"notes.jsonl"
    path.write_bytes(b'{"text":"dummy first"}\n\xff\n{"text":"dummy last"}\n')
    records=read_records(path)
    assert len(records)==3 and not records[0].errors and not records[2].errors
    assert base64.b64decode(records[1].original_record["raw_bytes_base64"])==b'\xff\n'


def test_invalid_json_constants_duplicates_and_surrogates_retained(tmp_path):
    path=tmp_path/"notes.jsonl"
    lines=['{"text":"a","text":"b"}','{"text":NaN}','{"text":"\\ud800"}','{"text":"dummy","metadata":1e400}']
    path.write_text("\n".join(lines)+"\n")
    records=read_records(path)
    assert len(records)==4 and all(r.errors for r in records)
    assert [r.original_record.strip() for r in records]==lines


def test_empty_malformed_unsupported_and_missing_files(tmp_path):
    for name, content in [("empty.txt",""),("empty.jsonl",""),("empty.json","[]"),("bad.json","[ {"),("unsupported.csv","dummy")]:
        path=tmp_path/name
        path.write_text(content)
        records=read_records(path)
        assert len(records)==1 and records[0].errors
    assert read_records(tmp_path/"missing.txt")[0].errors==["Input file cannot be read"]


def test_alternative_shapes_are_read_with_warnings_not_errors(tmp_path):
    rows=[("a1","dummy one"),("a2","dummy two")]
    shapes={"alt.jsonl":"\n".join(json.dumps({"id":i,"note":t}) for i,t in rows),
            "array.json":json.dumps([{"encounter_id":i,"clinician":"x","consult_note":t+" longer"} for i,t in rows]),
            "wrapped.json":json.dumps({"notes":[{"note_id":i,"text":t} for i,t in rows]}),
            "strings.json":json.dumps([t for _,t in rows]),
            "table.csv":"id,note\n"+"\n".join(f'{i},"{t}"' for i,t in rows)+"\n",
            "noext":"\n".join(json.dumps({"note_id":i,"text":t}) for i,t in rows),
            "multi.txt":"dummy one\n---\ndummy two\n"}
    for name,content in shapes.items():
        path=tmp_path/name
        path.write_text(content)
        records=read_records(path)
        assert len(records)==2 and not any(r.errors for r in records), name
        assert [r.note.text.strip().replace(" longer","") for r in records]==["dummy one","dummy two"], name
        if name not in ("wrapped.json","strings.json","multi.txt"):
            assert [r.note.note_id for r in records]==["a1","a2"], name
        if name!="strings.json":
            assert all(r.warnings for r in records), name


def test_unnamed_longest_text_field_is_flagged_and_unreadable_objects_still_error(tmp_path):
    path=tmp_path/"odd.jsonl"
    path.write_text(json.dumps({"ref":7,"k":"x","observations":"dummy long free text"})+"\n"+json.dumps({"ref":7,"n":3})+"\n")
    first,second=read_records(path)
    assert first.note.text=="dummy long free text" and "longest text field" in " ".join(first.warnings)
    assert second.errors==["Note record text must be a string"]


def test_plain_text_without_delimiters_or_json_stays_one_note(tmp_path):
    path=tmp_path/"note.dat"
    path.write_text("dummy line one\n\ndummy line two - still the same note\n")
    records=read_records(path)
    assert len(records)==1 and records[0].note.text==path.read_text() and not records[0].errors
    assert "Unrecognised input extension" in records[0].warnings[0]
