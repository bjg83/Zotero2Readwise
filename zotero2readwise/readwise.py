from dataclasses import dataclass
from enum import Enum
from json import dump
from typing import Dict, List, Optional, Union

import requests

from zotero2readwise import FAILED_ITEMS_DIR
from zotero2readwise.exception import Zotero2ReadwiseError
from zotero2readwise.helper import sanitize_tag
from zotero2readwise.zotero import ZoteroItem


@dataclass
class ReadwiseAPI:
    """Dataclass for ReadWise API endpoints"""

    base_url: str = "https://readwise.io/api/v2"
    highlights: str = base_url + "/highlights/"
    books: str = base_url + "/books/"


class Category(Enum):
    articles = 1
    books = 2
    tweets = 3
    podcasts = 4


@dataclass
class ReadwiseHighlight:
    text: str
    title: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    category: Optional[str] = None
    note: Optional[str] = None
    location: Union[int, None] = 0
    location_type: Optional[str] = "page"
    highlighted_at: Optional[str] = None
    highlight_url: Optional[str] = None

    def __post_init__(self):
        if not self.location:
            self.location = None

    def get_nonempty_params(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if v}


def roman_to_int(roman_str: str) -> int:
    """
    Convert Roman numerals to integers.
    Handles both uppercase and lowercase roman numerals.
    """
    if not roman_str:
        return 0

    # Convert to uppercase for processing
    roman_str = roman_str.upper().strip()

    # Roman numeral mapping
    roman_values = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }

    total = 0
    prev_value = 0

    # Process from right to left
    for char in reversed(roman_str):
        if char not in roman_values:
            return 0  # Invalid roman numeral

        value = roman_values[char]

        # If current value is less than previous, subtract it (e.g., IV = 4)
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

    # Clean the text
    text = text.upper().strip()

    # Check if it only contains valid Roman numeral characters
    valid_chars = set('IVXLCDM')
    if not all(char in valid_chars for char in text):
        return False

    # Additional validation: try to convert and see if it's reasonable
    try:
        value = roman_to_int(text)
        # Roman numerals for front matter typically don't exceed 50
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

    # Clean the page label
    cleaned = page_label.strip()

    # Check if it's a regular number
    if cleaned.isdigit():
        return (int(cleaned), False, cleaned)

    # Check if it's a Roman numeral
    if is_roman_numeral(cleaned):
        # Convert Roman numeral but give it negative value for sorting
        # This ensures Roman numerals come before regular page numbers
        roman_value = roman_to_int(cleaned)
        return (-roman_value, True, cleaned)

    # Handle mixed cases like "iv-v" or "pp. 23-24"
    # Extract the first number/roman numeral found
    import re

    # Try to find Roman numerals first
    roman_match = re.search(r'\b([ivxlcdm]+)\b', cleaned, re.IGNORECASE)
    if roman_match:
        roman_part = roman_match.group(1)
        if is_roman_numeral(roman_part):
            roman_value = roman_to_int(roman_part)
            return (-roman_value, True, cleaned)

    # Try to find regular numbers
    number_match = re.search(r'\b(\d+)\b', cleaned)
    if number_match:
        return (int(number_match.group(1)), False, cleaned)

    # If nothing found, return 0
    return (0, False, cleaned)


