import streamlit as st
import openai
import os
import time
import base64
from io import BytesIO
import pandas as pd

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

# Convert .xlsx or .csv → .txt with proper file extension
def convert_spreadsheet_to_txt(file, ext):
    if ext == "xlsx":
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)
    txt = df.to_csv(index=False)
    return BytesIO(txt.encode("utf-8"))

# Run one assistant on one thread, return messages and file_ids
def run_single_assistant(assistant_id, user_prompt, file_id):
    client = openai.OpenAI()
    name = assistant_id.split("_")[1]

    thread = client.beta.threads.create()
    st.write(f"🧵 `{name}` thread ID: `{thread.id}`")

    # Send message + file attachment
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_prompt,
        attachments=[{"file_id": file_id, "tools": [{"type": "file_search"}]}]
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )
    st.write(f"▶️ `{name}` run ID: `{run.id}`")

    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            st.success(f"✅ `{name}` completed.")
            break
        elif run_status.status == "failed":
            raise RuntimeError(f"❌ `{name}` run failed.")
        time.sleep(2)

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    return messages

# Upload file and run all assistants in sequence
def run_pipeline(file, ext):
    client = openai.OpenAI()

    with st.spinner("📤 Converting and uploading file..."):
        txt_file = convert_spreadsheet_to_txt(file, ext)
        txt_file.name = "converted_input.txt"  # ✅ required for OpenAI
        openai_file = client.files.create(file=txt_file, purpose="assistants")
        st.success(f"✅ File uploaded: `{openai_file.id}`")

    output_files = []

    assistant_steps = [
    (
        MAPPER_ID,
        """Please act as the Mapper: analyze the uploaded Comparor export and identify SOC roles and their CT FTE allocations.
Output your results in a downloadable CSV file named `mapper_output.csv`.

For each workflow in the uploaded file, output a table with the following columns:
- SOC Code
- SOC Title
- % of SOCs Participating in Workflow
- % of Participating SOC’s Time Spent on this Workflow
- % Share of Total Workflow Time
- CT FTEs (Total for that SOC)
- CT FTEs Assigned to this Workflow
- EZ Zone
- Cognitive/Manual
- Routine/Non-routine

Use the `code_interpreter` tool to write this output to `mapper_output.csv` and upload it so it appears as a file_id in your response.
Do not emit results only as Markdown or plain text — a downloadable file is required."""
    ),
    (
        ANALYZER_ID,
        "Please act as the Analyzer: use the output of the Mapper to assess AI impact, risk level, and generate Excel results."
    ),
    (
        COMPAROR_ID,
        "Please act as the Comparor: compare across workflows and produce summary insights and PowerPoint output."
    )
]


    for assistant_id, prompt in assistant_steps:
        try:
            messages = run_single_assistant(assistant_id, prompt, openai_file.id)
            found_files = False
            for msg in messages.data:
                for file_id in getattr(msg, "file_ids", []):
                    file_bytes = client.files.retrieve_content(file_id)
                    output_files.append((file_id, file_bytes))
                    found_files = True
            if not found_files:
                st.warning(f"⚠️ No output files returned by `{assistant_id.split('_')[1]}`.")
        except Exception as e:
            st.error(f"❌ Error running `{assistant_id}`: {e}")

    return output_files

# Convert bytes to downloadable link
def download_link(file_bytes, filename, label):
    b64 = base64.b64encode(file_bytes.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

# Main UI logic
if uploaded_file is not None:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext not in ["xlsx", "csv"]:
        st.error("❌ Only .xlsx or .csv files are supported.")
    else:
        st.success("File uploaded. Click below to run analysis.")
        if st.button("Submit"):
            with st.spinner("⏳ Running assistants in sequence..."):
                results = run_pipeline(uploaded_file, ext)

            if results:
                st.success("🎉 Analysis complete. Download your files:")
                for i, (fid, result_file) in enumerate(results):
                    ext = ".xlsx" if i == 0 else ".pptx"
                    filename = f"AI_Impact_Output_{i+1}{ext}"
                    st.markdown(download_link(BytesIO(result_file), filename, f"📥 Download {filename}"), unsafe_allow_html=True)
            else:
                st.warning("⚠️ All assistants completed, but no output files were generated.")
