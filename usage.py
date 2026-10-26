import csv, glob, json, os, sys
from collections import OrderedDict

W = {"input_tokens": 1, "output_tokens": 5,
     "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1}
LIMIT_5H   = 7_500_000    # placeholder, calibrate!
LIMIT_WEEK = 37_500_000   # placeholder, calibrate!
K = list(W)

FULL  = "--full" in sys.argv
CSV   = "--csv" in sys.argv
COUNT = "--count" in sys.argv
PATHS = [a for a in sys.argv[1:] if not a.startswith("--")]
if "--last" in sys.argv:   # newest session .jsonl next to this script
    here = os.path.dirname(os.path.abspath(__file__))
    found = glob.glob(os.path.join(here, "*.jsonl"))
    if not found: sys.exit(f"no .jsonl files in {here}")
    PATHS.append(max(found, key=os.path.getmtime))
if "--today" in sys.argv:  # --count over every session .jsonl touched today (+ their subagents)
    import datetime
    here = os.path.dirname(os.path.abspath(__file__))
    today = datetime.date.today()
    found = [f for f in glob.glob(os.path.join(here, "*.jsonl"))
             if datetime.date.fromtimestamp(os.path.getmtime(f)) == today]
    if not found: sys.exit(f"no .jsonl files modified today in {here}")
    PATHS += sorted(found, key=os.path.getmtime)
    COUNT = True
if "--sub" in sys.argv:    # --sub <id prefix>: detailed view of one subagent file
    i = sys.argv.index("--sub")
    if i + 1 >= len(sys.argv): sys.exit("usage: --sub <agent id prefix>")
    pre = sys.argv[i + 1]
    PATHS = [a for a in PATHS if a != pre]
    here = os.path.dirname(os.path.abspath(__file__))
    found = glob.glob(os.path.join(here, "**", "subagents", "**", pre + "*.jsonl"), recursive=True)
    if not found: sys.exit(f"no subagent file starting with {pre}")
    if len(found) > 1: sys.exit("more than one match:\n" + "\n".join(found))
    PATHS.append(found[0])

def short(s, n=160):
    s = " ".join(str(s).split())
    return s if n is None else s[:n] + ("…" if len(s) > n else "")

def describe(b):
    if b.get("type") == "text":
        return "SAYS: " + short(b["text"], None)
    if b.get("type") == "tool_use":
        i = b.get("input", {})
        d = (i.get("prompt") or i.get("description") or i.get("command")
             or i.get("file_path") or i.get("pattern") or json.dumps(i))
        return f"{b['name']}: " + short(d, None)

def parse(path):
    groups, allcalls = [], {}
    in_sub = "subagents" in path.split(os.sep)   # subagent files are all sidechain
    for line in open(path, encoding="utf-8"):
        try: e = json.loads(line)
        except ValueError: continue
        m = e.get("message") or {}
        if e.get("type") == "user" and (in_sub or not e.get("isSidechain")) and not e.get("isMeta"):
            c = m.get("content")
            if isinstance(c, list):
                if any(b.get("type") == "tool_result" for b in c): continue
                c = " ".join(b.get("text", "") for b in c)
            if c: groups.append((c, OrderedDict()))
        elif e.get("type") == "assistant" and m.get("usage"):
            mid = m.get("id") or e.get("uuid")
            allcalls[mid] = m["usage"]
            if groups:
                call = groups[-1][1].setdefault(mid, {"u": None, "d": []})
                call["u"] = m["usage"]
                for b in (m.get("content") or []):
                    if isinstance(b, dict) and (x := describe(b)): call["d"].append(x)
    return groups, allcalls

def sub_files(path):
    """<session>.jsonl -> <session>/subagents/**/*.jsonl"""
    d = os.path.splitext(path)[0]
    return sorted(glob.glob(os.path.join(d, "subagents", "**", "*.jsonl"), recursive=True))

def first_prompt(path):
    """first user message of a subagent file (= the task it was given)"""
    for line in open(path, encoding="utf-8"):
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("type") == "user":
            c = (e.get("message") or {}).get("content")
            if isinstance(c, list):
                c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
            if c: return short(c, 60)
    return "(no prompt)"

def sub_totals(path, seen):
    """per-subagent token totals; `seen` = message ids already counted (dedupe)"""
    out = []
    for sf in sub_files(path):
        _, calls = parse(sf)
        t, n = dict.fromkeys(K, 0), 0
        for mid, u in calls.items():
            if mid in seen: continue
            seen.add(mid); n += 1
            for k in K: t[k] += u.get(k, 0)
        out.append((sf, n, t))
    return out

def wt(u): return {k: u.get(k, 0) * W[k] for k in K}
def wsum(t): return sum(t[k] * W[k] for k in K)

def pct_line(w):
    return f"{w:,.0f} -> {w/LIMIT_5H*100:.1f}% of 5h limit | {w/LIMIT_WEEK*100:.1f}% of weekly limit"

# ---------- --count mode ----------
def count_mode():
    seen, grand, grand_sub, rows = set(), dict.fromkeys(K, 0), 0, []
    hdr = (f"{'file':<40} {'in':>10} {'out':>10} {'c.write':>12} {'c.read':>13} "
           f"{'weighted':>12} {'of which sub':>13}")
    print(hdr); print("-" * len(hdr))
    for p in PATHS:
        _, allcalls = parse(p)
        t = dict.fromkeys(K, 0)
        for mid, u in allcalls.items():
            if mid in seen: continue          # same message in a resumed session: count once
            seen.add(mid)
            for k in K: t[k] += u.get(k, 0)
        main_w = wsum(t)
        sub_w, nsub = 0, 0
        for sf, n, st in sub_totals(p, seen):  # subagents of this session
            nsub += 1
            sub_w += wsum(st)
            for k in K: t[k] += st[k]
        w = main_w + sub_w
        for k in K: grand[k] += t[k]
        grand_sub += sub_w
        rows.append([os.path.basename(p), *[t[k] for k in K], round(w, 1), nsub, round(sub_w, 1)])
        print(f"{short(os.path.basename(p), 38):<40} {t[K[0]]:>10,} {t[K[1]]:>10,} "
              f"{t[K[2]]:>12,} {t[K[3]]:>13,} {w:>12,.0f} {sub_w:>13,.0f}")
    gw = wsum(grand)
    print("-" * len(hdr))
    print(f"{'TOTAL':<40} {grand[K[0]]:>10,} {grand[K[1]]:>10,} {grand[K[2]]:>12,} {grand[K[3]]:>13,} "
          f"{gw:>12,.0f} {grand_sub:>13,.0f}")
    print(f"\nWEIGHTED TOTAL (incl. subagents): {pct_line(gw)}")
    print(f"  of which subagents: {pct_line(grand_sub)}")
    if CSV:
        with open("usage_count.csv", "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f)
            wr.writerow(["file", "in_tokens", "out_tokens", "cache_write_tokens",
                         "cache_read_tokens", "weighted_total", "subagent_files", "subagent_weighted"])
            wr.writerows(rows)
            wr.writerow(["TOTAL", *[grand[k] for k in K], round(gw, 1), "", round(grand_sub, 1)])
        print("CSV written: usage_count.csv")

# ---------- detailed mode ----------
def detailed(path):
    groups, allcalls = parse(path)
    csv_path = os.path.splitext(os.path.basename(path))[0] + ".csv"
    tot, tot_w, csv_rows = dict.fromkeys(K, 0), 0, []
    print(f"\n######## {os.path.basename(path)}")
    for i, (p, calls) in enumerate(groups, 1):
        rows = [(" | ".join(c["d"]) or "(no text)", wt(c["u"]), c["u"]) for c in calls.values()]
        ptotal = sum(sum(r[1].values()) for r in rows) or 1
        print(f"\n=== YOUR PROMPT #{i}: {p.strip() if FULL else short(p, 300)}")
        print(f"{'#':>3}  {'what it did':<60} {'in':>6} {'out':>6} {'c.write':>8} {'c.read':>7} {'TOTAL':>7}")
        for n, (d, w, u) in enumerate(rows, 1):
            pc = [w[k] / ptotal * 100 for k in K]
            print(f"{n:>3}  {short(d, 58):<60} {pc[0]:>5.1f}% {pc[1]:>5.1f}% {pc[2]:>7.1f}% {pc[3]:>6.1f}% {sum(w.values())/ptotal*100:>6.1f}%")
            csv_rows.append([i, short(p, None), n, d, *[u.get(k, 0) for k in K],
                             round(sum(w.values()), 1), *[round(x, 2) for x in pc],
                             round(sum(w.values()) / ptotal * 100, 2)])
        col = [sum(r[1][k] for r in rows) / ptotal * 100 for k in K]
        print(f"{'':>3}  {'SUM (share of this prompt)':<60} {col[0]:>5.1f}% {col[1]:>5.1f}% {col[2]:>7.1f}% {col[3]:>6.1f}% {'100.0%':>7}")
        if FULL:
            for n, (d, _, _) in enumerate(rows, 1):
                print(f"  [{n}] {d}")
        for c in calls.values():
            for k in K: tot[k] += c["u"].get(k, 0)
        tot_w += ptotal
    chk = {k: sum(u.get(k, 0) for u in allcalls.values()) for k in K}
    print("\nCHECK:", "OK" if chk == tot else f"MISMATCH {chk}")
    print(f"MAIN SESSION WEIGHTED TOTAL: {pct_line(tot_w)}")

    # ----- subagents -----
    subs = sub_totals(path, set(allcalls))     # skip calls already in the main file
    sub_w = 0
    if subs:
        print(f"\n--- SUBAGENTS ({len(subs)}) ---")
        print(f"{'subagent':<24} {'task':<42} {'calls':>5} {'in':>9} {'out':>9} {'c.write':>11} {'c.read':>12} {'weighted':>11}")
        for sf, n, t in subs:
            w = wsum(t); sub_w += w
            print(f"{short(os.path.basename(sf), 22):<24} {first_prompt(sf)[:40]:<42} {n:>5} "
                  f"{t[K[0]]:>9,} {t[K[1]]:>9,} {t[K[2]]:>11,} {t[K[3]]:>12,} {w:>11,.0f}")
            csv_rows.append(["subagent", os.path.basename(sf), n, first_prompt(sf),
                             *[t[k] for k in K], round(w, 1), "", "", "", "", ""])
        print(f"SUBAGENTS WEIGHTED TOTAL: {pct_line(sub_w)}")
    else:
        print("\n(no subagents found)")
    print(f"\nGRAND TOTAL (main + subagents): {pct_line(tot_w + sub_w)}")
    if CSV:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f)
            wr.writerow(["prompt_no", "your_prompt", "call_no", "what_it_did",
                         "in_tokens", "out_tokens", "cache_write_tokens", "cache_read_tokens",
                         "weighted_total", "in_%_of_prompt", "out_%_of_prompt",
                         "cache_write_%_of_prompt", "cache_read_%_of_prompt", "total_%_of_prompt"])
            wr.writerows(csv_rows)
            wr.writerow(["TOTAL main", "", "", "", *[tot[k] for k in K], round(tot_w, 1), "", "", "", "", ""])
            wr.writerow(["TOTAL main+subagents", "", "", "", "", "", "", "", round(tot_w + sub_w, 1), "", "", "", "", ""])
        print(f"CSV written: {csv_path}")

if COUNT: count_mode()
else:
    for p in PATHS: detailed(p)