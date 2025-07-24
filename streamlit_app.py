import streamlit as st
import openai
import os
import time
import base64

# Load API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

st.set_page_config(page_title="CT AI Impact Analyzer", layout="wide")
st.title("CT AI Impact Analyzer")
st.markdown("Upload a structured Excel export from Comparor to analyze workforce AI impact.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

def run_gpt_pipeline(file):
    client = openai.OpenAI()

    def upload_to_openai(file):
        return client.files.create(file=file, purpose="assistants")

    def run_assistant_pipeline(assistant_id, file_id):
        thread = client.beta.threads.create()

        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=[
                {
                    "type": "text",
                    "text": "Please process this Excel file."
                },
                {
                    "type": "file",
                    "file_id": file_id
                }
            ]
        )

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        while True:
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run.status == "completed":
                break
            elif run.status == "failed":
                raise RuntimeError("Run failed.")
            time.sleep(2)

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        return messages, thread

    # Step 1: Upload file to OpenAI
    openai_file = upload_to_openai(file)
    
    # Step 2: Run Mapper
    run_assistant_pipeline(MAPPER_ID, openai_file.id)

    # Step 3: Run Analyzer
    run_assistant_pipeline(ANALYZER_ID, openai_file.id)

    # Step 4: Run Comparor
    messages, thread = run_assistant_pipeline(COMPAROR_ID, openai_file.id)

    # Step 5: Retrieve attachments (PPT + Excel)
    file_ids = []
    for msg in messages.data:
        if msg.file_ids:
            file_ids.extend(msg.file_ids)

    downloaded_files = []
    for fid in file_ids:
        file_obj = client.files.retrieve_content(fid)
        downloaded_files.append((fid, file_obj))

    return downloaded_files

def download_link(file_bytes, filename, label):
    b64 = base64.b64encode(file_bytes.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

if uploaded_file is not None:
    st.success("File uploaded. Click below to run analysis.")
    if st.button("Submit"):
        try:
            with st.spinner("Running Mapper → Analyzer → Comparor..."):
                results = run_gpt_pipeline(uploaded_file)
            
            st.success("Analysis complete. Download files below:")
            for i, (fid, result_file) in enumerate(results):
                filename = f"output_file_{i+1}.xlsx" if i == 0 else f"output_file_{i+1}.pptx"
                st.markdown(download_link(result_file, filename, f"📥 Download {filename}"), unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Something went wrong: {str(e)}")
else:
    st.info("Please upload a valid Excel file (.xlsx) to begin.")
