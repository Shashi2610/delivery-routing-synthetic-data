import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import metrics  # noqa: E402
import validate  # noqa: E402
from generator.config import DEFAULT_SEED, SCALES  # noqa: E402

DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_GROUND_TRUTH = ROOT / "ground_truth" / "ground_truth.csv"
REPRODUCIBILITY_REPORT = ROOT / "docs" / "reproducibility_report.md"
HISTOGRAM_BINS = 10
HASH_PREFIX_LENGTH = 16


def run_command(arguments):
    completed = subprocess.run([sys.executable, *arguments], capture_output=True, text=True, cwd=ROOT)
    return completed.returncode, completed.stdout + completed.stderr


def folder_signature(folder):
    return tuple(sorted((path.name, path.stat().st_mtime_ns) for path in Path(folder).glob("*.csv")))


def file_signature(path):
    return path.stat().st_mtime_ns if path.exists() else None


def text_table(headers, rows):
    return pd.DataFrame(rows, columns=headers).astype(str)


@st.cache_data(show_spinner="Computing metrics")
def compute_metrics(folder, signature):
    data = metrics.load_data(Path(folder))
    events = data["delivery_status_event"]
    return {
        "frame": metrics.build_delivery_frame(data),
        "loads": metrics.build_load_frame(data),
        "shifts": metrics.build_shift_frame(data),
        "shift_count": len(data["shift"]),
        "unserved": events.loc[events["status"] == "unserved", "reason_code"],
        "travel_rows": metrics.travel_rows(data),
    }


@st.cache_data(show_spinner="Running validation")
def compute_validation(folder, signature, truth_path, truth_signature):
    data = validate.load_data(Path(folder))
    results = validate.run_structural_checks(data)
    detections = validate.run_detectors(data)
    exists = Path(truth_path).exists()
    labels = pd.read_csv(truth_path) if exists else pd.DataFrame(columns=validate.GROUND_TRUTH_COLUMNS)
    return results, detections, validate.score_detections(detections, labels, data), exists


def utilisation_histogram(values):
    top = max(1.0, float(values.max()))
    edges = np.linspace(0, top, HISTOGRAM_BINS + 1)
    counts, _ = np.histogram(values, bins=edges)
    labels = [f"{edges[i] * 100:03.0f}-{edges[i + 1] * 100:03.0f}%" for i in range(len(counts))]
    return pd.DataFrame({"Routes": counts}, index=labels)


def reason_chart(rows):
    table = pd.DataFrame(rows, columns=["Reason code", "Count", "Share"])
    st.dataframe(table.astype(str), hide_index=True)
    if table["Count"].sum() > 0:
        st.bar_chart(table.set_index("Reason code")["Count"])


def hub_service_chart(frame):
    grouped = frame.groupby("hub_id")
    rates = pd.DataFrame({
        "Service rate": grouped["assigned"].mean(),
        "On-time rate": grouped.apply(lambda group: group["on_time"].sum() / max(int(group["attempted"].sum()), 1), include_groups=False),
    })
    st.bar_chart(rates)


def render_overview(folder):
    manifest_path = Path(folder) / "manifest.json"
    if not manifest_path.exists():
        st.info("No manifest.json in this folder. Generate a dataset first.")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    columns = st.columns(3)
    columns[0].metric("Seed", manifest["seed"])
    columns[1].metric("Scale", manifest["scale"])
    columns[2].metric("Anomalies injected", "yes" if manifest["anomalies_injected"] else "no")
    st.code(manifest["command"], language="bash")
    st.caption(manifest["note"])
    files = pd.DataFrame(manifest["files"])
    files["rows"] = files["rows"].map(lambda rows: "n/a" if pd.isna(rows) else str(int(rows)))
    files["sha256"] = files["sha256"].str[:HASH_PREFIX_LENGTH]
    st.subheader("Files")
    st.dataframe(files, hide_index=True)


def render_data(folder):
    table_name = st.selectbox("Table", validate.TABLES)
    path = Path(folder) / f"{table_name}.csv"
    if not path.exists():
        st.info("This table is not in the data folder.")
        return
    table = pd.read_csv(path)
    st.caption(f"{len(table)} rows, {len(table.columns)} columns")
    limit = st.slider("Rows to show", 10, 1000, 100, step=10)
    st.dataframe(table.head(limit), hide_index=True)


