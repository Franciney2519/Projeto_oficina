"""
Aplicação Flask para gestão básica de oficina mecânica utilizando arquivos
Excel como persistência.

Como executar:
    1. Instale as dependências: pip install flask pandas openpyxl fpdf
    2. Execute: python app.py
    3. Acesse http://127.0.0.1:5000/ em seu navegador.

Arquivos de dados:
    Os arquivos .xlsx serão criados automaticamente na raiz do projeto
    (mesmo diretório deste app.py). Caso deseje adicionar novos campos,
    atualize as listas de colunas em data_access.py e adapte os formulários.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
import math
import unicodedata
import webbrowser
from threading import Timer
from typing import List, Tuple, Optional
from io import BytesIO

try:
    import pandas as pd
except ImportError as exc:  # Segurança: caso pandas não esteja disponível ainda
    raise RuntimeError(
        "Instale as dependências com 'pip install flask pandas openpyxl'"
    ) from exc

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_file,
)

from fpdf import FPDF

try:
    from PIL import Image
except ImportError:  # pillow is opcional; ícone será pulado se não estiver disponível
    Image = None

import data_access as dal

PROJECT_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_DIR, "templates"),
    static_folder=os.path.join(PROJECT_DIR, "static"),
)
app.secret_key = "oficina-mecanica-secret"  # Necessário para mensagens flash

# Informações fixas usadas no PDF do orçamento.
COMPANY_INFO = {
    "razao_social": "R R A AUTOS",
    "cnpj": "47.749.985/001-16",
    "endereco": "Rua Maracujá, 149 - Santa Etelvina, Manaus/AM",
    "telefone": "(92) 99391-7093",
    "email": "rogeriopereira2@gmail.com",
}


@app.context_processor
def inject_company_info():
    """Disponibiliza dados da empresa para todos os templates."""
    return {"company_info": COMPANY_INFO}
LOGO_SOURCE_PATH = os.path.join(PROJECT_DIR, "icone.ico")
LOGO_CACHE_PATH = os.path.join(PROJECT_DIR, "__logo_cache.png")
VALIDADE_PADRAO = "5 dias corridos"
OBSERVACOES_PADRAO = (
    "Valores sujeitos a alteração após o período de validade. "
    "Prazo estimado de execução conforme disponibilidade na agenda."
)
PAYMENT_OPTIONS = [
    "PIX",
    "Dinheiro",
    "Cartão Débito",
    "Cartão Crédito",
    "Crediário Parceiro Bemol",
]
COMMERCIAL_TERMS_TEXT = (
    "Forma de pagamento: Transferência bancária, boleto ou cartão de crédito."
)
FINALIZED_BUDGET_STATUSES = {"concluido", "finalizado"}
FINANCE_EXPENSE_TYPES = {
    "Despesas Fixas": [
        "Infraestrutura - Aluguel do ponto comercial",
        "Infraestrutura - IPTU",
        "Infraestrutura - Condomínio",
        "Infraestrutura - Seguro do espaço/equipamentos",
        "Energia e utilidades - Energia elétrica",
        "Energia e utilidades - Água",
        "Energia e utilidades - Internet e telefone",
        "Sistemas e softwares de gestão",
        "Assinatura de contabilidade",
        "Pessoal - Salários",
        "Pessoal - Encargos (INSS/FGTS etc.)",
        "Pessoal - Vale-transporte",
        "Pessoal - Vale-alimentação",
        "Administrativas - Contabilidade",
        "Administrativas - Taxas bancárias",
        "Administrativas - Taxas de cartão",
        "Administrativas - Licenças e alvarás",
        "Manutenção preventiva",
    ],
    "Despesas Variáveis": [
        "Materiais e peças - Componentes automotivos",
        "Materiais e peças - Lubrificantes",
        "Materiais e peças - Embalagens/limpeza do serviço",
        "Operação - Mão de obra variável",
        "Operação - Produtos químicos",
        "Operação - Gases industriais",
        "Despesas comerciais - Comissões",
        "Despesas comerciais - Marketing/divulgação",
    ],
    "Investimentos (CAPEX)": [
        "Equipamentos - Elevador/compressor",
        "Equipamentos - Scanner/diagnóstico",
        "Equipamentos - Ferramentas especiais",
        "Infraestrutura - Reforma/galpão",
        "Infraestrutura - Sistema elétrico/exaustão",
    ],
    "Despesas Financeiras": [
        "Juros de parcelamentos",
        "Taxa de antecipação",
        "Multas",
        "Empréstimos/financiamentos",
    ],
    "Despesas de apoio e limpeza": [
        "Produtos de limpeza",
        "Uniformes e EPIs",
        "Lavagem de panos industriais",
        "Coleta de resíduos automotivos",
    ],
}

# Garante criação das planilhas quando o servidor inicia.
dal.ensure_all_files_exist()


@app.route("/favicon.ico")
def favicon():
    """Serve o ícone do aplicativo para uso na interface e na aba do navegador."""
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icone.ico")
    if not os.path.exists(icon_path):
        # Evita erro caso o arquivo tenha sido removido; retorna 404 padrão.
        return ("", 404)
    return send_file(icon_path, mimetype="image/x-icon")


@app.route("/atualizar-base", methods=["POST"])
def atualizar_base():
    """Botão global que força a leitura/validação das planilhas de dados."""
    dal.ensure_all_files_exist()
    data_files = dal.get_data_files()
    saved_at = "; ".join(f"{nome}: {caminho}" for nome, caminho in data_files.items())
    app.logger.info("Atualização solicitada. Arquivos de dados em uso: %s", saved_at)
    flash("Base de dados atualizada a partir dos arquivos locais.", "success")
    return redirect(request.referrer or url_for("dashboard"))


def _parse_date(date_str: str) -> datetime:
    """Converte strings de data no formato YYYY-MM-DD."""
    if not date_str:
        return datetime.today()
    return datetime.strptime(date_str, "%Y-%m-%d")


def _normalize_status(value: str) -> str:
    """Remove acentos e padroniza para facilitar comparações de status."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.strip().lower()


