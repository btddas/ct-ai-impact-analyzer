import streamlit as st
import pandas as pd
import openai
import time

# Load your OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs from GitHub-synced logic
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

st.set_page_config(page_title="CT AI Impact Analyzer – Round Runner", layout="centered")

st.title("🧠 Round Runner – Multi-Workflow (Excel Upload)")
st.write("Upload an Excel file with 1–25 workflows to analyze AI impact across roles in Connecticut.")

uploaded_file = st.file_uploader("📤 Upload your `.xlsx` file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    if "Workflow" not in df.columns:
        st.error("❌ The Excel file must include a column labeled 'Workflow'.")
    else:
        workflows = df["Workflow"].dropna().astype(str).tolist()
        metadata_columns = [col for col in df.columns if col != "Workflow"]

        if not 1 <= len(workflows) <= 25:
            st.warning("⚠️ Please upload between 1 and 25 workflows.")
        else:
            st.success(f"✅ {len(workflows)} workflow(s) detected.")
            st.dataframe(df)

            if st.button("🚀 Run Round"):
                with st.spinner("Running Mapper..."):
                    mapper_output = openai.beta.assistants.run(
                        assistant_id=MAPPER_ID,
                        instructions="Run with uploaded metadata-aware workflows.",
                        input={"workflows": workflows, "metadata": df.to_dict("records")}
                    )
                    time.sleep(1)

                with st.spinner("Running Analyzer..."):
                    analyzer_output = openai.beta.assistants.run(
                        assistant_id=ANALYZER_ID,
                        instructions="Analyze all Mapper outputs for Round 12.",
                        input={"mapper_data": mapper_output}
                    )
                    time.sleep(1)

                with st.spinner("Running Comparor..."):
                    comparor_output = openai.beta.assistants.run(
                        assistant_id=COMPAROR_ID,
                        instructions="Generate PPT and Excel outputs aggregating all workflows.",
                        input={"analyzer_data": analyzer_output}
                    )
                    time.sleep(2)

                excel_url = comparor_output["excel_url"]
                ppt_url = comparor_output["ppt_url"]

                st.success("🎉 Round complete!")
                st.download_button("⬇️ Download Excel", excel_url, file_name="Round_Results.xlsx")
                st.download_button("⬇️ Download PowerPoint", ppt_url, file_name="Round_Slides.pptx")
