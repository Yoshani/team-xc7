import plotly.express as px
import requests
import streamlit as st


# --- Load Custom CSS ---
def load_css(file_name: str):
    """
    Loads external CSS styles into the Streamlit app.
    :param file_name: Path to the CSS file
    """
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("styles.css")


# ---------- Cached API Fetch ----------
@st.cache_data(ttl=300)  # cache for 5 minutes
def fetch_prod_metrics():
    """
    Fetch productivity metrics from the backend API.
    :return: Productivity metrics JSON
    """
    return requests.get("http://localhost:8000/generate_metrics").json()


# ---------- Page Config ----------
st.set_page_config(page_title="Dev Productivity Dashboard", layout="wide")

# -------- Fetch Data --------
prod_metrics_data = fetch_prod_metrics()

# Dummy data for risk & requirements endpoints
risk_data = {
    "risk_score": "Medium",
    "release_decision": "Conditional",
    "fr_completion_rate": 0.85,
    "nfr_completion_rate": 0.75,
    "compilation_success_rate": 0.9
}
requirements_data = {
    "functional_requirements": ["Login system implemented", "Export feature pending"],
    "non_functional_requirements": ["95% test coverage", "API latency under 200ms"]
}

# -------- Title --------
st.markdown('<div class="title">Productivity Dashboard</div>', unsafe_allow_html=True)

# -------- Project Risks & Readiness --------
st.header("🚨️ Project Risks & Release Readiness")

# ----- Release Decision -----
decision = risk_data["release_decision"]
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    color_map = {
        "Go": "#28a745",
        "No-Go": "#dc3545",
        "Conditional": "#fd7e14"
    }
    emoji_map = {
        "Go": "✅",
        "No-Go": "❌",
        "Conditional": "⚠️"
    }
    bg = color_map.get(decision, "#6c757d")
    emoji = emoji_map.get(decision, "")
    st.markdown(
        f"<div class='metric-card' style='background-color:{bg}; font-size:24px;'>{emoji} Release Decision: {decision.upper()}</div>",
        unsafe_allow_html=True
    )

# ----- Risk Metrics -----
st.markdown("### 📊 Risk Metrics")

metrics = {
    "FR Completion": risk_data["fr_completion_rate"],
    "NFR Completion": risk_data["nfr_completion_rate"],
    "Compilation Success": risk_data["compilation_success_rate"]
}

for name, value in metrics.items():
    col1, col2, col3 = st.columns([1, 5, 1])
    col1.write(f"{name}")
    col2.progress(int(value * 100))
    col3.write(f"{value * 100:.1f}%")

# ----- Functional Requirements -----
st.markdown("### 📑 Functional Requirements")
st.markdown("<div class='metric-card'><ul>" + "".join(
    f"<li>{fr}</li>" for fr in requirements_data["functional_requirements"]) + "</ul></div>", unsafe_allow_html=True)

# ----- Non-Functional Requirements -----
st.markdown("### ⚙️ Non-Functional Requirements")
st.markdown("<div class='metric-card'><ul>" + "".join(
    f"<li>{nfr}</li>" for nfr in requirements_data["non_functional_requirements"]) + "</ul></div>",
            unsafe_allow_html=True)

# ----- Team Metrics -----
team_metrics = prod_metrics_data["team_productivity_metrics"]
st.header("📊 Team Metrics")

# KPI Row
col1, col2, col3 = st.columns(3)
col1.metric("Avg Suggestions/Day", team_metrics["average_suggestions_handled_per_day"])
col2.metric("Acceptance Rate", f"{team_metrics['overall_suggestion_acceptance_rate'] * 100:.1f}%")
col3.metric("Top Issue Category",
            max(team_metrics["average_suggestions_handled_per_category_per_day"],
                key=team_metrics["average_suggestions_handled_per_category_per_day"].get)
            )

# Charts Row
st.markdown("### 📂 Suggestions Breakdown")

