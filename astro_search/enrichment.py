"""Bounded article enrichment; metadata never becomes verified answer evidence."""
import time
from concurrent.futures import wait
from urllib.parse import urlsplit
from .cache import TTLCache
from .runtime import EXECUTOR
from .sources.fetch import fetch_article


class Enricher:
    def __init__(self):
        self.cache = TTLCache(ttl_minutes=15, max_entries=64)

    def _fetch(self, url, deadline):
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        if time.monotonic() >= deadline:
            return {'fetch_ok': False}
        result = fetch_article(url, deadline=deadline)
        if result.get('fetch_ok'):
            self.cache.set(url, result)
        return result

    def enrich(self, rows, deadline):
        started = time.monotonic()
        end = min(deadline, started + 3.0)
        candidates = []
        seen = set()
        for row in rows:
            url = row.get('url', '')
            if (row.get('source_type') in ('rss', 'gnews') and isinstance(url, str)
                    and url.startswith(('https://', 'http://')) and url not in seen):
                seen.add(url)
                candidates.append(row)
        selected = candidates[:2]
        if len(candidates) > 2:
            hosts = {urlsplit(r['url']).hostname for r in selected}
            diverse = next((r for r in candidates[2:] if urlsplit(r['url']).hostname not in hosts), candidates[2])
            selected.append(diverse)
        futures, errors = {}, []
        for row in candidates:
            row['enrichment'] = {'status': 'not_selected'}
        for row in selected:
            if time.monotonic() >= end:
                row['enrichment'] = {'status': 'deadline_exceeded'}
                continue
            future = EXECUTOR.submit(self._fetch, row['url'], end)
            if future is not None:
                futures[future] = row
            else:
                row['enrichment'] = {'status': 'capacity_exceeded'}
        done, pending = wait(futures, timeout=max(0, end - time.monotonic())) if futures else (set(), set())
        for future in pending:
            future.cancel()
            futures[future]['enrichment'] = {'status': 'deadline_exceeded'}
        for future in done:
            row = futures[future]
            try:
                doc = future.result()
            except Exception:
                doc = {'fetch_ok': False}
            if not doc.get('fetch_ok'):
                row['enrichment'] = {'status': 'fetch_failed'}
                continue
            md = dict(row.get('metadata') or {})
            incoming = doc.get('metadata') or {}
            origins = {**md.get('field_sources', {}), **incoming.get('field_sources', {})}
            md.update(incoming)
            md['field_sources'] = origins
            row['metadata'] = md
            row['enrichment'] = {'status': 'fetched', 'retrieved_at': doc.get('retrieved_at'),
                                 'final_url': doc.get('final_url'), 'content_trust': 'untrusted_external'}
        for row in selected:
            status = row.get('enrichment', {}).get('status')
            if status != 'fetched':
                errors.append({'source': row.get('source', 'article'), 'stage': 'enrichment', 'error': status})
        return {'selected': len(selected), 'completed': sum(r.get('enrichment', {}).get('status') == 'fetched' for r in selected),
                'elapsed_ms': round((time.monotonic() - started) * 1000), 'errors': errors}
