import streamlit as st
import pandas as pd
import plotly.express as px
import uuid

# Optional: Ensure statsmodels is available for trendline
try:
    import statsmodels.api as sm
    STATS_AVAILABLE = True
except ImportError:
    STATS_AVAILABLE = False

st.set_page_config(page_title="HydroScope", layout="wide")

# ----------------------------
# SESSION STATE
# ----------------------------
if "has_predicted" not in st.session_state: st.session_state["has_predicted"] = False
if "prediction_log" not in st.session_state: st.session_state["prediction_log"] = []
if "prediction_log_water" not in st.session_state: st.session_state["prediction_log_water"] = []
if "forecast_log" not in st.session_state: st.session_state["forecast_log"] = []
if "crop_log" not in st.session_state: st.session_state["crop_log"] = []
if "weather_log_data" not in st.session_state:
    st.session_state["weather_log_data"] = pd.DataFrame(columns=["Date", "Temperature (°C)", "Rainfall (mm)", "ETo (mm/day)"])
if "eto_value_input" not in st.session_state: st.session_state["eto_value_input"] = 5.0
if "plots_data" not in st.session_state: st.session_state["plots_data"] = {}
if "active_plot_id" not in st.session_state: st.session_state["active_plot_id"] = None

# ----------------------------
# CROP DATA & FUNCTIONS
# ----------------------------
crop_options_detailed = {
    "Maize": {"Duration_Days": {"Initial": 20, "Development": 35, "Mid": 45, "Late": 26}, "Kc_Values": {"Initial": 0.3, "Mid": 1.2, "End": 0.7}},
    "Beans": {"Duration_Days": {"Initial": 15, "Development": 25, "Mid": 30, "Late": 10}, "Kc_Values": {"Initial": 0.4, "Mid": 1.1, "End": 0.4}},
    "Tomatoes": {"Duration_Days": {"Initial": 30, "Development": 40, "Mid": 60, "Late": 20}, "Kc_Values": {"Initial": 0.4, "Mid": 1.1, "End": 0.7}},
    "Other / Custom Crop": {"Duration_Days": None, "Kc_Values": None}
}

def calculate_stage_based_water(acres, avg_daily_eto, effective_rain_weekly, efficiency_percent, crop_data):
    if not crop_data or not crop_data["Duration_Days"]:
        return None, None
    area_sq_meters = acres * 4046.86
    efficiency_decimal = efficiency_percent / 100
    total_gross_irrigation_mm = 0
    avg_effective_rain_daily = (effective_rain_weekly / 7) if effective_rain_weekly else 0

    kc_mid = crop_data["Kc_Values"]["Mid"]
    kc_end = crop_data["Kc_Values"]["End"]
    kc_init = crop_data["Kc_Values"]["Initial"]
    stages = ["Initial", "Development", "Mid", "Late"]

    for stage in stages:
        duration_days = crop_data["Duration_Days"][stage]
        if stage == "Initial": kc_stage_avg = kc_init
        elif stage == "Mid": kc_stage_avg = kc_mid
        elif stage == "Late": kc_stage_avg = (kc_mid + kc_end) / 2
        elif stage == "Development": kc_stage_avg = (kc_init + kc_mid) / 2

        etc_daily_mm = kc_stage_avg * avg_daily_eto
        net_irrigation_stage_mm = max(0, (etc_daily_mm - avg_effective_rain_daily) * duration_days)
        gross_irrigation_stage_mm = net_irrigation_stage_mm / efficiency_decimal if efficiency_decimal > 0 else net_irrigation_stage_mm
        total_gross_irrigation_mm += gross_irrigation_stage_mm

    total_water_liters = total_gross_irrigation_mm * area_sq_meters
    return total_water_liters, total_gross_irrigation_mm

# ----------------------------
# SIDEBAR
# ----------------------------
st.sidebar.title("⚙️ HydroScope Controls")
page = st.sidebar.radio("Navigate", [
    "🌤️ Weather Guide", 
    "🌱 Crop Water Guide", 
    "🏡 Farm Setup & Plots", 
    "💧 Supply Planner", 
    "subscription", 
    "About"
])

# ----------------------------
# 1. WEATHER GUIDE
# ----------------------------
if page == "🌤️ Weather Guide":
    st.title("🌤️ Local Weather Data & ETo Guide")
    st.markdown("Log daily weather observations for better crop water calculations.")

    with st.form(key='weather_form'):
        col1, col2, col3, col4 = st.columns(4)
        date_entry = col1.date_input("Date")
        temp_entry = col2.number_input("Avg Temp (°C)", value=25.0)
        rain_entry = col3.number_input("Rainfall (mm)", value=0.0)
        eto_entry = col4.number_input("Avg ETo (mm/day)", value=5.0)
        log_btn = st.form_submit_button("➕ Log Weather Data")

    if log_btn:
        new_entry = {"Date": date_entry, "Temperature (°C)": temp_entry, "Rainfall (mm)": rain_entry, "ETo (mm/day)": eto_entry}
        st.session_state["weather_log_data"] = pd.concat([st.session_state["weather_log_data"], pd.DataFrame([new_entry])], ignore_index=True)
        st.session_state["eto_value_input"] = eto_entry
        st.success("Weather data logged!")

    if not st.session_state["weather_log_data"].empty:
        df = st.session_state["weather_log_data"].copy()
        df["Date"] = pd.to_datetime(df["Date"])
        st.subheader("📊 Historical Weather Trends")
        st.table(df.set_index("Date").sort_index())

        if len(df) >= 2 and STATS_AVAILABLE:
            fig_temp = px.scatter(df, x="Temperature (°C)", y="ETo (mm/day)", trendline="ols", title="ETo vs Temp")
            st.plotly_chart(fig_temp, use_container_width=True)
            fig_rain = px.scatter(df, x="Rainfall (mm)", y="ETo (mm/day)", trendline="ols", title="ETo vs Rainfall")
            st.plotly_chart(fig_rain, use_container_width=True)
        elif len(df) >= 2:
            st.info("Install statsmodels to see trendline regression: pip install statsmodels")
        else:
            st.info("Log at least 2 data points for trendlines.")

