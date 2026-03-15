"""
╔══════════════════════════════════════════════════════════════╗
║         MCQ ANALYZER — LICENSE SERVER (Flask)               ║
║                                                              ║
║  Deploy karne ka tarika:                                     ║
║  1. pip install flask                                        ║
║  2. python license_server.py                                 ║
║                                                              ║
║  Free hosting ke liye:                                       ║
║  - Railway.app  (recommended - free)                         ║
║  - Render.com   (free)                                       ║
║  - PythonAnywhere.com (free)                                 ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
import hashlib, hmac, json, os, datetime, uuid

app = Flask(__name__)

# ── Secret key — yeh SIRF server pe rakho, kabhi share mat karo ──
SECRET_KEY = "MCQ_ANALYZER_SECRET_2025_XK9#mQ"

# ── License database (simple JSON file) ──────────────────────────
DB_FILE = "licenses.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

# ── Hardware ID generate karna ────────────────────────────────────
def get_machine_fingerprint(hwid):
    """HWID ko secret key se hash karta hai."""
    return hmac.new(SECRET_KEY.encode(),
                    hwid.encode(), hashlib.sha256).hexdigest()

# ── License key generate karna ───────────────────────────────────
def generate_license_key():
    """Format: MCQA-XXXX-XXXX-XXXX-XXXX"""
    uid = uuid.uuid4().hex.upper()
    return f"MCQA-{uid[0:4]}-{uid[4:8]}-{uid[8:12]}-{uid[12:16]}"

# ════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ════════════════════════════════════════════════════════════════

# ── 1. License Validate ───────────────────────────────────────────
@app.route("/api/validate", methods=["POST"])
def validate_license():
    """
    App se aata hai:
    {
      "license_key": "MCQA-XXXX-XXXX-XXXX-XXXX",
      "hwid": "abc123..."   (machine fingerprint)
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Invalid request"}), 400

    key  = data.get("license_key", "").strip().upper()
    hwid = data.get("hwid", "").strip()

    if not key or not hwid:
        return jsonify({"status": "error",
                        "message": "Missing key or hwid"}), 400

    db = load_db()

    # Key exist karta hai?
    if key not in db:
        return jsonify({
            "status": "invalid",
            "message": "License key not found.",
            "licensed": False
        })

    lic = db[key]

    # Key active hai?
    if lic.get("status") != "active":
        return jsonify({
            "status": "revoked",
            "message": "This license has been revoked.",
            "licensed": False
        })

    # HWID check — ek device pe hi chale
    registered_hwid = lic.get("hwid")

    if not registered_hwid:
        # Pehli baar activate ho raha hai — HWID register karo
        db[key]["hwid"]           = hwid
        db[key]["activated_at"]   = str(datetime.datetime.utcnow())
        db[key]["activations"]    = 1
        save_db(db)
        return jsonify({
            "status":   "activated",
            "message":  "License activated successfully!",
            "licensed": True,
            "plan":     lic.get("plan", "pro"),
            "name":     lic.get("customer_name", "User"),
            "expires":  lic.get("expires", "lifetime")
        })

    elif registered_hwid == hwid:
        # Same device — valid!
        db[key]["last_check"] = str(datetime.datetime.utcnow())
        save_db(db)
        return jsonify({
            "status":   "valid",
            "message":  "License is valid.",
            "licensed": True,
            "plan":     lic.get("plan", "pro"),
            "name":     lic.get("customer_name", "User"),
            "expires":  lic.get("expires", "lifetime")
        })

    else:
        # Alag device!
        return jsonify({
            "status":   "device_mismatch",
            "message":  "This license is already activated on another device.\n"
                        "Contact support to transfer your license.",
            "licensed": False
        })


# ── 2. Admin — New License Generate ──────────────────────────────
@app.route("/api/admin/generate", methods=["POST"])
def admin_generate():
    """
    Naya license generate karo.
    Admin key required.
    {
      "admin_key": "admin_secret_here",
      "customer_name": "Ahmed",
      "plan": "pro",
      "expires": "lifetime"   or  "2025-12-31"
    }
    """
    ADMIN_KEY = "MCQ_ADMIN_2025_SECRET"   # ← apna admin password yahan

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    if data.get("admin_key") != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    new_key = generate_license_key()
    db      = load_db()

    db[new_key] = {
        "status":        "active",
        "customer_name": data.get("customer_name", "Customer"),
        "plan":          data.get("plan", "pro"),
        "expires":       data.get("expires", "lifetime"),
        "hwid":          None,
        "created_at":    str(datetime.datetime.utcnow()),
        "activated_at":  None,
        "last_check":    None,
        "activations":   0
    }
    save_db(db)

    return jsonify({
        "success":      True,
        "license_key":  new_key,
        "customer":     data.get("customer_name", "Customer"),
        "plan":         data.get("plan", "pro"),
        "expires":      data.get("expires", "lifetime")
    })


# ── 3. Admin — Revoke License ─────────────────────────────────────
@app.route("/api/admin/revoke", methods=["POST"])
def admin_revoke():
    ADMIN_KEY = "MCQ_ADMIN_2025_SECRET"
    data = request.get_json()
    if data.get("admin_key") != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    key = data.get("license_key", "").upper()
    db  = load_db()
    if key not in db:
        return jsonify({"error": "Key not found"}), 404

    db[key]["status"] = "revoked"
    save_db(db)
    return jsonify({"success": True, "message": f"{key} revoked."})


# ── 4. Admin — Reset HWID (device transfer) ───────────────────────
@app.route("/api/admin/reset_hwid", methods=["POST"])
def admin_reset_hwid():
    ADMIN_KEY = "MCQ_ADMIN_2025_SECRET"
    data = request.get_json()
    if data.get("admin_key") != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    key = data.get("license_key", "").upper()
    db  = load_db()
    if key not in db:
        return jsonify({"error": "Key not found"}), 404

    db[key]["hwid"]         = None
    db[key]["activations"]  = 0
    save_db(db)
    return jsonify({"success": True,
                    "message": f"{key} HWID reset. Ready for new device."})


# ── 5. Admin — List All Licenses ──────────────────────────────────
@app.route("/api/admin/list", methods=["POST"])
def admin_list():
    ADMIN_KEY = "MCQ_ADMIN_2025_SECRET"
    data = request.get_json()
    if data.get("admin_key") != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    db = load_db()
    return jsonify({"total": len(db), "licenses": db})


# ── 6. Health check ───────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "service": "MCQ Analyzer License Server",
        "status":  "running",
        "version": "1.0"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
