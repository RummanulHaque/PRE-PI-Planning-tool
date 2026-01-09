
from flask import Flask, render_template, send_file, request, redirect, url_for, session, jsonify
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "local-dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXCEL_PATH = os.path.join(DATA_DIR, "wsjf_features.xlsx")

os.makedirs(DATA_DIR, exist_ok=True)

# ==================================================
# SAFe FEATURE GENERATOR (SYSTEM-OWNED)
# ==================================================
def generate_safe_features_df():
    return pd.DataFrame([
        {
            "Feature ID": "FTR-PI-001",
            "Feature Name": "Payments Modernization",
            "Feature Description": "As a finance stakeholder, I want modern payment processing so that regulatory and customer expectations are met.",
            "Feature Acceptance Criteria": "• Regulatory compliance met\n• Zero manual reconciliation\n• Peak load validated",
        },
        {
            "Feature ID": "FTR-PI-002",
            "Feature Name": "Customer Analytics Platform",
            "Feature Description": "As a business owner, I want unified customer analytics so that decisions are data-driven.",
            "Feature Acceptance Criteria": "• Single source of truth\n• GDPR compliant\n• Business dashboards available",
        },
        {
            "Feature ID": "FTR-PI-003",
            "Feature Name": "Legacy System Decommissioning",
            "Feature Description": "As an IT leader, I want to retire legacy systems so that risk and cost are reduced.",
            "Feature Acceptance Criteria": "• No active consumers\n• Data archived\n• Support contracts closed",
        },
        {
            "Feature ID": "FTR-PI-004",
            "Feature Name": "AI Assisted Support",
            "Feature Description": "As a support manager, I want AI assistance so that resolution time improves.",
            "Feature Acceptance Criteria": "• Accuracy threshold met\n• Human override enabled\n• Audit logs available",
        },
        {
            "Feature ID": "FTR-PI-005",
            "Feature Name": "Mobile Experience Revamp",
            "Feature Description": "As a customer, I want a modern mobile experience so that interactions are intuitive.",
            "Feature Acceptance Criteria": "• UX council approved\n• Performance benchmarks met\n• Rating improvement tracked",
        }
    ])

