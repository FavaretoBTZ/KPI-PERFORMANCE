import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")
st.title("KPI VITAIS - Análise Dinâmica")

uploaded_file = st.file_uploader("Escolha a planilha (.xlsx):", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, header=0)
    df = df.dropna(axis=1, how='all')

    # Verifica se colunas essenciais existem
    col_necessarias = ['CarAlias', 'SessionDate', 'Run', 'TrackName', 'SessionName', 'Lap']
    if not all(c in df.columns for c in col_necessarias):
        st.error("❌ Planilha não contém as colunas obrigatórias:\n" + ", ".join(col_necessarias))
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

        # Detectar colunas numéricas (métricas)
        col_excluir = col_necessarias + ['SessionLapDate']
        metricas = df.select_dtypes(include='number').columns.difference(col_excluir).tolist()

        y1 = st.sidebar.selectbox("Métrica para Gráfico 1:", metricas)
        y2 = st.sidebar.selectbox("Métrica para Gráfico 2:", metricas)

        df_filtrado = df[df['CarAlias'] == car_alias]
        if selected_track != "TODAS":
            df_filtrado = df_filtrado[df_filtrado['TrackName'] == selected_track]

        df_filtrado = df_filtrado.sort_values(by=['SessionDate', 'Run', 'Lap'])

        for y, titulo in zip([y1, y2], ["Gráfico 1", "Gráfico 2"]):
            fig = px.line(df_filtrado, x='SessionLapDate', y=y, color='TrackName', markers=True, title=titulo)
            fig.update_layout(title_font=dict(size=40, color="white"), height=600)
            st.plotly_chart(fig, use_container_width=True)
            with st.expander(f"Estatísticas de {y}"):
                st.metric("Mínimo", round(df_filtrado[y].min(), 2))
                st.metric("Máximo", round(df_filtrado[y].max(), 2))
                st.metric("Média", round(df_filtrado[y].mean(), 2))

        st.sidebar.header("Dispersão")
        x = st.sidebar.selectbox("Métrica X:", metricas)
        y = st.sidebar.selectbox("Métrica Y:", metricas)
        show_trend = st.sidebar.checkbox("Mostrar linha de tendência")

        fig3 = px.scatter(df, x=x, y=y, color='TrackName',
                          trendline="ols" if show_trend else None,
                          hover_data=['SessionName', 'Lap', 'Run'], title="Dispersão")
        fig3.update_layout(title_font=dict(size=40, color="white"), height=600)
        st.plotly_chart(fig3, use_container_width=True)

else:
    st.info("Envie uma planilha .xlsx para iniciar a análise.")
