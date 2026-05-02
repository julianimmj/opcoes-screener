"""
Screener de Opções Baratas — B3
Identifica opções subvalorizadas comparando volatilidade implícita vs histórica.
Powered by Black-Scholes pricing.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np
import time

from tickers_opcoes import TICKERS_COM_OPCOES, NOMES_ATIVOS
from black_scholes import (
    calcular_vol_historica, obter_preco_atual, black_scholes_price,
    calcular_vol_implicita, SELIC_RATE, tempo_em_anos
)
from options_data import buscar_opcoes_completas

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Screener de Opções B3 — Vol. Implícita vs Histórica",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .main-header h1 {
        color: #fff;
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #00d2ff 0%, #7b2ff7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .main-header p {
        color: rgba(255,255,255,0.7);
        font-size: 0.95rem;
        margin: 0.5rem 0 0 0;
        font-weight: 300;
    }

    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, rgba(30,30,60,0.9) 0%, rgba(20,20,50,0.95) 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 24px rgba(123,47,247,0.15);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00d2ff, #7b2ff7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .metric-label {
        font-size: 0.85rem;
        color: rgba(255,255,255,0.55);
        margin-top: 0.3rem;
        font-weight: 400;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Results table styling */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29 0%, #1a1a3e 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #00d2ff;
    }

    /* Info cards */
    .info-card {
        background: rgba(30,30,60,0.6);
        border: 1px solid rgba(123,47,247,0.2);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        backdrop-filter: blur(8px);
    }
    .info-card .ticker-name {
        font-size: 1.1rem;
        font-weight: 600;
        color: #00d2ff;
    }
    .info-card .ticker-price {
        font-size: 0.9rem;
        color: rgba(255,255,255,0.7);
    }
    .info-card .ticker-vol {
        font-size: 0.85rem;
        color: rgba(255,255,255,0.5);
    }

    /* Badge */
    .badge-oportunidade {
        display: inline-block;
        background: linear-gradient(135deg, #00b09b, #96c93d);
        color: #fff;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: rgba(255,255,255,0.3);
        font-size: 0.75rem;
        margin-top: 3rem;
        padding: 1rem;
        border-top: 1px solid rgba(255,255,255,0.05);
    }

    /* Streamlit overrides */
    .stButton > button {
        background: linear-gradient(135deg, #7b2ff7 0%, #00d2ff 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 2rem;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 16px rgba(123,47,247,0.3);
    }

    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #7b2ff7, #00d2ff);
    }

    /* Streamlit branding — gerenciado pelo bloco hide_streamlit_style */

    /* Disclaimer */
    .disclaimer {
        background: rgba(255,165,0,0.1);
        border: 1px solid rgba(255,165,0,0.2);
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.8rem;
        color: rgba(255,255,255,0.6);
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def render_header():
    """Renderiza o cabeçalho premium do app."""
    st.markdown("""
    <div class="main-header">
        <h1>📊 Screener de Opções Baratas — B3</h1>
        <p>
            Identifica opções subvalorizadas onde a volatilidade implícita está
            significativamente abaixo da volatilidade histórica de 60 dias.
            Precificação via modelo Black-Scholes.
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_metric_cards(total, maior_desconto, media_diff_vol, ticker_top):
    """Renderiza os cards de métricas no topo."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total}</div>
            <div class="metric-label">Opções encontradas</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{maior_desconto:.1f}%</div>
            <div class="metric-label">Maior desconto</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{abs(media_diff_vol):.1f}pp</div>
            <div class="metric-label">Média diff vol.</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{ticker_top}</div>
            <div class="metric-label">Melhor oportunidade</div>
        </div>
        """, unsafe_allow_html=True)


