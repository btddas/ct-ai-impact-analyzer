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

def run_assistant(assistant_id, user_input, file_ids=None):
    thread = openai.beta.threads.create()
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_input
    )
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
        file_ids=file_ids or []
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
        metadata = df.drop(columns=["Workflow"]) if df.shape[1] > 1 else None

        if not 1 <= len(workflows) <= 25:
            st.warning("⚠️ Please upload between 1 and 25 workflows.")
        else:
            st.success(f"✅ {len(workflows)} workflow(s) detected.")
            st.dataframe(df)

            if st.button("🚀 Run Round"):
                with st.spinner("🔁 Mapper: Assigning SOCs..."):
                    joined_workflows = "\n".join([f"{i+1}. {w}" for i, w in enumerate(workflows)])
                    mapper_prompt = (
                        f"You are the Mapper Assistant. Given the following workflows:\n{joined_workflows}\n\n"
                        "Please return a single Markdown-formatted block with:\n"
                        "- SOC Code\n- Job Title\n- CT Workers\n- % on Workflow\n- CT FTEs\n- Time Distribution\n"
                        "- Tenure Bands (<3 yrs, 4–9 yrs, 10+ yrs)\n- Routine/Non-Routine\n- Cognitive/Manual\n\n"
                        "Follow all rules in Mapper_v3_Instructions.txt. Output only the table."
                    )
                    mapper_response = run_assistant(MAPPER_ID, mapper_prompt)
                    mapper_structured = extract_code_block(mapper_response)

                with st.spinner("📊 Analyzer: Assessing AI impact..."):
                    analyzer_prompt = (
                        f"You are the Analyzer Assistant. Please analyze the following structured SOC data:\n\n"
                        f"{mapper_structured}\n\n"
                        "Follow Analyzer_v3_Instructions.txt strictly. Return Markdown block only with assessed data."
                    )
                    analyzer_response = run_assistant(ANALYZER_ID, analyzer_prompt)
                    analyzer_structured = extract_code_block(analyzer_response)

                # Save Analyzer output to file and upload it
                with open("/tmp/analyzer_output.txt", "w") as f:
                    f.write(analyzer_structured)

                with st.spinner("📁 Uploading to OpenAI file store..."):
                    upload = openai.files.create(file=open("/tmp/analyzer_output.txt", "rb"), purpose="assistants")
                    uploaded_file_id = upload.id

                with st.spinner("📈 Comparor: Generating insights..."):
                    comparor_prompt = (
                        "You are the Comparor Assistant. Use the uploaded file containing the Analyzer SOC output. "
                        "Follow Comparor_v2_Instructions.txt. Generate all charts and slides as described. "
                        "Output links to downloadable Excel and PowerPoint files."
                    )
                    comparor_response = run_assistant(COMPAROR_ID, comparor_prompt, file_ids=[uploaded_file_id])

                st.success("🎉 Round complete!")
                st.markdown("#### 📄 Comparor Response")
                st.text_area("Comparor Output", comparor_response[:3000], height=300)
