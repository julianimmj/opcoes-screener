import requests
import pandas as pd
from datetime import datetime
import streamlit as st

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://opcoes.net.br/"
}

@st.cache_data(ttl=600, show_spinner=False)
def buscar_opcoes_completas(ticker: str, dias_min: int = 45, dias_max: int = 70) -> pd.DataFrame:
    """
    Busca opções verificando o endpoint JSON oficial interno da opcoes.net.br.
    É milhares de vezes mais rápido e dribla bloqueios de navegação pesados.
    """
    dados_completos = []
    hoje = datetime.now()
    url_base = f"https://opcoes.net.br/listaopcoes/completa?idAcao={ticker.upper()}&listarVencimentos=true&cotacoes=true"

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        # 1. Busca os vencimentos disponíveis no seletor
        response = session.get(url_base, timeout=10)
        response.raise_for_status()
        data = response.json()

        if 'data' not in data or 'vencimentos' not in data['data']:
            return pd.DataFrame()

        vencimentos = data['data']['vencimentos']
        vencimentos_validos = []

        for v in vencimentos:
            data_vencimento = v.get("value")
            if not data_vencimento: continue
            
            try:
                venc_date = datetime.strptime(data_vencimento, "%Y-%m-%d")
                dias_ate_venc = (venc_date - hoje).days
                if dias_min <= dias_ate_venc <= dias_max:
                    vencimentos_validos.append((data_vencimento, dias_ate_venc))
            except ValueError:
                pass

        # 2. Busca o array gigantesco via API usando os vencimentos encontrados
        for venc_str, dias_ate_venc in vencimentos_validos:
            url_vencimento = f"https://opcoes.net.br/listaopcoes/completa?idAcao={ticker.upper()}&listarVencimentos=false&cotacoes=true&vencimentos={venc_str}"
            resp_v = session.get(url_vencimento, timeout=10)
            
            if resp_v.status_code == 200:
                json_venc = resp_v.json()
                if 'data' in json_venc and 'cotacoesOpcoes' in json_venc['data']:
                    cotacoes = json_venc['data']['cotacoesOpcoes']
                    
                    for c in cotacoes:
                        if len(c) >= 11:
                            try:
                                ticker_opcao = c[0].split("_")[0]
                                tipo = str(c[2]).upper()
                                strike = float(c[5]) if c[5] is not None else 0.0
                                ultimo = float(c[8]) if c[8] is not None else 0.0
                                
                                # Apenas catalogar se teve pregoamento recente
                                if strike > 0 and ultimo > 0.01:
                                    dados_completos.append({
                                        "ticker_opcao": ticker_opcao,
                                        "ticker_base": ticker.upper(),
                                        "tipo": tipo.upper() if tipo else "",
                                        "strike": strike,
                                        "vencimento": venc_str,
                                        "dias_ate_venc": dias_ate_venc,
                                        "ultimo": ultimo,
                                        "vol_implicita": 0.0, # A B3 borra de propósito, o nosso app.py vai calcular reverso!
                                    })
                            except (ValueError, IndexError, TypeError):
                                continue

        return pd.DataFrame(dados_completos) if dados_completos else pd.DataFrame()

    except Exception as e:
        print(f"Alerta: Falha na API interna Híbrida ({str(e)}). Sem dados reais para {ticker}.")
        return pd.DataFrame()
