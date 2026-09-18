"""Bounded publisher metadata extraction. All fields remain untrusted claims."""
import json
import re
from html.parser import HTMLParser


def compact(text):
    return re.sub(r'\s+', ' ', text).strip()


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = {'field_sources': {}, 'headings': [], 'passages': []}
        self.stack = []
        self.blocks = []
        self.capture = None
        self.parts = []
        self.json_parts = None

    def put(self, key, value, origin):
        if isinstance(value, str) and value.strip() and key not in self.out:
            self.out[key] = compact(value)[:2000]
            self.out['field_sources'][key] = origin

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = (attrs.get('name') or attrs.get('property') or '').lower()
            names = {'description': 'meta_description', 'og:title': 'og_title',
                     'og:description': 'og_description', 'article:published_time': 'date_published',
                     'article:modified_time': 'date_modified', 'og:type': 'document_type'}
            if key in names:
                self.put(names[key], attrs.get('content'), key)
        if tag in {'script', 'style', 'nav', 'footer', 'aside', 'article', 'main'}:
            self.stack.append(tag)
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.json_parts = []
        if tag in {'title', 'h1', 'h2', 'h3', 'p', 'li'} and not any(t in self.stack for t in ('script', 'style', 'nav', 'footer', 'aside')):
            self.capture, self.parts = tag, []

    def handle_data(self, data):
        if self.json_parts is not None:
            self.json_parts.append(data)
        if self.capture and not any(t in self.stack for t in ('script', 'style', 'nav', 'footer', 'aside')):
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.json_parts is not None:
            try:
                self.structured(json.loads(''.join(self.json_parts)))
            except (ValueError, RecursionError):
                pass
            self.json_parts = None
        if tag == self.capture:
            text = compact(''.join(self.parts))
            if tag == 'title':
                self.put('html_title', text, 'title')
            elif text:
                self.blocks.append((tag, text, 'article' in self.stack or 'main' in self.stack))
            self.capture, self.parts = None, []
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def structured(self, data, depth=0):
        if depth > 5:
            return
        if isinstance(data, list):
            for item in data[:50]:
                self.structured(item, depth + 1)
        elif isinstance(data, dict):
            types = data.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if isinstance(types, list) and any(t in ('Article', 'NewsArticle', 'BlogPosting', 'ScholarlyArticle') for t in types):
                for key, dest in [('headline', 'structured_title'), ('description', 'structured_description'),
                                  ('datePublished', 'date_published'), ('dateModified', 'date_modified')]:
                    self.put(dest, data.get(key), 'json_ld')
                self.put('document_type', next(t for t in types if isinstance(t, str)), 'json_ld')
            self.structured(data.get('@graph'), depth + 1)


def extract_metadata(body):
    parser = MetadataParser()
    parser.feed(body[:2 * 1024 * 1024])
    parser.close()
    main = any(b[2] for b in parser.blocks)
    blocks = [b for b in parser.blocks if b[2] or not main]
    parser.out['headings'] = [text for tag, text, _ in blocks if tag.startswith('h') and len(text) <= 2000][:30]
    parser.out['passages'] = [text for tag, text, _ in blocks if tag in ('p', 'li') and len(text) <= 2000][:100]
    parser.out['passages_omitted'] = any(len(text) > 2000 for _, text, _ in blocks) or len(blocks) > 130
    parser.out['field_sources'].update(headings='html_heading', passages='article_text')
    return parser.out
