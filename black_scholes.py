"""
Módulo de cálculos financeiros: Black-Scholes, volatilidade histórica e implícita.
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
import yfinance as yf
import streamlit as st
import requests
from datetime import datetime, timedelta


def obter_taxa_selic_atual() -> float:
    """Busca a meta da taxa Selic atualizada via API do Banco Central do Brasil."""
    try:
        r = requests.get('https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json', timeout=5)
        return float(r.json()[0]['valor']) / 100.0
    except Exception:
        # Fallback razoável
        return 0.105

# Taxa SELIC dinâmica vinculada à economia atualizada
SELIC_RATE = obter_taxa_selic_atual()


def calcular_vol_historica(ticker: str, dias: int = 60) -> float | None:
    """
    Calcula a volatilidade histórica anualizada usando retornos log-normais.

    Args:
        ticker: Ticker da ação (sem .SA)
        dias: Número de dias úteis para o cálculo

    Returns:
        Volatilidade anualizada em decimal (ex: 0.35 = 35%)
    """
    try:
        # Busca dados com margem extra para garantir dias úteis suficientes
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(dias * 1.8))

        stock = yf.Ticker(f"{ticker}.SA")
        hist = stock.history(start=start_date, end=end_date)

        if hist.empty or len(hist) < dias:
            return None

        # Usa os últimos 'dias' pregões
        closes = hist["Close"].tail(dias)

        if len(closes) < 2:
            return None

        # Retornos logarítmicos
        log_returns = np.log(closes / closes.shift(1)).dropna()

        if len(log_returns) < 10:
            return None

        # Volatilidade anualizada (252 dias úteis)
        vol = log_returns.std() * np.sqrt(252)

        return float(vol)
    except Exception:
        return None


def obter_preco_atual(ticker: str) -> float | None:
    """Obtém o preço atual do ativo via yfinance."""
    try:
        stock = yf.Ticker(f"{ticker}.SA")
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def black_scholes_price(S: float, K: float, T: float, r: float,
                         sigma: float, option_type: str = "call") -> float:
    """
    Calcula o preço teórico de uma opção usando Black-Scholes.

    Args:
        S: Preço atual do ativo-objeto
        K: Strike da opção
        T: Tempo até o vencimento em anos
        r: Taxa livre de risco (anualizada)
        sigma: Volatilidade (anualizada)
        option_type: 'call' ou 'put'

    Returns:
        Preço teórico da opção
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type.lower() == "call":
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return max(price, 0.0)


def calcular_vol_implicita(preco_mercado: float, S: float, K: float,
                            T: float, r: float,
                            option_type: str = "call") -> float | None:
    """
    Calcula a volatilidade implícita usando o método de Brent.

    Args:
        preco_mercado: Preço de mercado da opção
        S: Preço atual do ativo
        K: Strike
        T: Tempo até vencimento em anos
        r: Taxa livre de risco
        option_type: 'call' ou 'put'

    Returns:
        Volatilidade implícita em decimal, ou None se não convergir
    """
    if preco_mercado <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None

    def objective(sigma):
        return black_scholes_price(S, K, T, r, sigma, option_type) - preco_mercado

    try:
        iv = brentq(objective, 0.001, 5.0, xtol=1e-6, maxiter=200)
        return float(iv)
    except (ValueError, RuntimeError):
        return None


def dias_uteis_ate_vencimento(data_vencimento: datetime) -> int:
    """Estima dias úteis entre hoje e a data de vencimento."""
    hoje = datetime.now()
    if isinstance(data_vencimento, str):
        try:
            data_vencimento = datetime.strptime(data_vencimento, "%Y-%m-%d")
        except ValueError:
            try:
                data_vencimento = datetime.strptime(data_vencimento, "%d/%m/%Y")
            except ValueError:
                return 0

    dias_corridos = (data_vencimento - hoje).days
    if dias_corridos <= 0:
        return 0

    # Aproximação: ~70% dos dias corridos são úteis
    return max(1, int(dias_corridos * 0.7))


def tempo_em_anos(dias_uteis: int) -> float:
    """Converte dias úteis em fração de ano (base 252 dias úteis)."""
    return dias_uteis / 252.0
