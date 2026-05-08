import streamlit as st
import os
import plotly.express as px
import plotly.graph_objects as go
from utils.database import get_engine, create_tables, get_session
from utils.parser import extract_and_parse
from utils.analysis import load_data, aggregate_data, compute_correlations

st.set_page_config(page_title="Apple Health Insights", layout="wide")

st.title("🍎 Apple Health Data Analysis")

DB_PATH = 'sqlite:///health_data.db'
engine = get_engine(DB_PATH)
create_tables(engine)

def check_db_has_data():
    session = get_session(engine)
    from utils.database import HealthRecord
    try:
        count = session.query(HealthRecord).count()
        return count > 0
    except Exception:
        return False
    finally:
        session.close()

if not check_db_has_data():
    st.info("No data found in the local database. Please upload your Apple Health `export.zip`.")
    uploaded_file = st.file_uploader("Upload export.zip", type=['zip'])

    if uploaded_file is not None:
        with st.spinner("Saving uploaded file..."):
            os.makedirs("data", exist_ok=True)
            zip_path = os.path.join("data", "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

        st.success("File uploaded successfully!")

        if st.button("Process Data"):
            status_text = st.empty()
            session = get_session(engine)
            try:
                extract_and_parse(zip_path, session, status_text)
                st.success("Data successfully parsed and saved to database!")
                st.rerun()
            except Exception as e:
                st.error(f"An error occurred: {e}")
            finally:
                session.close()
else:
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Overview", "Metric Deep Dive", "Top Correlations", "Correlation Heatmap", "Settings"])

    @st.cache_data
    def load_and_prep_data():
        df = load_data(engine)
        pivot_df = aggregate_data(df)
        corr_matrix, corr_pairs = compute_correlations(pivot_df)
        return df, pivot_df, corr_matrix, corr_pairs

    with st.spinner("Loading and analyzing data..."):
        df, pivot_df, corr_matrix, corr_pairs = load_and_prep_data()

    if page == "Overview":
        st.header("Overview")
        st.write(f"Loaded **{len(df)}** records across **{len(pivot_df.columns)}** different metrics.")
        st.write(f"Data ranges from **{pivot_df.index.min().date()}** to **{pivot_df.index.max().date()}**.")

        st.subheader("Available Metrics")
        st.write(list(pivot_df.columns))

    elif page == "Metric Deep Dive":
        st.header("Metric Deep Dive")
        selected_metric = st.selectbox("Select a Metric", sorted(pivot_df.columns))

        fig = px.line(pivot_df, x=pivot_df.index, y=selected_metric, title=f"{selected_metric} Over Time")
        fig.update_xaxes(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            )
        )
        st.plotly_chart(fig, use_container_width=True)

    elif page == "Top Correlations":
        st.header("Top Hidden Insights (Zusammenhänge)")
        st.write("These are the strongest statistical correlations found in your data. A correlation close to 1 means they move together, close to -1 means they move opposite to each other.")

        # Filter out extreme self-correlations or identical sources
        filtered_pairs = corr_pairs[corr_pairs['Abs_Corr'] < 0.99]

        num_insights = st.slider("Number of insights to show", 5, 20, 10)
        top_insights = filtered_pairs.head(num_insights)

        for idx, row in top_insights.iterrows():
            m1 = row['Metric 1']
            m2 = row['Metric 2']
            corr_val = row['Correlation']

            with st.expander(f"{m1} & {m2} (Score: {corr_val:.2f})"):
                st.write(f"**Correlation:** {corr_val:.2f}")

                scatter_fig = px.scatter(
                    pivot_df,
                    x=m1,
                    y=m2,
                    trendline="ols",
                    title=f"Scatter Plot: {m1} vs {m2}",
                    hover_data=[pivot_df.index.date]
                )
                st.plotly_chart(scatter_fig, use_container_width=True)

    elif page == "Correlation Heatmap":
        st.header("Full Correlation Heatmap")

        selected_metrics = st.multiselect(
            "Select metrics to include in heatmap",
            options=sorted(pivot_df.columns),
            default=sorted(pivot_df.columns)[:15] if len(pivot_df.columns) >= 15 else sorted(pivot_df.columns)
        )

        if len(selected_metrics) > 1:
            filtered_corr = pivot_df[selected_metrics].corr(method='spearman')

            fig = px.imshow(
                filtered_corr,
                labels=dict(color="Correlation"),
                x=selected_metrics,
                y=selected_metrics,
                color_continuous_scale='RdBu_r',
                zmin=-1, zmax=1
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Please select at least 2 metrics.")

    elif page == "Settings":
        st.header("Settings")
        st.warning("Danger Zone")
        if st.button("Delete Database and Upload New Data"):
            # Properly close engine connections before attempting file deletion
            engine.dispose()
            if os.path.exists('health_data.db'):
                try:
                    os.remove('health_data.db')
                except Exception as e:
                    st.error(f"Error removing database file: {e}")
            if os.path.exists('data/upload.zip'):
                try:
                    os.remove('data/upload.zip')
                except Exception as e:
                    st.error(f"Error removing upload file: {e}")
            st.cache_data.clear()
            st.rerun()
