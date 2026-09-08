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

# ---------------------------------------------------------
# CACHE
# ---------------------------------------------------------

# One cache entry per Chess.com username.
#
# Structure:
#
# CACHE["username"] = {
#     "archives": {
#         "archive_url": [game, game, game...]
#     },
#     "last_check": timestamp
# }
#
CACHE = {}

# Don't hit Chess.com again if the same account was analyzed
# within the last 60 seconds.
CACHE_TTL = 60


def get_json(url, retries=5):
    for attempt in range(retries):
        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=60
            )

            if r.status_code == 429:
                wait = 2 ** attempt

                print(
                    f"Rate limited. "
                    f"Waiting {wait} seconds..."
                )

                time.sleep(wait)
                continue

            r.raise_for_status()

            return r.json()

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


def classify(me_result, opp_result):
    if me_result == "win":
        return "W"

    if opp_result == "win":
        return "L"

    return "D"


def load_games(username):
    username = username.lower()

    now = time.time()

    # -----------------------------------------------------
    # CREATE CACHE FOR USER IF IT DOESN'T EXIST
    # -----------------------------------------------------

    if username not in CACHE:
        CACHE[username] = {
            "archives": {},
            "last_check": 0
        }

    user_cache = CACHE[username]

    # -----------------------------------------------------
    # VERY RECENT REQUEST
    # -----------------------------------------------------

    # If we just checked this account less than 60 seconds
    # ago, don't even contact Chess.com.
    if (
        user_cache["archives"]
        and now - user_cache["last_check"] < CACHE_TTL
    ):
        print(
            f"Using cached games for {username}. "
            f"No Chess.com refresh needed."
        )

        all_games = []

        for games in user_cache["archives"].values():
            all_games.extend(games)

        print(
            f"Cache contains "
            f"{len(all_games)} games."
        )

        return all_games

    # -----------------------------------------------------
    # GET CURRENT ARCHIVE LIST
    # -----------------------------------------------------

    archive_data = get_json(
        f"{BASE}/player/{username}/games/archives"
    )

    archives = archive_data.get(
        "archives",
        []
    )

    print(
        f"Chess.com reports "
        f"{len(archives)} monthly archives "
        f"for {username}"
    )

    if not archives:
        return []

    # The newest archive can change because new games
    # continue being added during the current month.
    latest_archive = archives[-1]

    # -----------------------------------------------------
    # LOAD ARCHIVES
    # -----------------------------------------------------

    for i, url in enumerate(archives):
        already_cached = (
            url in user_cache["archives"]
        )

        # Every historical month is permanent.
        # If we already have it, don't download it again.
        #
        # The most recent month IS refreshed so newly played
        # games appear.
        if (
            already_cached
            and url != latest_archive
        ):
            print(
                f"Archive {i + 1}/{len(archives)} "
                f"already cached"
            )

            continue

        try:
            data = get_json(url)

            games = data.get(
                "games",
                []
            )

            user_cache["archives"][url] = games

            if already_cached:
                print(
                    f"Refreshed latest archive "
                    f"{i + 1}/{len(archives)} "
                    f"- {len(games)} games"
                )

            else:
                print(
                    f"Downloaded archive "
                    f"{i + 1}/{len(archives)} "
                    f"- {len(games)} games"
                )

            # Only delay when actually downloading.
            time.sleep(0.15)

        except requests.RequestException as e:
            print(
                f"Failed to load archive "
                f"{i + 1}/{len(archives)}: {e}"
            )

            # If an archive was previously cached,
            # keep the old copy instead of losing it.
            continue

    # -----------------------------------------------------
    # REMOVE ARCHIVES CHESS.COM NO LONGER REPORTS
    # -----------------------------------------------------

    current_archive_set = set(archives)

    cached_urls = list(
        user_cache["archives"].keys()
    )

    for cached_url in cached_urls:
        if cached_url not in current_archive_set:
            print(
                f"Removing obsolete archive "
                f"from cache: {cached_url}"
            )

            del user_cache["archives"][
                cached_url
            ]

    user_cache["last_check"] = now

    # -----------------------------------------------------
    # COMBINE EVERYTHING
    # -----------------------------------------------------

    all_games = []

    for url in archives:
        games = user_cache[
            "archives"
        ].get(
            url,
            []
        )

        all_games.extend(games)

    print(
        f"Finished loading games for "
        f"{username}. "
        f"Total cached games: "
        f"{len(all_games)}"
    )

    return all_games


def normalize(games, username):
    uname = username.lower()

    rows = []

    for g in games:
        white = g.get(
            "white",
            {}
        )

        black = g.get(
            "black",
            {}
        )

        wn = str(
            white.get(
                "username",
                ""
            )
        )

        bn = str(
            black.get(
                "username",
                ""
            )
        )

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

        ts = g.get(
            "end_time"
        )

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

            "my_rating": me.get(
                "rating"
            ),

            "opp_rating": opp.get(
                "rating"
            ),

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

            "url": g.get(
                "url",
                ""
            )
        })

    return rows


def summarize(rows):
    groups = defaultdict(list)

    for row in rows:
        groups[
            row["opponent"]
        ].append(row)

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
            if isinstance(
                g["opp_rating"],
                int
            )
        ]

        n = len(games)

        out.append({
            "opponent": opp,

            "games": n,

            "wins": wins,

            "losses": losses,

            "draws": draws,

            "record":
                f"{wins}-"
                f"{losses}-"
                f"{draws}",

            "win_pct": round(
                100 * wins / n,
                1
            ),

            "score_pct": round(
                100
                * (
                    wins
                    + 0.5 * draws
                )
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
            "error":
                "Username is required"
        }), 400

    try:
        games = load_games(
            username
        )

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

        summary = summarize(
            rows
        )

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
            "error":
                str(e)
        }), 500


@app.route(
    "/manifest.webmanifest"
)
def manifest():
    return app.send_static_file(
        "manifest.webmanifest"
    )


@app.route(
    "/service-worker.js"
)
def sw():
    return app.send_static_file(
        "service-worker.js"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
