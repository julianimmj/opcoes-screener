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
        print(f"Alerta: Falha no injetor Selenium ({str(e)}). Sem dados reais para {ticker}.")
        return pd.DataFrame()





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