def _is_budget_finalized(status: str) -> bool:
    """Indica se um orçamento está em estado que impede nova efetivação."""
    return _normalize_status(status) in FINALIZED_BUDGET_STATUSES


def _format_quantity_display(value) -> str:
    """Formata quantidades para o PDF, mantendo texto caso não seja numérico."""
    if value is None or value == "":
        return "-"
    try:
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
        return f"{numeric:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _build_client_address(client: dict) -> str:
    """Monta uma string de endereço amigável para o PDF."""
    parts: List[str] = []

    def _as_text(value):
        if value is None:
            return ""
        if isinstance(value, float) and math.isnan(value):
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "none"}:
            return ""
        return text

    street = " ".join(
        text for text in [_as_text(client.get("endereco_rua")), _as_text(client.get("endereco_numero"))] if text
    )
    if street:
        parts.append(street)

    bairro = _as_text(client.get("endereco_bairro"))
    if bairro:
        parts.append(bairro)

    city_state = ", ".join(
        text for text in [_as_text(client.get("endereco_cidade")), _as_text(client.get("endereco_uf"))] if text
    )
    if city_state:
        parts.append(city_state)

    cep = _as_text(client.get("endereco_cep"))
    if cep:
        parts.append(f"CEP {cep}")

    return " - ".join(parts) if parts else "Não informado"


