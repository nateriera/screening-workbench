from screening_workbench.importers.pubmed_xml_importer import parse_pubmed_xml

ARTICLE_TEMPLATE = """<?xml version="1.0"?>
<PubmedArticleSet>
<PubmedArticle>
  <MedlineCitation>
    <PMID>12345</PMID>
    <Article>
      <ArticleTitle>A Study of <i>Things</i></ArticleTitle>
      <Journal>
        <Title>Journal of Examples</Title>
        <JournalIssue>
          <Volume>10</Volume>
          <Issue>2</Issue>
          <PubDate><Year>2021</Year></PubDate>
        </JournalIssue>
      </Journal>
      <Pagination><MedlinePgn>100-110</MedlinePgn></Pagination>
      <ELocationID EIdType="doi">10.1/xyz</ELocationID>
      <AuthorList>
        <Author><LastName>Smith</LastName><ForeName>Jane</ForeName></Author>
        <Author><CollectiveName>Study Group</CollectiveName></Author>
      </AuthorList>
      <Abstract>
        <AbstractText Label="BACKGROUND">Background text.</AbstractText>
        <AbstractText Label="METHODS">Methods text.</AbstractText>
      </Abstract>
      <Language>eng</Language>
      <KeywordList><Keyword>cancer</Keyword><Keyword>therapy</Keyword></KeywordList>
    </Article>
  </MedlineCitation>
</PubmedArticle>
</PubmedArticleSet>
"""


# IM-12: nested/mixed ArticleTitle, multiple authors, labeled abstract, DOI/PMID.
def test_im12_full_article_mapping():
    result = parse_pubmed_xml(ARTICLE_TEMPLATE)
    assert result.skipped == []
    assert len(result.records) == 1
    fields = result.records[0]["fields"]
    assert fields["title"] == "A Study of Things"
    assert fields["journal"] == "Journal of Examples"
    assert fields["year"] == "2021"
    assert fields["volume"] == "10"
    assert fields["issue"] == "2"
    assert fields["pages"] == "100-110"
    assert fields["doi"] == "10.1/xyz"
    assert fields["pmid"] == "12345"
    assert fields["authors"] == ["Smith Jane", "Study Group"]
    assert "Background text." in fields["abstract"]
    assert "Methods text." in fields["abstract"]
    assert fields["keywords"] == ["cancer", "therapy"]
    assert fields["language"] == "eng"
    assert fields["url"] == ""  # never synthesized


def test_multiple_articles_in_one_set():
    doc = (
        "<PubmedArticleSet>"
        "<PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
        "<ArticleTitle>First</ArticleTitle></Article></MedlineCitation></PubmedArticle>"
        "<PubmedArticle><MedlineCitation><PMID>2</PMID><Article>"
        "<ArticleTitle>Second</ArticleTitle></Article></MedlineCitation></PubmedArticle>"
        "</PubmedArticleSet>"
    )
    result = parse_pubmed_xml(doc)
    assert len(result.records) == 2
    assert [r["fields"]["title"] for r in result.records] == ["First", "Second"]


def test_delete_citation_skipped_not_applied_as_deletion():
    doc = (
        "<PubmedArticleSet>"
        "<PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
        "<ArticleTitle>Kept</ArticleTitle></Article></MedlineCitation></PubmedArticle>"
        "<DeleteCitation><PMID>999</PMID></DeleteCitation>"
        "</PubmedArticleSet>"
    )
    result = parse_pubmed_xml(doc)
    assert len(result.records) == 1
    assert any(s["reason"] == "unsupported_record_type" for s in result.skipped)


def test_medline_date_fallback_extracts_year():
    doc = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
        "<ArticleTitle>X</ArticleTitle>"
        "<Journal><JournalIssue><PubDate><MedlineDate>2019 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>"
        "</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    )
    result = parse_pubmed_xml(doc)
    assert result.records[0]["fields"]["year"] == "2019"


def test_malformed_xml_rejects_whole_file():
    result = parse_pubmed_xml("<PubmedArticleSet><PubmedArticle>unterminated")
    assert result.records == []
    assert len(result.skipped) == 1
    assert "malformed_record" in result.skipped[0]["reason"]


# Security: XXE / billion-laughs via inline DOCTYPE must be rejected, not parsed.
def test_xxe_doctype_is_rejected_not_parsed():
    xxe_payload = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE PubmedArticleSet [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<PubmedArticleSet>&xxe;</PubmedArticleSet>"
    )
    result = parse_pubmed_xml(xxe_payload)
    assert result.records == []
    assert result.skipped[0]["reason"].startswith("invalid_encoding")


def test_billion_laughs_doctype_is_rejected_not_parsed():
    bomb = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE lolz [<!ENTITY lol \"lol\">"
        "<!ENTITY lol2 \"&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;\">]>"
        "<PubmedArticleSet>&lol2;</PubmedArticleSet>"
    )
    result = parse_pubmed_xml(bomb)
    assert result.records == []
    assert result.skipped[0]["reason"].startswith("invalid_encoding")


def test_no_pubmed_article_returns_empty_not_error():
    result = parse_pubmed_xml("<PubmedArticleSet></PubmedArticleSet>")
    assert result.records == []
    assert result.skipped == []
