import streamlit as st
import pandas as pd
import openai
import os
import time
from tempfile import NamedTemporaryFile

openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

def run_assistant(assistant_id, user_input, file_path=None):
    thread = openai.beta.threads.create()

    if file_path:
        upload = openai.files.create(file=open(file_path, "rb"), purpose="assistants")
        message = openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input,
            attachments=[{"file_id": upload.id}]
        )
    else:
        message = openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )

    while True:
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status == "completed":
            break
        elif run.status in ["failed", "cancelled", "expired"]:
            raise RuntimeError(f"Run failed: {run.status}")
        time.sleep(2)

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    return messages.data[0].content[0].text.value

st.title("🔁 CT AI Workforce Impact Analyzer – Round 12")

uploaded_file = st.file_uploader("📂 Upload your workflow Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    df = pd.read_excel(tmp_path)
    if "Workflow" not in df.columns:
        st.error("❌ Excel must have a column named 'Workflow'")
    else:
        st.success("✅ Workflows loaded successfully!")
        st.dataframe(df[["Workflow"]])
        if st.button("▶ Run Round"):
            try:
                with st.spinner("Running Mapper..."):
                    mapper_output = run_assistant(MAPPER_ID, "Run all workflows through Mapper", file_path=tmp_path)

                st.success("✅ Mapper complete.")
                st.text_area("🔹 Mapper Output", mapper_output, height=300)

                with st.spinner("Running Analyzer..."):
                    analyzer_output = run_assistant(ANALYZER_ID, "Run all Mapper results through Analyzer", file_path=tmp_path)

                st.success("✅ Analyzer complete.")
                st.text_area("🔹 Analyzer Output", analyzer_output, height=300)

                with st.spinner("Running Comparor..."):
                    comparor_output = run_assistant(COMPAROR_ID, "Run Analyzer outputs through Comparor and generate Excel + PPT", file_path=tmp_path)

                st.success("✅ Comparor complete.")
                st.text_area("🔹 Comparor Output", comparor_output, height=300)

            except Exception as e:
                st.error(f"❌ Error during pipeline: {e}")
