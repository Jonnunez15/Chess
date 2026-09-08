from flask import Flask, jsonify, render_template, request
import requests
import time

from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


app = Flask(__name__)

BASE = "https://api.chess.com/pub"

HEADERS = {
    "User-Agent":
        "jonnunez-chess-analytics/1.0 "
        "(personal analytics app)"
}

LOCAL_TZ = ZoneInfo("America/New_York")

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

            if r.status_code == 404:
                r.raise_for_status()

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

    if (
        user_cache["archives"]
        and now - user_cache["last_check"] < CACHE_TTL
    ):

        print(
            f"Using cached games for {username}"
        )

        all_games = []

        for games in user_cache["archives"].values():
            all_games.extend(games)

        print(
            f"Cache contains "
            f"{len(all_games)} games"
        )

        return all_games

    archive_data = get_json(
        f"{BASE}/player/{username}/games/archives"
    )

    archives = archive_data.get(
        "archives",
        []
    )

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

        if (
            already_cached
            and url != latest_archive
        ):

            print(
                f"Archive "
                f"{i + 1}/{len(archives)} cached"
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
            user_cache["archives"].get(
                url,
                []
            )
        )

    print(
        f"Finished loading {username}: "
        f"{len(all_games)} games"
    )

    return all_games


# =========================================================
# NORMALIZE
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

        utc_date = None
        local_date = None
        local_hour = None
        weekday = None
        month = None

        if ts:

            dt_utc = datetime.fromtimestamp(
                ts,
                tz=timezone.utc
            )

            dt_local = dt_utc.astimezone(
                LOCAL_TZ
            )

            utc_date = dt_utc.isoformat()

            local_date = (
                dt_local
                .date()
                .isoformat()
            )

            local_hour = dt_local.hour

            weekday = dt_local.strftime(
                "%A"
            )

            month = dt_local.strftime(
                "%Y-%m"
            )

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

            "date": utc_date,

            "local_date": local_date,

            "local_hour": local_hour,

            "weekday": weekday,

            "month": month,

            "timestamp": ts,

            "url": g.get(
                "url",
                ""
            )
        })

    rows.sort(
        key=lambda x:
            x["timestamp"] or 0
    )

    return rows


# =========================================================
# BASIC HELPERS
# =========================================================

def game_record(games):

    n = len(games)

    if not n:

        return {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "record": "0-0-0",
            "score_pct": 0
        }

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

    return {
        "games": n,

        "wins": wins,

        "losses": losses,

        "draws": draws,

        "record":
            f"{wins}-{losses}-{draws}",

        "score_pct": round(
            100
            * (
                wins
                + 0.5 * draws
            )
            / n,
            1
        )
    }


# =========================================================
# OPPONENT SUMMARY
# =========================================================

