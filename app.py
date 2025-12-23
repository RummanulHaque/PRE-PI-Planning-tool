from flask import Flask, render_template, request

app = Flask(__name__)

# =========================
# HARD-CODED DEMO DATA
# =========================
TEAM_SIZE = 8
WORKING_DAYS = 60
FOCUS_FACTOR = 0.7
PLANNED_DEMAND = 300

FEATURES = [
    {"name": "Payments Modernization", "bv": 13, "tc": 8, "rr": 5, "size": 8},
    {"name": "Customer Analytics", "bv": 8, "tc": 5, "rr": 3, "size": 5},
    {"name": "Legacy Decommission", "bv": 5, "tc": 13, "rr": 8, "size": 13},
]

SPRINT_CAPACITY = 40

SPRINTS = {
    "Sprint 1": ["Payments Modernization"],
    "Sprint 2": ["Customer Analytics"],
    "Sprint 3": ["Legacy Decommission"],
    "Sprint 4": [],
    "Sprint 5": [],
    "Sprint 6": [],
}

DEPENDENCIES = {
    "Legacy Decommission": "Payments Modernization"
}

# =========================
# ROUTES
# =========================

@app.route("/", methods=["GET", "POST"])
def capacity():
    leaves = int(request.form.get("leaves", 0))
    available_days = WORKING_DAYS - leaves
    capacity = int(available_days * TEAM_SIZE * FOCUS_FACTOR)

    if capacity >= PLANNED_DEMAND:
        status = "green"
        score = 85
    elif capacity >= PLANNED_DEMAND * 0.9:
        status = "amber"
        score = 65
    else:
        status = "red"
        score = 40

    return render_template(
        "capacity.html",
        capacity=capacity,
        status=status,
        score=score
    )


@app.route("/wsjf")
def wsjf():
    computed = []

    for f in FEATURES:
        cod = f["bv"] + f["tc"] + f["rr"]
        wsjf = round(cod / f["size"], 2)

        computed.append({
            "name": f["name"],
            "cod": cod,
            "size": f["size"],
            "wsjf": wsjf
        })

    computed.sort(key=lambda x: x["wsjf"], reverse=True)

    return render_template("wsjf.html", features=computed)


@app.route("/pi")
def pi():
    sprint_loads = {}
    dependency_risks = []

    for sprint, items in SPRINTS.items():
        load = sum(f["size"] for f in FEATURES if f["name"] in items)
        sprint_loads[sprint] = load

    for feature, depends_on in DEPENDENCIES.items():
        feature_sprint = None
        dependency_sprint = None

        for sprint, items in SPRINTS.items():
            if feature in items:
                feature_sprint = sprint
            if depends_on in items:
                dependency_sprint = sprint

        if dependency_sprint and feature_sprint and dependency_sprint > feature_sprint:
            dependency_risks.append(feature)

    # PI CONFIDENCE SCORE
    confidence = 100
    for load in sprint_loads.values():
        if load > SPRINT_CAPACITY:
            confidence -= 20
    if dependency_risks:
        confidence -= 15

    if confidence >= 75:
        confidence_status = "green"
    elif confidence >= 50:
        confidence_status = "amber"
    else:
        confidence_status = "red"

    return render_template(
        "pi_planning.html",
        sprints=sprint_loads,
        capacity=SPRINT_CAPACITY,
        risks=dependency_risks,
        confidence=confidence,
        confidence_status=confidence_status
    )


if __name__ == "__main__":
    app.run(debug=True)
