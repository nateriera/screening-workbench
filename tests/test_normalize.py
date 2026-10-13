from screening_workbench.normalize import (
    extract_years,
    levenshtein,
    normalize_doi,
    normalize_first_author,
    normalize_title,
    title_similarity,
)


def test_doi_resolver_prefix_and_case():
    assert normalize_doi("https://doi.org/10.1136/BMJ.N71") == "10.1136/bmj.n71"
    assert normalize_doi("doi:10.1136/bmj.n71") == "10.1136/bmj.n71"
    assert normalize_doi("  10.1136/bmj.n71 .") == "10.1136/bmj.n71"


def test_doi_dx_prefix():
    assert normalize_doi("http://dx.doi.org/10.1000/xyz123") == "10.1000/xyz123"


def test_doi_missing():
    assert normalize_doi(None) is None
    assert normalize_doi("") is None
    assert normalize_doi("   ") is None


def test_title_unicode_case_punct_whitespace():
    a = normalize_title("The Impact of  COVID-19: A Review!")
    b = normalize_title("the impact of covid 19 a review")
    assert a == b


def test_title_nfkc_compatibility_form():
    # fullwidth vs ascii digits/letters normalize the same under NFKC+casefold
    a = normalize_title("COVID-19 Review")
    b = normalize_title("ＣＯＶＩＤ-19 Review")
    assert a == b


def test_title_empty_never_matches():
    assert normalize_title("") is None
    assert normalize_title("   ") is None
    assert normalize_title(None) is None


def test_title_diacritics_preserved_not_folded():
    a = normalize_title("Café study")
    b = normalize_title("Cafe study")
    assert a != b  # diacritics are not stripped per spec


def test_extract_years_only_from_given_fields():
    years = extract_years(["Published 2021 Jan", None, "no year here"])
    assert years == {"2021"}


def test_extract_years_multiple_conflicting_retained():
    years = extract_years(["2020", "2021"])
    assert years == {"2020", "2021"}


def test_extract_years_none_found():
    assert extract_years([None, "no digits", ""]) == set()


def test_first_author_normalization():
    assert normalize_first_author(["Smith"]) == "smith"
    assert normalize_first_author(["  Smith  "]) == "smith"
    assert normalize_first_author([]) is None
    assert normalize_first_author([""]) is None


def test_levenshtein_basic():
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("abc", "") == 3
    assert levenshtein("kitten", "sitting") == 3


def test_title_similarity_threshold_boundary():
    # Construct two titles with a known edit distance to hit exactly 0.90
    a = "a" * 100
    b = "a" * 90 + "b" * 10  # distance 10, max_len 100 -> similarity 0.90
    assert round(title_similarity(a, b), 2) == 0.90


def test_title_similarity_identical_is_one():
    assert title_similarity("same title", "same title") == 1.0