def create_vol_comparison_chart(df: pd.DataFrame) -> go.Figure:
    """Cria gráfico comparando vol implícita vs vol histórica."""
    fig = go.Figure()

    # Barra de vol implícita
    fig.add_trace(go.Bar(
        x=df["ticker_opcao"],
        y=df["vol_implicita"],
        name="Vol. Implícita",
        marker_color="rgba(123, 47, 247, 0.8)",
        marker_line_color="rgba(123, 47, 247, 1)",
        marker_line_width=1,
    ))

    # Barra de vol histórica
    fig.add_trace(go.Bar(
        x=df["ticker_opcao"],
        y=df["vol_historica_60d"],
        name="Vol. Histórica 60d",
        marker_color="rgba(0, 210, 255, 0.8)",
        marker_line_color="rgba(0, 210, 255, 1)",
        marker_line_width=1,
    ))

    fig.update_layout(
        title=dict(
            text="Volatilidade Implícita vs Histórica (60 dias)",
            font=dict(size=16, color="white"),
        ),
        barmode="group",
        paper_bgcolor="rgba(15,12,41,0.8)",
        plot_bgcolor="rgba(15,12,41,0.5)",
        font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
        xaxis=dict(
            tickangle=-45,
            gridcolor="rgba(255,255,255,0.05)",
            title="Opção",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            title="Volatilidade (%)",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0.3)",
            bordercolor="rgba(255,255,255,0.1)",
            font=dict(size=11),
        ),
        margin=dict(l=60, r=20, t=60, b=100),
        height=450,
    )

    return fig


def create_discount_chart(df: pd.DataFrame) -> go.Figure:
    """Cria gráfico de barras mostrando o desconto de cada opção."""
    colors = ["#00b09b" if d > 0 else "#ff4757" for d in df["desconto_pct"]]

    fig = go.Figure(go.Bar(
        x=df["ticker_opcao"],
        y=df["desconto_pct"],
        marker_color=colors,
        marker_line_width=0,
        text=[f"{d:+.1f}%" for d in df["desconto_pct"]],
        textposition="outside",
        textfont=dict(size=10, color="rgba(255,255,255,0.7)"),
    ))

    fig.update_layout(
        title=dict(
            text="Desconto da Opção (Preço Justo vs Mercado)",
            font=dict(size=16, color="white"),
        ),
        paper_bgcolor="rgba(15,12,41,0.8)",
        plot_bgcolor="rgba(15,12,41,0.5)",
        font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
        xaxis=dict(
            tickangle=-45,
            gridcolor="rgba(255,255,255,0.05)",
            title="Opção",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            title="Desconto (%)",
        ),
        margin=dict(l=60, r=20, t=60, b=100),
        height=400,
    )

    return fig


def processar_ticker(ticker: str, dias_min: int, dias_max: int,
                      diff_vol_min: float, progress_callback=None) -> pd.DataFrame:
    """
    Processa um ticker: busca opções, calcula vol histórica e filtra.

    Returns:
        DataFrame com opções que atendem aos critérios.
    """
    # 1. Obtém preço atual
    preco_atual = obter_preco_atual(ticker)
    if not preco_atual:
        return pd.DataFrame()

    # 2. Calcula volatilidade histórica 60d
    vol_hist = calcular_vol_historica(ticker, dias=60)
    if not vol_hist:
        return pd.DataFrame()

    # 3. Busca opções do opcoes.net.br
    opcoes_df = buscar_opcoes_completas(ticker, dias_min, dias_max)

    # 4. Verifica se a raspagem retornou dados
    if opcoes_df.empty:
        st.toast(f"⚠️ Não foi possível extrair dados da B3 para {ticker}.")
        return pd.DataFrame()

    # 5. Se os dados vieram do scraping, precisamos calcular B-S
    if "preco_justo_bs" not in opcoes_df.columns:
        resultados = []
        for _, row in opcoes_df.iterrows():
            T = tempo_em_anos(int(row.get("dias_ate_venc", 50) * 0.7))
            if T <= 0:
                continue

            tipo = row.get("tipo", "CALL").lower()
            K = row.get("strike", 0)
            preco_mkt = row.get("ultimo", 0)

            if K <= 0 or preco_mkt <= 0:
                continue

            preco_justo = black_scholes_price(
                preco_atual, K, T, SELIC_RATE, vol_hist, tipo
            )
            iv = row.get("vol_implicita")
            if iv is None or iv <= 0:
                iv_calc = calcular_vol_implicita(
                    preco_mkt, preco_atual, K, T, SELIC_RATE, tipo
                )
                iv = iv_calc * 100 if iv_calc else None

            if iv is None:
                continue

            diff = iv - (vol_hist * 100)
            desconto = ((preco_justo - preco_mkt) / preco_mkt * 100
                        if preco_mkt > 0 else 0)

            resultados.append({
                "ticker_opcao": row.get("ticker_opcao", ""),
                "ticker_base": ticker,
                "tipo": row.get("tipo", "").upper(),
                "strike": K,
                "preco_atual_base": round(preco_atual, 2),
                "vencimento": row.get("vencimento", ""),
                "dias_ate_venc": row.get("dias_ate_venc", 0),
                "preco_mercado": round(preco_mkt, 2),
                "preco_justo_bs": round(preco_justo, 2),
                "vol_implicita": round(iv, 2),
                "vol_historica_60d": round(vol_hist * 100, 2),
                "diff_vol": round(diff, 2),
                "desconto_pct": round(desconto, 2),
            })

        opcoes_df = pd.DataFrame(resultados)

    if opcoes_df.empty:
        return pd.DataFrame()

    # 6. Filtra: vol implícita pelo menos X pp abaixo da vol histórica
    # diff_vol negativo = IV < HV = opção potencialmente barata
    filtrada = opcoes_df[opcoes_df["diff_vol"] <= -diff_vol_min].copy()

    # Ordena por maior desconto
    if not filtrada.empty:
        filtrada = filtrada.sort_values("desconto_pct", ascending=False)

    return filtrada


