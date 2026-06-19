"""Property-based tests for to_bool().

100% line/branch coverage proves every line ran, not that behaviors hold across
the whole input space. These hypothesis properties pin the invariants a coercion
function must satisfy for *any* input, independent of the specific examples in the
other test modules. They never touch os.environ -- to_bool() is pure.
"""

from hypothesis import assume, given
from hypothesis import strategies as st

from envbool import to_bool
from envbool._defaults import DEFAULT_FALSY, DEFAULT_TRUTHY

# Printable ASCII keeps the case-folding property free of unicode edge cases
# (e.g. characters whose .upper()/.lower() are not clean round-trips).
_ASCII_PRINTABLE = st.text(st.characters(min_codepoint=32, max_codepoint=126))

_WHITESPACE = st.sampled_from(["", " ", "\t", "  ", "\n", " \t "])


def _noise(value: str, data) -> str:
    """Wrap a token in hypothesis-drawn surrounding whitespace and mixed case.

    Drawing from `data` (rather than the `random` module) keeps examples
    reproducible and shrinkable. to_bool() normalizes by stripping then
    lowercasing, so neither change may affect the outcome -- exactly what the
    membership properties assert.
    """
    cased = "".join(data.draw(st.sampled_from([c.upper(), c.lower()])) for c in value)
    return f"{data.draw(_WHITESPACE)}{cased}{data.draw(_WHITESPACE)}"


@given(st.text())
def test_always_returns_exactly_bool(value):
    # Not just truthy/falsy -- the public contract is the bool type itself.
    assert type(to_bool(value)) is bool


@given(st.text())
def test_surrounding_whitespace_never_changes_result(value):
    assert to_bool(value) == to_bool(f" \t\n{value}\n\t ")


@given(_ASCII_PRINTABLE)
def test_case_never_changes_result(value):
    assert to_bool(value) == to_bool(value.swapcase())


@given(st.sampled_from(sorted(DEFAULT_TRUTHY)), st.data())
def test_truthy_members_are_true_under_noise(token, data):
    assert to_bool(_noise(token, data)) is True


@given(st.sampled_from(sorted(DEFAULT_FALSY)), st.data())
def test_falsy_members_are_false_under_noise(token, data):
    assert to_bool(_noise(token, data)) is False


@given(st.text(alphabet=" \t\n\r\f\v"), st.booleans())
def test_blank_input_returns_default(value, default):
    # Anything that normalizes to empty is "unset" -- the caller's default wins.
    assert to_bool(value, default=default) is default


@given(_ASCII_PRINTABLE)
def test_unrecognized_is_false_in_lenient_mode(value):
    normalized = value.strip().lower()
    # Skip blanks (governed by default) and any recognized token.
    assume(normalized)
    assume(normalized not in DEFAULT_TRUTHY)
    assume(normalized not in DEFAULT_FALSY)
    assert to_bool(value) is False


@given(st.lists(_ASCII_PRINTABLE, min_size=1, max_size=5))
def test_every_custom_truthy_token_coerces_true(tokens):
    # Replacing the truthy set must make every one of its members coerce True,
    # even one that collides with a default falsy token (truthy wins on overlap).
    assume(all(t.strip().lower() for t in tokens))  # blanks return default instead
    for token in tokens:
        assert to_bool(token, truthy=tokens) is True
