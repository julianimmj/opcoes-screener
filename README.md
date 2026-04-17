# 📊 Screener de Opções Baratas — B3

Aplicação web profissional que identifica opções de ações brasileiras subvalorizadas, comparando a **volatilidade implícita** do mercado com a **volatilidade histórica de 60 dias**, utilizando o modelo **Black-Scholes** para precificação teórica.

## 🔍 O que faz?

- Busca opções de ações listadas na B3 com vencimento entre 45 e 70 dias
- Calcula a volatilidade histórica dos últimos 60 dias do ativo-objeto
- Utiliza Black-Scholes para calcular o preço justo teórico da opção
- Exibe apenas opções onde a vol. implícita está **≥ 8pp abaixo** da vol. histórica
- Gráficos interativos comparando IV vs HV
- Download dos resultados em CSV

## 📋 Colunas da Tabela

| Coluna | Descrição |
|--------|-----------|
| Opção | Ticker da opção |
| Ativo | Ativo-objeto |
| Vencimento | Data de expiração |
| Strike | Preço de exercício |
| Tipo | CALL ou PUT |
| Preço Mercado | Último preço negociado |
| Preço Justo (B-S) | Preço teórico via Black-Scholes |
| Vol. Impl. | Volatilidade implícita (%) |
| Vol. Hist. 60d | Volatilidade histórica de 60 dias (%) |
| Diff Vol | Diferença IV - HV em pontos percentuais |
| Desconto | Quanto a opção está abaixo do preço justo (%) |

## 🚀 Tecnologias

- **Python** + **Streamlit**
- **yfinance** — dados de preço das ações
- **scipy** — Black-Scholes + otimização numérica
- **Plotly** — gráficos interativos
- **opcoes.net.br** — dados de opções (scraping)

## ⚙️ Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## ⚠️ Aviso

Esta é uma ferramenta **educacional**. Não constitui recomendação de investimento. Os dados são baseados no fechamento do pregão anterior e podem não refletir condições de mercado em tempo real. Sempre verifique os dados com sua corretora antes de operar.

## 📄 Licença

MIT
