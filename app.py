"""
Mind Palace Builder -- web edition.

Flask app that teaches and walks a user through building a "method of
loci" memory palace: a five-lesson learning path with hands-on practice
after each lesson, then a real palace-building + spaced-repetition quiz
tool.

Run locally:
    pip install -r requirements.txt
    python app.py

Or via Docker -- see Dockerfile / docker-compose.yml.
"""

import json
import os
import random
from datetime import date, timedelta
from difflib import SequenceMatcher

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DATA_FILE = os.environ.get(
    "DATA_FILE", os.path.join(os.path.dirname(__file__), "data", "mind_palace.json")
)

TIPS = [
    "Make the image VIVID: exaggerate size, color, or motion.",
    "Make it WEIRD or funny -- brains remember the absurd far better than the mundane.",
    "Involve MULTIPLE SENSES: what does it sound, smell, or feel like?",
    "Add MOTION: a static image fades; something happening sticks.",
    "Keep locations in a fixed, logical ORDER -- always walk the route the same way.",
    "Don't cram: one vivid item per location works better than several.",
]

# ---------------------------------------------------------------------------
# Learning path content
# ---------------------------------------------------------------------------

LESSON_TITLES = {
    1: "Why Spatial Memory Works",
    2: "Choosing & Sizing Your Route",
    3: "Building Vivid Associations",
    4: "Encoding Hard Content",
    5: "Avoiding Mistakes & Spaced Review",
}
LESSON_COUNT = len(LESSON_TITLES)

PRACTICE_ITEMS = [
    "umbrella", "calculator", "trophy", "snowman", "lightbulb", "cactus",
    "kite", "anchor", "telescope", "drum", "pineapple", "violin",
    "chessboard", "lantern", "compass", "typewriter",
]

ABSTRACT_CONCEPTS = [
    "justice", "freedom", "economy", "democracy", "entropy", "privacy",
    "bureaucracy", "inflation", "identity", "momentum",
]

SENSE_WORDS = {
    "loud", "bright", "smell", "smells", "cold", "hot", "sound", "sounds",
    "taste", "tastes", "texture", "rough", "smooth", "sticky", "buzzing",
    "glowing", "roaring", "screaming", "cracking", "shimmering", "burning",
    "freezing", "sour", "sweet", "stinking", "stinky", "fragrant", "gritty",
    "slimy", "crunchy", "warm", "icy",
}

ACTION_WORDS = {
    "jumping", "spinning", "exploding", "flying", "dancing", "crashing",
    "melting", "growing", "shrinking", "running", "falling", "chasing",
    "smashing", "bursting", "screaming", "throwing", "climbing", "sliding",
    "spraying", "juggling", "leaking", "shaking", "bouncing", "collapsing",
}

# Simplified consonant code (a beginner-friendly version of the Major
# System): only the consonant sounds carry digits, vowels are silent.
MAJOR_MAP = {
    "s": "0", "z": "0",
    "t": "1", "d": "1",
    "n": "2",
    "m": "3",
    "r": "4",
    "l": "5",
    "j": "6",
    "k": "7", "c": "7", "q": "7", "g": "7",
    "f": "8", "v": "8",
    "p": "9", "b": "9",
}

INTERVALS = [1, 2, 4, 7, 14, 30]  # days until next review, indexed by box level


def word_to_digits(text):
    """Extract a simplified Major System digit string from consonants,
    collapsing immediate repeats (double letters count once)."""
    digits = []
    for ch in text.lower():
        d = MAJOR_MAP.get(ch)
        if d and (not digits or digits[-1] != d):
            digits.append(d)
    return "".join(digits)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_palace():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            palace = json.load(f)
    else:
        palace = {}

    palace.setdefault("name", None)
    palace.setdefault("locations", [])
    palace.setdefault("learning_progress", [])
    palace.setdefault("route_draft", [])

    for loc in palace["locations"]:
        loc.setdefault("box", 0)
        loc.setdefault("next_review", None)

    return palace


def save_palace(palace):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(palace, f, indent=2)


def is_due(loc):
    nr = loc.get("next_review")
    return nr is None or nr <= date.today().isoformat()


def schedule_next(loc, correct):
    box = loc.get("box", 0)
    box = min(box + 1, len(INTERVALS) - 1) if correct else 0
    loc["box"] = box
    loc["next_review"] = (date.today() + timedelta(days=INTERVALS[box])).isoformat()


def lesson_unlocked(lesson_id, progress):
    return lesson_id == 1 or (lesson_id - 1) in progress


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    palace = load_palace()
    due_count = sum(1 for loc in palace["locations"] if is_due(loc))
    lessons_done = len(palace["learning_progress"])
    return render_template(
        "index.html",
        palace=palace,
        due_count=due_count,
        lessons_done=lessons_done,
        lesson_count=LESSON_COUNT,
    )


@app.route("/palace/name", methods=["GET", "POST"])
def name_palace():
    palace = load_palace()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            palace["name"] = name
            save_palace(palace)
        return redirect(url_for("index"))
    return render_template("name_palace.html", palace=palace)


