import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")
st.title("KPI VITAIS - Análise Dinâmica")

uploaded_file = st.file_uploader("Escolha a planilha adaptada (CSV):", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

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
    metrics = [col for col in df.columns if "Metric_" in col]
    y1 = st.sidebar.selectbox("Métrica para Gráfico 1:", metrics)
    y2 = st.sidebar.selectbox("Métrica para Gráfico 2:", metrics)

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

    # Gráfico de Dispersão
    st.sidebar.header("Dispersão")
    x_metric = st.sidebar.selectbox("Métrica X:", metrics)
    y_metric = st.sidebar.selectbox("Métrica Y:", metrics)
    show_trend = st.sidebar.checkbox("Mostrar linha de tendência")

    fig3 = px.scatter(
        df, x=x_metric, y=y_metric, color='TrackName',
        trendline="ols" if show_trend else None,
        hover_data=['SessionName', 'Lap', 'Run'], title="Dispersão"
    )
    fig3.update_layout(title_font=dict(size=40, color="white"), height=600)
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Envie o arquivo CSV gerado para iniciar a análise.")
