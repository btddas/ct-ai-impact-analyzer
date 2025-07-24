
import streamlit as st

st.set_page_config(page_title="CT AI Impact Analyzer", layout="wide")

st.title("CT AI Impact Analyzer")
st.write("Upload a structured Excel export from Comparor to analyze workforce AI impact.")
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    st.success("File uploaded. Future: This will trigger backend Comparor GPT analysis.")
    # Placeholder for future analysis
    st.info("Analysis module is under construction.")
else:
    st.info("Please upload a valid Excel file (.xlsx) to begin.")
