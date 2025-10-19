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


@st.cache_data(ttl=300)
def fetch_projects():
    """Fetch unique project IDs from backend."""
    res = requests.get("http://localhost:8000/projects")
    if res.status_code == 200:
        data = res.json()
        return data.get("projects", [])
    return []


@st.cache_data(ttl=300)
def fetch_requirements(project_id: str):
    """Fetch requirements for a given project."""
    res = requests.get(f"http://localhost:8000/requirements/{project_id}")
    if res.status_code == 200:
        return res.json()
    return {"functional_requirements": [], "non_functional_requirements": []}


# ---------- Page Config ----------
st.set_page_config(page_title="Dev Productivity Dashboard", layout="wide")

# -------- Fetch Data --------
prod_metrics_data = fetch_prod_metrics()

# Dummy data for risk & requirements endpoints
risk_data = {
    "risk_score": "Medium",
    "release_decision": "GO",
    "fr_completion_rate": 0.85,
    "nfr_completion_rate": 0.75,
    "compilation_success_rate": 0.9
}

# -------- Title --------
st.markdown('<div class="title">Productivity Dashboard</div>', unsafe_allow_html=True)

# -------- Project Risks & Readiness --------
st.header("🚨️ Project Risks & Release Readiness")

projects = fetch_projects()
if not projects:
    st.error("No projects found in the database.")
    st.stop()

selected_project = st.selectbox("Select a Project", projects, index=len(projects) - 1)
requirements_data = fetch_requirements(selected_project)

# ----- Release Decision -----
decision = risk_data["release_decision"]
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    color_class = decision.lower().replace("-", "")
    emoji_map = {
        "Go": "✅",
        "No-Go": "❌",
        "Conditional": "⚠️"
    }
    emoji = emoji_map.get(decision, "")
    st.markdown(
        f"""
        <div class="metric-card decision {color_class}">
            Release Decision: {decision.upper()}
        </div>
        """,
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
    col1.markdown(f'<div class="metric-name">{name}</div>', unsafe_allow_html=True)
    col2.progress(int(value * 100))
    col3.markdown(f'<div class="metric-value">{value * 100:.1f}%</div>', unsafe_allow_html=True)

# ----- Functional Requirements -----
st.markdown("### 📑 Functional Requirements")
if requirements_data["functional_requirements"]:
    st.markdown(
        "<div class='metric-card'><ul class='requirements-list'>" +
        "".join(
            f"<li>{fr['description']}</li>"
            for fr in requirements_data["functional_requirements"]
        ) +
        "</ul></div>",
        unsafe_allow_html=True
    )
else:
    st.info("No functional requirements found for this project.")

# ----- Non-Functional Requirements -----
st.markdown("### ⚙️ Non-Functional Requirements")
if requirements_data["non_functional_requirements"]:
    st.markdown(
        """
        <div class='metric-card' style='max-height:300px; overflow-y:auto;'>
            <ul class='requirements-list'>
        """ +
        "".join(
            f"<li><b>{nfr['category']}:</b> {nfr['description']}</li>"
            for nfr in requirements_data["non_functional_requirements"]
        ) +
        """
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.info("No non-functional requirements found for this project.")

# ----- Team Metrics -----
team_metrics = prod_metrics_data["team_productivity_metrics"]
st.header("📊 Team Metrics")

# KPI Row
col1, col2, col3 = st.columns(3)
col1.markdown(f"""
<div class="metric-card">
    <div class="metric-name">Avg Suggestions/Day</div>
    <div class="metric-value2">{team_metrics['average_suggestions_handled_per_day']}</div>
</div>
""", unsafe_allow_html=True)

# Acceptance Rate
acceptance = team_metrics['overall_suggestion_acceptance_rate'] * 100
col2.markdown(f"""
<div class="metric-card">
  <div class="metric-name">Acceptance Rate</div>
  <div class="metric-value2">{acceptance:.1f}%</div>
</div>
""", unsafe_allow_html=True)

# Top Issue Category
top_category = max(team_metrics["average_suggestions_handled_per_category_per_day"],
                   key=team_metrics["average_suggestions_handled_per_category_per_day"].get)
col3.markdown(f"""
<div class="metric-card">
  <div class="metric-name">Top Issue Category</div>
  <div class="metric-value2">{top_category}</div>
</div>
""", unsafe_allow_html=True)

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
st.markdown("<hr>", unsafe_allow_html=True)
st.header("👩‍💻 Individual Developer Metrics")
devs = list(prod_metrics_data["developer_productivity_metrics"]["average_suggestions_handled_per_day"].keys())
st.markdown("<div class='dev-metric'>Select Developer:</div>", unsafe_allow_html=True)
selected_dev = st.selectbox("", devs)

if selected_dev:
    dev_metrics = prod_metrics_data["developer_productivity_metrics"]

    # Acceptance Rate
    st.markdown("### ✔ Acceptance Rate")
    acceptance = dev_metrics["suggestion_acceptance_rate"][selected_dev]
    st.progress(int(acceptance * 100))
    st.markdown(f"<p class='dev-metric-value'>{acceptance * 100:.1f}% suggestions accepted</p>", unsafe_allow_html=True)

    # Average Suggestions Handled/Day
    st.markdown("### 📈 Avg Suggestions Handled/Day")
    avg_suggestions = dev_metrics["average_suggestions_handled_per_day"][selected_dev]
    st.markdown(f"<div class='metric-card' style='font-size:40px;'>{avg_suggestions}</div>", unsafe_allow_html=True)

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
