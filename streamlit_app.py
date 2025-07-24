import streamlit as st
import openai
import os
import time
import base64
from io import BytesIO
import pandas as pd

# Set OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Assistant IDs
MAPPER_ID = "asst_ICb5UuKQmufzyx2lRaEE1CBA"
ANALYZER_ID = "asst_cRFnnCxMFqwhoVgFpiemOgIY"
COMPAROR_ID = "asst_RXgfmnQ2wHxIcFwtSiUYSbKR"

st.set_page_config(page_title="CT AI Impact Analyzer", layout="centered")
st.title("CT AI Impact Analyzer")
st.write("Upload a structured Excel or CSV export from Comparor to analyze workforce AI impact.")

uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["xlsx", "csv"])

# Retry-safe assistant runner with verbose logging
def run_single_assistant(assistant_id, user_prompt, file_id, max_retries=5):
    client = openai.OpenAI()
    name = assistant_id.split("_")[1]

    thread = client.beta.threads.create()
    st.write(f"🧵 `{name}` thread ID: `{thread.id}`")

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_prompt,
        attachments=[{"file_id": file_id, "tools": [{"type": "file_search"}]}]
    )

    for attempt in range(max_retries):
        try:
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant_id
            )
            st.write(f"▶️ `{name}` run ID: `{run.id}`")

            while True:
                run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

                if run_status.status == "completed":
                    st.success(f"✅ `{name}` completed.")
                    break

                elif run_status.status == "failed":
                    st.error(f"❌ `{name}` run failed.")

                    # DEBUG: Show assistant's reply before raising error
                    messages = client.beta.threads.messages.list(thread_id=thread.id)
                    st.write(f"📨 `{name}` last message contents:")
                    for msg in messages.data:
                        st.json(msg.dict())

                    raise RuntimeError(f"❌ `{name}` run failed.")

                # Sleep only if still queued/in_progress
                time.sleep(2)


            # Log all messages
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data[::-1]:
                st.write(f"🗨️ **Message from `{msg.role}`**")
                st.json(msg.dict(), expanded=False)

            return messages

        except openai.RateLimitError:
            wait_seconds = 10 * (attempt + 1)
            st.warning(f"⚠️ Rate limit hit. Retrying in {wait_seconds} seconds... (Attempt {attempt+1}/{max_retries})")
            time.sleep(wait_seconds)

    raise RuntimeError(f"❌ `{name}` run failed after {max_retries} retries.")
# Main processing pipeline
# Main processing pipeline
def run_pipeline(file, ext):
    client = openai.OpenAI()
    st.write("📤 Converting and splitting Excel...")

    # Load and chunk spreadsheet
    if ext == "xlsx":
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)

    chunk_size = 1  # Use 1 for now to stay under token limits
    chunks = [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]
    output_dfs = []

    for i, chunk in enumerate(chunks):
        st.write(f"🔹 Running Mapper on batch {i+1}/{len(chunks)}")

        txt = chunk.to_csv(index=False)
        txt_file = BytesIO(txt.encode("utf-8"))
        txt_file.name = f"mapper_input_batch_{i+1}.txt"

        openai_file = client.files.create(file=txt_file, purpose="assistants")

        messages = run_single_assistant(
            MAPPER_ID,
            """Please act as the Mapper: analyze the uploaded Comparor export and identify SOC roles and their CT FTE allocations.
Output your results in a downloadable CSV file named `mapper_output.csv`.

For each workflow in the uploaded file, output a table with the following columns:
- SOC Code
- SOC Title
- % of SOCs Participating in Workflow
- % of Participating SOC’s Time Spent on this Workflow
- % Share of Total Workflow Time
- CT FTEs (Total for that SOC)
- CT FTEs Assigned to this Workflow
- EZ Zone
- Cognitive/Manual
- Routine/Non-routine

Use the code_interpreter tool to:
1. Create the output as a pandas DataFrame
2. Write the DataFrame to a CSV file named `mapper_output.csv`
3. Ensure the file is returned by ending your run with: `return {"file_path": "mapper_output.csv"}`

Do not emit results only as Markdown or plain text — the output must be saved and uploaded as a file so downstream steps in this pipeline can access it.""",
            openai_file.id
        )

        found_file = False
        for msg in messages.data:
            for file_id in getattr(msg, "file_ids", []):
                try:
                    file_bytes = client.files.retrieve_content(file_id)
                    df_part = pd.read_csv(BytesIO(file_bytes))
                    output_dfs.append(df_part)
                    found_file = True
                except Exception as e:
                    st.error(f"⚠️ Failed to read returned file `{file_id}`: {e}")

        if not found_file:
            st.warning(f"⚠️ No output file returned for batch {i+1}")

    if not output_dfs:
        st.error("❌ No Mapper output collected from any batch.")
        return []

    combined_df = pd.concat(output_dfs, ignore_index=True)
    combined_csv = BytesIO(combined_df.to_csv(index=False).encode())
    combined_csv.name = "mapper_output.csv"

    openai_file = client.files.create(file=combined_csv, purpose="assistants")
    st.success("✅ Combined Mapper output ready.")

    output_files = []

    assistant_steps = [
        (
            ANALYZER_ID,
            "Please act as the Analyzer: use the output of the Mapper to assess AI impact, risk level, and generate Excel results."
        ),
        (
            COMPAROR_ID,
            "Please act as the Comparor: compare across workflows and produce summary insights and PowerPoint output."
        )
    ]

    for assistant_id, prompt in assistant_steps:
        try:
            st.write(f"▶️ Running `{assistant_id}`...")
            messages = run_single_assistant(assistant_id, prompt, openai_file.id)
            found_files = False
            for msg in messages.data:
                for file_id in getattr(msg, "file_ids", []):
                    try:
                        file_bytes = client.files.retrieve_content(file_id)
                        output_files.append((file_id, file_bytes))
                        found_files = True
                    except Exception as e:
                        st.error(f"⚠️ Failed to retrieve file `{file_id}`: {e}")
            if not found_files:
                st.warning(f"⚠️ No output files returned by `{assistant_id.split('_')[1]}`.")
        except Exception as e:
            st.error(f"❌ Error running `{assistant_id}`: {e}")

    return output_files

# Download link helper
def download_link(file_bytes, filename, label):
    b64 = base64.b64encode(file_bytes.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

# UI logic
if uploaded_file is not None:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext not in ["xlsx", "csv"]:
        st.error("❌ Only .xlsx or .csv files are supported.")
    else:
        st.success("File uploaded. Click below to run analysis.")
        if st.button("Submit"):
            with st.spinner("⏳ Running assistants in sequence..."):
                results = run_pipeline(uploaded_file, ext)

            if results:
                st.success("🎉 Analysis complete. Download your files:")
                for i, (fid, result_file) in enumerate(results):
                    ext = ".xlsx" if i == 0 else ".pptx"
                    filename = f"AI_Impact_Output_{i+1}{ext}"
                    st.markdown(download_link(BytesIO(result_file), filename, f"📥 Download {filename}"), unsafe_allow_html=True)
            else:
                st.warning("⚠️ All assistants completed, but no output files were generated.")
