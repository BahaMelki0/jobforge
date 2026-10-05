"""Retrieve candidate evidence relevant to a selected role without inventing facts."""
import re


def relevant(entries, job, limit):
    if job is None:
        return list(entries)[:limit]
    text = (job.title + ' ' + (job.description or '') + ' ' + (getattr(job, 'requirements', '') or '')).casefold()
    terms = set(re.findall(r'[\w+#.-]{3,}', text)) - {'the', 'and', 'with', 'les', 'des', 'pour', 'dans', 'une', 'your', 'you', 'our'}
    def score(entry):
        tokens = set(re.findall(r'[\w+#.-]{3,}', str(entry).casefold()))
        return len(tokens & terms)
    return sorted(entries, key=score, reverse=True)[:limit]
