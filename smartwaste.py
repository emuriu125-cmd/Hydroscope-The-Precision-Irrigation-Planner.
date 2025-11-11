# smartwaste.py
# SmartWaste - offline starter app (Streamlit)
# - Stores submissions locally in smartwaste_data/
# - Pages: Request Pickup, Report Dumping (with image), Collector Dashboard
# - Light / Dark eco-theme toggle
# Requires: streamlit, pillow
# Run: python -m streamlit run smartwaste.py

import streamlit as st
from PIL import Image
from pathlib import Path
import json
import uuid
from datetime import datetime
import os
from io import BytesIO

# ---------------------------
# Config / paths
# ---------------------------
BASE = Path.cwd() / "smartwaste_data"
IMAGES = BASE / "images"
DATA_FILE = BASE / "data.json"
os.makedirs(IMAGES, exist_ok=True)
if not BASE.exists():
    BASE.mkdir(parents=True, exist_ok=True)

# ---------------------------
# Load / save data helpers
# ---------------------------
def load_data():
    if not DATA_FILE.exists():
        # initialize structure
        data = {"pickups": [], "reports": [], "collectors": []}
        save_data(data)
        return data
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"pickups": [], "reports": [], "collectors": []}

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

data = load_data()

# ---------------------------
# Utilities
# ---------------------------
def now_iso():
    return datetime.utcnow().isoformat()

def save_uploaded_image(uploaded_file) -> str:
    # returns saved filename
    ext = Path(uploaded_file.name).suffix.lower() or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    path = IMAGES / name
    bytes_data = uploaded_file.read()
    # ensure it's a valid image and optionally resize if huge
    try:
        img = Image.open(BytesIO(bytes_data))
        img.save(path)
    except Exception:
        # fallback: write raw bytes
        path.write_bytes(bytes_data)
    return name

def user_points(user_id):
    # simple points: +10 per completed pickup, +5 per report accepted
    pts = 0
    for p in data.get("pickups", []):
        if p.get("requester_id") == user_id and p.get("status") == "completed":
            pts += 10
    for r in data.get("reports", []):
        if r.get("reporter_id") == user_id and r.get("status") == "addressed":
            pts += 5
    return pts