# Pie Chart — Suggestions by Category
cat_data = team_metrics["average_suggestions_handled_per_category_per_day"]
cat_fig = px.pie(
    names=list(cat_data.keys()),
    values=list(cat_data.values()),
    title="Suggestions by Category",
    hole=0.4,
    color_discrete_sequence=px.colors.sequential.Brwnyl_r
)
cat_fig.update_traces(textinfo="label+percent+value", textfont_size=18, textposition="outside")
cat_fig.update_layout(title=dict(font=dict(size=24, family="Arial Black")), legend=dict(font=dict(size=18)))
st.plotly_chart(cat_fig, use_container_width=True)

# Bar Chart — Top Recurring Issues
st.markdown("### 🔁 Top Recurring Issues")

issues_data = team_metrics["team_specific_recurring_issues"]
sorted_issues = dict(sorted(issues_data.items(), key=lambda x: x[1], reverse=True)[:5])
labels = [issue.title() for issue in sorted_issues.keys()]
values = list(sorted_issues.values())

issue_fig = px.bar(
    x=values, y=labels, orientation="h", text=values,
    color=values, color_continuous_scale="Reds",
    title="Top Recurring Issues"
)
issue_fig.update_traces(textposition="outside")
issue_fig.update_layout(
    title=dict(font=dict(size=24, family="Arial Black")),
    xaxis=dict(title="Count", tickfont=dict(size=16)),
    yaxis=dict(tickfont=dict(size=16)),
    margin=dict(l=250)
)
st.plotly_chart(issue_fig, use_container_width=True)

# -------- Developer Metrics --------
st.header("👩‍💻 Developer Metrics")
devs = list(prod_metrics_data["developer_productivity_metrics"]["average_suggestions_handled_per_day"].keys())
selected_dev = st.selectbox("Select Developer", devs)

if selected_dev:
    dev_metrics = prod_metrics_data["developer_productivity_metrics"]

    # Acceptance Rate
    st.markdown("### ✔ Acceptance Rate")
    acceptance = dev_metrics["suggestion_acceptance_rate"][selected_dev]
    st.progress(int(acceptance * 100))
    st.write(f"**{acceptance * 100:.1f}% suggestions accepted**")

    # Average Suggestions Handled/Day
    st.markdown("### 📈 Avg Suggestions Handled/Day")
    avg_suggestions = dev_metrics["average_suggestions_handled_per_day"][selected_dev]
    st.markdown(f"<div class='metric-card' style='font-size:20px;'>{avg_suggestions}</div>", unsafe_allow_html=True)

    # Issues by Category
    st.markdown("### 📂 Issues by Category")
    categories = dev_metrics["average_suggestions_handled_per_category_per_day"][selected_dev]
    dev_cat_fig = px.pie(
        names=list(categories.keys()),
        values=list(categories.values()),
        title=f"Suggestions by Category for {selected_dev}",
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.Agsunset_r
    )
    dev_cat_fig.update_traces(textinfo="label+percent+value", textfont_size=16, textposition="outside")
    dev_cat_fig.update_layout(title=dict(font=dict(size=24, family="Arial Black")), legend=dict(font=dict(size=18)))
    st.plotly_chart(dev_cat_fig, use_container_width=True)

    # Recurring Issues
    st.markdown("### 🔁 Recurring Issues")
    recurring = dev_metrics["dev_specific_recurring_issues"][selected_dev]
    sorted_issues = dict(sorted(recurring.items(), key=lambda x: x[1], reverse=True))
    dev_issue_fig = px.bar(
        x=list(sorted_issues.values()),
        y=[i.title() for i in sorted_issues.keys()],
        orientation='h',
        text=list(sorted_issues.values()),
        color=list(sorted_issues.values()),
        color_continuous_scale="greens",
        title=f"Top Recurring Issues for {selected_dev}"
    )
    dev_issue_fig.update_traces(textposition="outside")
    dev_issue_fig.update_layout(
        title=dict(font=dict(size=24, family="Arial Black")),
        xaxis=dict(title="Count", tickfont=dict(size=16)),
        yaxis=dict(tickfont=dict(size=16)),
        margin=dict(l=250)
    )
    st.plotly_chart(dev_issue_fig, use_container_width=True)
