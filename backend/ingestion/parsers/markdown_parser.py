import re

from markdown_it import MarkdownIt

from backend.ingestion.parsers.base import ParsedDocument

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

_md = MarkdownIt()


def _extract_links(raw_text: str) -> list[str]:
    links = set(_WIKILINK_RE.findall(raw_text))
    for target in _MD_LINK_RE.findall(raw_text):
        if target.startswith(("http://", "https://")):
            links.add(target)
        elif not target.startswith("#"):  # skip in-page anchors
            links.add(target)
    return sorted(links)


def _extract_sections(raw_text: str) -> list[tuple[int, str, str]]:
    """Split on markdown headings into (level, heading_text, section_body) tuples."""
    tokens = _md.parse(raw_text)
    lines = raw_text.splitlines()

    heading_positions: list[tuple[int, int, str]] = []  # (line_no, level, heading_text)
    for token in tokens:
        if token.type == "heading_open" and token.map:
            level = int(token.tag[1])
            line_no = token.map[0]
            heading_positions.append((line_no, level, None))

    # pull heading text from the inline token that follows each heading_open
    heading_texts = []
    i = 0
    for token in tokens:
        if token.type == "inline" and i < len(heading_positions):
            heading_texts.append(token.content)
            i += 1

    sections: list[tuple[int, str, str]] = []
    for idx, (line_no, level, _) in enumerate(heading_positions):
        heading_text = heading_texts[idx] if idx < len(heading_texts) else ""
        start = line_no + 1
        end = heading_positions[idx + 1][0] if idx + 1 < len(heading_positions) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        sections.append((level, heading_text, body))

    if not sections:
        sections = [(1, "", raw_text.strip())]
    return sections


def parse_markdown(raw_text: str, source_path: str) -> ParsedDocument:
    front_matter = {}
    body = raw_text
    if raw_text.startswith("---"):
        end = raw_text.find("\n---", 3)
        if end != -1:
            fm_block = raw_text[3:end].strip()
            body = raw_text[end + 4:].lstrip("\n")
            for line in fm_block.splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    front_matter[key.strip()] = value.strip()

    return ParsedDocument(
        text=body,
        metadata={"source_path": source_path, **front_matter},
        links=_extract_links(body),
        sections=_extract_sections(body),
    )
