"""Document parsing framework for Snip MCP."""

from snip_mcp.parser.documents.base import DocumentFile, DocumentSection
from snip_mcp.parser.documents.registry import get_parser, parse_document

__all__ = [
    "DocumentFile",
    "DocumentSection",
    "get_parser",
    "parse_document",
]