# ----------------------------
# 2. CROP WATER GUIDE
# ----------------------------
elif page == "🌱 Crop Water Guide":
    st.title("🌱 Crop Water Calculator")
    if st.session_state.get("active_plot_id") and st.session_state["active_plot_id"] in st.session_state["plots_data"]:
        plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        st.info(f"Using Active Plot: {plot['name']} ({plot['acres']} acres of {plot['crop_type']})")
        crop_name = plot['crop_type']
        acres = plot['acres']
        total_days = sum(crop_options_detailed[crop_name]["Duration_Days"].values())
        st.markdown(f"**Growth Period (weeks):** {round(total_days/7,1)}")
        eto_daily_avg = st.number_input("Average daily ETo (mm/day)", value=st.session_state["eto_value_input"])
        efficiency = st.slider("Irrigation Efficiency (%)", 10, 100, 75)
        effective_rain_weekly = st.number_input("Avg Effective Rainfall (mm/week)", value=10.0)
    else:
        st.warning("No active plot selected. Use 'Farm Setup & Plots' or enter manual inputs.")
        crop_name = st.selectbox("Choose Crop", list(crop_options_detailed.keys()))
        acres = st.number_input("Farm size (acres)", 0.1, 1000.0, 5.0)
        eto_daily_avg = st.number_input("Average daily ETo (mm/day)", value=st.session_state["eto_value_input"])
        efficiency = st.slider("Irrigation Efficiency (%)", 10, 100, 75)
        effective_rain_weekly = st.number_input("Avg Effective Rainfall (mm/week)", value=10.0)
        if crop_name != "Other / Custom Crop":
            total_days = sum(crop_options_detailed[crop_name]["Duration_Days"].values())
            st.markdown(f"**Growth Period (weeks):** {round(total_days/7,1)}")

# ----------------------------
# 3. FARM SETUP & PLOTS
# ----------------------------
elif page == "🏡 Farm Setup & Plots":
    st.title("🏡 Farm Plots")
    with st.form("new_plot_form"):
        plot_name = st.text_input("Plot Name")
        plot_crop = st.selectbox("Crop Type", list(crop_options_detailed.keys()))
        plot_acres = st.number_input("Acres", min_value=0.1, value=1.0)
        add_btn = st.form_submit_button("Save Plot")
        if add_btn and plot_name and plot_crop:
            plot_id = str(uuid.uuid4())
            st.session_state["plots_data"][plot_id] = {"id": plot_id, "name": plot_name, "crop_type": plot_crop, "acres": plot_acres}
            st.success(f"Plot '{plot_name}' added!")
    st.markdown("---")
    for plot in st.session_state["plots_data"].values():
        cols = st.columns(4)
        cols[0].write(plot['name'])
        cols[1].write(f"{plot['acres']} acres")
        cols[2].write(plot['crop_type'])
        is_active = st.session_state.get("active_plot_id") == plot['id']
        if cols[3].button("✅ Active" if is_active else "Set Active", key=f"activate_{plot['id']}"):
            st.session_state["active_plot_id"] = plot['id']
            st.experimental_rerun()
    st.markdown("---")
    if st.session_state.get("active_plot_id"):
        plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        st.success(f"Active Plot: {plot['name']} ({plot['acres']} acres of {plot['crop_type']})")
    else:
        st.warning("No active plot selected.")

# ----------------------------
# 4. SUPPLY PLANNER
# ----------------------------
elif page == "💧 Supply Planner":
    st.title("💧 Seasonal Water Planner")
    if not st.session_state.get("active_plot_id"):
        st.warning("Select an active plot first in 'Farm Setup & Plots'")
    else:
        plot = st.session_state["plots_data"][st.session_state["active_plot_id"]]
        crop_data = crop_options_detailed.get(plot['crop_type'])
        if not crop_data or not crop_data["Duration_Days"]:
            st.error("Seasonal planning only available for predefined crops.")
        else:
            sp_eto_daily_avg = st.number_input("Average daily ETo (mm/day) for Season", value=st.session_state["eto_value_input"])
            sp_efficiency = st.slider("Irrigation Efficiency (%)", 10, 100, 75)
            sp_effective_rain_weekly = st.number_input("Avg Effective Rainfall (mm/week) for Season", value=10.0)
            if st.button("Calculate Seasonal Water Need"):
                total_water_liters, total_gross_irrigation_mm = calculate_stage_based_water(
                    plot['acres'], sp_eto_daily_avg, sp_effective_rain_weekly, sp_efficiency, crop_data
                )
                total_days = sum(crop_data["Duration_Days"].values())
                st.subheader("Results Overview")
                st.metric("Total Water Needed (Liters)", f"{total_water_liters:,.0f} L")
                st.metric("Avg Daily Need (Liters/day)", f"{total_water_liters/total_days:,.0f} L/day")
                st.metric("Gross Irrigation (mm/season)", f"{total_gross_irrigation_mm:,.1f} mm")
                st.success(f"Estimated water needed for {plot['crop_type']} over the entire season: {total_water_liters:,.0f} L.")

# ----------------------------
# 5. SUBSCRIPTION / ABOUT
# ----------------------------
elif page == "subscription":
    st.title("💰 Subscription")
    st.info("Coming soon")

elif page == "About":
    st.title("ℹ️ About HydroScope")
    st.markdown("Precision water management tool for Kenyan farmers.")
