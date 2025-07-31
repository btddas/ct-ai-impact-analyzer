import streamlit as st
import pandas as pd
import openai
import time

# Set your OpenAI key from secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs from GitHub-synced deployment
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

# Streamlit UI setup
st.set_page_config(page_title="CT AI Impact Analyzer", layout="centered")
st.title("🧠 Round Runner – Multi-Workflow (Excel Upload)")

uploaded_file = st.file_uploader("📤 Upload an Excel file with a 'Workflow' column", type=["xlsx"])

def run_assistant(assistant_id, user_input):
    thread = openai.beta.threads.create()
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_input
    )
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )

    # Poll until complete
    while True:
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status == "completed":
            break
        elif run.status in ["failed", "cancelled", "expired"]:
            raise RuntimeError(f"Run failed with status: {run.status}")
        time.sleep(2)

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    return messages.data[0].content[0].text.value

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    if "Workflow" not in df.columns:
        st.error("❌ The Excel file must include a column labeled 'Workflow'.")
    else:
        workflows = df["Workflow"].dropna().astype(str).tolist()
        metadata = df.drop(columns=["Workflow"]) if df.shape[1] > 1 else None

        if not 1 <= len(workflows) <= 25:
            st.warning("⚠️ Please upload between 1 and 25 workflows.")
        else:
            st.success(f"✅ {len(workflows)} workflow(s) detected.")
            st.dataframe(df)

            if st.button("🚀 Run Round"):
                with st.spinner("🔁 Sending to Mapper..."):
                    mapper_input = "\n".join([f"{i+1}. {w}" for i, w in enumerate(workflows)])
                    mapper_result = run_assistant(MAPPER_ID, f"Map these workflows:\n{mapper_input}")

                with st.spinner("🔎 Sending to Analyzer..."):
                    analyzer_result = run_assistant(ANALYZER_ID, mapper_result)

                with st.spinner("📊 Sending to Comparor..."):
                    comparor_result = run_assistant(COMPAROR_ID, analyzer_result)

                st.success("🎉 Round complete.")
                st.markdown("#### 📄 Results")
                st.text_area("Excel Output Preview", analyzer_result[:1500])
                st.download_button("⬇️ Download Results (text)", analyzer_result, file_name="Round_Results.txt")
