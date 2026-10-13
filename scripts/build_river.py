"""Build the homepage river from ten reviewed event batches.

Regenerate broad-recall candidate input with scripts/river_events/prepare.py.
The committed review files are semantic review results, not derived labels;
this builder never upgrades a rule-selected paragraph to a reviewed event.
"""
from river_events.aggregate import build

if __name__ == '__main__':
    build()