@app.route("/palace/add", methods=["GET", "POST"])
def add_location():
    palace = load_palace()
    tip = random.choice(TIPS)
    if request.method == "POST":
        loc = request.form.get("location", "").strip()
        item = request.form.get("item", "").strip()
        assoc = request.form.get("association", "").strip()
        if loc and item:
            palace["locations"].append(
                {"location": loc, "item": item, "association": assoc, "box": 0, "next_review": None}
            )
            save_palace(palace)
            return redirect(url_for("add_location"))
    return render_template("add_location.html", palace=palace, tip=tip)


@app.route("/palace/walk")
def walkthrough():
    palace = load_palace()
    return render_template("walkthrough.html", palace=palace)


@app.route("/palace/edit/<int:idx>", methods=["GET", "POST"])
def edit_location(idx):
    palace = load_palace()
    if idx < 0 or idx >= len(palace["locations"]):
        return redirect(url_for("walkthrough"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            palace["locations"].pop(idx)
        else:
            existing = palace["locations"][idx]
            existing["location"] = request.form.get("location", "").strip()
            existing["item"] = request.form.get("item", "").strip()
            existing["association"] = request.form.get("association", "").strip()
        save_palace(palace)
        return redirect(url_for("walkthrough"))

    return render_template("edit_location.html", palace=palace, idx=idx, stop=palace["locations"][idx])


# ---------------------------------------------------------------------------
# Quiz / spaced review
# ---------------------------------------------------------------------------

@app.route("/quiz/start")
def quiz_start():
    palace = load_palace()
    scope = request.args.get("scope")
    indices = list(range(len(palace["locations"])))
    if scope == "due":
        indices = [i for i in indices if is_due(palace["locations"][i])]

    if not indices:
        return redirect(url_for("walkthrough"))

    random.shuffle(indices)
    session["quiz_order"] = indices
    session["quiz_pos"] = 0
    session["quiz_score"] = 0
    return redirect(url_for("quiz_question"))


@app.route("/quiz/question", methods=["GET", "POST"])
def quiz_question():
    palace = load_palace()
    order = session.get("quiz_order")
    pos = session.get("quiz_pos", 0)

    if order is None:
        return redirect(url_for("quiz_start"))

    if request.method == "POST":
        correct = request.form.get("correct") == "y"
        loc_index = order[pos]
        schedule_next(palace["locations"][loc_index], correct)
        save_palace(palace)
        if correct:
            session["quiz_score"] = session.get("quiz_score", 0) + 1
        session["quiz_pos"] = pos + 1
        return redirect(url_for("quiz_question"))

    if pos >= len(order):
        return redirect(url_for("quiz_result"))

    stop = palace["locations"][order[pos]]
    return render_template(
        "quiz_question.html",
        stop=stop,
        pos=pos + 1,
        total=len(order),
        revealed=request.args.get("reveal") == "1",
    )


@app.route("/quiz/result")
def quiz_result():
    score = session.get("quiz_score", 0)
    order = session.get("quiz_order", [])
    total = len(order)
    session.pop("quiz_order", None)
    session.pop("quiz_pos", None)
    session.pop("quiz_score", None)
    return render_template("quiz_result.html", score=score, total=total)


# ---------------------------------------------------------------------------
# Learning path -- overview
# ---------------------------------------------------------------------------

@app.route("/learn")
def learn():
    palace = load_palace()
    progress = palace["learning_progress"]
    lessons = []
    for lid, title in LESSON_TITLES.items():
        lessons.append({
            "id": lid,
            "title": title,
            "done": lid in progress,
            "unlocked": lesson_unlocked(lid, progress),
        })
    return render_template("learn.html", lessons=lessons)


def mark_complete(palace, lesson_id):
    if lesson_id not in palace["learning_progress"]:
        palace["learning_progress"].append(lesson_id)
    save_palace(palace)


# ---------------------------------------------------------------------------
# Lesson 1: Why spatial memory works (no practice input, just a read + ack)
# ---------------------------------------------------------------------------

@app.route("/learn/1", methods=["GET", "POST"])
def lesson1():
    palace = load_palace()
    if not lesson_unlocked(1, palace["learning_progress"]):
        return redirect(url_for("learn"))

    if request.method == "POST":
        mark_complete(palace, 1)
        return redirect(url_for("lesson2"))

    return render_template("lesson1.html", done=1 in palace["learning_progress"])


# ---------------------------------------------------------------------------
# Lesson 2: Choosing & sizing your route
# ---------------------------------------------------------------------------

@app.route("/learn/2", methods=["GET", "POST"])
def lesson2():
    palace = load_palace()
    if not lesson_unlocked(2, palace["learning_progress"]):
        return redirect(url_for("learn"))

    feedback = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save_route":
            raw = request.form.get("route", "")
            stops = [line.strip() for line in raw.splitlines() if line.strip()]
            palace["route_draft"] = stops
            save_palace(palace)
            if len(stops) < 5:
                feedback = {
                    "ok": False,
                    "message": f"You listed {len(stops)} stop(s). Aim for at least 5-8 "
                               "distinct spots so you have room for a full list without crowding.",
                }
            else:
                feedback = {
                    "ok": True,
                    "message": f"Solid route -- {len(stops)} stops saved. Distinct, "
                               "well-spaced locations like these are exactly what you want.",
                }
        elif action == "complete":
            mark_complete(palace, 2)
            return redirect(url_for("lesson3"))

    return render_template(
        "lesson2.html",
        route_draft=palace.get("route_draft", []),
        feedback=feedback,
        done=2 in palace["learning_progress"],
    )


# ---------------------------------------------------------------------------
# Lesson 3: Building vivid associations
# ---------------------------------------------------------------------------

@app.route("/learn/3", methods=["GET", "POST"])
def lesson3():
    palace = load_palace()
    if not lesson_unlocked(3, palace["learning_progress"]):
        return redirect(url_for("learn"))

    if "l3_item" not in session:
        session["l3_item"] = random.choice(PRACTICE_ITEMS)
        session["l3_attempts"] = 0

    feedback = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "check":
            text = request.form.get("association", "").strip()
            words = text.split()
            has_sense = any(w.strip(".,!?").lower() in SENSE_WORDS for w in words)
            has_action = any(w.strip(".,!?").lower() in ACTION_WORDS for w in words)
            long_enough = len(words) >= 8
            feedback = {
                "text": text,
                "long_enough": long_enough,
                "has_sense": has_sense,
                "has_action": has_action,
                "passed": long_enough and (has_sense or has_action),
            }
            session["l3_attempts"] = session.get("l3_attempts", 0) + 1
        elif action == "new_item":
            session["l3_item"] = random.choice(PRACTICE_ITEMS)
        elif action == "complete" and session.get("l3_attempts", 0) >= 1:
            mark_complete(palace, 3)
            session.pop("l3_item", None)
            session.pop("l3_attempts", None)
            return redirect(url_for("lesson4"))

    return render_template(
        "lesson3.html",
        item=session.get("l3_item"),
        attempts=session.get("l3_attempts", 0),
        feedback=feedback,
        done=3 in palace["learning_progress"],
    )


# ---------------------------------------------------------------------------
# Lesson 4: Encoding hard content (numbers + abstract concepts)
# ---------------------------------------------------------------------------

@app.route("/learn/4", methods=["GET", "POST"])
def lesson4():
    palace = load_palace()
    if not lesson_unlocked(4, palace["learning_progress"]):
        return redirect(url_for("learn"))

    if "l4_number" not in session:
        session["l4_number"] = str(random.randint(10, 99))
    if "l4_abstract" not in session:
        session["l4_abstract"] = random.choice(ABSTRACT_CONCEPTS)

    number_feedback = None
    abstract_feedback = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "check_number":
            word = request.form.get("number_word", "").strip()
            target = session["l4_number"]
            got = word_to_digits(word)
            number_feedback = {
                "word": word,
                "target": target,
                "got": got,
                "passed": got == target,
            }
        elif action == "new_number":
            session["l4_number"] = str(random.randint(10, 99))
        elif action == "check_abstract":
            image = request.form.get("abstract_image", "").strip()
            abstract_feedback = {"image": image, "submitted": bool(image)}
        elif action == "new_abstract":
            session["l4_abstract"] = random.choice(ABSTRACT_CONCEPTS)
        elif action == "complete":
            mark_complete(palace, 4)
            session.pop("l4_number", None)
            session.pop("l4_abstract", None)
            return redirect(url_for("lesson5"))

    return render_template(
        "lesson4.html",
        number=session.get("l4_number"),
        abstract=session.get("l4_abstract"),
        major_map=MAJOR_MAP,
        number_feedback=number_feedback,
        abstract_feedback=abstract_feedback,
        done=4 in palace["learning_progress"],
    )


# ---------------------------------------------------------------------------
# Lesson 5: Avoiding mistakes + spaced review
# ---------------------------------------------------------------------------

@app.route("/learn/5", methods=["GET", "POST"])
def lesson5():
    palace = load_palace()
    if not lesson_unlocked(5, palace["learning_progress"]):
        return redirect(url_for("learn"))

    if request.method == "POST" and request.form.get("action") == "complete":
        mark_complete(palace, 5)
        return redirect(url_for("learn"))

    locations = palace["locations"]
    similar_pairs = []
    for i in range(len(locations)):
        for j in range(i + 1, len(locations)):
            a = locations[i]["association"].lower()
            b = locations[j]["association"].lower()
            if a and b:
                ratio = SequenceMatcher(None, a, b).ratio()
                if ratio > 0.6:
                    similar_pairs.append((locations[i]["location"], locations[j]["location"], round(ratio, 2)))

    thin = [loc["location"] for loc in locations if len(loc["association"].split()) < 5]

    return render_template(
        "lesson5.html",
        palace=palace,
        similar_pairs=similar_pairs,
        thin=thin,
        done=5 in palace["learning_progress"],
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
