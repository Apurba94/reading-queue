# reading-queue

**A command-line reading list for papers: priorities, tags, progress tracking and reading
statistics, stored in a single SQLite file you own.**

Part of the *Research Automation Toolkit*: 100 open tools for daily research work.

## Why

Researchers collect far more papers than they can read. Browser tabs, "to read" folders and
starred e-mails do not answer the important question: *what should I read next?* `reading-queue`
keeps one prioritized list, tells you the next paper, and shows how your backlog evolves.

## Features

- Add papers with URL/DOI, priority 1 (urgent) to 5, tags, page count
- Statuses `to-read`, `reading`, `read`, `skipped` with automatic start/finish dates
- `next` command: the paper in progress, otherwise the highest-priority oldest paper
- Notes, ratings, tag and full-text filters
- Statistics: backlog per status, papers finished in the last 30 days, mean days from adding to
  finishing, most used tags
- Duplicate DOIs rejected; data in `~/.reading_queue.sqlite` (or `$READING_QUEUE_DB`, `--db`)

## Usage

```bash
pip install .
reading-queue add "Attention Is All You Need" --doi 10.48550/arXiv.1706.03762 -p 1 -t nlp
reading-queue next
reading-queue start 1
reading-queue note 1 "Key idea: self-attention replaces recurrence"
reading-queue done 1 -r 5
reading-queue list -s to-read -t nlp
reading-queue stats
```

## Testing

```bash
python -m unittest discover -s tests -t .
```

## License

MIT (c) JANIN A APURBA