def summarize(rows):

    groups = defaultdict(list)

    for row in rows:

        groups[
            row["opponent"]
        ].append(row)

    out = []

    for opp, games in groups.items():

        base = game_record(
            games
        )

        ratings = [
            g["opp_rating"]
            for g in games
            if isinstance(
                g["opp_rating"],
                int
            )
        ]

        out.append({

            "opponent":
                opp,

            **base,

            "win_pct": round(
                100
                * base["wins"]
                / base["games"],
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
# TIME CONTROL
# =========================================================

def time_control_stats(rows):

    groups = defaultdict(list)

    for row in rows:

        groups[
            row["time_class"]
        ].append(row)

    results = []

    for tc, games in groups.items():

        base = game_record(
            games
        )

        ratings = [
            g["my_rating"]
            for g in games
            if isinstance(
                g["my_rating"],
                int
            )
        ]

        opp_ratings = [
            g["opp_rating"]
            for g in games
            if isinstance(
                g["opp_rating"],
                int
            )
        ]

        results.append({

            "time_class":
                tc,

            **base,

            "avg_rating": (
                round(
                    sum(ratings)
                    / len(ratings)
                )
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
        key=lambda x:
            x["games"],
        reverse=True
    )

    return results


# =========================================================
# RATING HISTORY
# =========================================================

def rating_history(rows):

    daily = {}

    for g in rows:

        if not g["local_date"]:
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

        key = (
            tc,
            g["local_date"]
        )

        daily[key] = {
            "date":
                g["local_date"],

            "rating":
                g["my_rating"],

            "time_class":
                tc
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
            "date":
                item["date"],

            "rating":
                item["rating"]
        })

    for tc in history:

        history[tc].sort(
            key=lambda x:
                x["date"]
        )

    return history


# =========================================================
# PEAK RATINGS
# =========================================================

def peak_ratings(rows):

    peaks = {}

    for tc in [
        "bullet",
        "blitz",
        "rapid"
    ]:

        games = [
            g
            for g in rows
            if (
                g["time_class"] == tc
                and isinstance(
                    g["my_rating"],
                    int
                )
            )
        ]

        if not games:

            peaks[tc] = None
            continue

        best = max(
            games,
            key=lambda x:
                x["my_rating"]
        )

        peaks[tc] = {
            "rating":
                best["my_rating"],

            "date":
                best["local_date"]
        }

    return peaks


# =========================================================
# COLOR PERFORMANCE
# =========================================================

def color_stats(rows):

    result = {}

    for color in [
        "White",
        "Black"
    ]:

        games = [
            g
            for g in rows
            if g["color"] == color
        ]

        result[
            color.lower()
        ] = game_record(
            games
        )

    return result


# =========================================================
# STREAKS
# =========================================================

def streak_stats(rows):

    def longest(predicate):

        best_length = 0
        best_start = None
        best_end = None

        current = 0
        current_start = None

        for g in rows:

            if predicate(g):

                if current == 0:
                    current_start = (
                        g["local_date"]
                    )

                current += 1

                if current > best_length:

                    best_length = current
                    best_start = current_start
                    best_end = g["local_date"]

            else:

                current = 0
                current_start = None

        return {
            "games":
                best_length,

            "start_date":
                best_start,

            "end_date":
                best_end
        }

    return {
        "wins": longest(
            lambda g:
                g["result"] == "W"
        ),

        "losses": longest(
            lambda g:
                g["result"] == "L"
        ),

        "unbeaten": longest(
            lambda g:
                g["result"] != "L"
        )
    }


# =========================================================
# RECENT FORM
# =========================================================

def recent_form(rows):

    career = game_record(
        rows
    )

    result = {}

    for n in [
        10,
        25,
        50,
        100
    ]:

        games = rows[-n:]

        stats = game_record(
            games
        )

        stats["vs_career"] = round(
            stats["score_pct"]
            - career["score_pct"],
            1
        )

        result[str(n)] = stats

    return result


# =========================================================
# RATING DIFFERENCE
# =========================================================

def rating_difference_stats(rows):

    buckets = [
        (
            "300+ lower",
            lambda d: d <= -300
        ),
        (
            "150–299 lower",
            lambda d: -299 <= d <= -150
        ),
        (
            "50–149 lower",
            lambda d: -149 <= d <= -50
        ),
        (
            "Within 49",
            lambda d: -49 <= d <= 49
        ),
        (
            "50–149 higher",
            lambda d: 50 <= d <= 149
        ),
        (
            "150–299 higher",
            lambda d: 150 <= d <= 299
        ),
        (
            "300+ higher",
            lambda d: d >= 300
        )
    ]

    grouped = {
        label: []
        for label, _ in buckets
    }

    for g in rows:

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

        diff = (
            g["opp_rating"]
            - g["my_rating"]
        )

        for label, rule in buckets:

            if rule(diff):

                grouped[
                    label
                ].append(g)

                break

    return [
        {
            "bucket":
                label,

            **game_record(
                grouped[label]
            )
        }
        for label, _ in buckets
    ]


# =========================================================
# WEEKDAY
# =========================================================

def weekday_stats(rows):

    order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    ]

    result = []

    for day in order:

        games = [
            g
            for g in rows
            if g["weekday"] == day
        ]

        result.append({
            "day":
                day,

            **game_record(
                games
            )
        })

    return result


# =========================================================
# TIME OF DAY
# =========================================================

def time_of_day_stats(rows):

    buckets = {
        "Overnight": [],
        "Morning": [],
        "Afternoon": [],
        "Evening": []
    }

    for g in rows:

        hour = g[
            "local_hour"
        ]

        if hour is None:
            continue

        if 0 <= hour < 6:

            label = "Overnight"

        elif hour < 12:

            label = "Morning"

        elif hour < 18:

            label = "Afternoon"

        else:

            label = "Evening"

        buckets[
            label
        ].append(g)

    return [
        {
            "period":
                label,

            **game_record(
                games
            )
        }
        for label, games
        in buckets.items()
    ]


# =========================================================
# MONTHLY PERFORMANCE
# =========================================================

def monthly_stats(rows):

    grouped = defaultdict(list)

    for g in rows:

        if g["month"]:

            grouped[
                g["month"]
            ].append(g)

    months = []

    for month, games in grouped.items():

        months.append({
            "month":
                month,

            **game_record(
                games
            )
        })

    months.sort(
        key=lambda x:
            x["month"]
    )

    qualified = [
        x
        for x in months
        if x["games"] >= 50
    ]

    pool = (
        qualified
        if qualified
        else months
    )

    best = sorted(
        pool,
        key=lambda x: (
            x["score_pct"],
            x["games"]
        ),
        reverse=True
    )[:3]

    worst = sorted(
        pool,
        key=lambda x: (
            x["score_pct"],
            -x["games"]
        )
    )[:3]

    return {
        "all":
            months,

        "best":
            best,

        "worst":
            worst
    }


# =========================================================
# ACTIVITY
# =========================================================

def activity_stats(rows):

    counts = defaultdict(int)

    for g in rows:

        if g["local_date"]:

            counts[
                g["local_date"]
            ] += 1

    if not counts:

        return {
            "days": [],
            "busiest_day": None
        }

    days = [
        {
            "date":
                date,

            "games":
                count
        }
        for date, count
        in counts.items()
    ]

    days.sort(
        key=lambda x:
            x["date"]
    )

    busiest = max(
        days,
        key=lambda x:
            x["games"]
    )

    return {
        "days":
            days,

        "busiest_day":
            busiest
    }


# =========================================================
# 30-DAY RATING MOVES
# =========================================================

def rating_moves_30_days(history):

    results = {}

    for tc, data in history.items():

        if len(data) < 2:

            results[tc] = {
                "gain": None,
                "drop": None
            }

            continue

        dates = [
            datetime.strptime(
                x["date"],
                "%Y-%m-%d"
            ).date()
            for x in data
        ]

        best_gain = None
        worst_drop = None

        for i in range(
            1,
            len(data)
        ):

            target = (
                dates[i]
                - timedelta(days=30)
            )

            j = (
                bisect_right(
                    dates,
                    target
                )
                - 1
            )

            if j < 0:
                continue

            change = (
                data[i]["rating"]
                - data[j]["rating"]
            )

            item = {
                "change":
                    change,

                "start_rating":
                    data[j]["rating"],

                "end_rating":
                    data[i]["rating"],

                "start_date":
                    data[j]["date"],

                "end_date":
                    data[i]["date"]
            }

            if (
                best_gain is None
                or change
                > best_gain["change"]
            ):

                best_gain = item

            if (
                worst_drop is None
                or change
                < worst_drop["change"]
            ):

                worst_drop = item

        results[tc] = {
            "gain":
                best_gain,

            "drop":
                worst_drop
        }

    all_gains = []
    all_drops = []

    for tc, value in results.items():

        if value["gain"]:

            all_gains.append({
                "time_class":
                    tc,

                **value["gain"]
            })

        if value["drop"]:

            all_drops.append({
                "time_class":
                    tc,

                **value["drop"]
            })

    overall_gain = (
        max(
            all_gains,
            key=lambda x:
                x["change"]
        )
        if all_gains
        else None
    )

    overall_drop = (
        min(
            all_drops,
            key=lambda x:
                x["change"]
        )
        if all_drops
        else None
    )

    return {
        "by_time_class":
            results,

        "biggest_gain":
            overall_gain,

        "biggest_drop":
            overall_drop
    }


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
                abs(
                    x["score_pct"]
                    - 50
                ),
                -x["games"]
            )
        )

    return {
        "nemesis":
            nemesis,

        "punching_bag":
            punching_bag,

        "closest_rival":
            closest_rival
    }


# =========================================================
# BIGGEST UPSETS
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
            "opponent":
                g["opponent"],

            "my_rating":
                g["my_rating"],

            "opp_rating":
                g["opp_rating"],

            "rating_difference":
                difference,

            "time_class":
                g["time_class"],

            "date":
                g["local_date"],

            "color":
                g["color"],

            "url":
                g["url"]
        })

    wins.sort(
        key=lambda x:
            x["rating_difference"],
        reverse=True
    )

    return wins[:10]


