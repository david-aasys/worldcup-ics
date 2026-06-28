import json

with open("/tmp/matches.json") as f:
    data = json.load(f)

matches = data.get("matches", [])
print(f"Total matches returned: {len(matches)}")
for m in matches[:5]:
    home = (m.get("homeTeam") or {}).get("name", "?")
    away = (m.get("awayTeam") or {}).get("name", "?")
    print(f"  ID={m['id']}  {m.get('utcDate','')}  {home} vs {away}")
