import streamlit as st
import pandas as pd
import openai
import time
import re
from tempfile import NamedTemporaryFile

openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_PTfsO2JxEjkgRpDeZVvcPPG7"

def extract_code_block(text):
    blocks = re.findall(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)
    return blocks[0].strip() if blocks else text.strip()

def run_assistant(assistant_id, user_input, file_path=None):
    thread = openai.beta.threads.create()

    if file_path:
        upload = openai.files.create(file=open(file_path, "rb"), purpose="assistants")
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input,
            attachments=[{
                "file_id": upload.id,
                "tools": [{"type": "file_search"}]
            }]
        )
    else:
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

    run = openai.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id)

    while run.status not in ["completed", "failed", "cancelled", "expired"]:
        time.sleep(2)
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    if run.status != "completed":
        raise RuntimeError(f"Run failed: {run.status}")

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    return messages.data[0].content[0].text.value

# Streamlit layout
st.set_page_config(page_title="CT AI Workforce Impact Analyzer – Round 12", layout="centered")
st.title("📊 CT AI Workforce Impact Analyzer – Round 12")

uploaded_file = st.file_uploader("📥 Upload Excel with a column labeled 'Workflow'", type=["xlsx"])

if uploaded_file:
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    df = pd.read_excel(tmp_path)
    if "Workflow" not in df.columns:
        st.error("❌ Excel must include a column named 'Workflow'")
    else:
        workflows = df["Workflow"].dropna().astype(str).tolist()

        if not 1 <= len(workflows) <= 25:
            st.warning("⚠️ Please provide 1–25 workflows.")
        else:
            st.success(f"✅ {len(workflows)} workflow(s) detected.")
            st.dataframe(df)

            if st.button("🚀 Run Round"):
                try:
                    with st.spinner("🔁 Step 1: Running Mapper..."):
                        joined = "\n".join(workflows)
                        mapper_prompt = (
                            f"Given the following workflows:\n{joined}\n\n"
                            "Return only a Markdown table with:\n"
                            "- SOC Code, Job Title, CT Workers, % on Workflow, CT FTEs, Time Distribution, "
                            "Tenure Bands (<3 yrs, 4–9 yrs, 10+ yrs), Routine/Non-Routine, Cognitive/Manual\n\n"
                            "Follow Mapper_v3_Instructions.txt strictly. Output table only."
                        )
                        mapper_out = run_assistant(MAPPER_ID, mapper_prompt)
                        mapper_structured = extract_code_block(mapper_out)
                        st.success("✅ Mapper complete.")
                        st.text_area("🔹 Mapper Output", mapper_structured, height=200)

                    with st.spinner("📊 Step 2: Running Analyzer..."):
                        analyzer_prompt = (
                            "Use the uploaded Markdown table containing SOC data for a single workflow. "
                            "Follow Analyzer_v3_Instructions.txt. Output a Markdown table only."
                        )
                        with NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as f:
                            f.write(mapper_structured)
                            mapper_txt_path = f.name

                        analyzer_out = run_assistant(ANALYZER_ID, analyzer_prompt, file_path=mapper_txt_path)
                        analyzer_structured = extract_code_block(analyzer_out)
                        st.success("✅ Analyzer complete.")
                        st.text_area("🔹 Analyzer Output", analyzer_structured, height=200)

                    # ⚠️ Strip non-table content from Analyzer output for Comparor
                    analyzer_table = "\n".join([
                        line for line in analyzer_structured.splitlines()
                        if "|" in line and not line.strip().startswith("```")
                    ])

                    with NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as f:
                        f.write(analyzer_table.strip())
                        analyzer_txt_path = f.name

                    with st.spinner("📈 Step 3: Running Comparor..."):
                        comparor_prompt = (
                            "Use the uploaded file containing Analyzer SOC output. "
                            "Follow Comparor_v2_Instructions.txt to generate Excel + PowerPoint outputs. "
                            "Return links or text output as appropriate."
                        )
                        comparor_out = run_assistant(COMPAROR_ID, comparor_prompt, file_path=analyzer_txt_path)
                        st.success("✅ Comparor complete.")
                        st.text_area("📄 Comparor Output", comparor_out[:3000], height=300)

                except Exception as e:
                    st.error(f"❌ Pipeline failed: {e}")
