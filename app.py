from flask import Flask, render_template, send_file
import pandas as pd
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXCEL_PATH = os.path.join(DATA_DIR, "wsjf_features.xlsx")

os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# SAFe FEATURE GENERATOR
# -----------------------------
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

# -----------------------------
# ENSURE EXCEL EXISTS AND HAS DATA
# -----------------------------
def ensure_excel_with_features():
    if not os.path.exists(EXCEL_PATH):
        print("📄 Excel missing → generating features")
        df = generate_safe_features_df()
    else:
        df = pd.read_excel(EXCEL_PATH)
        if df.empty:
            print("📄 Excel empty → regenerating features")
            df = generate_safe_features_df()
        else:
            print(f"📄 Excel loaded with {len(df)} rows")
            return df

    # Add WSJF columns
    for col in [
        "Business Value",
        "Time Criticality",
        "OE / RR Value",
        "Job Size",
        "Cost of Delay",
        "WSJF",
        "Story Points",
    ]:
        if col not in df.columns:
            df[col] = ""

    df.to_excel(EXCEL_PATH, index=False)
    return df

# -----------------------------
# WSJF PAGE
# -----------------------------
@app.route("/")
@app.route("/wsjf")
def wsjf():
    df = ensure_excel_with_features()

    # Numeric safety
    for col in ["Business Value", "Time Criticality", "OE / RR Value", "Job Size"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Cost of Delay"] = (
        df["Business Value"] +
        df["Time Criticality"] +
        df["OE / RR Value"]
    )

    df["WSJF"] = (df["Cost of Delay"] / df["Job Size"]).round(2)

    try:
        df.to_excel(EXCEL_PATH, index=False)
    except PermissionError:
        print("⚠️ Excel open – skipping write")

    features = df.to_dict(orient="records")
    print(f"➡️ Sending {len(features)} features to UI")

    return render_template("wsjf.html", features=features)

# -----------------------------
# EXPORT
# -----------------------------
@app.route("/export/wsjf")
def export_wsjf():
    return send_file(EXCEL_PATH, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
