import os
import sys
import logging
import traceback
from datetime import datetime, timedelta, timezone

import requests
from icalendar import Calendar, Event, vText, vDuration
import pytz

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

API_BASE = "https://api.football-data.org/v4"
COMPETITION = "WC"
ET = pytz.timezone("America/New_York")

STATUS_LABELS = {
    "SCHEDULED": "Not Started",
    "TIMED": "Not Started",
    "IN_PLAY": "Live",
    "PAUSED": "Half Time",
    "FINISHED": "Full Time",
    "POSTPONED": "Postponed",
    "SUSPENDED": "Suspended",
    "CANCELLED": "Cancelled",
}

LIVE_STATUSES = {"IN_PLAY", "PAUSED"}
FINISHED_STATUSES = {"FINISHED"}

FLAG_MAP = {
    "Afghanistan": "🇦🇫", "Albania": "🇦🇱", "Algeria": "🇩🇿", "Argentina": "🇦🇷",
    "Australia": "🇦🇺", "Austria": "🇦🇹", "Belgium": "🇧🇪", "Bolivia": "🇧🇴",
    "Brazil": "🇧🇷", "Cameroon": "🇨🇲", "Canada": "🇨🇦", "Chile": "🇨🇱",
    "China": "🇨🇳", "Colombia": "🇨🇴", "Costa Rica": "🇨🇷", "Croatia": "🇭🇷",
    "Czech Republic": "🇨🇿", "Denmark": "🇩🇰", "Ecuador": "🇪🇨", "Egypt": "🇪🇬",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "France": "🇫🇷", "Germany": "🇩🇪", "Ghana": "🇬🇭",
    "Greece": "🇬🇷", "Honduras": "🇭🇳", "Hungary": "🇭🇺", "Iran": "🇮🇷",
    "Iraq": "🇮🇶", "Israel": "🇮🇱", "Italy": "🇮🇹", "Ivory Coast": "🇨🇮",
    "Jamaica": "🇯🇲", "Japan": "🇯🇵", "Jordan": "🇯🇴", "Kenya": "🇰🇪",
    "Korea Republic": "🇰🇷", "Mexico": "🇲🇽", "Morocco": "🇲🇦", "Netherlands": "🇳🇱",
    "New Zealand": "🇳🇿", "Nigeria": "🇳🇬", "Norway": "🇳🇴", "Panama": "🇵🇦",
    "Paraguay": "🇵🇾", "Peru": "🇵🇪", "Poland": "🇵🇱", "Portugal": "🇵🇹",
    "Qatar": "🇶🇦", "Romania": "🇷🇴", "Saudi Arabia": "🇸🇦", "Senegal": "🇸🇳",
    "Serbia": "🇷🇸", "Slovakia": "🇸🇰", "Slovenia": "🇸🇮", "South Africa": "🇿🇦",
    "Spain": "🇪🇸", "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Thailand": "🇹🇭",
    "Tunisia": "🇹🇳", "Turkey": "🇹🇷", "Ukraine": "🇺🇦", "United States": "🇺🇸",
    "Uruguay": "🇺🇾", "Venezuela": "🇻🇪", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
}


def flag(team_name: str) -> str:
    return FLAG_MAP.get(team_name, "")


def fetch_matches(api_key: str) -> list[dict]:
    headers = {"X-Auth-Token": api_key}
    resp = requests.get(
        f"{API_BASE}/competitions/{COMPETITION}/matches",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 403:
        log.error("API returned 403 Forbidden — check that your football-data.org key has access to the World Cup competition.")
        sys.exit(1)
    if resp.status_code != 200:
        log.error("API returned HTTP %s: %s", resp.status_code, resp.text[:300])
        sys.exit(1)

    data = resp.json()
    matches = data.get("matches", [])
    log.info("Fetched %d matches", len(matches))
    return matches


def build_event(match: dict) -> Event:
    mid = match["id"]
    status = match.get("status", "SCHEDULED")
    home = (match.get("homeTeam") or {}).get("name") or "TBD"
    away = (match.get("awayTeam") or {}).get("name") or "TBD"
    score = match.get("score", {})
    full_time = score.get("fullTime") or {}
    home_goals = full_time.get("home")
    away_goals = full_time.get("away")
    venue = match.get("venue") or ""
    stage = match.get("stage", "").replace("_", " ").title()
    group = match.get("group") or ""
    round_label = f"{stage} – {group}" if group else stage

    # Parse kickoff
    kickoff_str = match["utcDate"]  # "2026-06-11T16:00:00Z"
    kickoff_utc = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    dtend_utc = kickoff_utc + timedelta(hours=2)
    kickoff_et = kickoff_utc.astimezone(ET)

    # SUMMARY
    home_flag = flag(home)
    away_flag = flag(away)
    has_score = (
        status in LIVE_STATUSES or status in FINISHED_STATUSES
    ) and home_goals is not None and away_goals is not None

    if has_score:
        summary = f"{home_flag} {home} {home_goals}–{away_goals} {away} {away_flag}".strip()
    else:
        h = f"{home_flag} {home}".strip()
        a = f"{away} {away_flag}".strip()
        summary = f"{h} vs {a}"

    # DESCRIPTION
    kickoff_label = kickoff_et.strftime("%B %-d, %Y at %-I:%M %p ET")
    status_label = STATUS_LABELS.get(status, status)

    desc_lines = [
        f"Round: {round_label}",
        f"Kickoff: {kickoff_label}",
        f"Venue: {venue}" if venue else None,
    ]
    if has_score:
        desc_lines.append(f"Score: {home} {home_goals} – {away_goals} {away} ({status_label})")
    else:
        desc_lines.append(f"Status: {status_label}")

    description = "\n".join(line for line in desc_lines if line is not None)

    ev = Event()
    ev.add("UID", vText(f"{mid}@worldcup2026"))
    ev.add("DTSTART", kickoff_utc)
    ev.add("DTEND", dtend_utc)
    ev.add("SUMMARY", summary)
    ev.add("DESCRIPTION", description)
    if venue:
        ev.add("LOCATION", venue)
    ev.add("STATUS", "CONFIRMED")
    ev.add("LAST-MODIFIED", datetime.now(timezone.utc))

    return ev


def write_ics(events: list[Event], path: str):
    cal = Calendar()
    cal.add("VERSION", "2.0")
    cal.add("PRODID", "-//WorldCup2026//EN")
    cal.add("X-WR-CALNAME", "2026 FIFA World Cup")
    cal.add("X-WR-TIMEZONE", "America/New_York")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")
    refresh = vDuration(timedelta(minutes=30))
    refresh.params["VALUE"] = "DURATION"
    cal.add("REFRESH-INTERVAL", refresh)
    cal.add("X-PUBLISHED-TTL", "PT30M")

    for ev in events:
        cal.add_component(ev)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(cal.to_ical())

    log.info("Wrote %d events to %s", len(events), path)


def main():
    api_key = os.environ.get("FOOTBALL_DATA_KEY")
    if not api_key:
        log.error("FOOTBALL_DATA_KEY environment variable not set")
        sys.exit(1)

    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("FOOTBALL_DATA_KEY", api_key)
    except ImportError:
        pass

    matches = fetch_matches(api_key)

    missing = [m for m in matches if not m.get("utcDate")]
    if missing:
        log.warning("%d matches are missing utcDate fields", len(missing))

    events = [build_event(m) for m in matches if m.get("utcDate")]
    write_ics(events, "docs/worldcup.ics")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
