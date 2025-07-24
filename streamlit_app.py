import streamlit as st
import openai
import os
import time
import base64
from io import BytesIO

# Set your OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

st.set_page_config(page_title="CT AI Impact Analyzer", layout="centered")
st.title("CT AI Impact Analyzer")
st.write("Upload a structured Excel export from Comparor to analyze workforce AI impact.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

def run_pipeline(file):
    client = openai.OpenAI()

    with st.spinner("\u2705 Step 1: Uploading file to OpenAI..."):
        openai_file = client.files.create(file=file, purpose="assistants")
        st.success(f"\u2705 File uploaded: `{openai_file.id}`")

    def run_assistant(assistant_id):
        st.info(f"\U0001F535 Running `{assistant_id.split('_')[1]}` assistant...")
        thread = client.beta.threads.create()

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
            tool_resources={"file_ids": [openai_file.id]}
        )

        while True:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run_status.status == "completed":
                break
            elif run_status.status == "failed":
                raise RuntimeError("Run failed.")
            time.sleep(2)

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        return messages

    try:
        messages = run_assistant(MAPPER_ID)
        messages = run_assistant(ANALYZER_ID)
        messages = run_assistant(COMPAROR_ID)
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return []

    output_files = []
    for msg in messages.data:
        for file_id in getattr(msg, "file_ids", []):
            file_bytes = client.files.retrieve_content(file_id)
            output_files.append((file_id, file_bytes))

    return output_files

def download_link(file_bytes, filename, label):
    b64 = base64.b64encode(file_bytes.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

if uploaded_file is not None:
    st.success("File uploaded. Click below to run analysis.")
    if st.button("Submit"):
        with st.spinner("Running Mapper → Analyzer → Comparor..."):
            results = run_pipeline(uploaded_file)

        if results:
            st.success("Analysis complete. Download files below:")
            for i, (fid, result_file) in enumerate(results):
                ext = ".xlsx" if i == 0 else ".pptx"
                filename = f"AI_Impact_Output_{i+1}{ext}"
                st.markdown(download_link(BytesIO(result_file), filename, f"📥 Download {filename}"), unsafe_allow_html=True)
        else:
            st.warning("⚠️ No output files generated.")