def _pdf_safe_text(value) -> str:
    """Remove caracteres fora do latin-1 para evitar erros na geração do PDF."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.encode("latin-1", "ignore").decode("latin-1")


def _get_pdf_logo_path() -> Optional[str]:
    """Retorna o caminho de uma imagem compatível com o PDF a partir do ícone."""
    if not os.path.exists(LOGO_SOURCE_PATH):
        return None

    ext = os.path.splitext(LOGO_SOURCE_PATH)[1].lower()
    if ext in {".png", ".jpg", ".jpeg"}:
        return LOGO_SOURCE_PATH

    if Image is None:
        return None

    try:
        source_mtime = os.path.getmtime(LOGO_SOURCE_PATH)
        if os.path.exists(LOGO_CACHE_PATH) and os.path.getmtime(LOGO_CACHE_PATH) >= source_mtime:
            return LOGO_CACHE_PATH

        with Image.open(LOGO_SOURCE_PATH) as img:
            img.save(LOGO_CACHE_PATH, format="PNG")
        return LOGO_CACHE_PATH
    except Exception:
        return None


def _slugify_filename(value: str) -> str:
    """Gera um identificador simples para uso em nomes de arquivos."""
    if not value:
        return "recibo"
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    safe = "".join(ch if ch.isalnum() else "_" for ch in ascii_text).strip("_")
    return safe.lower() or "recibo"


def _format_date(date_value) -> str:
    """Padroniza exibição de datas mesmo quando vierem como Timestamp."""
    if date_value is None or pd.isna(date_value):
        return "-"
    try:
        return pd.to_datetime(date_value).strftime("%d/%m/%Y")
    except Exception:  # pylint: disable=broad-except
        return str(date_value)


@app.route("/")
def dashboard():
    clients_df = dal.get_all_clients()
    budgets_df = dal.get_all_budgets()
    financial_df = dal.get_all_financial_entries()

    total_clients = len(clients_df)
    open_budgets = budgets_df[budgets_df["status"] != "Concluído"]
    total_open_budgets = len(open_budgets)

    financial_df["data"] = pd.to_datetime(financial_df["data"], errors="coerce")
    today = datetime.today()
    monthly = financial_df[
        (financial_df["data"].dt.month == today.month)
        & (financial_df["data"].dt.year == today.year)
    ]
    entradas = monthly[monthly["tipo_lancamento"] == "Entrada"]["valor"].sum()
    saidas = monthly[monthly["tipo_lancamento"] == "Saída"]["valor"].sum()

    return render_template(
        "index.html",
        total_clients=total_clients,
        total_open_budgets=total_open_budgets,
        total_entradas=entradas,
        total_saidas=saidas,
        saldo=entradas - saidas,
    )


CLIENT_FIELDS = [
    "nome",
    "telefone_whatsapp",
    "email",
    "endereco_rua",
    "endereco_numero",
    "endereco_bairro",
    "endereco_cidade",
    "endereco_uf",
    "endereco_cep",
    "carro_marca",
    "carro_modelo",
    "carro_ano",
    "carro_placa",
    "observacoes",
]


@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    if request.method == "POST":
        payload = {field: request.form.get(field, "").strip() for field in CLIENT_FIELDS}
        dal.add_client(payload)
        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for("clientes"))

    clients_df = dal.get_all_clients().fillna("")
    clients = clients_df.to_dict(orient="records")
    return render_template("clientes.html", clients=clients)


@app.route("/clientes/editar/<int:client_id>", methods=["GET", "POST"])
def editar_cliente(client_id: int):
    client = dal.get_client_by_id(client_id)
    if not client:
        flash("Cliente não encontrado.", "danger")
        return redirect(url_for("clientes"))

    if request.method == "POST":
        updates = {field: request.form.get(field, "").strip() for field in CLIENT_FIELDS}
        dal.update_client(client_id, updates)
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for("clientes"))

    return render_template("editar_cliente.html", client=client)


@app.route("/clientes/<int:client_id>/historico")
def historico_cliente(client_id: int):
    client = dal.get_client_by_id(client_id)
    if not client:
        flash("Cliente não encontrado.", "danger")
        return redirect(url_for("clientes"))

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    services_df = dal.get_all_services()
    services_df = services_df[services_df["id_cliente"] == client_id]
    services_df["data_execucao"] = pd.to_datetime(services_df["data_execucao"], errors="coerce")

    if data_inicio:
        services_df = services_df[services_df["data_execucao"] >= _parse_date(data_inicio)]
    if data_fim:
        services_df = services_df[services_df["data_execucao"] <= _parse_date(data_fim)]

    services_df = services_df.sort_values("data_execucao", ascending=False)
    services = []
    for row in services_df.to_dict(orient="records"):
        row["data_formatada"] = _format_date(row.get("data_execucao"))
        services.append(row)

    return render_template(
        "historico_cliente.html",
        client=client,
        services=services,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@app.route("/historico-servicos")
def historico_servicos():
    """Tela consolidada de serviços com filtro por cliente."""
    selected_client_id = request.args.get("cliente")
    try:
        selected_client_id = int(selected_client_id) if selected_client_id else None
    except ValueError:
        flash("Seleção de cliente inválida.", "danger")
        return redirect(url_for("historico_servicos"))

    services_df = dal.get_all_services()
    clients_df = dal.get_all_clients()[["id_cliente", "nome"]]
    budgets_df = dal.get_all_budgets()[["id_orcamento", "status"]]

    services_df = services_df.merge(clients_df, on="id_cliente", how="left")
    services_df = services_df.merge(budgets_df, on="id_orcamento", how="left")
    services_df["data_execucao"] = pd.to_datetime(
        services_df["data_execucao"], errors="coerce"
    )

    if selected_client_id:
        services_df = services_df[services_df["id_cliente"] == selected_client_id]

    services_df = services_df.sort_values("data_execucao", ascending=False)
    services = []
    for row in services_df.to_dict(orient="records"):
        services.append(
            {
                "client_id": row.get("id_cliente"),
                "client_name": row.get("nome") or "N/D",
                "budget_id": row.get("id_orcamento"),
                "service_date": _format_date(row.get("data_execucao")),
                "service_type": row.get("tipo_servico"),
                "service_value": row.get("valor") or 0,
                "status": row.get("status") or "Sem status",
            }
        )

    clients = clients_df.sort_values("nome").to_dict(orient="records")

    return render_template(
        "historico_servicos.html",
        services=services,
        clients=clients,
        selected_client_id=selected_client_id,
    )


def _build_budget_items_from_form(form) -> List[dict]:
    descricoes = form.getlist("item_descricao[]")
    tipos = form.getlist("item_tipo[]")
    quantidades = form.getlist("item_quantidade[]")
    valores = form.getlist("item_valor[]")

    items = []
    for desc, tipo, qtd, val in zip(descricoes, tipos, quantidades, valores):
        if not desc:
            continue
        quantidade = float(qtd or 1)
        valor_unitario = float(val or 0)
        items.append(
            {
                "descricao": desc.strip(),
                "tipo": tipo.strip(),
                "quantidade": quantidade,
                "valor_unitario": valor_unitario,
                "subtotal": quantidade * valor_unitario,
            }
        )
    return items


# ---------------------------
# Funções auxiliares de apresentação
# ---------------------------
def _calculate_total_with_payment(base_total: float, payment_method: str) -> Tuple[float, float]:
    """Retorna (total_final, taxa) aplicando regras da forma de pagamento."""
    total = base_total
    taxa = 0.0
    if payment_method == "Cartão Crédito":
        taxa = round(base_total * 0.03, 2)
        total = round(base_total + taxa, 2)
    return total, taxa


def _generate_whatsapp_text(
    client_name: str,
    items: List[dict],
    total: float,
    payment_method: str,
    taxa: float,
) -> str:
    linhas = [
        f"Olá {client_name}, tudo bem?",
        f"Segue abaixo o orçamento detalhado da oficina {COMPANY_INFO['razao_social']}:",
        "",
    ]
    for item in items:
        linhas.append(
            f"- {item['descricao']} ({item['quantidade']}x R$ {item['valor_unitario']:.2f}) = R$ {item['subtotal']:.2f}"
        )
    linhas.extend(
        [
            "",
            f"Forma de pagamento: {payment_method}",
            f"Valor total: R$ {total:.2f}"
            + (" (inclui taxa de cartão de crédito)" if taxa > 0 else ""),
            "Validade do orçamento: 5 dias corridos.",
            "Prazo estimado para execução: conforme disponibilidade na agenda.",
            "Qualquer dúvida é só me chamar!",
        ]
    )
    return "\n".join(linhas)



def _generate_budget_pdf(budget: dict, client: dict, items: List[dict]) -> BytesIO:
    """Gera o PDF de orçamento no layout do modelo fornecido."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    yellow = (244, 195, 28)
    dark_blue = (26, 55, 102)
    light_gray = (230, 230, 230)
    text_gray = (90, 90, 90)

    # Faixas decorativas inspiradas no template.
    pdf.set_fill_color(*yellow)
    pdf.rect(-5, -5, 90, 18, "F")
    pdf.rect(150, 285, 70, 15, "F")

    # Logo centralizada.
    logo_path = _get_pdf_logo_path()
    y_after_logo = 16
    if logo_path:
        try:
            pdf.image(logo_path, x=85, y=16, w=40, h=32)
            y_after_logo = 16 + 32
        except RuntimeError:
            y_after_logo = 20

    # Contatos no topo direito.
    pdf.set_xy(135, 14)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(*dark_blue)
    contact_lines = [COMPANY_INFO.get("telefone", "")]
    email = COMPANY_INFO.get("email")
    if email:
        contact_lines.append(email)
    pdf.multi_cell(60, 5, _pdf_safe_text("\n".join(line for line in contact_lines if line)), align="R")

    # Título.
    pdf.set_y(max(y_after_logo + 6, 50))
    pdf.set_font("Arial", "B", 26)
    pdf.set_text_color(*dark_blue)
    pdf.cell(0, 12, "ORÇAMENTO", ln=1, align="C")

    base_total = sum(float(item.get("subtotal", 0) or 0) for item in items)
    forma_pagamento = budget.get("forma_pagamento") or "PIX"
    final_total = float(budget.get("valor_total", base_total) or base_total)

    # Barra de dados da loja.
    pdf.ln(6)
    info_rows = [
        ("Razão Social", COMPANY_INFO.get("razao_social", "")),
        ("CNPJ", COMPANY_INFO.get("cnpj", "")),
        ("Endereço", COMPANY_INFO.get("endereco", "")),
        ("Telefone", COMPANY_INFO.get("telefone", "")),
    ]
    row_y = pdf.get_y()
    for label, value in info_rows:
        pdf.set_fill_color(*light_gray)
        pdf.rect(10, row_y, 190, 12, "F")
        pdf.set_xy(14, row_y + 3.5)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(*dark_blue)
        pdf.cell(0, 0, _pdf_safe_text(label.upper()))
        pdf.set_xy(70, row_y + 2.5)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 0, _pdf_safe_text(value))
        row_y += 14
    pdf.set_y(row_y + 4)

    # Tabela de itens.
    headers = [
        ("ITEM", 18),
        ("DESCRIÇÃO", 84),
        ("QUANT.", 20),
        ("UNITÁRIO", 32),
        ("TOTAL", 36),
    ]
    pdf.set_fill_color(*yellow)
    pdf.set_text_color(*dark_blue)
    pdf.set_font("Arial", "B", 11)
    for header, width in headers:
        pdf.cell(width, 9, header, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_text_color(*text_gray)
    pdf.set_font("Arial", "", 10)
    pdf.set_draw_color(200, 200, 200)
    min_rows = max(len(items), 6)
    for idx in range(min_rows):
        if idx < len(items):
            item = items[idx]
            descricao = _pdf_safe_text(item.get("descricao") or f"Serviço {idx + 1}")
            quantidade_raw = item.get("quantidade", 1)
            quantidade_display = _format_quantity_display(quantidade_raw)
            try:
                quantidade_num = float(quantidade_raw)
            except (TypeError, ValueError):
                quantidade_num = 1.0
            valor_unitario = float(item.get("valor_unitario", 0) or 0)
            subtotal = float(item.get("subtotal", valor_unitario * quantidade_num))
            row_values = [
                str(idx + 1),
                descricao,
                quantidade_display,
                dal.format_currency(valor_unitario),
                dal.format_currency(subtotal),
            ]
        else:
            row_values = ["", "", "", "", ""]

        for (label, width), value in zip(headers, row_values):
            align = "C" if label in {"ITEM", "QUANT.", "UNITÁRIO", "TOTAL"} else "L"
            pdf.cell(width, 9, _pdf_safe_text(value), border=1, align=align)
        pdf.ln()

    pdf.set_fill_color(*yellow)
    pdf.set_text_color(*dark_blue)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(sum(width for _, width in headers[:-1]), 9, "TOTAL:", border=1, align="R", fill=True)
    pdf.cell(headers[-1][1], 9, dal.format_currency(final_total), border=1, align="C", fill=True)
    pdf.ln(12)

    # Informações complementares.
    pdf.set_text_color(*dark_blue)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "DATA:", ln=1)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, _format_date(budget.get("data_criacao")), ln=1)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "VALIDADE DO DOCUMENTO:", ln=1)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, VALIDADE_PADRAO, ln=1)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "OBSERVAÇÕES:", ln=1)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, OBSERVACOES_PADRAO)

    pdf.ln(4)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(*text_gray)
    pdf.multi_cell(0, 5, _pdf_safe_text(COMPANY_INFO.get("endereco", "")))

    pdf_output = pdf.output(dest="S").encode("latin-1")
    buffer = BytesIO(pdf_output)
    buffer.seek(0)
    return buffer


