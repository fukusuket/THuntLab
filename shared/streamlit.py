import streamlit as st
import pandas as pd
import numpy as np

# Page title and header
st.title("Simple Streamlit Sample App")
st.header("Welcome to this demo application!")

# Sidebar
st.sidebar.title("Control Panel")
name = st.sidebar.text_input("Enter your name:", "Guest")
age = st.sidebar.slider("Select your age:", 0, 100, 25)

# Main content
st.write(f"Hello, {name}! You are {age} years old.")

# Data display
st.subheader("Sample Data")
data = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
    'Age': [25, 30, 35, 28],
    'Score': [85, 92, 78, 95]
})
st.dataframe(data)

# Chart using Streamlit's built-in charting
st.subheader("Sample Chart")
chart_data = pd.DataFrame(
    np.random.randn(20, 3),
    columns=['A', 'B', 'C']
)
st.line_chart(chart_data)

# Interactive widgets
st.subheader("Interactive Elements")
if st.button("Click me!"):
    st.success("Button clicked! 🎉")

color = st.selectbox("Choose a color:", ["Red", "Green", "Blue"])
st.write(f"You selected: {color}")

# Footer
st.markdown("---")
st.markdown("*This is a simple Streamlit application for demonstration purposes.*")