def render_metrics(folder):
    result = compute_metrics(str(folder), folder_signature(folder))
    frame, loads = result["frame"], result["loads"]
    attempted, total = int(frame["attempted"].sum()), len(frame)
    columns = st.columns(5)
    columns[0].metric("Deliveries", total)
    columns[1].metric("Service rate", metrics.percent(int(frame["assigned"].sum()), total))
    columns[2].metric("On-time % of attempted", metrics.percent(int(frame["on_time"].sum()), attempted))
    columns[3].metric("Failed", int(frame["failed"].sum()))
    columns[4].metric("Mean weight utilisation", f"{loads['weight_utilisation'].mean():.1%}")
    st.subheader("Delivery performance")
    st.dataframe(text_table(["Metric", "Value"], metrics.performance_rows(frame)), hide_index=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Failures by reason code")
        reason_chart(metrics.reason_rows(frame.loc[frame["failed"], "reason_code"]))
    with right:
        st.subheader("Unserved by reason code")
        reason_chart(metrics.reason_rows(result["unserved"]))
    st.subheader("Route load vs vehicle capacity")
    left, right = st.columns(2)
    left.caption("Weight")
    left.bar_chart(utilisation_histogram(loads["weight_utilisation"].dropna()))
    right.caption("Volume")
    right.bar_chart(utilisation_histogram(loads["volume_utilisation"].dropna()))
    headers = ["Measure", "Routes", "Mean", "Min", "25th", "Median", "75th", "Max", "Routes above 100%"]
    st.dataframe(text_table(headers, metrics.load_rows(loads)), hide_index=True)
    st.subheader("Shift utilisation")
    st.dataframe(text_table(["Metric", "Value"], metrics.shift_rows(result["shifts"], result["shift_count"])), hide_index=True)
    st.subheader("Per hub")
    hub_headers = ["Hub", "Deliveries", "Assigned", "Service rate", "Attempted", "On time", "On-time %"]
    st.dataframe(text_table(hub_headers, metrics.hub_rows(frame)), hide_index=True)
    hub_service_chart(frame)
    left, right = st.columns(2)
    with left:
        st.subheader("Lateness of late deliveries")
        st.dataframe(text_table(["Metric", "Value"], metrics.lateness_rows(frame)), hide_index=True)
    with right:
        st.subheader("Planned vs actual travel time")
        st.dataframe(text_table(["Metric", "Value"], result["travel_rows"]), hide_index=True)


def score_table(scores):
    rows = [
        (
            score["issue_type"], score["anomalies"], score["detected"],
            validate.format_ratio(validate.ratio(score["detected"], score["anomalies"])),
            score["detections"], score["true_positives"],
            validate.format_ratio(validate.ratio(score["true_positives"], score["detections"])),
            len(score["false_positives"]), len(score["missed"]),
        )
        for score in scores
    ]
    headers = ["Issue type", "Injected", "Detected", "Recall", "Detections", "True positives", "Precision", "False positives", "Missed"]
    return text_table(headers, rows)


def render_validation(folder, truth_path):
    results, detections, scores, has_truth = compute_validation(
        str(folder), folder_signature(folder), str(truth_path), file_signature(truth_path)
    )
    failed = [result for result in results if not result.passed]
    passed = not failed and validate.scoring_passes(scores, has_truth)
    (st.success if passed else st.error)(f"Overall: {'PASS' if passed else 'FAIL'}")
    columns = st.columns(3)
    columns[0].metric("Structural checks passed", f"{len(results) - len(failed)} of {len(results)}")
    columns[1].metric("Anomalies detected", len(detections))
    columns[2].metric("Ground truth", "found" if has_truth else "not found")
    st.subheader("Rule detectors")
    counts = detections.groupby("issue_type").size()
    st.dataframe(text_table(["Issue type", "Detections"], [(name, int(counts.get(name, 0))) for name in validate.ISSUE_TYPES]), hide_index=True)
    st.subheader("Scoring against ground truth")
    if has_truth:
        st.dataframe(score_table(scores), hide_index=True)
        st.markdown(validate.missed_lines(scores))
    else:
        st.info("No ground truth file. On a clean dataset every detector should report zero detections.")
    st.subheader("Structural checks")
    table = text_table(["Group", "Check", "Rows checked", "Failures", "Status"], [(r.group, r.name, r.checked, r.failures, "pass" if r.passed else "FAIL") for r in results])
    if failed:
        st.dataframe(table[table["Status"] == "FAIL"], hide_index=True)
    with st.expander("All structural checks"):
        st.dataframe(table, hide_index=True)
    with st.expander("Checks not implemented"):
        st.markdown("\n".join(f"- {item}" for item in validate.NOT_IMPLEMENTED))


def render_reproducibility():
    scale = st.selectbox("Scale", list(SCALES), key="reproducibility_scale")
    if st.button("Run reproducibility check"):
        with st.spinner("Generating three datasets and comparing checksums"):
            code, output = run_command(["scripts/check_reproducibility.py", "--scale", scale])
        (st.success if code == 0 else st.error)(f"Exit code {code}")
        st.code(output)
    if REPRODUCIBILITY_REPORT.exists():
        st.markdown(REPRODUCIBILITY_REPORT.read_text(encoding="utf-8"))
    else:
        st.info("No reproducibility report yet.")


def render_generator_controls():
    st.sidebar.header("Generate a dataset")
    seed = st.sidebar.number_input("Seed", value=DEFAULT_SEED, step=1)
    scale = st.sidebar.selectbox("Scale", list(SCALES))
    anomalies = st.sidebar.checkbox("Inject anomalies", value=True)
    st.sidebar.caption("Writes data/, sql/ and ground_truth/ in the project folder, replacing the current files.")
    if st.sidebar.button("Generate"):
        arguments = ["generate.py", "--seed", str(int(seed)), "--scale", scale] + ([] if anomalies else ["--no-anomalies"])
        with st.spinner("Generating"):
            code, output = run_command(arguments)
        st.cache_data.clear()
        st.session_state["generate_result"] = (code, output)
    if "generate_result" in st.session_state:
        code, output = st.session_state["generate_result"]
        (st.sidebar.success if code == 0 else st.sidebar.error)(f"generate.py exit code {code}")
        st.sidebar.code(output)


def main():
    st.set_page_config(page_title="Delivery routing synthetic data", layout="wide")
    st.title("Delivery routing synthetic data")
    render_generator_controls()
    folder = Path(st.sidebar.text_input("Data folder", str(DEFAULT_DATA_DIR)))
    truth_path = Path(st.sidebar.text_input("Ground truth file", str(DEFAULT_GROUND_TRUTH)))
    if not (folder / "delivery.csv").exists():
        st.warning("No dataset in the data folder. Use Generate in the sidebar.")
        return
    overview, data, metrics_tab, validation, reproducibility = st.tabs(["Overview", "Data", "Metrics", "Validation", "Reproducibility"])
    with overview:
        render_overview(folder)
    with data:
        render_data(folder)
    with metrics_tab:
        render_metrics(folder)
    with validation:
        render_validation(folder, truth_path)
    with reproducibility:
        render_reproducibility()


main()
