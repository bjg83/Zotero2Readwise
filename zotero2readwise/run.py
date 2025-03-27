import json
import requests
from argparse import ArgumentParser
from distutils.util import strtobool
from zotero2readwise.helper import write_library_version, read_library_version
from zotero2readwise.zt2rw import Zotero2Readwise

def safe_json_decode(response):
    try:
        return response.json()
    except json.JSONDecodeError:
        print("Failed to decode JSON response")
        return None

if __name__ == "__main__":
    parser = ArgumentParser(description="Generate Markdown files")
    parser.add_argument("readwise_token", help="Readwise Access Token (visit https://readwise.io/access_token)")
    parser.add_argument("zotero_key", help="Zotero API key (visit https://www.zotero.org/settings/keys)")
    parser.add_argument("zotero_library_id", help="Zotero User ID (visit https://www.zotero.org/settings/keys)")
    parser.add_argument("--library_type", default="user", help="Zotero Library type ('user': for personal library (default value), 'group': for a shared library)")
    parser.add_argument("--include_annotations", type=str, default="y", help="Include Zotero annotations (highlights + comments) | Options: 'y'/'yes' (default), 'n'/'no'")
    parser.add_argument("--include_notes", type=str, default="n", help="Include Zotero notes | Options: 'y'/'yes', 'n'/'no' (default)")
    parser.add_argument("--filter_color", choices=['#ffd400', '#ff6666', '#5fb236', '#2ea8e5', '#a28ae5', '#e56eee', '#f19837', '#aaaaaa'], action="append", default=[], help="Filter Zotero annotations by given color")
    parser.add_argument("--use_since", action='store_true', help="Include Zotero items since last run")

    args = vars(parser.parse_args())

    # Cast str to bool values for bool flags
    for bool_arg in ["include_annotations", "include_notes"]:
        try:
            args[bool_arg] = bool(strtobool(args[bool_arg]))
        except ValueError:
            raise ValueError(f"Invalid value for --{bool_arg}. Use 'n' or 'y' (default).")

    since = read_library_version() if args["use_since"] else 0
    zt2rw = Zotero2Readwise(
        readwise_token=args["readwise_token"],
        zotero_key=args["zotero_key"],
        zotero_library_id=args["zotero_library_id"],
        zotero_library_type=args["library_type"],
        include_annotations=args["include_annotations"],
        include_notes=args["include_notes"],
        filter_colors=args["filter_color"],
        since=since
    )

    # Override the run method to use safe_json_decode
    original_run = zt2rw.run
    def run_with_safe_decode():
        response = requests.get("your-api-endpoint-here")  # Replace with actual API call
        data = safe_json_decode(response)
        if data is None:
            print("Skipping due to JSON decode error")
            return
        original_run()
    
    zt2rw.run = run_with_safe_decode
    zt2rw.run()

    if args["use_since"]:
        write_library_version(zt2rw.zotero_client)