# ==================================================
# ENSURE EXCEL EXISTS & HAS FEATURES
# ==================================================
def ensure_excel_with_features():
    if not os.path.exists(EXCEL_PATH):
        df = generate_safe_features_df()
    else:
        df = pd.read_excel(EXCEL_PATH)
        if df.empty:
            df = generate_safe_features_df()

    required_cols = [
        "Business Value",
        "Time Complexity",
        "OE/RR Value",
        "Job Size",
        "Cost of Delay",
        "WSJF",
        "Story Points",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df.to_excel(EXCEL_PATH, index=False)
    return df

# ================================
# PLANNING POKER (IN-MEMORY)
# ================================
POKER_SESSIONS = {}

FIBO_DECK = [1, 2, 3, 5, 8, 13, 21, 34]

ESTIMATION_FIELDS = [
    "Business Value",
    "Time Complexity",
    "OE/RR Value",
    "Job Size",
    "Story Points",
]

def nearest_fibo(v: float) -> int:
    return min(FIBO_DECK, key=lambda x: abs(x - v))

def _require_joined():
    if "user" not in session:
        return False
    return True

def _require_host(session_id: str):
    if not _require_joined():
        return False
    s = POKER_SESSIONS.get(session_id)
    if not s:
        return False
    return session.get("user") == s.get("host_name")

@app.route("/", methods=["GET", "POST"])
def home():
    PROJECTS = [
        "Digital Channels",
        "Payments",
        "Data Platform",
        "Agile Gamification PoC",
    ]

    if request.method == "POST":
        selected = request.form.get("project", "").strip()
        session["selected_project"] = selected if selected else "—"
        return redirect(url_for("wsjf"))

    # 👇 hide top nav on this page
    return render_template("home.html", projects=PROJECTS, hide_nav=True)



# ==================================================
# WSJF PAGE
# ==================================================
@app.route("/wsjf")
def wsjf():
    df = ensure_excel_with_features()

    # Keep NaN for UI; compute using safe copies
    for col in ["Business Value", "Time Complexity", "OE/RR Value", "Job Size"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    bv = df["Business Value"].fillna(0)
    tc = df["Time Complexity"].fillna(0)
    oe = df["OE/RR Value"].fillna(0)

    df["Cost of Delay"] = bv + tc + oe

    df["WSJF"] = df.apply(
        lambda row: round(row["Cost of Delay"] / row["Job Size"], 2)
        if pd.notna(row["Job Size"]) and row["Job Size"] > 0
        else 0,
        axis=1
    )

    try:
        df.to_excel(EXCEL_PATH, index=False)
    except PermissionError:
        pass

    df = df.sort_values(by="WSJF", ascending=False)
    features = df.to_dict(orient="records")
    return render_template("wsjf.html", features=features)

# ==================================================
# CAPACITY PAGE (UNCHANGED)
# ==================================================
@app.route("/capacity")
def capacity():
    import math

    TEAM_MEMBERS = [
        {"name": "John", "role": "Backend Engineer", "leaves": 10, "last_sprint_sp": 7},
        {"name": "Tom", "role": "Frontend Engineer", "leaves": 4, "last_sprint_sp": 6},
        {"name": "Sarah", "role": "QA Engineer", "leaves": 2, "last_sprint_sp": 8},
        {"name": "Emma", "role": "Scrum Master", "leaves": 6, "last_sprint_sp": 5},
    ]

    member_details = []
    total_cap_days = 0  # this is fte/days across the PI window

    for m in TEAM_MEMBERS:
        cap_days = round((60 - m["leaves"]) * 0.7, 0)  # PI capacity in days
        total_cap_days += cap_days

        member_details.append({
            **m,
            "cap": cap_days,
            # show per-sprint average (whole number) - display only
            "sprint_avg": round(cap_days / 6)
        })

    # ✅ Committable Story Points (no rounding inflation)
    # Convert total PI-days -> SP per sprint (floor), then multiply by 6 sprints
    sp_per_sprint = math.floor(total_cap_days / 6)
    total_sp_pi = sp_per_sprint * 6

    # Your score logic (keep as-is, but base on days)
    score = min(int((total_cap_days / 300) * 100), 100)
    status = "green" if total_cap_days >= 300 else "amber" if total_cap_days >= 270 else "red"

    return render_template(
        "capacity.html",
        members=member_details,
        capacity=int(total_cap_days),     # ✅ still days
        total_sp=total_sp_pi,             # ✅ PI commitment in SP (e.g., 150)
        sp_per_sprint=sp_per_sprint,      # ✅ optional display (e.g., 25)
        status=status,
        score=score
    )

# ==================================================
# PI PLANNING PAGE (UNCHANGED)
# ==================================================
@app.route("/pi")
def pi_planning():
    df = ensure_excel_with_features()

    # Ensure numeric fields
    for col in ["Business Value", "Time Complexity", "OE/RR Value", "Job Size"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Recalculate WSJF (same logic as WSJF page)
    bv = df["Business Value"].fillna(0)
    tc = df["Time Complexity"].fillna(0)
    oe = df["OE/RR Value"].fillna(0)

    df["Cost of Delay"] = bv + tc + oe

    df["WSJF"] = df.apply(
        lambda row: round(row["Cost of Delay"] / row["Job Size"], 2)
        if pd.notna(row["Job Size"]) and row["Job Size"] > 0
        else 0,
        axis=1
    )

    # 🔥 SORT BY WSJF DESCENDING
    df = df.sort_values(by="WSJF", ascending=False)

    # Pass WSJF also (nothing else)
    features = df[["Feature Name", "WSJF","Story Points"]].to_dict(orient="records")

    return render_template("pi_planning.html", features=features)


# ==================================================
# EXPORT EXCEL
# ==================================================
@app.route("/export/wsjf")
def export_wsjf():
    return send_file(EXCEL_PATH, as_attachment=True)

# ==================================================
# POKER: Start a session per feature
# ==================================================
@app.route("/start_poker/<feature_id>")
def start_poker(feature_id):
    session_id = f"POKER-{feature_id}"

    if session_id not in POKER_SESSIONS:
        POKER_SESSIONS[session_id] = {
            "feature_id": feature_id,
            "users": set(),
            "host_name": None,
            "revealed": False,
            "votes": {field: {} for field in ESTIMATION_FIELDS},
            "consensus": {}
        }

    return redirect(url_for("poker_lobby", session_id=session_id))

# ==================================================
# POKER: Lobby (join session) — first join becomes host
# ==================================================
@app.route("/poker/<session_id>", methods=["GET", "POST"])
def poker_lobby(session_id):
    s = POKER_SESSIONS.get(session_id)
    if not s:
        return "Session not found", 404

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            return render_template("poker_lobby.html", session_id=session_id, error="Name is required.", host_name=s.get("host_name"))

        session["user"] = name
        session["poker_session"] = session_id

        s["users"].add(name)

        # Assign host if not set
        if not s.get("host_name"):
            s["host_name"] = name

        return redirect(url_for("poker_room", session_id=session_id))

    return render_template("poker_lobby.html", session_id=session_id, error=None, host_name=s.get("host_name"))

# ==================================================
# POKER: Room (vote)
# ==================================================
@app.route("/poker/<session_id>/room")
def poker_room(session_id):
    s = POKER_SESSIONS.get(session_id)
    if not s:
        return "Session not found", 404
    if "user" not in session:
        return redirect(url_for("poker_lobby", session_id=session_id))

    df = ensure_excel_with_features()
    row = df[df["Feature ID"] == s["feature_id"]]
    feature_name = row.iloc[0]["Feature Name"] if not row.empty else s["feature_id"]

    username = session["user"]
    is_host = (username == s.get("host_name"))

    # Your own selections (so we can show them immediately on load)
    your_votes = {}
    for field in ESTIMATION_FIELDS:
        your_votes[field] = s["votes"].get(field, {}).get(username)

    return render_template(
        "poker_room.html",
        session_id=session_id,
        feature_id=s["feature_id"],
        feature_name=feature_name,
        fields=ESTIMATION_FIELDS,
        fibo=FIBO_DECK,
        users=sorted(list(s["users"])),
        username=username,
        host_name=s.get("host_name"),
        is_host=is_host,
        your_votes=your_votes
    )

# ==================================================
# API: Current state (vote status + your selections)
# - Shows only who voted (not values) unless revealed
# - Always shows your own selected values
# ==================================================
@app.route("/api/state/<session_id>")
def api_state(session_id):
    s = POKER_SESSIONS.get(session_id)
    if not s:
        return jsonify({"error": "Session not found"}), 404
    if "user" not in session:
        return jsonify({"error": "Not joined"}), 401

    username = session["user"]
    revealed = bool(s.get("revealed"))

    fields_state = {}
    for field in ESTIMATION_FIELDS:
        votes = s["votes"].get(field, {})
        voted_users = sorted(list(votes.keys()))

        fields_state[field] = {
            "voted_users": voted_users,
            "your_value": votes.get(username),
            "values": votes if revealed else None
        }

    return jsonify({
        "session_id": session_id,
        "feature_id": s.get("feature_id"),
        "users": sorted(list(s.get("users", []))),
        "host_name": s.get("host_name"),
        "revealed": revealed,
        "consensus": s.get("consensus", {}),
        "fields": fields_state
    })

# ==================================================
# API: Submit vote
# ==================================================
@app.route("/api/vote", methods=["POST"])
def api_vote():
    if "user" not in session:
        return jsonify({"error": "Not joined"}), 401

    data = request.get_json(force=True)
    session_id = data.get("session")
    field = data.get("field")
    value = data.get("value")

    s = POKER_SESSIONS.get(session_id)
    if not s:
        return jsonify({"error": "Session not found"}), 404
    if field not in ESTIMATION_FIELDS:
        return jsonify({"error": "Invalid field"}), 400

    try:
        value_int = int(value)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid value"}), 400

    user = session["user"]

    # once voting changes, hide reveal again until host reveals
    s["revealed"] = False
    s["consensus"] = {}

    s["votes"][field][user] = value_int
    return jsonify({"status": "ok"})

# ==================================================
# API: Reveal consensus (HOST ONLY)
# ==================================================
@app.route("/api/reveal/<session_id>")
def api_reveal(session_id):
    if not _require_host(session_id):
        return jsonify({"error": "Host only"}), 403

    s = POKER_SESSIONS.get(session_id)
    s["revealed"] = True

    consensus = {}
    for field, votes in s["votes"].items():
        if not votes:
            consensus[field] = None
            continue
        avg = sum(votes.values()) / len(votes)
        consensus[field] = nearest_fibo(avg)

    s["consensus"] = consensus
    return jsonify(consensus)

# ==================================================
# API: Commit consensus to Excel (HOST ONLY)
# ==================================================
@app.route("/api/commit/<session_id>")
def api_commit(session_id):
    if not _require_host(session_id):
        return jsonify({"error": "Host only"}), 403

    s = POKER_SESSIONS.get(session_id)
    fid = s["feature_id"]

    df = ensure_excel_with_features()

    # Commit to Excel columns
    for col, val in s.get("consensus", {}).items():
        if col in df.columns and val is not None:
            df.loc[df["Feature ID"] == fid, col] = val

    try:
        df.to_excel(EXCEL_PATH, index=False)
    except PermissionError:
        return jsonify({"error": "Excel file open; close it and try again."}), 409

    return jsonify({"status": "saved"})

# ==================================================
if __name__ == "__main__":
    app.run(debug=True)
