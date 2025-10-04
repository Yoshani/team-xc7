import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Dev Productivity Dashboard", layout="wide")

# -------- Fetch Data --------
prod_metrics_data = requests.get("http://localhost:8000/generate_metrics").json()

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

# -------- Layout --------
# Custom CSS for styling
st.markdown("""
    <style>
    .title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        font-family: 'Trebuchet MS', 'Lucida Sans Unicode', 'Lucida Grande', sans-serif;
        color: lightblue;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# Apply styled title
st.markdown('<div class="title">🎯 Productivity Dashboard</div>', unsafe_allow_html=True)

# ----- Requirements & Risks -----

st.header("🚨️ Project Risks & Readiness")

# ----- Release Decision -----
decision = risk_data["release_decision"]
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if decision == "Go":
        st.markdown(
            "<div style='background-color:#28a745; color:white; padding:20px; border-radius:10px; text-align:center; font-size:24px;'>✅ Release Decision: GO</div>",
            unsafe_allow_html=True
        )
    elif decision == "No-Go":
        st.markdown(
            "<div style='background-color:#dc3545; color:white; padding:20px; border-radius:10px; text-align:center; font-size:24px;'>❌ Release Decision: NO-GO</div>",
            unsafe_allow_html=True
        )
    elif decision == "Conditional":
        st.markdown(
            "<div style='background-color:#fd7e14; color:white; padding:20px; border-radius:10px; text-align:center; font-size:24px;'>⚠️ Release Decision: CONDITIONAL</div>",
            unsafe_allow_html=True
        )

# ----- Risk Metrics with Progress Bars and Percentages -----
st.markdown("### 📊 Risk Metrics")

metrics = {
    "FR Completion": risk_data["fr_completion_rate"],
    "NFR Completion": risk_data["nfr_completion_rate"],
    "Compilation Success": risk_data["compilation_success_rate"]
}

for name, value in metrics.items():
    col1, col2, col3 = st.columns([1, 5, 1])
    col1.write(f"{name}")  # name on the left
    col2.progress(int(value * 100))
    col3.write(f"{value * 100:.1f}%")  # percentage on the right

# ----- Functional Requirements -----
st.markdown("### 📑 Functional Requirements")
fr_list = requirements_data["functional_requirements"]
fr_html = "<ul style='margin:0; padding-left:20px; color:white;'>"
for fr in fr_list:
    fr_html += f"<li>{fr}</li>"
fr_html += "</ul>"

st.markdown(
    f"<div style='background-color:rgba(200,200,200,0.2); padding:15px; border-radius:10px; margin-bottom:10px;'>{fr_html}</div>",
    unsafe_allow_html=True
)

# ----- Non-Functional Requirements -----
st.markdown("### ⚙️ Non-Functional Requirements")
nfr_list = requirements_data["non_functional_requirements"]
nfr_html = "<ul style='margin:0; padding-left:20px; color:white;'>"
for nfr in nfr_list:
    nfr_html += f"<li>{nfr}</li>"
nfr_html += "</ul>"

st.markdown(
    f"<div style='background-color:rgba(200,200,200,0.2); padding:15px; border-radius:10px; margin-bottom:10px;'>{nfr_html}</div>",
    unsafe_allow_html=True
)

# ----- Team Metrics -----
team_metrics = prod_metrics_data["team_productivity_metrics"]
st.markdown('<div style="margin-top:30px;"></div>', unsafe_allow_html=True)
st.header("📊 Team Metrics")

# KPIs Row
col1, col2, col3 = st.columns(3)
col1.metric("Avg Suggestions Handled/Day", team_metrics["average_suggestions_handled_per_day"])
col2.metric("Acceptance Rate", f"{team_metrics['overall_suggestion_acceptance_rate'] * 100:.1f}%")
col3.metric("Top Category of Issues Detected with Reviews",
            max(team_metrics["average_suggestions_handled_per_category_per_day"],
                key=team_metrics["average_suggestions_handled_per_category_per_day"].get)
            )

# Charts Row
st.markdown("### 📂 Suggestions Breakdown")

# Suggestions by Category Pie Chart
cat_data = team_metrics["average_suggestions_handled_per_category_per_day"]
cat_fig = px.pie(
    names=list(cat_data.keys()),
    values=list(cat_data.values()),
    title="Suggestions by Category",
    hole=0.4,  # donut style
    color_discrete_sequence=px.colors.sequential.Brwnyl_r
)
cat_fig.update_traces(
    textinfo="label+percent+value",  # show category, percentage, and value
    textfont_size=18,  # increase font size
    textposition="outside"  # can be "inside" or "outside"
)
cat_fig.update_layout(
    title=dict(font=dict(size=24, family="Arial Black")),
    legend=dict(font=dict(size=18))
)
st.plotly_chart(cat_fig, use_container_width=True)

# Recurring Issues Horizontal Bar Chart
st.markdown("### 🔁 Top Recurring Issues")

issues_data = team_metrics["team_specific_recurring_issues"]

# Sort by count descending and pick top 5
sorted_issues = dict(sorted(issues_data.items(), key=lambda x: x[1], reverse=True)[:5])
labels = [issue.title() for issue in sorted_issues.keys()]
values = list(sorted_issues.values())

issue_fig = px.bar(
    x=values,
    y=labels,
    orientation="h",
    text=values,
    color=values,
    color_continuous_scale="Reds",
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

# ----- Developer Metrics -----
st.markdown('<div style="margin-top:30px;"></div>', unsafe_allow_html=True)
st.header("👩‍💻 Developer Metrics")
devs = list(prod_metrics_data["developer_productivity_metrics"]["average_suggestions_handled_per_day"].keys())
selected_dev = st.selectbox("Select Developer", devs)

if selected_dev:
    dev_metrics = prod_metrics_data["developer_productivity_metrics"]

    # --- Suggestions handled categories (Pie) ---
    st.markdown("### 📂 Issues by Category")
    categories = dev_metrics["average_suggestions_handled_per_category_per_day"][selected_dev]

    dev_cat_fig = px.pie(
        names=list(categories.keys()),
        values=list(categories.values()),
        title=f"Suggestions by Category for {selected_dev}",
        hole=0.4,  # donut style
        color_discrete_sequence=px.colors.sequential.Agsunset_r
    )
    dev_cat_fig.update_traces(
        textinfo="label+percent+value",
        textfont_size=16,
        textposition="outside"
    )
    dev_cat_fig.update_layout(
        title=dict(font=dict(size=24, family="Arial Black")),
        legend=dict(font=dict(size=18))
    )
    st.plotly_chart(dev_cat_fig, use_container_width=True)

    # --- Recurring Issues (Horizontal Bar) ---
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

    # --- Acceptance Rate ---
    st.markdown("### ✅ Acceptance Rate")
    acceptance = dev_metrics["suggestion_acceptance_rate"][selected_dev]
    st.progress(int(acceptance * 100))
    st.write(f"**{acceptance * 100:.1f}% suggestions accepted**")
