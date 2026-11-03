"""Every environment variable the code reads must be documented, and nothing stale may linger.

The variable names are found by scanning the code, so a new variable that is read but not
listed in .env.example and in the README configuration table fails this test.
"""

import re
from pathlib import Path

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent
# `.get("NAME"` / `getenv("NAME"` / `environ["NAME"]` with an UPPER_CASE literal name.
ENV_READ = re.compile(r'(?:\.get\(|getenv\(|environ\[)\s*"([A-Z][A-Z0-9_]+)"')


def variables_read_by_the_code() -> set[str]:
    names = {name.upper() for name in Settings.model_fields}  # read by pydantic-settings
    for path in (ROOT / "app").rglob("*.py"):
        names |= set(ENV_READ.findall(path.read_text()))
    return names


def env_example_variables() -> set[str]:
    found: set[str] = set()
    for line in (ROOT / ".env.example").read_text().splitlines():
        match = re.match(r"^#?\s*([A-Z][A-Z0-9_]+)=", line)  # active or commented-out example
        if match:
            found.add(match.group(1))
    return found


def readme_variables() -> set[str]:
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## Configuration", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\|\s*`([A-Z][A-Z0-9_]+)`", section, flags=re.MULTILINE))


def test_the_scan_finds_the_known_variables() -> None:
    names = variables_read_by_the_code()
    assert {"LLM_MODEL", "LLM_API_KEY", "FUNDRAISINGBOX_APITOKEN", "DATA_DIR"} <= names
    assert {"PORT", "STATIC_DIR"} <= names  # read directly, not through Settings


def test_every_variable_the_code_reads_is_in_env_example() -> None:
    missing = variables_read_by_the_code() - env_example_variables()
    assert not missing, f"add to .env.example: {sorted(missing)}"


def test_every_variable_the_code_reads_is_in_the_readme_table() -> None:
    missing = variables_read_by_the_code() - readme_variables()
    assert not missing, f"add to the README configuration table: {sorted(missing)}"


def test_documentation_lists_no_variable_the_code_does_not_read() -> None:
    read = variables_read_by_the_code()
    assert not env_example_variables() - read, "stale entries in .env.example"
    assert not readme_variables() - read, "stale entries in the README table"
