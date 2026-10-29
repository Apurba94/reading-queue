"""Command-line interface for reading-queue."""
import argparse

from .core import STATUSES, ReadingQueue


def _fmt(p):
    return "%4d  P%d  %-8s %s%s" % (p["id"], p["priority"], p["status"], p["title"][:70],
                                   "  <%s>" % (p["url"] or ("https://doi.org/" + p["doi"])) if (p["url"] or p["doi"]) else "")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reading-queue", description="Manage your paper reading list.")
    ap.add_argument("--db", help="SQLite file (default ~/.reading_queue.sqlite or $READING_QUEUE_DB)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="add a paper")
    a.add_argument("title")
    a.add_argument("--url")
    a.add_argument("--doi")
    a.add_argument("-p", "--priority", type=int, default=3, choices=range(1, 6))
    a.add_argument("-t", "--tag", action="append", default=[])
    a.add_argument("--pages", type=int)
    ls = sub.add_parser("list", help="list papers")
    ls.add_argument("-s", "--status", choices=STATUSES)
    ls.add_argument("-t", "--tag")
    ls.add_argument("-q", "--search")
    sub.add_parser("next", help="show what to read next")
    for name in ("start", "done", "skip"):
        s = sub.add_parser(name)
        s.add_argument("id", type=int)
        if name == "done":
            s.add_argument("-r", "--rating", type=int, choices=range(1, 6))
    n = sub.add_parser("note")
    n.add_argument("id", type=int)
    n.add_argument("text")
    r = sub.add_parser("rm")
    r.add_argument("id", type=int)
    sub.add_parser("stats")
    args = ap.parse_args(argv)

    q = ReadingQueue(args.db)
    try:
        if args.cmd == "add":
            print("added #%d" % q.add(args.title, args.url, args.doi, args.priority, args.tag, args.pages))
        elif args.cmd == "list":
            for p in q.list(args.status, args.tag, args.search):
                print(_fmt(p))
        elif args.cmd == "next":
            p = q.next()
            print(_fmt(p) if p else "Queue is empty.")
        elif args.cmd in ("start", "done", "skip"):
            status = {"start": "reading", "done": "read", "skip": "skipped"}[args.cmd]
            q.set_status(args.id, status, getattr(args, "rating", None))
            print("#%d -> %s" % (args.id, status))
        elif args.cmd == "note":
            q.note(args.id, args.text)
        elif args.cmd == "rm":
            q.remove(args.id)
        elif args.cmd == "stats":
            s = q.stats()
            print("  ".join("%s: %d" % kv for kv in s["counts"].items()))
            print("finished in last %d days: %d; mean days to finish: %s" %
                  (s["days"], s["finished_recently"], s["mean_days_to_finish"]))
            if s["top_tags"]:
                print("top tags: " + ", ".join("%s (%d)" % t for t in s["top_tags"]))
    except (KeyError, ValueError) as exc:
        print("error: %s" % exc)
        return 1
    finally:
        q.close()
    return 0
