import streamlit as st
import pandas as pd
import openai
import time
import re
from tempfile import NamedTemporaryFile

# Load your OpenAI API key from secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs from GitHub
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

# Extract the first Markdown code block from assistant response
def extract_code_block(text):
    blocks = re.findall(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)
    return blocks[0].strip() if blocks else text.strip()

# Unified assistant runner: handles optional file attachment
def run_assistant(assistant_id, user_input, file_path=None):
    thread = openai.beta.threads.create()

    if file_path:
        uploaded_file = openai.files.create(file=open(file_path, "rb"), purpose="assistants")
        message = openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input,
            attachments=[{
                "file_id": uploaded_file.id,
                "tools": [{"type": "file_search"}]
            }]
        )
    else:
        openai.beta.threads.messages.create(
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

# Streamlit app layout
st.set_page_config(page_title="CT AI Workforce Impact Analyzer – Round 12", layout="centered")
st.title("📊 CT AI Workforce Impact Analyzer – Round 12")

uploaded_file = st.file_uploader("📥 Upload Excel with a column labeled 'Workflow'", type=["xlsx"])

if uploaded_file:
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    df = pd.read_excel(tmp_path)
    if "Workflow" not in df.columns:
        st.error("❌ Excel must include a column named 'Workflow'.")
    else:
        workflows = df["Workflow"].dropna().astype(str).tolist()

        if not 1 <= len(workflows) <= 25:
            st.warning("⚠️ Please provide between 1 and 25 workflows.")
        else:
            st.success(f"✅ {len(workflows)} workflow(s) detected.")
            st.dataframe(df)

            if st.button("🚀 Run Round"):
                try:
                    with st.spinner("⚙️ Step 1: Running Mapper..."):
                        joined_workflows = "\n".join(workflows)
                        mapper_prompt = (
                            f"Given the following workflows:\n{joined_workflows}\n\n"
                            "Return a Markdown table with these columns:\n"
                            "- SOC Code, Job Title, CT Workers, % on Workflow, CT FTEs, Time Distribution, "
                            "Tenure Bands (<3 yrs, 4–9 yrs, 10+ yrs), Routine/Non-Routine, Cognitive/Manual\n\n"
                            "Follow Mapper_v3_Instructions.txt. Output only the Markdown table — no headings or notes."
                        )
                        mapper_result = run_assistant(MAPPER_ID, mapper_prompt)
                        mapper_structured = extract_code_block(mapper_result)
                        st.success("✅ Mapper completed.")
                        st.text_area("📄 Mapper Output", mapper_structured, height=200)

                    with st.spinner("⚙️ Step 2: Running Analyzer..."):
                        analyzer_prompt = (
                            f"Analyze the following Mapper output per Analyzer_v3_Instructions.txt:\n\n{mapper_structured}"
                        )
                        analyzer_result = run_assistant(ANALYZER_ID, analyzer_prompt)
                        analyzer_structured = extract_code_block(analyzer_result)
                        st.success("✅ Analyzer completed.")
                        st.text_area("📄 Analyzer Output", analyzer_structured, height=200)

                    with NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as tmp_out:
                        tmp_out.write(analyzer_structured)
                        analyzer_file_path = tmp_out.name

                    with st.spinner("⚙️ Step 3: Running Comparor..."):
                        comparor_prompt = (
                            "You are the Comparor Assistant. Use the uploaded Analyzer output to generate:\n"
                            "- 1 PowerPoint aggregating all workflows (white theme)\n"
                            "- 1 Excel with all SOC-level results\n"
                            "- Summary quadrant charts, seniority stack, and AI roles created\n\n"
                            "Follow Comparor_v2_Instructions.txt."
                        )
                        comparor_result = run_assistant(COMPAROR_ID, comparor_prompt, file_path=analyzer_file_path)
                        st.success("✅ Comparor completed.")
                        st.text_area("📄 Comparor Output", comparor_result[:3000], height=300)

                except Exception as e:
                    st.error(f"❌ Pipeline failed: {e}")