# =========================================================
# ROUTES
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

    game_filter = request.args.get(
        "filter",
        "all"
    ).strip().lower()

    time_filter = request.args.get(
        "time_classes",
        "all"
    ).strip().lower()

    if not username:

        return jsonify({
            "error":
                "Username is required"
        }), 400

    if game_filter not in {
        "all",
        "rated",
        "unrated"
    }:

        return jsonify({
            "error":
                "Invalid game filter"
        }), 400

    valid_time_classes = {
        "rapid",
        "blitz",
        "bullet"
    }

    selected_time_classes = None

    if time_filter != "all":

        selected_time_classes = {
            x.strip()
            for x in time_filter.split(",")
            if x.strip()
        }

        if not selected_time_classes:

            return jsonify({
                "error":
                    "No time controls selected"
            }), 400

        if not selected_time_classes.issubset(
            valid_time_classes
        ):

            return jsonify({
                "error":
                    "Invalid time-control filter"
            }), 400

    try:

        games = load_games(
            username
        )

        rows = normalize(
            games,
            username
        )

        # =================================================
        # RATED / UNRATED FILTER
        # =================================================

        if game_filter == "rated":

            rows = [
                g
                for g in rows
                if g["rated"] is True
            ]

        elif game_filter == "unrated":

            rows = [
                g
                for g in rows
                if g["rated"] is False
            ]

        # =================================================
        # RAPID / BLITZ / BULLET FILTER
        # =================================================

        if selected_time_classes is not None:

            rows = [
                g
                for g in rows
                if g["time_class"]
                in selected_time_classes
            ]

        # =================================================

        if not rows:

            return jsonify({
                "error":
                    "No games found for "
                    "the selected filters"
            }), 404

        total_record = game_record(
            rows
        )

        summary = summarize(
            rows
        )

        history = rating_history(
            rows
        )

        return jsonify({

            "username":
                username,

            "filter":
                game_filter,

            "time_filter": (
                sorted(
                    selected_time_classes
                )
                if selected_time_classes
                is not None
                else "all"
            ),

            "totals":
                total_record,

            "top_opponents":
                summary[:10],

            "opponents":
                summary,

            "time_controls":
                time_control_stats(
                    rows
                ),

            "rating_history":
                history,

            "peak_ratings":
                peak_ratings(
                    rows
                ),

            "color_stats":
                color_stats(
                    rows
                ),

            "streaks":
                streak_stats(
                    rows
                ),

            "recent_form":
                recent_form(
                    rows
                ),

            "rating_difference":
                rating_difference_stats(
                    rows
                ),

            "weekday_stats":
                weekday_stats(
                    rows
                ),

            "time_of_day":
                time_of_day_stats(
                    rows
                ),

            "monthly_stats":
                monthly_stats(
                    rows
                ),

            "activity":
                activity_stats(
                    rows
                ),

            "rating_moves_30":
                rating_moves_30_days(
                    history
                ),

            "rivals":
                rivalry_stats(
                    summary
                ),

            "biggest_upsets":
                biggest_upsets(
                    rows
                ),

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