def _generate_receipt_pdf(
    budget_id: int,
    budget: dict,
    client: dict,
    items: List[dict],
    valor_final: float,
    data_conclusao: datetime,
) -> BytesIO:
    """Gera um recibo baseado nos dados do orçamento e pagamento."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    yellow = (244, 195, 28)
    dark_blue = (26, 55, 102)
    gray = (200, 200, 200)

    header_top = 14
    logo_w = 26
    logo_h = 26
    logo_bottom = header_top + logo_h

    logo_path = _get_pdf_logo_path()
    if logo_path:
        try:
            pdf.image(logo_path, x=12, y=header_top, w=logo_w, h=logo_h)
        except RuntimeError:
            logo_bottom = header_top + 4

    text_x = 50
    block_w = 95
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(*dark_blue)
    pdf.set_xy(text_x, header_top)
    pdf.cell(block_w, 6, _pdf_safe_text(COMPANY_INFO.get("razao_social", "")), ln=1)

    pdf.set_font("Arial", "", 10)
    pdf.set_x(text_x)
    pdf.cell(block_w, 5, f"CNPJ: {_pdf_safe_text(COMPANY_INFO.get('cnpj', ''))}", ln=1)
    pdf.set_x(text_x)
    pdf.cell(block_w, 5, _pdf_safe_text(COMPANY_INFO.get("telefone", "")), ln=1)
    email_line = COMPANY_INFO.get("email", "")
    if email_line:
        pdf.set_x(text_x)
        pdf.cell(block_w, 5, f"Email: {_pdf_safe_text(email_line)}", ln=1)
    pdf.set_x(text_x)
    pdf.cell(block_w, 5, _pdf_safe_text(COMPANY_INFO.get("endereco", "")), ln=1)
    text_bottom = pdf.get_y()

    pdf.set_xy(150, header_top)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(40, 8, f"RECIBO Nº: {budget_id}", border=1, align="C", ln=1)
    header_bottom = max(logo_bottom, text_bottom, pdf.get_y())

    # Bloco de informações do cliente.
    pdf.set_y(header_bottom + 12)
    pdf.set_fill_color(*gray)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "INFORMAÇÕES DO CLIENTE", ln=1, align="C", fill=True)
    pdf.set_font("Arial", "", 10)
    pdf.set_draw_color(80, 80, 80)

    table_x = 10
    table_w = 190
    row_h = 9
    label_w = 24

    def row_two(left_label, left_value, right_label, right_value):
        pdf.rect(table_x, pdf.get_y(), table_w, row_h)
        pdf.rect(table_x, pdf.get_y(), table_w / 2, row_h)
        pdf.rect(table_x + table_w / 2, pdf.get_y(), table_w / 2, row_h)

        pdf.set_xy(table_x + 2, pdf.get_y() + 2)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(label_w, 5, _pdf_safe_text(f"{left_label}:"))
        pdf.set_font("Arial", "", 9)
        pdf.cell(table_w / 2 - label_w - 4, 5, _pdf_safe_text(left_value))

        pdf.set_xy(table_x + table_w / 2 + 2, pdf.get_y())
        pdf.set_font("Arial", "B", 9)
        pdf.cell(label_w, 5, _pdf_safe_text(f"{right_label}:"))
        pdf.set_font("Arial", "", 9)
        pdf.cell(table_w / 2 - label_w - 4, 5, _pdf_safe_text(right_value))
        pdf.ln(row_h)

    def row_three(a_label, a_val, b_label, b_val, c_label, c_val):
        col_w = table_w / 3
        y_start = pdf.get_y()
        for idx, (label, value) in enumerate(
            [(a_label, a_val), (b_label, b_val), (c_label, c_val)]
        ):
            x = table_x + idx * col_w
            pdf.rect(x, y_start, col_w, row_h)
            pdf.set_xy(x + 2, y_start + 2)
            pdf.set_font("Arial", "B", 9)
            pdf.cell(label_w, 5, _pdf_safe_text(f"{label}:"))
            pdf.set_font("Arial", "", 9)
            pdf.cell(col_w - label_w - 4, 5, _pdf_safe_text(value))
        pdf.ln(row_h)

    row_two("CLIENTE", client.get("nome", ""), "VEICULO", client.get("carro_modelo", ""))
    row_two("MARCA", client.get("carro_marca", ""), "PLACA", client.get("carro_placa", ""))
    row_three("ANO", client.get("carro_ano", ""), "COR", "", "KM", "")

    # Descrição principal.
    pdf.ln(8)
    descricao_itens = "; ".join(
        f"{item.get('descricao', 'Item')} ({item.get('quantidade', 1)}x {dal.format_currency(item.get('valor_unitario', 0))})"
        for item in items
    )
    descricao_texto = (
        f'Recebi(emos) de {_pdf_safe_text(client.get("nome", "cliente não informado"))}, '
        f'a quantia de {dal.format_currency(valor_final)}, referente aos serviços/itens: {descricao_itens or "Itens do orçamento"}. '
        f'Orçamento #{budget_id} concluído em {_format_date(data_conclusao)}.'
    )
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, _pdf_safe_text(descricao_texto), border=1)

    # Observações.
    pdf.ln(4)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "OBSERVAÇÕES.", ln=1)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, "-", border=1)

    # Assinatura / selo pago.
    pdf.ln(6)
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, f"Data: {_format_date(data_conclusao)}", ln=1, align="R")
    pdf.cell(0, 5, f"Hora: {datetime.now().strftime('%H:%M:%S')}", ln=1, align="R")

    pdf.ln(6)
    pdf.set_fill_color(220, 60, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(25, 10, "PAGO", border=1, align="C", fill=True)

    pdf.set_xy(40, pdf.get_y() - 2)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, _pdf_safe_text(COMPANY_INFO.get("razao_social", "")), ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.set_xy(40, pdf.get_y())
    pdf.cell(0, 6, f"CNPJ: {_pdf_safe_text(COMPANY_INFO.get('cnpj', ''))}", ln=1)

    pdf.set_y(pdf.get_y() + 6)
    pdf.set_font("Arial", "I", 9)
    pdf.cell(0, 6, "Manaus - AM", ln=1, align="C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 6, data_conclusao.strftime("%Y"), ln=1, align="C")

    pdf_output = pdf.output(dest="S").encode("latin-1")
    buffer = BytesIO(pdf_output)
    buffer.seek(0)
    return buffer


@app.route("/orcamentos/novo", methods=["GET", "POST"])
def novo_orcamento():
    clients_df = dal.get_all_clients().fillna("")
    clients = clients_df.to_dict(orient="records")

    if request.method == "POST":
        client_id = int(request.form.get("id_cliente"))
        client = dal.get_client_by_id(client_id)
        if not client:
            flash("Cliente informado não existe.", "danger")
            return redirect(url_for("novo_orcamento"))

        payment_method = request.form.get("forma_pagamento", "PIX")
        if payment_method not in PAYMENT_OPTIONS:
            payment_method = "PIX"

        items = _build_budget_items_from_form(request.form)
        if not items:
            flash("Adicione pelo menos um item ao orçamento.", "warning")
            return redirect(url_for("novo_orcamento"))

        base_total = sum(item["subtotal"] for item in items)
        total, taxa = _calculate_total_with_payment(base_total, payment_method)
        texto_whatsapp = _generate_whatsapp_text(
            client["nome"], items, total, payment_method, taxa
        )

        data = {
            "id_cliente": client_id,
            "data_criacao": datetime.today().strftime("%Y-%m-%d"),
            "status": "Em análise",
            "itens": json.dumps(items, ensure_ascii=False),
            "valor_total": total,
            "texto_whatsapp": texto_whatsapp,
            "data_aprovacao": "",
            "data_conclusao": "",
            "forma_pagamento": payment_method,
        }
        new_id = dal.add_budget(data)
        flash("Orçamento criado com sucesso!", "success")
        return render_template(
            "orcamento_criado.html",
            orcamento_id=new_id,
            client=client,
            items=items,
            base_total=base_total,
            total=total,
            taxa=taxa,
            forma_pagamento=payment_method,
            texto_whatsapp=texto_whatsapp,
        )

    return render_template(
        "novo_orcamento.html",
        clients=clients,
        payment_options=PAYMENT_OPTIONS,
    )


@app.route("/orcamentos")
def listar_orcamentos():
    budgets_df = dal.get_all_budgets()
    clients_df = dal.get_all_clients()[["id_cliente", "nome"]]
    merged = budgets_df.merge(clients_df, left_on="id_cliente", right_on="id_cliente", how="left")
    merged = merged.sort_values("data_criacao", ascending=False)
    orcamentos = merged.to_dict(orient="records")
    for orcamento in orcamentos:
        status = orcamento.get("status") or ""
        is_finalizado = _is_budget_finalized(status)
        orcamento["is_finalizado"] = is_finalizado
        orcamento["can_efetivar"] = not is_finalizado
        orcamento["can_editar"] = not is_finalizado
        orcamento["can_reprovar"] = not is_finalizado
    return render_template("listar_orcamentos.html", orcamentos=orcamentos)


@app.route("/orcamentos/<int:budget_id>")
def detalhes_orcamento(budget_id: int):
    budget = dal.get_budget_by_id(budget_id)
    if not budget:
        flash("Orçamento não encontrado.", "danger")
        return redirect(url_for("listar_orcamentos"))

    client = dal.get_client_by_id(int(budget["id_cliente"]))
    items = dal.parse_budget_items(budget["itens"])
    base_total = sum(float(item.get("subtotal", item.get("quantidade", 0) * item.get("valor_unitario", 0)) or 0) for item in items)
    forma_pagamento = budget.get("forma_pagamento") or "PIX"
    if forma_pagamento not in PAYMENT_OPTIONS:
        forma_pagamento = "PIX"
    final_total = float(budget.get("valor_total", base_total) or base_total)
    taxa = max(0.0, round(final_total - base_total, 2))
    is_finalizado = _is_budget_finalized(budget.get("status"))

    return render_template(
        "detalhes_orcamento.html",
        budget=budget,
        client=client,
        items=items,
        base_total=base_total,
        final_total=final_total,
        taxa=taxa,
        forma_pagamento=forma_pagamento,
        can_efetivar=not is_finalizado,
        can_edit=not is_finalizado,
        can_reprovar=not is_finalizado,
    )


@app.route("/orcamentos/<int:budget_id>/editar", methods=["GET", "POST"])
def editar_orcamento(budget_id: int):
    budget = dal.get_budget_by_id(budget_id)
    if not budget:
        flash("Orçamento não encontrado.", "danger")
        return redirect(url_for("listar_orcamentos"))

    clients_df = dal.get_all_clients().fillna("")
    clients = clients_df.to_dict(orient="records")
    items = dal.parse_budget_items(budget["itens"])
    base_total = sum(
        float(
            item.get(
                "subtotal",
                item.get("quantidade", 0) * item.get("valor_unitario", 0),
            )
            or 0
        )
        for item in items
    )
    current_payment = budget.get("forma_pagamento") or "PIX"
    if current_payment not in PAYMENT_OPTIONS:
        current_payment = "PIX"
    final_total = float(budget.get("valor_total", base_total) or base_total)

    if request.method == "POST":
        client_id = int(request.form.get("id_cliente"))
        client = dal.get_client_by_id(client_id)
        if not client:
            flash("Cliente selecionado não existe.", "danger")
            return redirect(url_for("editar_orcamento", budget_id=budget_id))

        payment_method = request.form.get("forma_pagamento", current_payment)
        if payment_method not in PAYMENT_OPTIONS:
            payment_method = "PIX"

        updated_items = _build_budget_items_from_form(request.form)
        if not updated_items:
            flash("Inclua ao menos um item no orçamento.", "warning")
            return redirect(url_for("editar_orcamento", budget_id=budget_id))

        base_total = sum(item["subtotal"] for item in updated_items)
        total, taxa = _calculate_total_with_payment(base_total, payment_method)
        texto_whatsapp = _generate_whatsapp_text(
            client["nome"], updated_items, total, payment_method, taxa
        )

        dal.update_budget(
            budget_id,
            {
                "id_cliente": client_id,
                "itens": json.dumps(updated_items, ensure_ascii=False),
                "valor_total": total,
                "texto_whatsapp": texto_whatsapp,
                "forma_pagamento": payment_method,
            },
        )

        flash("Orçamento atualizado com sucesso!", "success")
        return redirect(url_for("detalhes_orcamento", budget_id=budget_id))

    return render_template(
        "editar_orcamento.html",
        budget=budget,
        clients=clients,
        items=items,
        payment_options=PAYMENT_OPTIONS,
        current_payment=current_payment,
        base_total=base_total,
        final_total=final_total,
    )


@app.route("/orcamentos/<int:budget_id>/pdf")
def gerar_pdf_orcamento(budget_id: int):
    budget = dal.get_budget_by_id(budget_id)
    if not budget:
        flash("Orçamento não encontrado.", "danger")
        return redirect(url_for("listar_orcamentos"))

    client = dal.get_client_by_id(int(budget["id_cliente"]))
    if not client:
        flash("Cliente associado ao orçamento não foi localizado.", "warning")
        return redirect(url_for("listar_orcamentos"))

    items = dal.parse_budget_items(budget["itens"])
    pdf_buffer = _generate_budget_pdf(budget, client, items)
    filename = f"orcamento_{budget_id}.pdf"
    pdf_buffer.seek(0)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


@app.route("/orcamentos/<int:budget_id>/recibo")
def gerar_recibo(budget_id: int):
    budget = dal.get_budget_by_id(budget_id)
    if not budget:
        flash("Orçamento não encontrado.", "danger")
        return redirect(url_for("listar_orcamentos"))

    client = dal.get_client_by_id(int(budget["id_cliente"]))
    if not client:
        flash("Cliente associado ao orçamento não foi localizado.", "warning")
        return redirect(url_for("listar_orcamentos"))

    items = dal.parse_budget_items(budget.get("itens", ""))
    base_total = sum(
        float(item.get("subtotal", item.get("quantidade", 0) * item.get("valor_unitario", 0)) or 0)
        for item in items
    )
    valor_final = float(budget.get("valor_total", base_total) or base_total)
    data_conclusao = pd.to_datetime(
        budget.get("data_conclusao") or budget.get("data_criacao") or datetime.today()
    )

    pdf_buffer = _generate_receipt_pdf(
        budget_id=budget_id,
        budget=budget,
        client=client,
        items=items,
        valor_final=valor_final,
        data_conclusao=data_conclusao,
    )
    filename = f"recibo_{budget_id}_{_slugify_filename(client.get('nome', ''))}.pdf"
    pdf_buffer.seek(0)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


@app.route("/orcamentos/<int:budget_id>/reprovar", methods=["POST"])
def reprovar_orcamento(budget_id: int):
    budget = dal.get_budget_by_id(budget_id)
    if not budget:
        flash("Orçamento não encontrado.", "danger")
        return redirect(url_for("listar_orcamentos"))

    dal.update_budget(
        budget_id,
        {
            "status": "Reprovado",
            "data_conclusao": datetime.today().strftime("%Y-%m-%d"),
        },
    )
    flash("Orçamento marcado como reprovado.", "info")
    return redirect(url_for("listar_orcamentos"))


@app.route("/orcamentos/<int:budget_id>/efetivar", methods=["GET", "POST"])
def efetivar_orcamento(budget_id: int):
    budget = dal.get_budget_by_id(budget_id)
    if not budget:
        flash("Orçamento não encontrado.", "danger")
        return redirect(url_for("listar_orcamentos"))
    if _is_budget_finalized(budget.get("status")):
        flash("Este orçamento já foi concluído e não pode ser efetivado novamente.", "info")
        return redirect(url_for("listar_orcamentos"))

    client = dal.get_client_by_id(int(budget["id_cliente"]))
    items = dal.parse_budget_items(budget["itens"])
    base_total = sum(
        float(item.get("subtotal", item.get("quantidade", 0) * item.get("valor_unitario", 0)) or 0)
        for item in items
    )

    if request.method == "POST":
        forma_pagamento = request.form.get("forma_pagamento", "")
        data_conclusao = _parse_date(request.form.get("data_conclusao"))
        status_final = request.form.get("status_final", "Concluído")
        if forma_pagamento not in PAYMENT_OPTIONS:
            flash("Escolha uma forma de pagamento válida.", "warning")
            return redirect(url_for("efetivar_orcamento", budget_id=budget_id))

        taxa = 0.0
        valor_final = base_total
        if forma_pagamento == "Cartão Crédito":
            taxa = round(base_total * 0.03, 2)
            valor_final = round(base_total + taxa, 2)

        dal.update_budget(
            budget_id,
            {
                "status": status_final,
                "data_aprovacao": data_conclusao.strftime("%Y-%m-%d"),
                "data_conclusao": data_conclusao.strftime("%Y-%m-%d"),
                "forma_pagamento": forma_pagamento,
                "valor_total": valor_final,
            },
        )

        for item in items:
            dal.add_service(
                {
                    "id_orcamento": budget_id,
                    "id_cliente": budget["id_cliente"],
                    "data_execucao": data_conclusao.strftime("%Y-%m-%d"),
                    "descricao_servico": item.get("descricao"),
                    "tipo_servico": item.get("tipo"),
                    "valor": item.get("subtotal"),
                    "observacoes": "",
                }
            )

        dal.add_financial_entry(
            {
                "data": data_conclusao.strftime("%Y-%m-%d"),
                "tipo_lancamento": "Entrada",
                "categoria": "Serviço Oficina",
                "descricao": f"Orçamento #{budget_id} - {client['nome']}",
                "valor": valor_final,
                "relacionado_orcamento_id": budget_id,
                "relacionado_servico_id": "",
            }
        )

        recibo_buffer = _generate_receipt_pdf(
            budget_id,
            budget,
            client,
            items,
            valor_final,
            data_conclusao,
        )
        filename = f"recibo_{budget_id}_{_slugify_filename(client.get('nome', ''))}.pdf"
        recibo_buffer.seek(0)
        return send_file(
            recibo_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )

    return render_template(
        "efetivar_orcamento.html",
        budget=budget,
        client=client,
        items=items,
        payment_options=PAYMENT_OPTIONS,
        base_total=base_total,
    )


@app.route("/financeiro", methods=["GET", "POST"])
def financeiro():
    if request.method == "POST":
        data = request.form.get("data_saida")
        tipo_despesa = request.form.get("tipo_despesa")
        categoria = request.form.get("categoria")
        descricao = request.form.get("descricao")
        valor = float(request.form.get("valor", "0") or 0)

        if tipo_despesa not in FINANCE_EXPENSE_TYPES:
            flash("Selecione um tipo de despesa válido.", "danger")
            return redirect(url_for("financeiro"))
        if categoria not in FINANCE_EXPENSE_TYPES[tipo_despesa]:
            flash("Selecione uma categoria correspondente ao tipo escolhido.", "danger")
            return redirect(url_for("financeiro"))

        dal.add_financial_entry(
            {
                "data": _parse_date(data).strftime("%Y-%m-%d"),
                "tipo_lancamento": "Saída",
                "categoria": f"{tipo_despesa} - {categoria}",
                "descricao": descricao,
                "valor": valor,
                "relacionado_orcamento_id": "",
                "relacionado_servico_id": "",
            }
        )
        flash("Despesa registrada com sucesso.", "success")
        return redirect(url_for("financeiro"))

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    tipo = request.args.get("tipo")

    entries_df = dal.get_all_financial_entries()
    entries_df["data"] = pd.to_datetime(entries_df["data"], errors="coerce")

    if data_inicio:
        entries_df = entries_df[entries_df["data"] >= _parse_date(data_inicio)]
    if data_fim:
        entries_df = entries_df[entries_df["data"] <= _parse_date(data_fim)]
    if tipo in {"Entrada", "Saída"}:
        entries_df = entries_df[entries_df["tipo_lancamento"] == tipo]

    entries_df = entries_df.sort_values("data", ascending=False)
    total_entradas = entries_df[entries_df["tipo_lancamento"] == "Entrada"]["valor"].sum()
    total_saidas = entries_df[entries_df["tipo_lancamento"] == "Saída"]["valor"].sum()

    entries = []
    for entry in entries_df.to_dict(orient="records"):
        entry["data_formatada"] = _format_date(entry["data"])
        entries.append(entry)

    return render_template(
        "financeiro.html",
        entries=entries,
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        saldo=total_entradas - total_saidas,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo=tipo,
        expense_types=FINANCE_EXPENSE_TYPES,
    )


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG") == "1"

    def open_browser():
        webbrowser.open_new("http://127.0.0.1:5000/")

    # Abre o navegador automaticamente (pode desativar com FLASK_NO_BROWSER=1).
    if not os.environ.get("FLASK_NO_BROWSER") and not os.environ.get("WERKZEUG_RUN_MAIN"):
        Timer(1, open_browser).start()

    # Em executável, roda sem debugger nem reloader para evitar erros de assets.
    app.run(debug=debug_mode, use_reloader=debug_mode)
