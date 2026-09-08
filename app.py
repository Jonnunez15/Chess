from flask import Flask, jsonify, render_template, request
import requests
from collections import defaultdict
from datetime import datetime, timezone

app = Flask(__name__)
BASE = "https://api.chess.com/pub"
HEADERS = {"User-Agent": "jonnunez-chess-analytics/1.0 (personal analytics app)"}


def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def classify(me_result, opp_result):
    if me_result == "win":
        return "W"
    if opp_result == "win":
        return "L"
    return "D"


def load_games(username):
    archives = get_json(f"{BASE}/player/{username}/games/archives").get("archives", [])
    all_games = []
    for url in archives:
        try:
            all_games.extend(get_json(url).get("games", []))
        except requests.RequestException:
            continue
    return all_games


def normalize(games, username):
    uname = username.lower()
    rows = []
    for g in games:
        white = g.get("white", {})
        black = g.get("black", {})
        wn = str(white.get("username", ""))
        bn = str(black.get("username", ""))
        if wn.lower() == uname:
            me, opp, color = white, black, "White"
        elif bn.lower() == uname:
            me, opp, color = black, white, "Black"
        else:
            continue
        ts = g.get("end_time")
        date = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
        rows.append({
            "opponent": opp.get("username", "Unknown"),
            "result": classify(me.get("result"), opp.get("result")),
            "color": color,
            "my_rating": me.get("rating"),
            "opp_rating": opp.get("rating"),
            "time_class": g.get("time_class", "unknown"),
            "time_control": g.get("time_control", ""),
            "rated": g.get("rated", False),
            "date": date,
            "url": g.get("url", "")
        })
    return rows


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["opponent"]].append(row)
    out = []
    for opp, games in groups.items():
        wins = sum(g["result"] == "W" for g in games)
        losses = sum(g["result"] == "L" for g in games)
        draws = sum(g["result"] == "D" for g in games)
        ratings = [g["opp_rating"] for g in games if isinstance(g["opp_rating"], int)]
        n = len(games)
        out.append({
            "opponent": opp,
            "games": n,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "record": f"{wins}-{losses}-{draws}",
            "win_pct": round(100 * wins / n, 1),
            "score_pct": round(100 * (wins + .5 * draws) / n, 1),
            "avg_opp_rating": round(sum(ratings) / len(ratings)) if ratings else None,
            "white_games": sum(g["color"] == "White" for g in games),
            "black_games": sum(g["color"] == "Black" for g in games),
        })
    out.sort(key=lambda x: (x["games"], x["wins"]), reverse=True)
    return out


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/analytics")
def analytics():
    username = request.args.get("username", "jonnunez15").strip()
    if not username:
        return jsonify({"error": "Username is required"}), 400
    try:
        rows = normalize(load_games(username), username)
        if not rows:
            return jsonify({"error": "No public games found for that username"}), 404
        wins = sum(r["result"] == "W" for r in rows)
        losses = sum(r["result"] == "L" for r in rows)
        draws = sum(r["result"] == "D" for r in rows)
        total = len(rows)
        summary = summarize(rows)
        return jsonify({
            "username": username,
            "totals": {
                "games": total,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "score_pct": round(100 * (wins + .5 * draws) / total, 1)
            },
            "top_opponents": summary[:10],
            "opponents": summary,
            "games": rows
        })
    except requests.HTTPError as e:
        return jsonify({"error": f"Chess.com API error: {e}"}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/manifest.webmanifest')
def manifest():
    return app.send_static_file('manifest.webmanifest')


@app.route('/service-worker.js')
def sw():
    return app.send_static_file('service-worker.js')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
