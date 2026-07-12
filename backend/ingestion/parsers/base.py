from dataclasses import dataclass, field


@dataclass
class ParsedDocument:
    """Format-agnostic output of any parser (markdown, PDF, ...)."""

    text: str
    metadata: dict = field(default_factory=dict)
    links: list[str] = field(default_factory=list)  # wikilinks / relative links / plain URLs found in the doc
    sections: list[tuple[int, str, str]] = field(default_factory=list)
    # sections: (heading_level, heading_text, section_text) - used to build parent/child chunk hierarchy
