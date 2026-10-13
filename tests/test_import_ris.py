from screening_workbench.importers.ris_importer import map_ris_record, parse_ris


# IM-08: standard-style records with repeated AU, KW, tags in varying order.
def test_im08_repeated_au_kw_order_preserved():
    text = (
        "TY  - JOUR\n"
        "AU  - Smith, J\n"
        "AU  - Doe, A\n"
        "TI  - A Study\n"
        "KW  - cancer\n"
        "KW  - therapy\n"
        "PY  - 2020\n"
        "ER  - \n"
    )
    result = parse_ris(text)
    assert len(result.records) == 1
    assert result.skipped == []
    fields = map_ris_record(result.records[0])
    assert fields["authors"] == ["Smith, J", "Doe, A"]
    assert fields["keywords"] == ["cancer", "therapy"]
    assert fields["title"] == "A Study"
    assert fields["year"] == "2020"


def test_ty_is_structural_not_a_canonical_field():
    text = "TY  - JOUR\nTI  - X\nER  - \n"
    result = parse_ris(text)
    fields = map_ris_record(result.records[0])
    assert "TY" not in fields
    assert "type" not in fields


# IM-09: one-space tag delimiter, missing ER, nested TY, orphan line, unknown tag.
def test_im09_one_space_delimiter_accepted():
    text = "TY - JOUR\nTI - One Space\nER - \n"
    result = parse_ris(text)
    assert len(result.records) == 1
    assert map_ris_record(result.records[0])["title"] == "One Space"


def test_im09_missing_er_skips_damaged_record():
    text = "TY  - JOUR\nTI  - Unterminated\n"
    result = parse_ris(text)
    assert result.records == []
    assert len(result.skipped) == 1
    assert result.skipped[0]["reason"] == "missing_record_boundary"


def test_im09_nested_ty_before_er_reports_damage_and_recovers():
    text = (
        "TY  - JOUR\n"
        "TI  - First unterminated\n"
        "TY  - JOUR\n"
        "TI  - Second complete\n"
        "ER  - \n"
    )
    result = parse_ris(text)
    assert len(result.skipped) == 1
    assert result.skipped[0]["reason"] == "missing_record_boundary"
    assert len(result.records) == 1
    assert map_ris_record(result.records[0])["title"] == "Second complete"


def test_im09_unknown_tag_retained_as_raw_but_unmapped():
    text = "TY  - JOUR\nTI  - X\nZZ  - something custom\nER  - \n"
    result = parse_ris(text)
    fields = map_ris_record(result.records[0])
    assert fields["title"] == "X"
    # ZZ has no canonical mapping; raw tag is still present in record.tags.
    assert ("ZZ", "something custom") in result.records[0].tags


def test_im09_orphan_continuation_line_outside_record_is_skipped():
    text = "stray line before anything\nTY  - JOUR\nTI  - X\nER  - \n"
    result = parse_ris(text)
    assert len(result.records) == 1
    assert any(s["reason"] == "malformed_record" for s in result.skipped)


# IM-11: SP+EP combine; SP-only intact; already-ranged SP not doubled.
def test_im11_sp_ep_combine():
    text = "TY  - JOUR\nTI  - X\nSP  - 100\nEP  - 110\nER  - \n"
    fields = map_ris_record(parse_ris(text).records[0])
    assert fields["pages"] == "100-110"


def test_im11_sp_only_intact():
    text = "TY  - JOUR\nTI  - X\nSP  - 100\nER  - \n"
    fields = map_ris_record(parse_ris(text).records[0])
    assert fields["pages"] == "100"


def test_im11_sp_already_ranged_not_doubled():
    text = "TY  - JOUR\nTI  - X\nSP  - 100-120\nEP  - 130\nER  - \n"
    fields = map_ris_record(parse_ris(text).records[0])
    assert fields["pages"] == "100-120"  # EP not appended per spec


# Continuation lines append to the active tag.
def test_continuation_line_appends_to_active_tag():
    text = (
        "TY  - JOUR\n"
        "AB  - First line of abstract\n"
        "continuation of abstract\n"
        "TI  - X\n"
        "ER  - \n"
    )
    fields = map_ris_record(parse_ris(text).records[0])
    assert "First line of abstract" in fields["abstract"]
    assert "continuation of abstract" in fields["abstract"]


def test_multiple_records_in_one_file():
    text = (
        "TY  - JOUR\nTI  - Rec One\nER  - \n"
        "TY  - JOUR\nTI  - Rec Two\nER  - \n"
    )
    result = parse_ris(text)
    assert len(result.records) == 2
    titles = [map_ris_record(r)["title"] for r in result.records]
    assert titles == ["Rec One", "Rec Two"]
