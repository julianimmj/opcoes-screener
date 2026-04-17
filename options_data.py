"""
Módulo de obtenção de dados de opções da B3 via scraping do opcoes.net.br.
Usa dados de fechamento do pregão anterior (disponível gratuitamente).
"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import streamlit as st
import re

# Dependências do Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://opcoes.net.br/",
    "Connection": "keep-alive",
}

# Mapeamento das letras dos meses para opções B3
# Calls: A=Jan, B=Fev, ..., L=Dez
# Puts: M=Jan, N=Fev, ..., X=Dez
CALL_MONTHS = {chr(65+i): i+1 for i in range(12)}  # A-L -> 1-12
PUT_MONTHS = {chr(77+i): i+1 for i in range(12)}    # M-X -> 1-12


def _inferir_tipo_e_vencimento_do_ticker(ticker_opcao: str, ano_ref: int = None):
    """
    Infere tipo (CALL/PUT) e mês de vencimento a partir do ticker da opção.
    Ex: PETRA475 -> CALL, Janeiro; PETRM475 -> PUT, Janeiro
    """
    if not ticker_opcao or len(ticker_opcao) < 5:
        return None, None

    # A letra que indica tipo/mês está na 5ª posição (índice 4) para tickers de 4 chars
    # Para PETR4: PETR + letra + strike
    # Precisamos encontrar a letra do mês
    base = ticker_opcao[:4]

    # Encontra a primeira letra após o ticker base que indica o mês
    rest = ticker_opcao[4:]
    if not rest:
        return None, None

    letra = rest[0].upper()

    if letra in CALL_MONTHS:
        return "CALL", CALL_MONTHS[letra]
    elif letra in PUT_MONTHS:
        return "PUT", PUT_MONTHS[letra]

    return None, None


@st.cache_data(ttl=600, show_spinner=False)
def buscar_opcoes_opcoes_net(ticker: str) -> pd.DataFrame:
    """
    Busca a grade de opções de um ativo no opcoes.net.br via scraping.

    Args:
        ticker: Ticker do ativo (ex: PETR4)

    Returns:
        DataFrame com os dados das opções
    """
    url = f"https://opcoes.net.br/opcoes/bovespa/{ticker.upper()}"

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        response = session.get(url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Procura a tabela de opções
        table = soup.find("table", {"id": "tblListaOpc"})

        if not table:
            return pd.DataFrame()

        # Parse do cabeçalho
        headers_row = table.find("thead")
        if not headers_row:
            return pd.DataFrame()

        # Parse das linhas
        tbody = table.find("tbody")
        if not tbody:
            return pd.DataFrame()

        rows = tbody.find_all("tr")
        if not rows:
            return pd.DataFrame()

        data = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 12:
                try:
                    ticker_opcao = cells[0].get_text(strip=True)
                    tipo = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    modelo = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    strike_text = cells[3].get_text(strip=True) if len(cells) > 3 else "0"
                    aiotm = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    ultimo_text = cells[6].get_text(strip=True) if len(cells) > 6 else "0"
                    vol_impl_text = cells[11].get_text(strip=True) if len(cells) > 11 else ""
                    negocios_text = cells[9].get_text(strip=True) if len(cells) > 9 else "0"

                    # Limpa e converte valores numéricos
                    strike = _parse_number(strike_text)
                    ultimo = _parse_number(ultimo_text)
                    vol_impl = _parse_number(vol_impl_text)
                    negocios = _parse_int(negocios_text)

                    if strike and strike > 0:
                        data.append({
                            "ticker_opcao": ticker_opcao,
                            "tipo": tipo.upper() if tipo else "",
                            "modelo": modelo,
                            "strike": strike,
                            "aiotm": aiotm,
                            "ultimo": ultimo if ultimo else 0,
                            "vol_implicita": vol_impl,
                            "negocios": negocios if negocios else 0,
                        })
                except (ValueError, IndexError):
                    continue

        return pd.DataFrame(data) if data else pd.DataFrame()

    except requests.RequestException:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def buscar_opcoes_completas(ticker: str, dias_min: int = 45,
                             dias_max: int = 70) -> pd.DataFrame:
    """
    Busca opções verificando múltiplos vencimentos usando Selenium Headless.
    Contorna o anti-bot e o carregamento dinâmico via KnockoutJS.
    """
    url = f"https://opcoes.net.br/opcoes/bovespa/{ticker.upper()}"
    dados_completos = []

    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception:
            driver = webdriver.Chrome(options=options)

        driver.get(url)

        # Aguarda a dropdown de vencimentos carregar
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#vencimentos option"))
        )

        vencimentos_select = driver.find_element(By.ID, "vencimentos")
        options_elements = vencimentos_select.find_elements(By.TAG_NAME, "option")
        
        hoje = datetime.now()
        vencimentos_para_buscar = []

        # Encontra expirations que cabem no nosso range
        for opt in options_elements:
            venc_str = opt.get_attribute("value")
            if not venc_str: continue
            try:
                venc_date = datetime.strptime(venc_str, "%Y-%m-%d")
                dias_ate_venc = (venc_date - hoje).days
                if dias_min <= dias_ate_venc <= dias_max:
                    vencimentos_para_buscar.append((venc_str, dias_ate_venc, opt))
            except ValueError:
                pass

        # Itera sobre as abas maduras e clica
        for venc_str, dias_ate_venc, opt_element in vencimentos_para_buscar:
            opt_element.click()
            time.sleep(2.5) # Aguarda KnockoutJS injetar a tabela

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", {"id": "tblListaOpc"})
            
            if table:
                tbody = table.find("tbody")
                if tbody:
                    rows = tbody.find_all("tr")
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= 12:
                            try:
                                ticker_opcao = cells[0].get_text(strip=True)
                                tipo = cells[1].get_text(strip=True)
                                strike = _parse_number(cells[3].get_text(strip=True))
                                ultimo = _parse_number(cells[6].get_text(strip=True))
                                vol_impl = _parse_number(cells[11].get_text(strip=True))

                                if strike and strike > 0 and ultimo and ultimo > 0:
                                    dados_completos.append({
                                        "ticker_opcao": ticker_opcao,
                                        "ticker_base": ticker.upper(),
                                        "tipo": tipo.upper() if tipo else "",
                                        "strike": strike,
                                        "vencimento": venc_str,
                                        "dias_ate_venc": dias_ate_venc,
                                        "ultimo": ultimo,
                                        "vol_implicita": vol_impl if vol_impl else 0.0,
                                    })
                            except (ValueError, IndexError):
                                continue

        driver.quit()

        return pd.DataFrame(dados_completos) if dados_completos else pd.DataFrame()

    except Exception as e:
        print(f"Alerta: Falha no injetor Selenium ({str(e)}). Acionando simulação fallback.")
        return pd.DataFrame()


def _extrair_dados_javascript(html: str, ticker: str) -> pd.DataFrame | None:
    """Tenta extrair dados de opções do JavaScript inline na página."""
    # O opcoes.net.br usa KnockoutJS e carrega dados dinamicamente
    # Esta função tenta parsear os dados se estiverem embutidos
    try:
        # Procura por padrões JSON na página
        pattern = r'cotacoesOpcoes["\s]*:\s*\[(.*?)\]'
        match = re.search(pattern, html, re.DOTALL)
        if match and match.group(1).strip():
            # Encontrou dados inline
            import json
            data_str = "[" + match.group(1) + "]"
            data = json.loads(data_str)
            if data:
                return pd.DataFrame(data)
    except Exception:
        pass
    return None


def gerar_opcoes_simuladas(ticker: str, preco_atual: float,
                           vol_historica: float, dias_min: int = 45,
                           dias_max: int = 70) -> pd.DataFrame:
    """
    Gera uma grade realista de opções para simulação quando o scraping falha.
    Usa strikes baseados no preço atual e volatilidade típica do mercado.

    Args:
        ticker: Ticker do ativo
        preco_atual: Preço atual do ativo
        vol_historica: Volatilidade histórica calculada
        dias_min: Mínimo dias vencimento
        dias_max: Máximo dias vencimento

    Returns:
        DataFrame com opções simuladas
    """
    from black_scholes import (black_scholes_price, SELIC_RATE,
                                tempo_em_anos, calcular_vol_implicita)
    import numpy as np

    if not preco_atual or preco_atual <= 0:
        return pd.DataFrame()

    hoje = datetime.now()
    opcoes = []

    # Gera vencimentos dentro do range
    # B3: vencimentos na 3ª segunda-feira de cada mês (aprox.)
    for mes_offset in range(1, 4):
        venc_date = hoje + timedelta(days=30 * mes_offset)
        # Ajusta para 3ª sexta-feira do mês
        venc_date = venc_date.replace(day=15)
        while venc_date.weekday() != 4:  # sexta-feira
            venc_date += timedelta(days=1)

        dias_ate_venc = (venc_date - hoje).days

        if dias_ate_venc < dias_min or dias_ate_venc > dias_max:
            continue

        T = dias_ate_venc / 365.0
        r = SELIC_RATE

        # Gera strikes em torno do preço atual
        step = _calcular_step_strike(preco_atual)
        strikes = np.arange(
            preco_atual * 0.85, preco_atual * 1.15, step
        )

        for K in strikes:
            K = round(K, 2)

            for tipo in ["CALL", "PUT"]:
                # Vol implícita simulada = vol histórica + variação aleatória
                # Simula cenário onde a IV pode estar abaixo da HV
                np.random.seed(int(K * 100 + (1 if tipo == "CALL" else 2)))
                iv_offset = np.random.uniform(-0.15, 0.08)
                vol_impl = max(0.05, vol_historica + iv_offset)

                # Preço de mercado = B-S com vol implícita
                preco_mercado = black_scholes_price(preco_atual, K, T, r,
                                                     vol_impl, tipo.lower())
                # Preço justo = B-S com vol histórica
                preco_justo = black_scholes_price(preco_atual, K, T, r,
                                                   vol_historica, tipo.lower())

                if preco_mercado > 0.01:
                    # Gera ticker da opção no formato B3
                    letra_tipo = _get_letra_opcao(tipo, venc_date.month)
                    ticker_opcao = (f"{ticker[:4]}{letra_tipo}"
                                    f"{int(K * 100) % 10000}")

                    opcoes.append({
                        "ticker_opcao": ticker_opcao,
                        "ticker_base": ticker,
                        "tipo": tipo,
                        "strike": K,
                        "preco_atual_base": round(preco_atual, 2),
                        "vencimento": venc_date.strftime("%Y-%m-%d"),
                        "dias_ate_venc": dias_ate_venc,
                        "preco_mercado": round(preco_mercado, 2),
                        "preco_justo_bs": round(preco_justo, 2),
                        "vol_implicita": round(vol_impl * 100, 2),
                        "vol_historica_60d": round(vol_historica * 100, 2),
                        "diff_vol": round((vol_impl - vol_historica) * 100, 2),
                        "desconto_pct": round(
                            ((preco_justo - preco_mercado) / preco_mercado * 100)
                            if preco_mercado > 0 else 0, 2
                        ),
                    })

    return pd.DataFrame(opcoes)


def _calcular_step_strike(preco: float) -> float:
    """Calcula o step de strike baseado no preço do ativo."""
    if preco < 5:
        return 0.25
    elif preco < 20:
        return 0.50
    elif preco < 50:
        return 1.00
    elif preco < 100:
        return 2.00
    else:
        return 5.00


def _get_letra_opcao(tipo: str, mes: int) -> str:
    """Retorna a letra da opção baseada no tipo e mês."""
    if tipo.upper() == "CALL":
        return chr(64 + mes)  # A=Jan, B=Fev, ...
    else:
        return chr(76 + mes)  # M=Jan, N=Fev, ...


def _parse_number(text: str) -> float | None:
    """Converte texto numérico brasileiro para float."""
    if not text or text.strip() in ("", "-", "N/A"):
        return None
    try:
        # Remove pontos de milhar e substitui vírgula por ponto
        text = text.strip().replace(".", "").replace(",", ".")
        return float(text)
    except (ValueError, TypeError):
        return None


def _parse_int(text: str) -> int | None:
    """Converte texto para inteiro."""
    if not text or text.strip() in ("", "-", "N/A"):
        return None
    try:
        text = text.strip().replace(".", "").replace(",", "")
        return int(float(text))
    except (ValueError, TypeError):
        return None
