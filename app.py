from flask import Flask, jsonify, render_template, request
import requests
import time
from collections import defaultdict
from datetime import datetime, timezone

app = Flask(__name__)

BASE = "https://api.chess.com/pub"

HEADERS = {
    "User-Agent": "jonnunez-chess-analytics/1.0 (personal analytics app)"
}

CACHE = {}
CACHE_TTL = 60


# =========================================================
# CHESS.COM API
# =========================================================

def get_json(url, retries=5):
    for attempt in range(retries):
        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=60
            )

            # Don't waste time retrying missing archives
            if r.status_code == 404:
                r.raise_for_status()

            if r.status_code == 429:
                wait = 2 ** attempt
                print(f"Rate limited. Waiting {wait} seconds...")
                time.sleep(wait)
                continue

            r.raise_for_status()
            return r.json()

        except requests.HTTPError:
            raise

        except requests.RequestException as e:
            if attempt == retries - 1:
                raise

            wait = 2 ** attempt

            print(
                f"Request failed: {e}. "
                f"Retrying in {wait} seconds..."
            )

            time.sleep(wait)

    return {}


def load_games(username):
    username = username.lower()

    now = time.time()

    if username not in CACHE:
        CACHE[username] = {
            "archives": {},
            "last_check": 0
        }

    user_cache = CACHE[username]

    # Recent request: use memory cache only
    if (
        user_cache["archives"]
        and now - user_cache["last_check"] < CACHE_TTL
    ):
        print(f"Using cached games for {username}")

        all_games = []

        for games in user_cache["archives"].values():
            all_games.extend(games)

        print(f"Cache contains {len(all_games)} games")

        return all_games

    archive_data = get_json(
        f"{BASE}/player/{username}/games/archives"
    )

    archives = archive_data.get("archives", [])

    print(
        f"Found {len(archives)} monthly archives "
        f"for {username}"
    )

    if not archives:
        return []

    latest_archive = archives[-1]

    for i, url in enumerate(archives):

        already_cached = (
            url in user_cache["archives"]
        )

        # Old months never need to be downloaded again
        if (
            already_cached
            and url != latest_archive
        ):
            print(
                f"Archive {i + 1}/{len(archives)} cached"
            )
            continue

        try:
            data = get_json(url)

            games = data.get("games", [])

            user_cache["archives"][url] = games

            if already_cached:
                print(
                    f"Refreshed archive "
                    f"{i + 1}/{len(archives)} "
                    f"- {len(games)} games"
                )
            else:
                print(
                    f"Downloaded archive "
                    f"{i + 1}/{len(archives)} "
                    f"- {len(games)} games"
                )

            time.sleep(0.15)

        except requests.HTTPError as e:
            print(
                f"Skipping archive "
                f"{i + 1}/{len(archives)}: {e}"
            )
            continue

        except requests.RequestException as e:
            print(
                f"Failed archive "
                f"{i + 1}/{len(archives)}: {e}"
            )
            continue

    user_cache["last_check"] = now

    all_games = []

    for url in archives:
        all_games.extend(
            user_cache["archives"].get(url, [])
        )

    print(
        f"Finished loading {username}: "
        f"{len(all_games)} games"
    )

    return all_games


# =========================================================
# NORMALIZE GAMES
# =========================================================

def classify(me_result, opp_result):
    if me_result == "win":
        return "W"

    if opp_result == "win":
        return "L"

    return "D"


def normalize(games, username):
    uname = username.lower()

    rows = []

    for g in games:

        white = g.get("white", {})
        black = g.get("black", {})

        wn = str(white.get("username", ""))
        bn = str(black.get("username", ""))

        if wn.lower() == uname:
            me = white
            opp = black
            color = "White"

        elif bn.lower() == uname:
            me = black
            opp = white
            color = "Black"

        else:
            continue

        ts = g.get("end_time")

        if ts:
            date = datetime.fromtimestamp(
                ts,
                tz=timezone.utc
            ).isoformat()
        else:
            date = None

        rows.append({
            "opponent": opp.get(
                "username",
                "Unknown"
            ),

            "result": classify(
                me.get("result"),
                opp.get("result")
            ),

            "color": color,

            "my_rating": me.get("rating"),

            "opp_rating": opp.get("rating"),

            "time_class": g.get(
                "time_class",
                "unknown"
            ),

            "time_control": g.get(
                "time_control",
                ""
            ),

            "rated": g.get(
                "rated",
                False
            ),

            "date": date,

            "timestamp": ts,

            "url": g.get(
                "url",
                ""
            )
        })

    rows.sort(
        key=lambda x: x["timestamp"] or 0
    )

    return rows


