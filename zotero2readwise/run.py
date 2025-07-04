# Import required libraries
from argparse import ArgumentParser
from distutils.util import strtobool

from zotero2readwise.helper import write_library_version, read_library_version
from zotero2readwise.readwise import Readwise
from zotero2readwise.zt2rw import Zotero2Readwise

# Define constants for argument help messages
READWISE_TOKEN_HELP = "Readwise Access Token (visit https://readwise.io/access_token)"
ZOTERO_KEY_HELP = "Zotero API key (visit https://www.zotero.org/settings/keys)"
ZOTERO_LIBRARY_ID_HELP = "Zotero User ID (visit https://www.zotero.org/settings/keys)"
LIBRARY_TYPE_HELP = "Zotero Library type ('user': for personal library (default value), 'group': for a shared library)"
INCLUDE_ANNOTATIONS_HELP = "Include Zotero annotations (highlights + comments) | Options: 'y'/'yes' (default), 'n'/'no'"
INCLUDE_NOTES_HELP = "Include Zotero notes | Options: 'y'/'yes', 'n'/'no' (default)"
FILTER_COLOR_HELP = ("Filter Zotero annotations by given color | Options: '#ffd400' (yellow), '#ff6666' (red), '#5fb236' "
                     "(green), '#2ea8e5' (blue), '#a28ae5' (purple), '#e56eee' (magenta), '#f19837' (orange), '#aaaaaa' (grey)")
USE_SINCE_HELP = "Include Zotero items since last run"


def parse_arguments():
    """Parse command-line arguments."""
    parser = ArgumentParser(description="Generate Markdown files")
    parser.add_argument("readwise_token", help=READWISE_TOKEN_HELP)
    parser.add_argument("zotero_key", help=ZOTERO_KEY_HELP)
    parser.add_argument("zotero_library_id", help=ZOTERO_LIBRARY_ID_HELP)
    parser.add_argument("--library_type", default="user", help=LIBRARY_TYPE_HELP)
    parser.add_argument("--include_annotations", type=str, default="y", help=INCLUDE_ANNOTATIONS_HELP)
    parser.add_argument("--include_notes", type=str, default="n", help=INCLUDE_NOTES_HELP)
    parser.add_argument("--filter_color", choices=['#ffd400', '#ff6666', '#5fb236', '#2ea8e5', '#a28ae5', '#e56eee', '#f19837', '#aaaaaa'], action="append", default=[], help=FILTER_COLOR_HELP)
    parser.add_argument("--use_since", action='store_true', help=USE_SINCE_HELP)
    return vars(parser.parse_args())


def cast_bool_args(args):
    """Cast boolean arguments to actual boolean values."""
    for bool_arg in ["include_annotations", "include_notes"]:
        try:
            args[bool_arg] = bool(strtobool(args[bool_arg]))
        except ValueError:
            raise ValueError(f"Invalid value for --{bool_arg}. Use 'n' or 'y' (default).")


def main():
    """Main entry point of the script."""
    args = parse_arguments()
    cast_bool_args(args)
    
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
    zt2rw.run()
    
    if args["use_since"]:
        write_library_version(zt2rw.zotero_client)


if __name__ == "__main__":
    main()
