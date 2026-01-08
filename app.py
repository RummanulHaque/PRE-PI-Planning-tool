from flask import Flask, render_template, request

app = Flask(__name__)

# ==========================================
# ENTERPRISE DATA (Updated with more features)
# ==========================================
FEATURES = [
    {"name": "Payments Modernization", "label": "Finance", "bv": 13, "tc": 8, "rr": 5, "size": 8,
     "rationale": "Critical for UPI 2.0 compliance."},
    {"name": "Customer Analytics", "label": "Marketing", "bv": 8, "tc": 5, "rr": 3, "size": 5,
     "rationale": "Required for personalized ads."},
    {"name": "Legacy Decommission", "label": "Infrastructure", "bv": 5, "tc": 13, "rr": 8, "size": 13,
     "rationale": "High maintenance cost on old servers."},
    {"name": "AI Chatbot Beta", "label": "AI/ML", "bv": 21, "tc": 3, "rr": 5, "size": 13,
     "rationale": "Competitor advantage."},
    {"name": "Mobile UI Refresh", "label": "UX", "bv": 5, "tc": 5, "rr": 2, "size": 3,
     "rationale": "Improves retention rates."},
    {"name": "Cloud Migration", "label": "IT", "bv": 8, "tc": 21, "rr": 13, "size": 21,
     "rationale": "Security mandate for 2026."}
]

TEAM_MEMBERS = [
    {"name": "John", "leaves": 10},
    {"name": "Tom", "leaves": 4},
    {"name": "Sarah", "leaves": 2},
    {"name": "Emma", "leaves": 6}
]


# ==========================================
# ROUTES
# ==========================================

# SCREEN 1: WSJF (Landing Page)
@app.route("/")
@app.route("/wsjf")
def wsjf():
    computed = []
    for f in FEATURES:
        # WSJF Formula: (BV + TC + RR) / Size
        cod = f["bv"] + f["tc"] + f["rr"]
        computed.append({**f, "cod": cod, "wsjf": round(cod / f["size"], 2)})
    # Sort by priority
    return render_template("wsjf.html", features=sorted(computed, key=lambda x: x["wsjf"], reverse=True))


# SCREEN 2: CAPACITY PLANNING
@app.route("/capacity")
def capacity():
    member_details = []
    total_cap = 0
    # Average 60 working days in a quarter, 0.7 Focus Factor
    for m in TEAM_MEMBERS:
        cap = round((60 - m['leaves']) * 0.7, 0)
        total_cap += cap
        member_details.append({**m, "cap": cap, "sprint_avg": round(cap / 6, 1)})

    # Status logic based on target of 300 mandays
    score = min(int((total_cap / 300) * 100), 100)
    status = "green" if total_cap >= 300 else "amber" if total_cap >= 270 else "red"

    return render_template("capacity.html", members=member_details, capacity=int(total_cap), status=status, score=score)


# SCREEN 3: PI PLANNING (Story Point Rows & Right-Click Split)
@app.route("/pi")
def pi_planning():
    return render_template("pi_planning.html", features=FEATURES)


if __name__ == "__main__":
    app.run(debug=True)
