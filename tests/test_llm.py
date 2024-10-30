from unittest.mock import AsyncMock
from typing import Optional

from src.const import DISCORD_MESSAGE_MAX_CHARS
from src.types.message_formatter import BaseMessageFormatter, ParseResponse


class TestMessageFormatter(BaseMessageFormatter):
    """A concrete implementation of BaseMessageFormatter for testing"""
    async def parse_messages(self, response: str) -> ParseResponse:
        return ParseResponse(
            complete_message=response,
            split_messages=[response],
            username=None
        )


def test_break_messages_strips_regular_whitespace():
    formatter = TestMessageFormatter(AsyncMock())
    original_text = "    hello world!\n   "
    expected_result = [original_text.strip()]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_preserves_single_newlines():
    formatter = TestMessageFormatter(AsyncMock())
    original_text = "hello world\nhello universe\nhello multiverse"
    expected_result = [original_text]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_breaks_on_double_newlines():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = "hello world\n\nhello_universe\n\nhello multiverse"
    expected_result = ["hello world", "hello_universe", "hello multiverse"]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_breaks_on_triple_newlines():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = "hello world\n\n\nhello_universe\n\n\nhello multiverse"
    expected_result = ["hello world", "hello_universe", "hello multiverse"]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_breaks_long_text():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = " ".join(["test"] * 10000)
    results = formatter.break_messages(original_text)
    for result in results:
        assert len(result) <= DISCORD_MESSAGE_MAX_CHARS


def test_break_messages_avoids_breaking_short_code_blocks():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = """\
```
import antigravity

antigravity.engage()
```
"""
    expected_result = [original_text.strip()]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_inserts_backticks_around_breaks_in_long_code_blocks():
    formatter = BaseMessageFormatter(AsyncMock())
    newline = "\n"  # necessary for syntax reasons
    original_text = f"""\
```
{newline.join(["test"] * 1000)}
```
"""
    result = formatter.break_messages(original_text)
    for result in result:
        assert result.startswith("```\n")
        assert result.endswith("\n```")


def test_break_messages_strips_newlines_from_edges_of_code_blocks():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = f"""\
```



```
"""
    expected_result = ["```\n```"]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_preserves_spaces_in_code_blocks():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = f"""\
```
    test{"    "}    
```
"""
    # trailing spaces after "test" are intentional, do not remove
    expected_result = [original_text.strip()]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_strips_whitespace_around_code_blocks():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = f"""\
test

```

```
"""
    expected_result = ["test", "```\n```"]
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_strips_language_marker_from_code_block():
    formatter = BaseMessageFormatter(AsyncMock())
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
    assert formatter.break_messages(original_text) == expected_result


def test_break_messages_only_counts_language_marker_if_block_is_nonempty():
    formatter = BaseMessageFormatter(AsyncMock())
    original_text = f"""\
```python
```
"""
    expected_result = ["```\npython\n```"]
    assert formatter.break_messages(original_text) == expected_result
