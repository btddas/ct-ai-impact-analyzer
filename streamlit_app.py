import streamlit as st
import openai
import os
import time
import base64
from io import BytesIO

# Set your assistant IDs here
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Streamlit UI
st.set_page_config(page_title="CT AI Impact Analyzer", layout="centered")
st.title("CT AI Impact Analyzer")
st.markdown("Upload a structured Excel export from Comparor to analyze workforce AI impact.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

def run_pipeline(file):
    client = openai.OpenAI()

    # Upload the Excel file to OpenAI
    with st.spinner("🔼 Step 1: Uploading file to OpenAI..."):
        uploaded = client.files.create(file=file, purpose="assistants")
        st.success(f"✅ File uploaded: `{uploaded.id}`")

    def run_assistant(assistant_id, file_id, label):
        st.info(f"🤖 Running **{label}** assistant...")
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            file_id=file_id,
            content="Please process this Comparor Excel file."
        )
        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id)

        while True:
            status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id).status
            if status == "completed":
                break
            elif status == "failed":
                raise RuntimeError(f"{label} assistant run failed.")
            time.sleep(2)

        return client.beta.threads.messages.list(thread_id=thread.id)

    # Run Mapper → Analyzer → Comparor
    try:
        run_assistant(MAPPER_ID, uploaded.id, "Mapper")
        run_assistant(ANALYZER_ID, uploaded.id, "Analyzer")
        messages = run_assistant(COMPAROR_ID, uploaded.id, "Comparor")
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return []

    # Extract file IDs from final messages
    file_ids = []
    for msg in messages.data:
        if hasattr(msg, "file_ids"):
            file_ids.extend(msg.file_ids)

    outputs = []
    for fid in file_ids:
        content = client.files.retrieve_content(fid)
        outputs.append((fid, content))

    return outputs

def render_download_link(file_data, filename):
    b64 = base64.b64encode(file_data.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📥 Download {filename}</a>'
    return href

# Run pipeline and show results
if uploaded_file:
    st.success("✅ File uploaded. Click below to run analysis.")
    if st.button("Submit"):
        with st.spinner("🧠 Running Mapper → Analyzer → Comparor..."):
            results = run_pipeline(uploaded_file)

        if results:
            st.success("✅ Analysis complete. Download files below:")
            for i, (fid, result_file) in enumerate(results):
                filename = f"AI_Impact_Output_{i+1}.xlsx" if i == 0 else f"AI_Impact_Insights_{i+1}.pptx"
                st.markdown(render_download_link(result_file, filename), unsafe_allow_html=True)
        else:
            st.warning("⚠️ No output files generated.")
