"""
Flask server for Pocketly Social Intelligence Dashboard.
Serves the dashboard and exposes the latest report via API.
"""

import glob
import json
import os
from flask import Flask, jsonify, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

app = Flask(__name__)


@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "dashboard.html"))


@app.route("/api/latest-report")
def latest_report():
    reports = sorted(glob.glob(os.path.join(REPORTS_DIR, "pocketly_social_raw_*.json")))
    if not reports:
        return jsonify({"error": "No reports available yet."}), 404
    with open(reports[-1], encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/report-dates")
def report_dates():
    reports = sorted(glob.glob(os.path.join(REPORTS_DIR, "pocketly_social_raw_*.json")), reverse=True)
    dates = [os.path.basename(r).replace("pocketly_social_raw_", "").replace(".json", "") for r in reports]
    return jsonify(dates)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
