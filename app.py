from flask import Flask, render_template, send_file, request, redirect, url_for, session, jsonify
import pandas as pd
import os
import json
import re
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = "local-dev-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXCEL_PATH = os.path.join(DATA_DIR, "wsjf_features.xlsx")
USER_STORIES_PATH = os.path.join(DATA_DIR, "user_stories.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ==================================================
# OPENAI (API) - lightweight requests client
# ==================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# ==================================================
# AI FEATURE QUALITY (IN-MEMORY CACHE)
# ==================================================
AI_QUALITY_CACHE = {}  # { feature_id: {"result": {...}, "ts": "..."} }

AI_QUALITY_SYSTEM_PROMPT = (
    "You are an expert SAFe Program Consultant, Senior Agile Coach, and Enterprise Product Strategist.\n\n"
    "You specialize in:\n"
    "- WSJF prioritization\n"
    "- SAFe Feature definition standards\n"
    "- INVEST and SMART criteria\n"
    "- Acceptance criteria quality\n"
    "- Outcome-driven product management\n"
    "- Risk and dependency analysis\n"
    "- Enterprise architecture alignment\n\n"
    "Your job is to critically assess the quality of a Feature used in PI Planning.\n\n"
    "Be direct, analytical, and practical.\n"
    "Do NOT give generic advice.\n"
    "Be specific and actionable.\n"
    "Score objectively.\n\n"
    "Return structured output in JSON format only."
)


def _openai_chat(messages, temperature: float = 0.2, max_tokens: int = 1600) -> str:
    """Calls OpenAI Chat Completions via HTTPS.

    Note: keep implementation dependency-free. Requires OPENAI_API_KEY.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"OpenAI error {r.status_code}: {r.text}")
    data = r.json()
    return data["choices"][0]["message"]["content"]


def _safe_json_loads(text: str):
    """Robust JSON parsing: prefers full string; falls back to extracting first JSON object."""
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


def _safe_num(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def _read_user_stories():
    if not os.path.exists(USER_STORIES_PATH):
        return {"features": {}}
    try:
        with open(USER_STORIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # if file is corrupted, do not crash the app
        return {"features": {}}


def _write_user_stories(payload: dict):
    tmp = USER_STORIES_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, USER_STORIES_PATH)


def _get_feature_by_id(feature_id: str):
    df = ensure_excel_with_features()
    row = df[df["Feature ID"] == feature_id]
    if row.empty:
        return None
    r = row.iloc[0].to_dict()
    return {
        "Feature ID": str(r.get("Feature ID", "")),
        "Feature Name": str(r.get("Feature Name", "")),
        "Feature Description": str(r.get("Feature Description", "")),
        "Feature Acceptance Criteria": str(r.get("Feature Acceptance Criteria", "")),
    }


def build_ai_feature_quality_user_prompt(row: dict) -> str:
    feature_id = str(row.get("Feature ID", "")).strip()
    feature_name = str(row.get("Feature Name", "")).strip()
    feature_description = str(row.get("Feature Description", "")).strip()
    acceptance_criteria = str(row.get("Feature Acceptance Criteria", "")).strip()

    business_value = _safe_num(row.get("Business Value"))
    time_criticality = _safe_num(row.get("Time Complexity"))
    oe_rr = _safe_num(row.get("OE/RR Value"))
    job_size = _safe_num(row.get("Job Size"))
    story_points = _safe_num(row.get("Story Points"))

    cost_of_delay = business_value + time_criticality + oe_rr
    wsjf = round(cost_of_delay / job_size, 2) if job_size > 0 else 0

    return f"""You are assessing the following Feature used in PI Planning.

Feature ID: {feature_id}
Feature Name: {feature_name}

Description:
{feature_description}

Acceptance Criteria:
{acceptance_criteria}

Current WSJF Inputs:
- Business Value: {business_value}
- Time Criticality: {time_criticality}
- OE / RR Value: {oe_rr}
- Job Size: {job_size}
- Story Points: {story_points}
- Calculated Cost of Delay: {round(cost_of_delay, 2)}
- Calculated WSJF: {wsjf}

---

Evaluate this Feature on the following dimensions (score 1–5 where 5 is excellent):

1. Strategic Alignment (Does it clearly link to business outcome or OKR?)
2. Clarity of Problem Statement
3. Quality of Acceptance Criteria
4. Testability & Measurability
5. Size Appropriateness (Is it feature-sized or too large/small?)
6. Risk Visibility (Dependencies, compliance, architecture impact)
7. WSJF Input Justification (Do the numbers logically match the feature?)

For each dimension:
- Give a score (1–5)
- Provide 2–3 lines explaining WHY
- Suggest 1 concrete improvement

Then provide:

- Overall Feature Quality Score (average out of 5)
- Maturity Level:
    1. Weak
    2. Needs Refinement
    3. PI-Ready with Risks
    4. Strong
    5. Exemplary

- Top 3 Improvements Required Before PI Commitment
- A rewritten improved Feature version (concise, high-quality)

Return response strictly in JSON with this structure:

{{
  "dimension_scores": [
    {{
      "dimension": "",
      "score": 0,
      "reason": "",
      "improvement": ""
    }}
  ],
  "overall_score": 0,
  "maturity_level": "",
  "top_3_improvements": [],
  "improved_feature_version": ""
}}
"""


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
    return "user" in session


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
# API: AI Feature Quality Assessment
# ==================================================
@app.route("/api/feature_quality/<feature_id>", methods=["POST"])
def api_feature_quality(feature_id):
    cache_hit = AI_QUALITY_CACHE.get(feature_id)
    if cache_hit and isinstance(cache_hit, dict) and cache_hit.get("result"):
        return jsonify({"cached": True, **cache_hit["result"]})

    feature = _get_feature_by_id(feature_id)
    if not feature:
        return jsonify({"error": "Feature not found"}), 404

    if not OPENAI_API_KEY:
        return jsonify({"error": "Missing OPENAI_API_KEY environment variable"}), 500

    df = ensure_excel_with_features()
    row_df = df[df["Feature ID"] == feature_id]
    if row_df.empty:
        return jsonify({"error": "Feature not found"}), 404

    row = row_df.iloc[0].to_dict()
    user_prompt = build_ai_feature_quality_user_prompt(row)

    try:
        content = _openai_chat(
            messages=[
                {"role": "system", "content": AI_QUALITY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1800,
        )

        data = _safe_json_loads(content)

        result = {
            "feature_id": feature_id,
            "feature_name": str(row.get("Feature Name", "")),
            "assessment": {
                "dimension_scores": data.get("dimension_scores", []),
                "overall_score": data.get("overall_score", 0),
                "maturity_level": data.get("maturity_level", ""),
                "top_3_improvements": data.get("top_3_improvements", []),
                "improved_feature_version": data.get("improved_feature_version", ""),
            },
        }

        AI_QUALITY_CACHE[feature_id] = {"result": result, "ts": datetime.utcnow().isoformat() + "Z"}
        return jsonify({"cached": False, **result})

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Failed to evaluate feature quality"}), 500


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
    total_cap_days = 0  # fte/days across PI

    for m in TEAM_MEMBERS:
        cap_days = round((60 - m["leaves"]) * 0.7, 0)  # PI capacity in days
        total_cap_days += cap_days

        member_details.append({
            **m,
            "cap": cap_days,
            "sprint_avg": round(cap_days / 6)
        })

    sp_per_sprint = math.floor(total_cap_days / 6)
    total_sp_pi = sp_per_sprint * 6

    score = min(int((total_cap_days / 300) * 100), 100)
    status = "green" if total_cap_days >= 300 else "amber" if total_cap_days >= 270 else "red"

    return render_template(
        "capacity.html",
        members=member_details,
        capacity=int(total_cap_days),
        total_sp=total_sp_pi,
        sp_per_sprint=sp_per_sprint,
        status=status,
        score=score
    )


# ==================================================
# PI PLANNING PAGE
# ==================================================
@app.route("/pi")
def pi_planning():
    df = ensure_excel_with_features()

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

    df = df.sort_values(by="WSJF", ascending=False)
    features = df[["Feature ID", "Feature Name", "WSJF", "Story Points"]].to_dict(orient="records")

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

        if not s.get("host_name"):
            s["host_name"] = name

        return redirect(url_for("poker_room", session_id=session_id))

    return render_template("poker_lobby.html", session_id=session_id, error=None, host_name=s.get("host_name"))


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

    s["revealed"] = False
    s["consensus"] = {}

    s["votes"][field][user] = value_int
    return jsonify({"status": "ok"})


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


@app.route("/api/commit/<session_id>")
def api_commit(session_id):
    if not _require_host(session_id):
        return jsonify({"error": "Host only"}), 403

    s = POKER_SESSIONS.get(session_id)
    fid = s["feature_id"]

    df = ensure_excel_with_features()

    for col, val in s.get("consensus", {}).items():
        if col in df.columns and val is not None:
            df.loc[df["Feature ID"] == fid, col] = val

    try:
        df.to_excel(EXCEL_PATH, index=False)
    except PermissionError:
        return jsonify({"error": "Excel file open; close it and try again."}), 409

    return jsonify({"status": "saved"})


# ==================================================
# AI: Feature -> User Story breakdown (SIMPLE)
# ==================================================
@app.route("/api/ai/breakdown_feature", methods=["POST"])
def api_ai_breakdown_feature():
    data = request.get_json(force=True)
    feature_id = (data.get("feature_id") or "").strip()

    if not feature_id:
        return jsonify({"error": "feature_id is required"}), 400

    feature = _get_feature_by_id(feature_id)
    if not feature:
        return jsonify({"error": "Feature not found"}), 404

    system = (
        "You are an expert Agile Product Owner. "
        "Break down a SAFe Feature into clear, sprint-implementable user stories. "
        "Keep it simple and practical. Avoid over-engineering."
    )

    user = f"""
Break down this Feature into user stories.

Feature ID: {feature['Feature ID']}
Feature Name: {feature['Feature Name']}
Feature Description: {feature['Feature Description']}
Feature Acceptance Criteria:
{feature['Feature Acceptance Criteria']}

Rules:
- Create a sensible set of stories (typically 5–10) that cover end-to-end delivery.
- Use classic format: As a <role>, I want <capability>, so that <benefit>.
- Include acceptance criteria (3–6 bullets per story).
- Mention dependencies only if truly required.
- If discovery/unknowns exist, include a spike explicitly with type="spike".
- Do NOT include any story point estimation.
- Output MUST be valid JSON only.

Return JSON in this exact shape:
{{
  "feature_id": "...",
  "feature_name": "...",
  "stories": [
    {{
      "story_id": "USR-001",
      "title": "...",
      "user_story": "As a ...",
      "acceptance_criteria": ["..."],
      "type": "story|spike",
      "dependencies": ["..."]
    }}
  ]
}}
"""

    try:
        content = _openai_chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=1700,
        )

        payload = _safe_json_loads(content)
        payload.setdefault("feature_id", feature["Feature ID"])
        payload.setdefault("feature_name", feature["Feature Name"])

        stories = payload.get("stories") or []
        if not isinstance(stories, list) or len(stories) == 0:
            return jsonify({"error": "AI returned no stories"}), 502

        # normalize
        for i, s in enumerate(stories, start=1):
            if not isinstance(s, dict):
                continue
            s.setdefault("story_id", f"USR-{i:03d}")
            s.setdefault("type", "story")
            s.setdefault("dependencies", [])
            s.pop("suggested_sp", None)

        payload["stories"] = stories
        return jsonify(payload)

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Failed to generate breakdown"}), 500


# ==================================================
# User Stories storage: Accept + Fetch (NO SP)
# ==================================================
@app.route("/api/user_stories/accept", methods=["POST"])
def api_user_stories_accept():
    data = request.get_json(force=True)
    feature_id = (data.get("feature_id") or "").strip()
    feature_name = (data.get("feature_name") or "").strip()
    stories = data.get("stories") or []

    if not feature_id or not isinstance(stories, list) or len(stories) == 0:
        return jsonify({"error": "feature_id and stories[] are required"}), 400

    norm = []
    for i, s in enumerate(stories, start=1):
        if not isinstance(s, dict):
            continue
        norm.append({
            "story_id": str(s.get("story_id") or f"USR-{i:03d}"),
            "title": str(s.get("title") or "").strip(),
            "user_story": str(s.get("user_story") or "").strip(),
            "acceptance_criteria": s.get("acceptance_criteria") if isinstance(s.get("acceptance_criteria"), list) else [],
            "type": str(s.get("type") or "story"),
            "dependencies": s.get("dependencies") if isinstance(s.get("dependencies"), list) else [],
        })

    db = _read_user_stories()
    db.setdefault("features", {})
    db["features"][feature_id] = {
        "feature_id": feature_id,
        "feature_name": feature_name or (_get_feature_by_id(feature_id) or {}).get("Feature Name", ""),
        "accepted_at": datetime.utcnow().isoformat() + "Z",
        "stories": norm,
    }
    _write_user_stories(db)
    return jsonify({"status": "saved", "feature_id": feature_id, "stories": len(norm)})


@app.route("/api/user_stories")
def api_user_stories_all():
    db = _read_user_stories()
    features = (db.get("features") or {})

    flat = []
    for fid, block in features.items():
        fname = (block or {}).get("feature_name", "")
        for s in (block or {}).get("stories", []) or []:
            flat.append({
                "feature_id": fid,
                "feature_name": fname,
                **s,
            })
    return jsonify({"stories": flat, "feature_count": len(features)})


# ==================================================
# Planning data feeds (Features vs User Stories)
# ==================================================
@app.route("/api/planning/features")
def api_planning_features():
    df = ensure_excel_with_features()

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
    df = df.sort_values(by="WSJF", ascending=False)

    out = []
    for _, r in df.iterrows():
        sp = r.get("Story Points")
        try:
            sp = int(sp) if pd.notna(sp) else 0
        except Exception:
            sp = 0

        out.append({
            "type": "feature",
            "id": str(r.get("Feature ID", "")),
            "title": str(r.get("Feature Name", "")),
            "wsjf": float(r.get("WSJF") or 0),
            "sp": sp,
        })
    return jsonify({"items": out})


@app.route("/api/planning/stories")
def api_planning_stories():
    db = _read_user_stories()
    features = (db.get("features") or {})

    out = []
    for fid, block in features.items():
        fname = (block or {}).get("feature_name", "")
        for s in (block or {}).get("stories", []) or []:
            out.append({
                "type": "story",
                "id": f"{fid}:{s.get('story_id','')}",
                "feature_id": fid,
                "feature_name": fname,
                "title": str(s.get("title") or s.get("story_id") or "User Story"),
                "story_id": str(s.get("story_id") or ""),
            })

    return jsonify({"items": out, "feature_count": len(features)})


# ==================================================
if __name__ == "__main__":
    app.run(debug=True)