"""Tests for toolkit.parser."""

import sys
import unittest

from toolkit.exceptions import ParseError, ToolkitError
from toolkit.parser import (
    MAX_INTEGER_DIGITS,
    parse_element,
    parse_mapping,
    parse_set,
)


class TestParseElement(unittest.TestCase):
    def test_integers(self):
        self.assertEqual(parse_element("7"), 7)
        self.assertEqual(parse_element("-3"), -3)
        self.assertEqual(parse_element("+5"), 5)
        self.assertEqual(parse_element("  42 "), 42)

    def test_words(self):
        self.assertEqual(parse_element("apple"), "apple")
        self.assertEqual(parse_element("x1"), "x1")
        self.assertEqual(parse_element("3.5"), "3.5")  # not an integer

    def test_invalid(self):
        for bad in ["", "   ", "{1}", "(1", "a b", "1->a"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    parse_element(bad)

    # --- Regression tests for audit findings -----------------------------

    def test_extremely_long_integer_is_a_parse_error(self):
        # B1: used to escape as an uncaught ValueError (Python 3.11+).
        with self.assertRaises(ParseError) as ctx:
            parse_element("1" * 5000)
        self.assertIn("5000 characters", str(ctx.exception))
        self.assertIn(f"at most {MAX_INTEGER_DIGITS} digits", str(ctx.exception))

    def test_integer_digit_limit_boundary(self):
        self.assertEqual(parse_element("9" * MAX_INTEGER_DIGITS),
                         int("9" * MAX_INTEGER_DIGITS))
        self.assertEqual(parse_element("-" + "9" * MAX_INTEGER_DIGITS),
                         -int("9" * MAX_INTEGER_DIGITS))
        with self.assertRaises(ParseError):
            parse_element("9" * (MAX_INTEGER_DIGITS + 1))

    def test_digit_limit_does_not_depend_on_python_version(self):
        # Older Python releases have no built-in 4300-digit limit. Simulate
        # one by switching Python's limit off (possible on 3.11+): the
        # parser's own check must still reject the number.
        if not hasattr(sys, "set_int_max_str_digits"):
            self.skipTest("this Python cannot switch off its int limit")
        old_limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)  # 0 = no limit
        try:
            with self.assertRaises(ParseError):
                parse_element("1" * (MAX_INTEGER_DIGITS + 1))
        finally:
            sys.set_int_max_str_digits(old_limit)

    def test_only_ascii_digits_make_integers(self):
        # B2: Bengali ৩ and Arabic-Indic ٣ used to become the integer 3.
        self.assertEqual(parse_element("৩"), "৩")
        self.assertEqual(parse_element("٣"), "٣")
        self.assertEqual(parse_element("３"), "３")  # full-width digit
        self.assertEqual(parse_element("3"), 3)

    def test_square_brackets_are_ordinary_characters(self):
        # Documented behaviour: only braces and parentheses are reserved.
        self.assertEqual(parse_element("[1]"), "[1]")

    def test_error_message_names_reserved_characters(self):
        with self.assertRaises(ParseError) as ctx:
            parse_element("(1")
        self.assertIn("parentheses", str(ctx.exception))
        self.assertNotIn("brackets", str(ctx.exception))


class TestParseSet(unittest.TestCase):
    def test_simple(self):
        result = parse_set("{1, 2, 3}")
        self.assertEqual(result.elements, frozenset({1, 2, 3}))
        self.assertEqual(result.duplicates, ())

    def test_whitespace_is_flexible(self):
        self.assertEqual(parse_set("  {1,2 ,   3}  ").elements,
                         frozenset({1, 2, 3}))

    def test_mixed_types(self):
        self.assertEqual(parse_set("{1, apple}").elements,
                         frozenset({1, "apple"}))

    def test_empty_set(self):
        self.assertEqual(parse_set("{}").elements, frozenset())
        self.assertEqual(parse_set("{   }").elements, frozenset())

    def test_duplicates_are_removed_and_reported(self):
        result = parse_set("{1, 1, 2, a, a, a}")
        self.assertEqual(result.elements, frozenset({1, 2, "a"}))
        self.assertEqual(result.duplicates, (1, "a"))

    def test_numbers_are_normalised(self):
        # 07 and 7 are the same integer, so this is a duplicate.
        result = parse_set("{7, 07}")
        self.assertEqual(result.elements, frozenset({7}))
        self.assertEqual(result.duplicates, (7,))

    def test_integer_and_word_are_different(self):
        self.assertEqual(len(parse_set("{1, one}").elements), 2)

    def test_errors(self):
        bad_inputs = [
            "",           # nothing typed
            "1, 2, 3",    # no braces
            "{1, 2",      # missing closing brace
            "1, 2}",      # missing opening brace
            "{1,,2}",     # empty element
            "{1, 2,}",    # trailing comma
            "{,}",        # only a comma
            "{{1}, 2}",   # nested set
            "{1 2}",      # missing comma
            "{(1, 2)}",   # tuple
        ]
        for bad in bad_inputs:
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    parse_set(bad)

    def test_non_ascii_digit_is_not_a_duplicate_of_ascii_digit(self):
        # B2 regression: {3, ৩} used to collapse to {3}.
        result = parse_set("{3, ৩}")
        self.assertEqual(result.elements, frozenset({3, "৩"}))
        self.assertEqual(result.duplicates, ())

    def test_long_integer_in_set(self):
        # B1 regression at the set level.
        with self.assertRaises(ParseError):
            parse_set("{" + "1" * 5000 + "}")

    def test_parse_error_is_toolkit_error(self):
        with self.assertRaises(ToolkitError):
            parse_set("oops")


class TestParseMapping(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_mapping("1->a, 2->b"), [(1, "a"), (2, "b")])

    def test_spaces_and_braces(self):
        self.assertEqual(parse_mapping("{ 1 -> a , 2->b }"),
                         [(1, "a"), (2, "b")])

    def test_empty_mapping(self):
        self.assertEqual(parse_mapping(""), [])
        self.assertEqual(parse_mapping("{}"), [])

    def test_conflicting_pairs_are_kept(self):
        # The parser must NOT hide the conflict; the Function validator
        # is responsible for rejecting it.
        self.assertEqual(parse_mapping("1->a, 1->b"), [(1, "a"), (1, "b")])

    def test_negative_numbers(self):
        self.assertEqual(parse_mapping("-1->-2"), [(-1, -2)])

    def test_long_integer_in_mapping(self):
        # B1 regression at the mapping level.
        with self.assertRaises(ParseError):
            parse_mapping("1->" + "2" * 5000)

    def test_errors(self):
        bad_inputs = [
            "1 a",          # no arrow
            "1->a->b",      # two arrows
            "->a",          # missing input
            "1->",          # missing output
            "1->a,",        # trailing comma
            "1->a 2->b",    # missing comma
            "1=a",          # wrong arrow
        ]
        for bad in bad_inputs:
            with self.subTest(bad=bad):
                with self.assertRaises(ParseError):
                    parse_mapping(bad)


if __name__ == "__main__":
    unittest.main()
