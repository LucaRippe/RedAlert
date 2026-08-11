import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from matcher import KeywordGroup, find_matches, load_keyword_groups  # noqa: E402


def test_match_any_substring_case_insensitive():
    group = KeywordGroup(name="Litmaps", match_any=["litmaps alternative"])
    assert group.matches("Looking for a LITMAPS ALTERNATIVE, any tips?")
    assert not group.matches("Litmaps is great, no complaints")


def test_exclude_any_suppresses_match():
    group = KeywordGroup(
        name="Lit review tool",
        match_any=["literature review tool"],
        exclude_any=["hiring"],
    )
    assert group.matches("What's the best literature review tool out there?")
    assert not group.matches("We are hiring: build our literature review tool")


def test_case_sensitive_group():
    group = KeywordGroup(name="Brand", match_any=["Orblit"], case_sensitive=True)
    assert group.matches("Just tried Orblit today")
    assert not group.matches("just tried orblit today")


def test_find_matches_returns_all_matching_group_names():
    groups = [
        KeywordGroup(name="A", match_any=["foo"]),
        KeywordGroup(name="B", match_any=["bar"]),
        KeywordGroup(name="C", match_any=["baz"]),
    ]
    assert find_matches("this has foo and bar but not the third", groups) == ["A", "B"]


def test_load_keyword_groups_from_yaml(tmp_path):
    yaml_content = """
- name: "Test Group"
  match_any:
    - "hello world"
  exclude_any:
    - "spam"
  case_sensitive: false
"""
    yaml_path = tmp_path / "keywords.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")

    groups = load_keyword_groups(yaml_path)
    assert len(groups) == 1
    assert groups[0].name == "Test Group"
    assert groups[0].matches("say Hello World please")
    assert not groups[0].matches("Hello World but this is spam")
