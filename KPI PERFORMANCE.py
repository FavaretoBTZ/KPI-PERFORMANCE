import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")
st.title("KPI VITAIS - Análise Dinâmica")

uploaded_file = st.file_uploader("Escolha a planilha (.xlsx):", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name=0, header=1)
    df = df.dropna(axis=1, how='all')  # remove colunas totalmente vazias

    # Certifique-se de que essas colunas existem na planilha
    required_cols = ['CarAlias', 'SessionDate', 'Run', 'TrackName', 'SessionName', 'Lap']
    if not all(col in df.columns for col in required_cols):
        st.error("A planilha precisa conter as colunas obrigatórias: " + ", ".join(required_cols))
    else:
        df['SessionLapDate'] = (
            df['SessionDate'].astype(str) +
            ' | Run ' + df['Run'].astype(str) +
            ' | Lap ' + df['Lap'].astype(str) +
            ' | ' + df['SessionName'].astype(str) +
            ' | Track ' + df['TrackName'].astype(str)
        )

        st.sidebar.header("Filtros Line Plot")
        car_alias = st.sidebar.selectbox("CarAlias:", df['CarAlias'].unique())
        tracks = ["TODAS"] + sorted(df['TrackName'].dropna().unique())
        selected_track = st.sidebar.selectbox("Etapa (TrackName):", tracks)

        # Detectar colunas numéricas automaticamente, exceto as não úteis
        excluded = required_cols + ['SessionLapDate']
        numeric_cols = df.select_dtypes(include='number').columns.difference(excluded).tolist()

        y1 = st.sidebar.selectbox("Métrica para Gráfico 1:", numeric_cols)
        y2 = st.sidebar.selectbox("Métrica para Gráfico 2:", numeric_cols)

        filtered = df[df['CarAlias'] == car_alias]
        if selected_track != "TODAS":
            filtered = filtered[filtered['TrackName'] == selected_track]

        filtered = filtered.sort_values(by=['SessionDate', 'Run', 'Lap'])

        for y, title in zip([y1, y2], ["Gráfico 1", "Gráfico 2"]):
            fig = px.line(filtered, x='SessionLapDate', y=y, color='TrackName', markers=True, title=title)
            fig.update_layout(title_font=dict(size=40, color="white"), height=600)
            st.plotly_chart(fig, use_container_width=True)
            with st.expander(f"Estatísticas de {y}"):
                st.metric("Mínimo", round(filtered[y].min(), 2))
                st.metric("Máximo", round(filtered[y].max(), 2))
                st.metric("Média", round(filtered[y].mean(), 2))

        st.sidebar.header("Dispersão")
        x_metric = st.sidebar.selectbox("Métrica X:", numeric_cols)
        y_metric = st.sidebar.selectbox("Métrica Y:", numeric_cols)
        show_trend = st.sidebar.checkbox("Mostrar linha de tendência")

        fig3 = px.scatter(
            df, x=x_metric, y=y_metric, color='TrackName',
            trendline="ols" if show_trend else None,
            hover_data=['SessionName', 'Lap', 'Run'], title="Dispersão"
        )
        fig3.update_layout(title_font=dict(size=40, color="white"), height=600)
        st.plotly_chart(fig3, use_container_width=True)

else:
    st.info("Envie uma planilha .xlsx para iniciar a análise.")
