#!/usr/bin/env python3
"""Build step for the Sports Elo model.

Bundles recent results (with bookmaker odds) for the top-5 European soccer
leagues from football-data.co.uk, a keyless CSV source. Odds let the tool
benchmark the Elo model against the betting market. No API key.

Re-run to refresh / extend: `python3 build.py`.
"""
import csv
import io
import json
import sys
import urllib.request
from datetime import date, datetime

BASE = "https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
LEAGUES = [("E0", "Premier League"), ("SP1", "La Liga"), ("D1", "Bundesliga"),
           ("I1", "Serie A"), ("F1", "Ligue 1")]
SEASONS = ["2223", "2324", "2425", "2526", "2627"]  # label index -> see SEASON_LABELS
SEASON_LABELS = ["2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]
EPOCH = date(2000, 1, 1)
UA = {"User-Agent": "elo-sports-build/1.0"}


def fetch(div, season):
    url = BASE.format(season=season, div=div)
    last = None
    for _ in range(4):  # football-data occasionally drops the TLS connection
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("latin-1")
        except Exception as e:
            last = e
    raise last


def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def num(x):
    try:
        return round(float(x), 2)
    except (ValueError, TypeError):
        return None


def main():
    teams_by_league, matches_by_league = {}, {}
    for div, name in LEAGUES:
        idx = {}        # team -> index
        rows = []       # (date, hi, ai, hg, ag, sIdx, oH, oD, oA)
        for sIdx, season in enumerate(SEASONS):
            try:
                text = fetch(div, season)
            except Exception as e:
                sys.stderr.write("  %s %s: fetch failed (%s)\n" % (div, season, e))
                continue
            reader = csv.DictReader(io.StringIO(text))
            n = 0
            for row in reader:
                ht, at = (row.get("HomeTeam") or "").strip(), (row.get("AwayTeam") or "").strip()
                d = parse_date(row.get("Date") or "")
                hg, ag = row.get("FTHG"), row.get("FTAG")
                if not ht or not at or d is None or hg in (None, "") or ag in (None, ""):
                    continue
                try:
                    hg, ag = int(float(hg)), int(float(ag))
                except ValueError:
                    continue
                for t in (ht, at):
                    if t not in idx:
                        idx[t] = len(idx)
                rows.append((d, idx[ht], idx[at], hg, ag, sIdx,
                             num(row.get("B365H") or row.get("AvgH") or row.get("PSH")),
                             num(row.get("B365D") or row.get("AvgD") or row.get("PSD")),
                             num(row.get("B365A") or row.get("AvgA") or row.get("PSA"))))
                n += 1
            sys.stderr.write("  %-4s %s: %d matches\n" % (div, season, n))
        rows.sort(key=lambda r: r[0])
        teams = [None] * len(idx)
        for t, i in idx.items():
            teams[i] = t
        teams_by_league[div] = teams
        matches_by_league[div] = [
            [r[5], (r[0] - EPOCH).days, r[1], r[2], r[3], r[4], r[6], r[7], r[8]] for r in rows
        ]
        sys.stderr.write("%s (%s): %d teams, %d matches\n" % (div, name, len(teams), len(rows)))

    bundle = {
        "built": date.today().isoformat(),
        "seasons": SEASON_LABELS,
        "leagues": [{"id": d, "name": n} for d, n in LEAGUES],
        "teams": teams_by_league,
        "matches": matches_by_league,
    }
    payload = json.dumps(bundle, separators=(",", ":"))
    with open("index.template.html") as f:
        template = f.read()
    html = template.replace("/*__DATA__*/", payload)
    with open("index.html", "w") as f:
        f.write(html)
    sys.stderr.write("wrote index.html (%d KB)\n" % (len(html) // 1024))


if __name__ == "__main__":
    main()