class Readwise:
    def __init__(self, readwise_token: str):
        self._token = readwise_token
        self._header = {"Authorization": f"Token {self._token}"}
        self.endpoints = ReadwiseAPI
        self.failed_highlights: List = []

    def create_highlights(self, highlights: List[Dict]) -> None:
        resp = requests.post(
            url=self.endpoints.highlights,
            headers=self._header,
            json={"highlights": highlights},
        )
        if resp.status_code != 200:
            error_log_file = (
                f"error_log_{resp.status_code}_failed_post_request_to_readwise.json"
            )
            with open(error_log_file, "w") as f:
                dump(resp.json(), f)
            raise Zotero2ReadwiseError(
                f"Uploading to Readwise failed with following details:\n"
                f"POST request Status Code={resp.status_code} ({resp.reason})\n"
                f"Error log is saved to {error_log_file} file."
            )

    @staticmethod
    def convert_tags_to_readwise_format(tags: List[str]) -> str:
        return " ".join([f".{sanitize_tag(t.lower())}" for t in tags])

    def format_readwise_note(self, tags, comment) -> Union[str, None]:
        rw_tags = self.convert_tags_to_readwise_format(tags)
        highlight_note = ""
        if rw_tags:
            highlight_note += rw_tags + "\n"
        if comment:
            highlight_note += comment
        return highlight_note if highlight_note else None

    def convert_zotero_annotation_to_readwise_highlight(
        self, annot: ZoteroItem
    ) -> ReadwiseHighlight:

        highlight_note = self.format_readwise_note(
            tags=annot.tags, comment=annot.comment
        )

        # IMPROVED LOCATION LOGIC WITH ROMAN NUMERAL SUPPORT
        location = None
        location_type = "order"

        if annot.sort_index is not None:
            # Use Zotero's sort index as the primary location indicator
            location = annot.sort_index
        elif annot.page_label:
            # Parse the page label (handles both numeric and Roman numerals)
            numeric_value, is_roman, original_label = parse_page_label(annot.page_label)
            if numeric_value != 0:
                location = numeric_value
                location_type = "page"
            # Note: negative values for Roman numerals will sort before positive values

        highlight_url = None
        if annot.attachment_url is not None:
            attachment_id = annot.attachment_url.split("/")[-1]
            annot_id = annot.annotation_url.split("/")[-1]

            # For Zotero URL, use the original page label if available
            page_for_url = annot.page_label if annot.page_label else "1"
            # Convert Roman numerals to approximate page numbers for the URL
            if annot.page_label:
                _, is_roman, _ = parse_page_label(annot.page_label)
                if is_roman:
                    # For Roman numerals, convert to positive number for URL
                    roman_value = abs(location) if location else 1
                    page_for_url = str(roman_value)

            highlight_url = f'zotero://open-pdf/library/items/{attachment_id}?page={page_for_url}&annotation={annot_id}'

        return ReadwiseHighlight(
            text=annot.text,
            title=annot.title,
            note=highlight_note,
            author=annot.creators,
            category=Category.articles.name
            if annot.document_type != "book"
            else Category.books.name,
            highlighted_at=annot.annotated_at,
            source_url=annot.source_url,
            highlight_url=annot.annotation_url
            if highlight_url is None
            else highlight_url,
            location=location,
            location_type=location_type,
        )

        def sort_annotations_by_reading_order(self, formatted_annots: List[ZoteroItem]) -> List[ZoteroItem]:
    """Sort annotations by document and reading order within each document"""
    
    def get_sort_key(annotation):
        # Group by document first
        doc_key = annotation.parent_item_key or ""
        
        # Then by sort index if available
        if annotation.sort_index is not None:
            return (doc_key, 0, annotation.sort_index, annotation.annotated_at)
        
        # Then by page label (with Roman numeral support)
        if annotation.page_label:
            numeric_value, is_roman, original = parse_page_label(annotation.page_label)
            return (doc_key, 1, numeric_value, annotation.annotated_at)
        
        # Finally by date
        return (doc_key, 2, 0, annotation.annotated_at)
    
    return sorted(formatted_annots, key=get_sort_key)
    
    def post_zotero_annotations_to_readwise(
        self, zotero_annotations: List[ZoteroItem]
    ) -> None:
        print(
            f"\nReadwise: Push {len(zotero_annotations)} Zotero annotations/notes to Readwise...\n"
            f"It may take some time depending on the number of highlights...\n"
            f"A complete message will show up once it's done!\n"
        )
        rw_highlights = []
        for annot in zotero_annotations:
            try:
                if len(annot.text) >= 8191:
                    print(
                        f"A Zotero annotation from an item with {annot.title} (item_key={annot.key} and "
                        f"version={annot.version}) cannot be uploaded since the highlight/note is very long. "
                        f"A Readwise highlight can be up to 8191 characters."
                    )
                    self.failed_highlights.append(annot.get_nonempty_params())
                    continue  # Go to next annot
                rw_highlight = self.convert_zotero_annotation_to_readwise_highlight(
                    annot
                )
            except Exception:
                self.failed_highlights.append(annot.get_nonempty_params())
                continue  # Go to next annot
            rw_highlights.append(rw_highlight.get_nonempty_params())
        self.create_highlights(rw_highlights)

        finished_msg = ""
        if self.failed_highlights:
            finished_msg = (
                f"\nNOTE: {len(self.failed_highlights)} highlights (out of {len(self.failed_highlights)}) failed "
                f"to upload to Readwise.\n"
            )

        finished_msg += f"\n{len(rw_highlights)} highlights were successfully uploaded to Readwise.\n\n"
        print(finished_msg)

    def save_failed_items_to_json(self, json_filepath_failed_items: str = None):
        FAILED_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
        if json_filepath_failed_items:
            out_filepath = FAILED_ITEMS_DIR.joinpath(json_filepath_failed_items)
        else:
            out_filepath = FAILED_ITEMS_DIR.joinpath("failed_readwise_items.json")

        with open(out_filepath, "w") as f:
            dump(self.failed_highlights, f)
        print(
            f"{len(self.failed_highlights)} highlights failed to format (hence failed to upload to Readwise).\n"
            f"Detail of failed items are saved into {out_filepath}"
        )
    
