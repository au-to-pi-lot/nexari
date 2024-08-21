from src.bot import DiscordBot
from src.const import DISCORD_MESSAGE_MAX_CHARS


def test_break_messages_strips_regular_whitespace():
    original_text = "    hello world!\n   "
    expected_result = [original_text.strip()]
    assert DiscordBot.break_messages(original_text) == expected_result

def test_break_messages_preserves_single_newlines():
    original_text = "hello world\nhello universe\nhello multiverse"
    expected_result = [original_text]
    assert DiscordBot.break_messages(original_text) == expected_result


def test_break_messages_breaks_on_double_newlines():
    original_text = "hello world\n\nhello_universe\n\nhello multiverse"
    expected_result = original_text.split("\n\n")
    assert DiscordBot.break_messages(original_text) == expected_result


def test_break_messages_breaks_long_text():
    original_text = " ".join(["test"] * 10000)
    results = DiscordBot.break_messages(original_text)
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
    assert DiscordBot.break_messages(original_text) == expected_result

def test_break_messages_inserts_backticks_around_breaks_in_long_code_blocks():
    newline = "\n"  # necessary for syntax reasons
    original_text = f"""\
```
{newline.join(["test"] * 1000)}
```
"""
    result = DiscordBot.break_messages(original_text)
    for result in result:
        assert result.startswith("```\n")
        assert result.endswith("\n```")

def test_break_messages_preserves_number_of_newlines_within_code_block():
    original_text = f"""\
```



```
"""
    expected_result = [original_text.strip()]
    assert DiscordBot.break_messages(original_text) == expected_result


def test_break_messages_strips_whitespace_around_code_blocks():
    original_text = f"""\
test

```

```
"""
    expected_result = ["test", "```\n\n```"]
    assert DiscordBot.break_messages(original_text) == expected_result
