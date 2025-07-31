import streamlit as st
import pandas as pd
import openai
import time
import re

openai.api_key = st.secrets["OPENAI_API_KEY"]

MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

st.set_page_config(page_title="CT AI Impact Analyzer", layout="centered")
st.title("🧠 Round Runner – Multi-Workflow (Excel Upload)")

uploaded_file = st.file_uploader("📤 Upload an Excel file with a 'Workflow' column", type=["xlsx"])

def extract_code_block(text):
    blocks = re.findall(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)
    return blocks[0].strip() if blocks else text.strip()

def run_assistant(assistant_id, user_input, file_path=None):
    thread = openai.beta.threads.create()

    if file_path:
        upload = openai.files.create(file=open(file_path, "rb"), purpose="assistants")
        message = openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input,
            file_ids=[upload.id]
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

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    if "Workflow" not in df.columns:
        st.error("❌ Excel file must include a column labeled 'Workflow'.")
    else:
        workflows = df["Workflow"].dropna().astype(str).tolist()

        if not 1 <= len(workflows) <= 25:
            st.warning("⚠️ Please upload between 1 and 25 workflows.")
        else:
            st.success(f"✅ {len(workflows)} workflow(s) detected.")
            st.dataframe(df)

            if st.button("🚀 Run Round"):
                with st.spinner("🔁 Mapper: Assigning SOCs..."):
                    joined_workflows = "\n".join(workflows)  # Removed numbering — safer for parser

                    mapper_prompt = (
                        f"You are the Mapper Assistant. Given the following workflows:\n{joined_workflows}\n\n"
                        "Return a Markdown table with the following columns:\n"
                        "- SOC Code, Job Title, CT Workers, % on Workflow, CT FTEs, Time Distribution, "
                        "Tenure Bands (<3 yrs, 4–9 yrs, 10+ yrs), Routine/Non-Routine, Cognitive/Manual\n\n"
                        "Output only the Markdown table. No headings, no explanations, no summaries."
                    )

                    mapper_response = run_assistant(MAPPER_ID, mapper_prompt)
                    mapper_structured = extract_code_block(mapper_response)

                with st.spinner("📊 Analyzer: Assessing AI impact..."):
                    analyzer_prompt = (
                        f"You are the Analyzer Assistant. Analyze the following SOC data:\n\n"
                        f"{mapper_structured}\n\n"
                        "Follow Analyzer_v3_Instructions.txt. Return Markdown table only."
                    )
                    analyzer_response = run_assistant(ANALYZER_ID, analyzer_prompt)
                    analyzer_structured = extract_code_block(analyzer_response)

                with open("/tmp/analyzer_output.txt", "w") as f:
                    f.write(analyzer_structured)

                with st.spinner("📈 Comparor: Generating charts and summaries..."):
                    comparor_prompt = (
                        "You are the Comparor Assistant. The uploaded file contains Analyzer SOC output. "
                        "Follow Comparor_v2_Instructions.txt and generate the PowerPoint and Excel outputs. "
                        "Return URLs to download them."
                    )
                    comparor_response = run_assistant(COMPAROR_ID, comparor_prompt, file_path="/tmp/analyzer_output.txt")

                st.success("🎉 Round complete!")
                st.markdown("#### 📄 Comparor Output Preview")
                st.text_area("Comparor Output", comparor_response[:3000], height=300)