def main():
    """Função principal do app."""
    render_header()

    # ─── Sidebar ───────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Configurações")

        st.markdown("---")
        st.markdown("### 🎯 Seleção de Ativos")

        # Modo de seleção
        modo = st.radio(
            "Modo de seleção",
            ["Lista pré-definida", "Digitar manualmente"],
            index=0,
            label_visibility="collapsed",
        )

        if modo == "Lista pré-definida":
            opcoes_display = [
                f"{t} — {NOMES_ATIVOS.get(t, '')}" for t in TICKERS_COM_OPCOES
            ]
            selecionados_display = st.multiselect(
                "Selecione os ativos",
                opcoes_display,
                default=[opcoes_display[0], opcoes_display[1]],  # PETR4, VALE3
                help="Escolha um ou mais ativos para analisar",
            )
            tickers = [s.split(" — ")[0] for s in selecionados_display]
        else:
            ticker_input = st.text_input(
                "Digite o(s) ticker(s)",
                value="PETR4, VALE3",
                help="Separe múltiplos tickers por vírgula",
            )
            tickers = [t.strip().upper() for t in ticker_input.split(",")
                        if t.strip()]

        st.markdown("---")
        st.markdown("### 📅 Vencimento")

        col_min, col_max = st.columns(2)
        with col_min:
            dias_min = st.number_input("Dias mín.", value=45, min_value=1,
                                        max_value=365, step=5)
        with col_max:
            dias_max = st.number_input("Dias máx.", value=70, min_value=1,
                                        max_value=365, step=5)

        st.markdown("---")
        st.markdown("### 📉 Filtro de Volatilidade")

        diff_vol_min = st.slider(
            "Diferença mínima IV < HV (pp)",
            min_value=1, max_value=30, value=8, step=1,
            help="Mostra opções onde a vol. implícita está "
                 "pelo menos X pontos percentuais abaixo da vol. histórica",
        )

        st.markdown("---")

        escanear = st.button("🔍 Escanear Opções", use_container_width=True,
                              type="primary")

        st.markdown("""
        <div class="disclaimer">
            ⚠️ <strong>Aviso:</strong> Este screener é uma ferramenta educacional.
            Dados de opções baseados em fechamento do pregão anterior.
            Não constitui recomendação de investimento.
        </div>
        """, unsafe_allow_html=True)

    # ─── Main Content ──────────────────────────────────────────────────────
    if escanear and tickers:
        resultados_total = []

        progress_bar = st.progress(0, text="Iniciando análise...")

        for idx, ticker in enumerate(tickers):
            progress_pct = (idx) / len(tickers)
            progress_bar.progress(
                progress_pct,
                text=f"Analisando {ticker}... ({idx+1}/{len(tickers)})"
            )

            with st.spinner(f"Processando {ticker}..."):
                df = processar_ticker(ticker, dias_min, dias_max, diff_vol_min)
                if not df.empty:
                    resultados_total.append(df)

            time.sleep(0.3)  # Rate limiting

        progress_bar.progress(1.0, text="✅ Análise concluída!")
        time.sleep(0.5)
        progress_bar.empty()

        if resultados_total:
            df_final = pd.concat(resultados_total, ignore_index=True)
            df_final = df_final.sort_values("desconto_pct", ascending=False)

            # ─── Métricas ──────────────────────────────────────────────
            total = len(df_final)
            maior_desconto = df_final["desconto_pct"].max()
            media_diff = df_final["diff_vol"].mean()
            ticker_top = df_final.iloc[0]["ticker_opcao"] if total > 0 else "—"

            render_metric_cards(total, maior_desconto, media_diff, ticker_top)

            st.markdown("<br>", unsafe_allow_html=True)

            # ─── Gráficos ─────────────────────────────────────────────
            tab_chart, tab_table = st.tabs([
                "📊 Gráficos", "📋 Tabela Detalhada"
            ])

            with tab_chart:
                # Limita a 20 opções para visualização
                df_chart = df_final.head(20)

                fig_vol = create_vol_comparison_chart(df_chart)
                st.plotly_chart(fig_vol, use_container_width=True)

                st.markdown("<br>", unsafe_allow_html=True)

                fig_disc = create_discount_chart(df_chart)
                st.plotly_chart(fig_disc, use_container_width=True)

                # Scatter plot: IV vs HV
                fig_scatter = go.Figure()
                fig_scatter.add_trace(go.Scatter(
                    x=df_final["vol_historica_60d"],
                    y=df_final["vol_implicita"],
                    mode="markers+text",
                    marker=dict(
                        size=10,
                        color=df_final["desconto_pct"],
                        colorscale="Viridis",
                        showscale=True,
                        colorbar=dict(title="Desconto %"),
                    ),
                    text=df_final["ticker_opcao"],
                    textposition="top center",
                    textfont=dict(size=8, color="rgba(255,255,255,0.6)"),
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Vol. Histórica: %{x:.1f}%<br>"
                        "Vol. Implícita: %{y:.1f}%<br>"
                        "Desconto: %{marker.color:.1f}%<extra></extra>"
                    ),
                ))

                # Linha de referência (IV = HV)
                max_val = max(
                    df_final["vol_historica_60d"].max(),
                    df_final["vol_implicita"].max()
                ) * 1.1
                fig_scatter.add_trace(go.Scatter(
                    x=[0, max_val], y=[0, max_val],
                    mode="lines",
                    line=dict(color="rgba(255,255,255,0.2)", dash="dash"),
                    name="IV = HV",
                    hoverinfo="skip",
                ))

                fig_scatter.update_layout(
                    title=dict(
                        text="Vol. Implícita vs Vol. Histórica — Opções abaixo da linha estão subvalorizadas",
                        font=dict(size=14, color="white"),
                    ),
                    paper_bgcolor="rgba(15,12,41,0.8)",
                    plot_bgcolor="rgba(15,12,41,0.5)",
                    font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
                    xaxis=dict(
                        title="Vol. Histórica 60d (%)",
                        gridcolor="rgba(255,255,255,0.05)",
                    ),
                    yaxis=dict(
                        title="Vol. Implícita (%)",
                        gridcolor="rgba(255,255,255,0.05)",
                    ),
                    showlegend=False,
                    height=500,
                )

                st.plotly_chart(fig_scatter, use_container_width=True)

            with tab_table:
                # ─── Tabela ────────────────────────────────────────────
                st.markdown("### 📋 Opções Subvalorizadas")
                st.markdown(
                    f"*Filtro: Vol. Implícita pelo menos **{diff_vol_min}pp** "
                    f"abaixo da Vol. Histórica de 60 dias*"
                )

                df_display = df_final[[
                    "ticker_opcao", "ticker_base", "vencimento", "strike", "preco_atual_base",
                    "tipo", "preco_mercado", "preco_justo_bs", "vol_implicita",
                    "vol_historica_60d", "diff_vol", "desconto_pct"
                ]].copy()

                df_display.columns = [
                    "Opção", "Ativo", "Vencimento", "Strike", "Preço Ativo",
                    "Tipo", "Preço Mercado", "Preço Justo (Black-Scholes)",
                    "Vol. Impl. (%)", "Vol. Hist. 60d (%)",
                    "Diff Vol (pp)", "Desconto (%)"
                ]

                st.dataframe(
                    df_display.style
                    .format({
                        "Strike": "R$ {:.2f}",
                        "Preço Ativo": "R$ {:.2f}",
                        "Preço Mercado": "R$ {:.2f}",
                        "Preço Justo (Black-Scholes)": "R$ {:.2f}",
                        "Vol. Impl. (%)": "{:.1f}%",
                        "Vol. Hist. 60d (%)": "{:.1f}%",
                        "Diff Vol (pp)": "{:+.1f}",
                        "Desconto (%)": "{:+.1f}%",
                    })
                    .background_gradient(
                        subset=["Desconto (%)"],
                        cmap="RdYlGn",
                        vmin=-50, vmax=100,
                    ),
                    use_container_width=True,
                    height=500,
                )

                # Download CSV
                csv = df_display.to_csv(index=False, sep=";", decimal=",")
                st.download_button(
                    "📥 Baixar CSV",
                    csv,
                    f"opcoes_baratas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv",
                    use_container_width=True,
                )

        else:
            st.warning(
                "⚠️ Nenhuma opção encontrada com os critérios selecionados. "
                "Tente ajustar os filtros (reduzir a diferença mínima de "
                "volatilidade ou ampliar a faixa de vencimento)."
            )

    elif not escanear:
        # Estado inicial — mostra instruções
        st.markdown("""
        <div style="text-align: center; padding: 4rem 2rem;">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🔍</div>
            <h2 style="color: rgba(255,255,255,0.8); font-weight: 600;">
                Selecione os ativos e clique em "Escanear"
            </h2>
            <p style="color: rgba(255,255,255,0.4); max-width: 600px; margin: 1rem auto;">
                Este screener analisa opções da B3, calcula a volatilidade histórica
                de 60 dias e compara com a volatilidade implícita do mercado para
                encontrar opções potencialmente baratas usando o modelo Black-Scholes.
            </p>
            <div style="display: flex; justify-content: center; gap: 2rem;
                        margin-top: 2rem; flex-wrap: wrap;">
                <div style="background: rgba(30,30,60,0.6); border: 1px solid
                            rgba(123,47,247,0.2); border-radius: 12px;
                            padding: 1.5rem; width: 200px;">
                    <div style="font-size: 1.5rem;">📈</div>
                    <div style="color: #00d2ff; font-weight: 600;
                                margin-top: 0.5rem;">Vol. Histórica</div>
                    <div style="color: rgba(255,255,255,0.4); font-size: 0.8rem;
                                margin-top: 0.3rem;">
                        Calculada com 60 dias de dados
                    </div>
                </div>
                <div style="background: rgba(30,30,60,0.6); border: 1px solid
                            rgba(123,47,247,0.2); border-radius: 12px;
                            padding: 1.5rem; width: 200px;">
                    <div style="font-size: 1.5rem;">⚖️</div>
                    <div style="color: #7b2ff7; font-weight: 600;
                                margin-top: 0.5rem;">Black-Scholes</div>
                    <div style="color: rgba(255,255,255,0.4); font-size: 0.8rem;
                                margin-top: 0.3rem;">
                        Preço justo teórico
                    </div>
                </div>
                <div style="background: rgba(30,30,60,0.6); border: 1px solid
                            rgba(123,47,247,0.2); border-radius: 12px;
                            padding: 1.5rem; width: 200px;">
                    <div style="font-size: 1.5rem;">💎</div>
                    <div style="color: #96c93d; font-weight: 600;
                                margin-top: 0.5rem;">Oportunidades</div>
                    <div style="color: rgba(255,255,255,0.4); font-size: 0.8rem;
                                margin-top: 0.3rem;">
                        IV {'<'} HV em ≥8pp
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ─── Footer ────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="footer">
        Screener de Opções B3 — Dados de fechamento (opcoes.net.br / yfinance) •
        Modelo Black-Scholes • Desenvolvido com Streamlit<br>
        <strong>Aviso:</strong> Ferramenta educacional. Não constitui recomendação
        de investimento. Verifique sempre os dados com sua corretora.
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
