import streamlit as st
import pandas as pd

st.set_page_config(page_title="CT AI Impact Analyzer", layout="centered")

st.title("CT AI Impact Analyzer")
st.markdown("Upload a structured Excel export from Comparor to analyze workforce AI impact.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file is not None:
    st.success("File uploaded. Future: This will trigger backend Comparor GPT analysis.")
    
    try:
        df = pd.read_excel(uploaded_file)
        st.dataframe(df.head())
        st.info("Analysis module is under construction.")
    except Exception as e:
        st.error(f"Failed to read Excel file: {e}")
else:
    st.info("Please upload a valid Excel file (.xlsx) to begin.")
