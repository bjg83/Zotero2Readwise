from dataclasses import dataclass
from enum import Enum
from json import dump
from typing import Dict, List, Optional, Union

import requests

import logging
from .logging_utils import setup_logger

from zotero2readwise import FAILED_ITEMS_DIR
from zotero2readwise.exception import Zotero2ReadwiseError
from zotero2readwise.helper import sanitize_tag
from zotero2readwise.zotero import ZoteroItem
from zotero2readwise.utils import roman_to_int, is_roman_numeral, parse_page_label


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


class Readwise:
    def __init__(self, readwise_token: str, logger=None):
        self._token = readwise_token
        self._header = {"Authorization": f"Token {self._token}"}
        self.endpoints = ReadwiseAPI
        self.failed_highlights: List = []
        self.logger = logger or setup_logger("zotero2readwise.readwise")

    def create_highlights(self, highlights: List[Dict]) -> None:
        try:
            resp = requests.post(
                url=self.endpoints.highlights,
                headers=self._header,
                json={"highlights": highlights},
                timeout=30  # Recommend setting a timeout
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            error_log_file = (
                f"error_log_failed_post_request_to_readwise.json"
            )
            self.logger.error(f"Failed to upload highlights to Readwise: {e}")
            if resp is not None:
                with open(error_log_file, "w") as f:
                    dump(resp.json(), f)
                self.logger.error(f"API response saved to {error_log_file}")
            raise Zotero2ReadwiseError(
                f"Uploading to Readwise failed: {e}\n"
                f"See error log at {error_log_file}"
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
            location = annot.sort_index
        elif annot.page_label:
            numeric_value, is_roman, original_label = parse_page_label(annot.page_label)
            if numeric_value != 0:
                location = numeric_value
                location_type = "page"
            # Note: negative values for Roman numerals will sort before positive values

        highlight_url = None
        if annot.attachment_url is not None:
            attachment_id = annot.attachment_url.split("/")[-1]
            annot_id = annot.annotation_url.split("/")[-1]
            page_for_url = annot.page_label if annot.page_label else "1"
            if annot.page_label:
                _, is_roman, _ = parse_page_label(annot.page_label)
                if is_roman:
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
            doc_key = annotation.parent_item_key or ""
            if annotation.sort_index is not None:
                return (doc_key, 0, annotation.sort_index, annotation.annotated_at)
            if annotation.page_label:
                numeric_value, is_roman, original = parse_page_label(annotation.page_label)
                return (doc_key, 1, numeric_value, annotation.annotated_at)
            return (doc_key, 2, 0, annotation.annotated_at)
        return sorted(formatted_annots, key=get_sort_key)

    def post_zotero_annotations_to_readwise(self, zotero_annotations: List[ZoteroItem]) -> None:
        self.logger.info(
            f"Readwise: Pushing {len(zotero_annotations)} Zotero annotations/notes to Readwise..."
        )
        rw_highlights = []
        for annot in zotero_annotations:
            try:
                if len(annot.text) >= 8191:
                    self.logger.warning(
                        f"Highlight too long for Readwise: {annot.title} (item_key={annot.key})"
                    )
                    self.failed_highlights.append(annot.get_nonempty_params())
                    continue
                rw_highlight = self.convert_zotero_annotation_to_readwise_highlight(annot)
            except Exception as e:
                self.logger.error(
                    f"Failed to convert annotation {getattr(annot, 'key', '?')}: {e}"
                )
                self.failed_highlights.append(annot.get_nonempty_params())
                continue
            rw_highlights.append(rw_highlight.get_nonempty_params())
        self.create_highlights(rw_highlights)
        self.logger.info(
            f"{len(rw_highlights)} highlights uploaded, {len(self.failed_highlights)} failed."
        )

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
