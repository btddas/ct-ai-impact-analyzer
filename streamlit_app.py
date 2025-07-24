import streamlit as st
import openai
import os
import time
import base64
from io import BytesIO
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

st.set_page_config(page_title="CT AI Impact Analyzer", layout="centered")
st.title("CT AI Impact Analyzer")
st.write("Upload a structured Excel or CSV export from Comparor to analyze workforce AI impact.")

uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["xlsx", "csv"])

# ✅ Converts any spreadsheet file into a plain .txt (CSV-style)
def convert_spreadsheet_to_txt(file, ext):
    if ext == "xlsx":
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)
    txt = df.to_csv(index=False)
    return BytesIO(txt.encode("utf-8"))

def run_single_assistant(assistant_id, openai_file_id):
    client = openai.OpenAI()
    assistant_name = assistant_id.split("_")[1]
    thread = client.beta.threads.create()
    st.write(f"📌 `{assistant_name}` thread ID: `{thread.id}`")

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"Run `{assistant_name}` analysis on uploaded file.",
        attachments=[{"file_id": openai_file_id, "tools": [{"type": "file_search"}]}]
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )
    st.write(f"▶️ `{assistant_name}` run ID: `{run.id}`")

    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            st.success(f"✅ `{assistant_name}` completed.")
            break
        elif run_status.status == "failed":
            raise RuntimeError(f"{assistant_name} failed.")
        time.sleep(2)

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    output_files = []
    for msg in messages.data:
        for file_id in getattr(msg, "file_ids", []):
            file_bytes = client.files.retrieve_content(file_id)
            output_files.append((file_id, file_bytes))

    return assistant_name, output_files

def run_pipeline(file, ext):
    client = openai.OpenAI()

    with st.spinner("📤 Converting and uploading file to OpenAI..."):
        converted_txt = convert_spreadsheet_to_txt(file, ext)
        openai_file = client.files.create(file=converted_txt, purpose="assistants")
        st.success(f"✅ File uploaded as .txt: `{openai_file.id}`")

    assistant_ids = [MAPPER_ID, ANALYZER_ID, COMPAROR_ID]
    results = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_single_assistant, aid, openai_file.id): aid for aid in assistant_ids
        }
        for future in as_completed(futures):
            try:
                name, files = future.result()
                results[name] = files
            except Exception as e:
                st.error(f"❌ Error in `{futures[future]}`: {e}")

    all_outputs = []
    for name in ["MAPPER", "ANALYZER", "COMPAROR"]:
        if name in results:
            all_outputs.extend(results[name])
    return all_outputs

def download_link(file_bytes, filename, label):
    b64 = base64.b64encode(file_bytes.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

if uploaded_file is not None:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext not in ["xlsx", "csv"]:
        st.error("❌ Only .xlsx or .csv files are supported.")
    else:
        st.success("File uploaded. Click below to run analysis.")
        if st.button("Submit"):
            with st.spinner("🚀 Running Mapper, Analyzer, and Comparor in parallel..."):
                results = run_pipeline(uploaded_file, ext)

            if results:
                st.success("✅ Analysis complete. Download files below:")
                for i, (fid, result_file) in enumerate(results):
                    ext = ".xlsx" if i == 0 else ".pptx"
                    filename = f"AI_Impact_Output_{i+1}{ext}"
                    st.markdown(download_link(BytesIO(result_file), filename, f"📥 Download {filename}"), unsafe_allow_html=True)
            else:
                st.warning("⚠️ No output files generated.")

