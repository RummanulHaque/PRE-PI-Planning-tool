from flask import Flask, render_template, send_file, request, jsonify
import pandas as pd
import os

app = Flask(__name__)

# Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXCEL_PATH = os.path.join(DATA_DIR, "wsjf_features.xlsx")
os.makedirs(DATA_DIR, exist_ok=True)

# ==================================================
# RUMI'S FEATURE GENERATOR (Ensures data exists)
# ==================================================
def generate_safe_features_df():
    return pd.DataFrame([
        {
            "Feature ID": "FTR-PI-001",
            "Feature Name": "Payments Modernization",
            "Feature Description": "Modernize payment processing to meet regulatory and customer expectations.",
            "Feature Acceptance Criteria": "• Regulatory compliance met\n• Zero manual reconciliation\n• Peak load validated",
        },
        {
            "Feature ID": "FTR-PI-002",
            "Feature Name": "Customer Analytics Platform",
            "Feature Description": "Unified customer analytics so that decisions are data-driven.",
            "Feature Acceptance Criteria": "• Single source of truth\n• GDPR compliant\n• Business dashboards available",
        },
        {
            "Feature ID": "FTR-PI-003",
            "Feature Name": "Legacy System Decommissioning",
            "Feature Description": "Retire legacy systems to reduce risk and maintenance costs.",
            "Feature Acceptance Criteria": "• No active consumers\n• Data archived\n• Support contracts closed",
        },
        {
            "Feature ID": "FTR-PI-004",
            "Feature Name": "AI Assisted Support",
            "Feature Description": "Implement AI assistance to improve resolution time and accuracy.",
            "Feature Acceptance Criteria": "• Accuracy threshold met\n• Human override enabled\n• Audit logs available",
        },
        {
            "Feature ID": "FTR-PI-005",
            "Feature Name": "Mobile Experience Revamp",
            "Feature Description": "Revamp the mobile UI for intuitive customer interactions.",
            "Feature Acceptance Criteria": "• UX council approved\n• Performance benchmarks met\n• Rating improvement tracked",
        }
    ])

def ensure_excel_with_features():
    if not os.path.exists(EXCEL_PATH):
        df = generate_safe_features_df()
    else:
        df = pd.read_excel(EXCEL_PATH)
        if df.empty:
            df = generate_safe_features_df()
        else:
            return df

    # Add WSJF columns if they don't exist
    cols = ["Business Value", "Time Complexity", "OE/RR Value", "Job Size", "Cost of Delay", "WSJF", "Story Points"]
    for col in cols:
        if col not in df.columns:
            df[col] = 0

    df.to_excel(EXCEL_PATH, index=False)
    return df

# ==================================================
# WSJF PAGE (Calculates live based on Poker)
# ==================================================
@app.route("/")
@app.route("/wsjf")
def wsjf():
    df = ensure_excel_with_features()

    # Numeric safety for math
    for col in ["Business Value", "Time Complexity", "OE/RR Value", "Job Size"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # SAFe WSJF Calculation 
    df["Cost of Delay"] = df["Business Value"] + df["Time Complexity"] + df["OE/RR Value"]
    df["WSJF"] = df.apply(lambda row: round(row["Cost of Delay"] / row["Job Size"], 2) if row["Job Size"] > 0 else 0, axis=1)

    # Save calculated values to Excel
    try:
        df.to_excel(EXCEL_PATH, index=False)
    except PermissionError:
        pass # Handle if file is open in Excel

    # Sort: Highest WSJF first for prioritization
    df = df.sort_values(by="WSJF", ascending=False)
    features = df.to_dict(orient="records")
    return render_template("wsjf.html", features=features)

# ==================================================
# SAVE POKER INPUTS (Live from Modal)
# ==================================================
@app.route("/save_poker", methods=["POST"])
def save_poker():
    data = request.json
    feature_id = data.get("id")
    
    df = pd.read_excel(EXCEL_PATH)
    
    # Update values for the specific feature row
    idx = df[df['Feature ID'] == feature_id].index
    if not idx.empty:
        df.loc[idx, "Business Value"] = data.get("bv")
        df.loc[idx, "Time Complexity"] = data.get("tc")
        df.loc[idx, "OE/RR Value"] = data.get("rroe")
        df.loc[idx, "Job Size"] = data.get("size")
        df.to_excel(EXCEL_PATH, index=False)
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Feature not found"}), 404

# ==================================================
# CAPACITY PAGE
# ==================================================
@app.route("/capacity")
def capacity():
    TEAM_MEMBERS = [
        {"name": "John", "leaves": 10},
        {"name": "Tom", "leaves": 4},
        {"name": "Sarah", "leaves": 2},
        {"name": "Emma", "leaves": 6},
    ]

    member_details = []
    total_cap = 0
    for m in TEAM_MEMBERS:
        cap = round((60 - m["leaves"]) * 0.7, 0)
        total_cap += cap
        member_details.append({**m, "cap": cap, "sprint_avg": round(cap / 6, 1)})

    score = min(int((total_cap / 300) * 100), 100)
    status = "green" if total_cap >= 270 else "amber"
    return render_template("capacity.html", members=member_details, capacity=int(total_cap), status=status, score=score)

# ==================================================
# PI PLANNING PAGE
# ==================================================
@app.route("/pi")
def pi_planning():
    df = pd.read_excel(EXCEL_PATH)
    # Only show features sorted by WSJF for the draggable bank
    df["Cost of Delay"] = df["Business Value"] + df["Time Complexity"] + df["OE/RR Value"]
    df["WSJF"] = df.apply(lambda row: round(row["Cost of Delay"] / row["Job Size"], 2) if row["Job Size"] > 0 else 0, axis=1)
    
    df = df.sort_values(by="WSJF", ascending=False)
    features = df.to_dict(orient="records")
    return render_template("pi_planning.html", features=features)

@app.route("/export/wsjf")
def export_wsjf():
    return send_file(EXCEL_PATH, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)