# =========================================================
# OPPONENT SUMMARY
# =========================================================

def summarize(rows):

    groups = defaultdict(list)

    for row in rows:
        groups[row["opponent"]].append(row)

    out = []

    for opp, games in groups.items():

        wins = sum(
            g["result"] == "W"
            for g in games
        )

        losses = sum(
            g["result"] == "L"
            for g in games
        )

        draws = sum(
            g["result"] == "D"
            for g in games
        )

        ratings = [
            g["opp_rating"]
            for g in games
            if isinstance(g["opp_rating"], int)
        ]

        n = len(games)

        out.append({
            "opponent": opp,
            "games": n,
            "wins": wins,
            "losses": losses,
            "draws": draws,

            "record":
                f"{wins}-{losses}-{draws}",

            "win_pct": round(
                100 * wins / n,
                1
            ),

            "score_pct": round(
                100
                * (wins + 0.5 * draws)
                / n,
                1
            ),

            "avg_opp_rating": (
                round(
                    sum(ratings)
                    / len(ratings)
                )
                if ratings
                else None
            ),

            "white_games": sum(
                g["color"] == "White"
                for g in games
            ),

            "black_games": sum(
                g["color"] == "Black"
                for g in games
            )
        })

    out.sort(
        key=lambda x: (
            x["games"],
            x["wins"]
        ),
        reverse=True
    )

    return out


# =========================================================
# TIME CONTROL ANALYTICS
# =========================================================

def time_control_stats(rows):

    groups = defaultdict(list)

    for row in rows:
        groups[row["time_class"]].append(row)

    results = []

    for tc, games in groups.items():

        n = len(games)

        wins = sum(
            g["result"] == "W"
            for g in games
        )

        losses = sum(
            g["result"] == "L"
            for g in games
        )

        draws = sum(
            g["result"] == "D"
            for g in games
        )

        ratings = [
            g["my_rating"]
            for g in games
            if isinstance(g["my_rating"], int)
        ]

        opp_ratings = [
            g["opp_rating"]
            for g in games
            if isinstance(g["opp_rating"], int)
        ]

        results.append({
            "time_class": tc,
            "games": n,
            "wins": wins,
            "losses": losses,
            "draws": draws,

            "record":
                f"{wins}-{losses}-{draws}",

            "score_pct": round(
                100
                * (wins + 0.5 * draws)
                / n,
                1
            ),

            "avg_rating": (
                round(sum(ratings) / len(ratings))
                if ratings
                else None
            ),

            "avg_opp_rating": (
                round(
                    sum(opp_ratings)
                    / len(opp_ratings)
                )
                if opp_ratings
                else None
            ),

            "peak_rating": (
                max(ratings)
                if ratings
                else None
            )
        })

    results.sort(
        key=lambda x: x["games"],
        reverse=True
    )

    return results


# =========================================================
# RATING HISTORY
# =========================================================

def rating_history(rows):

    # Keep one rating per day per time class.
    # This keeps the response much smaller than sending
    # 28,000 chart points.

    daily = {}

    for g in rows:

        if not g["date"]:
            continue

        if not isinstance(
            g["my_rating"],
            int
        ):
            continue

        tc = g["time_class"]

        if tc not in {
            "bullet",
            "blitz",
            "rapid"
        }:
            continue

        day = g["date"][:10]

        key = (
            tc,
            day
        )

        daily[key] = {
            "date": day,
            "rating": g["my_rating"],
            "time_class": tc
        }

    history = {
        "bullet": [],
        "blitz": [],
        "rapid": []
    }

    for item in daily.values():
        history[
            item["time_class"]
        ].append({
            "date": item["date"],
            "rating": item["rating"]
        })

    for tc in history:
        history[tc].sort(
            key=lambda x: x["date"]
        )

    return history


