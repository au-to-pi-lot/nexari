from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.llm import LLMHandler


def test_parse_llm_response_removes_content_open_tag():
    original_text = "<content>\nhello world"
    expected_result = "hello world"
    assert LLMHandler.parse_llm_response(original_text) == expected_result


def test_parse_llm_response_leaves_untagged_content_alone():
    original_text = "hello world"
    expected_result = "hello world"
    assert LLMHandler.parse_llm_response(original_text) == expected_result


def test_parse_llm_response_removes_content_closing_tag():
    original_text = "hello world\n</content>\nother stuff"
    expected_result = "hello world"
    assert LLMHandler.parse_llm_response(original_text) == expected_result


def test_parse_llm_response_removes_metadata():
    original_text = "hello world\n<metadata>\nName: test</metadata>"
    expected_result = "hello world"
    assert LLMHandler.parse_llm_response(original_text) == expected_result


def test_break_messages_strips_regular_whitespace():
    original_text = "    hello world!\n   "
    expected_result = [original_text.strip()]
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_preserves_single_newlines():
    original_text = "hello world\nhello universe\nhello multiverse"
    expected_result = [original_text]
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_breaks_on_double_newlines():
    original_text = "hello world\n\nhello_universe\n\nhello multiverse"
    expected_result = original_text.split("\n\n")
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_breaks_on_triple_newlines():
    original_text = "hello world\n\n\nhello_universe\n\n\nhello multiverse"
    expected_result = original_text.split("\n\n\n")
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_breaks_long_text():
    original_text = " ".join(["test"] * 10000)
    results = LLMHandler.break_messages(original_text)
    for result in results:
        assert len(result) <= DISCORD_MESSAGE_MAX_CHARS


def test_break_messages_avoids_breaking_short_code_blocks():
    original_text = """\
```
import antigravity

antigravity.engage()
```
"""
    expected_result = [original_text.strip()]
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_inserts_backticks_around_breaks_in_long_code_blocks():
    newline = "\n"  # necessary for syntax reasons
    original_text = f"""\
```
{newline.join(["test"] * 1000)}
```
"""
    result = LLMHandler.break_messages(original_text)
    for result in result:
        assert result.startswith("```\n")
        assert result.endswith("\n```")


def test_break_messages_strips_newlines_from_edges_of_code_blocks():
    original_text = f"""\
```



```
"""
    expected_result = ["```\n```"]
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_preserves_spaces_in_code_blocks():
    original_text = f"""\
```
    test{"    "}    
```
"""
    # trailing spaces after "test" are intentional, do not remove
    expected_result = [original_text.strip()]
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_strips_whitespace_around_code_blocks():
    original_text = f"""\
test

```

```
"""
    expected_result = ["test", "```\n```"]
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_strips_language_marker_from_code_block():
    original_text = f"""\
```python
from datetime import datetime

print(datetime.utcnow())
```
"""
    expected_result = [
        f"""\
```
from datetime import datetime

print(datetime.utcnow())
```"""
    ]
    assert LLMHandler.break_messages(original_text) == expected_result


def test_break_messages_only_counts_language_marker_if_block_is_nonempty():
    original_text = f"""\
```python
```
"""
    expected_result = ["```\npython\n```"]
    assert LLMHandler.break_messages(original_text) == expected_result
