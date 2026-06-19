import os
import sys
import logging
from datetime import datetime, timedelta, timezone

import requests
from icalendar import Calendar, Event, vText
import pytz

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

API_BASE = "https://v3.football.api-sports.io"
LEAGUE_ID = 1
SEASON = 2026
ET = pytz.timezone("America/New_York")

STATUS_LABELS = {
    "NS": "Not Started",
    "1H": "First Half",
    "HT": "Half Time",
    "2H": "Second Half",
    "ET": "Extra Time",
    "P": "Penalty Shootout",
    "FT": "Full Time",
    "AET": "Full Time (AET)",
    "PEN": "Full Time (Pens)",
    "PST": "Postponed",
    "CANC": "Cancelled",
    "ABD": "Abandoned",
    "AWD": "Awarded",
    "WO": "Walkover",
    "LIVE": "Live",
}

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
    "South Korea": "🇰🇷", "Mexico": "🇲🇽", "Morocco": "🇲🇦", "Netherlands": "🇳🇱",
    "New Zealand": "🇳🇿", "Nigeria": "🇳🇬", "Norway": "🇳🇴", "Panama": "🇵🇦",
    "Paraguay": "🇵🇾", "Peru": "🇵🇪", "Poland": "🇵🇱", "Portugal": "🇵🇹",
    "Qatar": "🇶🇦", "Romania": "🇷🇴", "Saudi Arabia": "🇸🇦", "Senegal": "🇸🇳",
    "Serbia": "🇷🇸", "Slovakia": "🇸🇰", "Slovenia": "🇸🇮", "South Africa": "🇿🇦",
    "Spain": "🇪🇸", "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Thailand": "🇹🇭",
    "Tunisia": "🇹🇳", "Turkey": "🇹🇷", "Ukraine": "🇺🇦", "United States": "🇺🇸",
    "Uruguay": "🇺🇾", "Venezuela": "🇻🇪", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
}

LIVE_STATUSES = {"1H", "HT", "2H", "ET", "P", "LIVE"}
FINISHED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}


def flag(team_name: str) -> str:
    return FLAG_MAP.get(team_name, "")


def fetch_fixtures(api_key: str) -> list[dict]:
    headers = {"x-apisports-key": api_key}
    resp = requests.get(
        f"{API_BASE}/fixtures",
        headers=headers,
        params={"league": LEAGUE_ID, "season": SEASON},
        timeout=30,
    )
    if resp.status_code != 200:
        log.error("API returned HTTP %s: %s", resp.status_code, resp.text[:200])
        sys.exit(1)

    data = resp.json()
    errors = data.get("errors", {})
    if errors:
        log.error("API errors: %s", errors)
        sys.exit(1)

    fixtures = data.get("response", [])
    log.info("Fetched %d fixtures", len(fixtures))
    return fixtures


def build_event(fixture: dict) -> Event:
    fid = fixture["fixture"]["id"]
    status_short = fixture["fixture"]["status"]["short"]
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    home_goals = fixture["goals"]["home"]
    away_goals = fixture["goals"]["away"]
    venue_name = (fixture["fixture"].get("venue") or {}).get("name") or ""
    venue_city = (fixture["fixture"].get("venue") or {}).get("city") or ""
    round_name = fixture["league"].get("round", "")

    # Parse kickoff time
    kickoff_str = fixture["fixture"]["date"]  # ISO 8601 with timezone
    kickoff_utc = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
    kickoff_utc = kickoff_utc.astimezone(timezone.utc)
    dtend_utc = kickoff_utc + timedelta(hours=2)
    kickoff_et = kickoff_utc.astimezone(ET)

    # Build SUMMARY
    home_flag = flag(home)
    away_flag = flag(away)
    has_score = (
        status_short in LIVE_STATUSES or status_short in FINISHED_STATUSES
    ) and home_goals is not None and away_goals is not None

    if has_score:
        summary = f"{home_flag} {home} {home_goals}–{away_goals} {away} {away_flag}".strip()
    else:
        h = f"{home_flag} {home}".strip()
        a = f"{away} {away_flag}".strip()
        summary = f"{h} vs {a}"

    # Build DESCRIPTION
    kickoff_label = kickoff_et.strftime("%B %-d, %Y at %-I:%M %p ET")
    location_str = ", ".join(filter(None, [venue_name, venue_city]))
    status_label = STATUS_LABELS.get(status_short, status_short)

    desc_lines = [
        f"Round: {round_name}",
        f"Kickoff: {kickoff_label}",
        f"Venue: {location_str}" if location_str else None,
    ]
    if has_score:
        desc_lines.append(f"Score: {home} {home_goals} – {away_goals} {away} ({status_label})")
    else:
        desc_lines.append(f"Status: {status_label}")

    description = "\n".join(line for line in desc_lines if line is not None)

    ev = Event()
    ev.add("UID", vText(f"{fid}@worldcup2026"))
    ev.add("DTSTART", kickoff_utc)
    ev.add("DTEND", dtend_utc)
    ev.add("SUMMARY", summary)
    ev.add("DESCRIPTION", description)
    if location_str:
        ev.add("LOCATION", location_str)
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
    cal.add("REFRESH-INTERVAL;VALUE=DURATION", "PT30M")
    cal.add("X-PUBLISHED-TTL", "PT30M")

    for ev in events:
        cal.add_component(ev)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(cal.to_ical())

    log.info("Wrote %d events to %s", len(events), path)


def main():
    api_key = os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        log.error("API_FOOTBALL_KEY environment variable not set")
        sys.exit(1)

    # Load .env for local dev without requiring python-dotenv at runtime
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get("API_FOOTBALL_KEY", api_key)
    except ImportError:
        pass

    fixtures = fetch_fixtures(api_key)

    missing = [f for f in fixtures if not f.get("fixture", {}).get("date")]
    if missing:
        log.warning("%d fixtures are missing date fields", len(missing))

    events = [build_event(f) for f in fixtures if f.get("fixture", {}).get("date")]
    write_ics(events, "docs/worldcup.ics")


if __name__ == "__main__":
    main()