# ---------------------------
# Theme CSS (eco green)
# ---------------------------
def inject_css(theme="light"):
    if theme == "light":
        bg = "#f6fff2"
        panel = "#ffffff"
        text = "#0b3d0b"
        accent = "#2e8b57"
        card_shadow = "0 6px 18px rgba(0,0,0,0.06)"
    else:
        bg = "#071204"
        panel = "#071204"
        text = "#e6f7ec"
        accent = "#3bb07b"
        card_shadow = "0 6px 18px rgba(0,0,0,0.6)"

    css = f"""
    <style>
    /* page layout */
    .stApp {{ background: {bg}; color: {text}; }}
    .topbar {{ padding: 12px 24px; display:flex; align-items:center; gap:12px; background:{panel}; box-shadow:{card_shadow}; border-radius:8px; margin-bottom:12px; }}
    .brand {{ font-weight:800; color:{accent}; font-size:20px; letter-spacing:1px; }}
    .panel {{ background:{panel}; padding:16px; border-radius:10px; box-shadow:{card_shadow}; }}
    .card {{ background:{panel}; padding:10px; border-radius:8px; box-shadow:{card_shadow}; margin-bottom:12px; }}
    .small {{ color: {text}; opacity:0.8; font-size:13px; }}
    /* inputs */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {{ border-radius:8px; border:1px solid #d6eddc; padding:10px; }}
    .stButton>button {{ background: {accent}; color: white; border-radius:8px; padding:8px 12px; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ---------------------------
# App UI
# ---------------------------
st.set_page_config(page_title="SmartWaste — Local Pickup", layout="wide")
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"
inject_css(st.session_state["theme"])

# Topbar
col1, col2, col3 = st.columns([1,6,1])
with col1:
    st.markdown(f"<div class='brand'>SmartWaste</div>", unsafe_allow_html=True)
with col2:
    q = st.text_input("Quick search (address, tag, user)", value="", key="quick_search")
with col3:
    if st.button("Toggle Theme"):
        st.session_state["theme"] = "dark" if st.session_state["theme"] == "light" else "light"
        inject_css(st.session_state["theme"])

st.markdown("---")

# Sidebar navigation
st.sidebar.header("Menu")
page = st.sidebar.radio("Go to", ["Request Pickup", "Report Dumping", "Collector Dashboard", "My Profile", "About"])
st.sidebar.markdown("---")
st.sidebar.info("SmartWaste (offline prototype)\nUpload requests and reports — data stored locally.")
st.sidebar.markdown(f"Data folder: `{BASE}`")

# ---------------
# Request Pickup
# ---------------
if page == "Request Pickup":
    st.header("Request a Waste Pickup")
    st.markdown("Fill details and a nearby collector will be able to accept the job (offline prototype shows requests in dashboard).")
    with st.form("pickup_form"):
        requester_name = st.text_input("Your name")
        phone = st.text_input("Phone (optional)")
        address = st.text_input("Pick-up address (street / landmark)")
        waste_type = st.selectbox("Waste type", ["Household (general)", "Recyclables", "Organic/compost", "Bulky/metal", "E-waste", "Other"])
        notes = st.text_area("Notes (optional)")
        submit = st.form_submit_button("Request Pickup")
        if submit:
            req = {
                "id": str(uuid.uuid4()),
                "requester_name": requester_name or "Anonymous",
                "requester_phone": phone or "",
                "requester_id": requester_name or "anon",
                "address": address or "",
                "waste_type": waste_type,
                "notes": notes or "",
                "status": "open",   # open, accepted, completed
                "created_at": now_iso(),
                "accepted_by": None,
                "completed_at": None
            }
            data = load_data()
            data["pickups"].append(req)
            save_data(data)
            st.success("Pickup requested — it appears in the Collector Dashboard.")
            st.balloons()

# ---------------
# Report Dumping
# ---------------
elif page == "Report Dumping":
    st.header("Report Illegal Dumping / Dump Sites")
    st.markdown("Report a site with optional photo. Include location or landmark.")
    with st.form("report_form"):
        reporter_name = st.text_input("Your name")
        location_description = st.text_input("Location (street / landmark)")
        photo = st.file_uploader("Photo (optional)", type=["png","jpg","jpeg","webp"])
        description = st.text_area("Description")
        submit = st.form_submit_button("Report")
        if submit:
            img_name = None
            if photo:
                img_name = save_uploaded_image(photo)
            report = {
                "id": str(uuid.uuid4()),
                "reporter_name": reporter_name or "Anonymous",
                "reporter_id": reporter_name or "anon",
                "location": location_description or "",
                "photo": img_name,
                "description": description or "",
                "status": "reported",  # reported, addressed
                "created_at": now_iso(),
                "addressed_at": None
            }
            d = load_data()
            d["reports"].append(report)
            save_data(d)
            st.success("Report submitted. Thank you — local collectors will see it on the dashboard.")
            st.snow()

# -----------------------
# Collector Dashboard
# -----------------------
elif page == "Collector Dashboard":
    st.header("Collector Dashboard — Open Requests & Reports")
    st.markdown("This view simulates what local collectors or youth groups would see. They can accept jobs, mark complete, and address reports.")
    d = load_data()

    st.subheader("Open Pickups")
    open_pickups = [p for p in d["pickups"] if p["status"] in ("open","accepted")]
    if not open_pickups:
        st.info("No pickup requests at the moment.")
    else:
        for p in sorted(open_pickups, key=lambda x: x["created_at"], reverse=True):
            with st.container():
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                cols = st.columns([3,1])
                with cols[0]:
                    st.write(f"**{p['waste_type']}** — {p['requester_name']}")
                    st.write(f"📍 {p['address']}")
                    st.write(f"📝 {p['notes'] or '-'}")
                    st.write(f"Status: **{p['status']}** — created {p['created_at'][:19].replace('T',' ')}")
                with cols[1]:
                    if p["status"] == "open":
                        if st.button(f"Accept {p['id']}", key=f"accept_{p['id']}"):
                            # simulate collector name
                            p["status"] = "accepted"
                            p["accepted_by"] = "Local Collector"
                            save_data(d)
                            st.experimental_rerun()
                    elif p["status"] == "accepted":
                        if st.button(f"Mark Completed {p['id']}", key=f"complete_{p['id']}"):
                            p["status"] = "completed"
                            p["completed_at"] = now_iso()
                            save_data(d)
                            st.experimental_rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Reported Dump Sites")
    reports = d.get("reports", [])
    if not reports:
        st.info("No reports yet.")
    else:
        for r in sorted(reports, key=lambda x: x["created_at"], reverse=True):
            with st.container():
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                c0, c1 = st.columns([2,1])
                with c0:
                    st.write(f"**Location:** {r['location']}")
                    if r.get("photo"):
                        imgpath = IMAGES / r["photo"]
                        if imgpath.exists():
                            st.image(str(imgpath), use_column_width=True)
                    st.write(f"📝 {r['description'] or '-'}")
                    st.write(f"Status: **{r['status']}** — reported {r['created_at'][:19].replace('T',' ')}")
                with c1:
                    if r["status"] == "reported":
                        if st.button(f"Mark Addressed {r['id']}", key=f"address_{r['id']}"):
                            r["status"] = "addressed"
                            r["addressed_at"] = now_iso()
                            save_data(d)
                            st.experimental_rerun()
                st.markdown("</div>", unsafe_allow_html=True)

# -----------------------
# My Profile
# -----------------------
elif page == "My Profile":
    st.header("My Profile & Points")
    name = st.text_input("Your name (used to track points)", value="guest")
    if st.button("Show my points"):
        pid = name or "guest"
        pts = user_points(pid)
        st.success(f"{name} — You have {pts} points")
    st.markdown("Recent activity:")
    d = load_data()
    user_activities = []
    for p in d.get("pickups", []):
        if p.get("requester_id") == (name or "guest") or p.get("requester_name") == name:
            user_activities.append(("Pickup", p["status"], p["created_at"]))
    for r in d.get("reports", []):
        if r.get("reporter_id") == (name or "guest") or r.get("reporter_name") == name:
            user_activities.append(("Report", r["status"], r["created_at"]))
    if not user_activities:
        st.info("No recent activity found for this name.")
    else:
        for a in sorted(user_activities, key=lambda x: x[2], reverse=True):
            st.write(f"- {a[0]} — {a[1]} — {a[2][:19].replace('T',' ')}")

# -----------------------
# About
# -----------------------
elif page == "About":
    st.header("About SmartWaste")
    st.markdown("""
    **SmartWaste** is a local, offline-first prototype for connecting households with local waste collectors.
    This starter app stores data locally and is meant to be expanded into a full system with:
      - Notifications (SMS or push)
      - Authentication for collectors
      - Payment / micro-payments
      - Map integration and geolocation
      - Analytics dashboards for local governments
    """)
    st.markdown("Data stored locally at: `" + str(BASE) + "`")

# ---------------------------
# Save data at end (ensure persistence)
# ---------------------------
save_data(data)
