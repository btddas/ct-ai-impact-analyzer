import streamlit as st
import openai
import os
import time
import base64

# Set page config
st.set_page_config(page_title="CT AI Impact Analyzer", layout="wide")
st.title("CT AI Impact Analyzer")
st.markdown("Upload a structured Excel export from Comparor to analyze workforce AI impact.")

# Load API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

# Upload widget
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# Utility to create download link
def download_link(file_bytes, filename, label):
    b64 = base64.b64encode(file_bytes.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

# Pipeline function
def run_gpt_pipeline(file):
    client = openai.OpenAI()
    st.write("🔄 Step 1: Uploading file to OpenAI...")

    try:
        openai_file = client.files.create(file=file, purpose="assistants")
        st.write(f"✅ File uploaded: `{openai_file.id}`")
    except Exception as e:
        st.error(f"❌ File upload failed: {e}")
        return []

    def run_assistant_pipeline(assistant_id, file_id, name):
        st.write(f"🔄 Running `{name}` assistant...")
        try:
            thread = client.beta.threads.create()

            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="Process this file.",
                file_ids=[file_id]
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant_id
            )

            while True:
                run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
                if run.status == "completed":
                    st.write(f"✅ {name} completed")
                    break
                elif run.status == "failed":
                    st.error(f"❌ {name} run failed.")
                    return [], thread
                time.sleep(2)

            messages = client.beta.threads.messages.list(thread_id=thread.id)
            return messages, thread

        except Exception as e:
            st.error(f"❌ {name} pipeline error: {e}")
            return [], None

    # Run pipeline
    messages, _ = run_assistant_pipeline(MAPPER_ID, openai_file.id, "Mapper")
    if not messages: return []
    run_assistant_pipeline(ANALYZER_ID, openai_file.id, "Analyzer")
    messages, _ = run_assistant_pipeline(COMPAROR_ID, openai_file.id, "Comparor")
    if not messages: return []

    # Retrieve result files
    st.write("📦 Extracting output files...")
    file_ids = []
    for msg in messages.data:
        if hasattr(msg, "file_ids") and msg.file_ids:
            file_ids.extend(msg.file_ids)

    if not file_ids:
        st.warning("⚠️ No output files returned from Comparor.")
        return []

    downloaded_files = []
    for fid in file_ids:
        result = client.files.retrieve_content(fid)
        downloaded_files.append((fid, result))

    return downloaded_files

# Trigger
if uploaded_file is not None:
    st.success("File uploaded. Click below to run analysis.")
    if st.button("Submit"):
        try:
            with st.spinner("🔍 Running Mapper → Analyzer → Comparor..."):
                results = run_gpt_pipeline(uploaded_file)

            if results:
                st.success("✅ Analysis complete. Download files below:")
                for i, (fid, result_file) in enumerate(results):
                    filename = f"output_{i+1}.xlsx" if i == 0 else f"output_{i+1}.pptx"
                    st.markdown(download_link(result_file, filename, f"📥 Download {filename}"), unsafe_allow_html=True)
            else:
                st.warning("⚠️ No output files generated.")

        except Exception as e:
            st.error(f"❌ Something went wrong: {str(e)}")
else:
    st.info("Please upload a valid Excel file (.xlsx) to begin.")