# =========================================================
# RIVALS
# =========================================================

def rivalry_stats(summary):

    qualified = [
        o
        for o in summary
        if o["games"] >= 5
    ]

    if not qualified:
        return {
            "nemesis": None,
            "punching_bag": None,
            "closest_rival": None
        }

    nemesis = max(
        qualified,
        key=lambda x: (
            x["losses"],
            -x["score_pct"]
        )
    )

    punching_bag = max(
        qualified,
        key=lambda x: (
            x["wins"],
            x["score_pct"]
        )
    )

    close_candidates = [
        o
        for o in qualified
        if o["games"] >= 10
    ]

    closest_rival = None

    if close_candidates:
        closest_rival = min(
            close_candidates,
            key=lambda x: (
                abs(x["score_pct"] - 50),
                -x["games"]
            )
        )

    return {
        "nemesis": nemesis,
        "punching_bag": punching_bag,
        "closest_rival": closest_rival
    }


# =========================================================
# BIGGEST UPSET WINS
# =========================================================

def biggest_upsets(rows):

    wins = []

    for g in rows:

        if g["result"] != "W":
            continue

        if not isinstance(
            g["my_rating"],
            int
        ):
            continue

        if not isinstance(
            g["opp_rating"],
            int
        ):
            continue

        difference = (
            g["opp_rating"]
            - g["my_rating"]
        )

        if difference <= 0:
            continue

        wins.append({
            "opponent": g["opponent"],
            "my_rating": g["my_rating"],
            "opp_rating": g["opp_rating"],
            "rating_difference": difference,
            "time_class": g["time_class"],
            "date": (
                g["date"][:10]
                if g["date"]
                else None
            ),
            "color": g["color"],
            "url": g["url"]
        })

    wins.sort(
        key=lambda x: x["rating_difference"],
        reverse=True
    )

    return wins[:10]


# =========================================================
# FLASK ROUTES
# =========================================================

@app.route("/")
def home():
    return render_template(
        "index.html"
    )


@app.route("/api/analytics")
def analytics():

    username = request.args.get(
        "username",
        "jonnunez152"
    ).strip()

    if not username:
        return jsonify({
            "error": "Username is required"
        }), 400

    try:

        games = load_games(username)

        rows = normalize(
            games,
            username
        )

        if not rows:
            return jsonify({
                "error":
                    "No public games found "
                    "for that username"
            }), 404

        wins = sum(
            r["result"] == "W"
            for r in rows
        )

        losses = sum(
            r["result"] == "L"
            for r in rows
        )

        draws = sum(
            r["result"] == "D"
            for r in rows
        )

        total = len(rows)

        summary = summarize(rows)

        return jsonify({

            "username": username,

            "totals": {
                "games": total,
                "wins": wins,
                "losses": losses,
                "draws": draws,

                "score_pct": round(
                    100
                    * (
                        wins
                        + 0.5 * draws
                    )
                    / total,
                    1
                )
            },

            "top_opponents":
                summary[:10],

            "opponents":
                summary,

            "time_controls":
                time_control_stats(rows),

            "rating_history":
                rating_history(rows),

            "rivals":
                rivalry_stats(summary),

            "biggest_upsets":
                biggest_upsets(rows),

            "games":
                rows
        })

    except requests.HTTPError as e:

        return jsonify({
            "error":
                f"Chess.com API error: {e}"
        }), 502

    except requests.RequestException as e:

        return jsonify({
            "error":
                f"Network error: {e}"
        }), 502

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


@app.route("/manifest.webmanifest")
def manifest():
    return app.send_static_file(
        "manifest.webmanifest"
    )


@app.route("/service-worker.js")
def sw():
    return app.send_static_file(
        "service-worker.js"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
