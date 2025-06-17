def roman_to_int(roman_str: str) -> int:
    """
    Convert Roman numerals to integers.
    Handles both uppercase and lowercase roman numerals.
    """
    if not roman_str:
        return 0

    roman_str = roman_str.upper().strip()
    roman_values = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }
    total = 0
    prev_value = 0

    for char in reversed(roman_str):
        if char not in roman_values:
            return 0  # Invalid roman numeral
        value = roman_values[char]
        if value < prev_value:
            total -= value
        else:
            total += value
        prev_value = value

    return total


def is_roman_numeral(text: str) -> bool:
    """
    Check if a string is a valid Roman numeral.
    """
    if not text:
        return False

    text = text.upper().strip()
    valid_chars = set('IVXLCDM')
    if not all(char in valid_chars for char in text):
        return False

    try:
        value = roman_to_int(text)
        return 1 <= value <= 100
    except Exception:
        return False


def parse_page_label(page_label: str) -> tuple:
    """
    Parse a page label and return (numeric_value, is_roman, original_label).
    Returns:
        tuple: (int, bool, str) - (numeric_value, is_roman_numeral, original_label)
    """
    if not page_label:
        return (0, False, "")

    cleaned = page_label.strip()

    if cleaned.isdigit():
        return (int(cleaned), False, cleaned)

    if is_roman_numeral(cleaned):
        roman_value = roman_to_int(cleaned)
        return (-roman_value, True, cleaned)

    import re
    roman_match = re.search(r'\b([ivxlcdm]+)\b', cleaned, re.IGNORECASE)
    if roman_match:
        roman_part = roman_match.group(1)
        if is_roman_numeral(roman_part):
            roman_value = roman_to_int(roman_part)
            return (-roman_value, True, cleaned)

    number_match = re.search(r'\b(\d+)\b', cleaned)
    if number_match:
        return (int(number_match.group(1)), False, cleaned)

    return (0, False, cleaned)
