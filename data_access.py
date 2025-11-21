"""
Camada de acesso a dados baseada em arquivos Excel.

Cada função deste módulo garante que o arquivo exista antes de ler ou
escrever e mantém a lógica de geração de IDs incrementais. Esta
abordagem facilita a futura migração para bancos de dados tradicionais.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Diretórios e arquivos baseados no diretório atual do projeto.
# Quando empacotado com PyInstaller usamos o diretório do executável.
if getattr(sys, "frozen", False):
    base_dir = os.path.dirname(sys.executable)
    internal_dir = os.path.join(base_dir, "_internal")
    if os.path.exists(os.path.join(internal_dir, "dados_clientes.xlsx")):
        BASE_DIR = internal_dir
    else:
        BASE_DIR = base_dir
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILES = {
    "clientes": os.path.join(BASE_DIR, "dados_clientes.xlsx"),
    "orcamentos": os.path.join(BASE_DIR, "dados_orcamentos.xlsx"),
    "servicos": os.path.join(BASE_DIR, "dados_servicos.xlsx"),
    "financeiro": os.path.join(BASE_DIR, "dados_financeiro.xlsx"),
    "funcionarios": os.path.join(BASE_DIR, "dados_funcionarios.xlsx"),
}

# Definição de colunas para cada planilha.
CLIENT_COLUMNS = [
    "id_cliente",
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
ORCAMENTO_COLUMNS = [
    "id_orcamento",
    "id_cliente",
    "data_criacao",
    "status",
    "carro_km",
    "carro_cor",
    "responsavel_planejado_id",
    "responsavel_planejado_nome",
    "itens",
    "valor_total",
    "texto_whatsapp",
    "data_aprovacao",
    "data_conclusao",
    "forma_pagamento",
]
SERVICO_COLUMNS = [
    "id_servico",
    "id_orcamento",
    "id_cliente",
    "data_execucao",
    "descricao_servico",
    "tipo_servico",
    "valor",
    "observacoes",
    "responsavel",
]
FINANCEIRO_COLUMNS = [
    "id_lancamento",
    "data",
    "tipo_lancamento",
    "categoria",
    "descricao",
    "valor",
    "relacionado_orcamento_id",
    "relacionado_servico_id",
]
FUNCIONARIOS_COLUMNS = [
    "id_funcionario",
    "nome",
    "telefone",
    "cargo",
    "observacoes",
    "ativo",
]


def _ensure_file(path: str, columns: List[str]) -> None:
    """Cria o arquivo Excel com as colunas corretas caso ele não exista."""
    if not os.path.exists(path):
        df = pd.DataFrame(columns=columns)
        df.to_excel(path, index=False, engine="openpyxl")
        logger.info("Arquivo de dados criado: %s", path)


def _load_dataframe(path: str, columns: List[str]) -> pd.DataFrame:
    """Carrega a planilha garantindo que ela exista."""
    _ensure_file(path, columns)
    return pd.read_excel(path, engine="openpyxl")


def _save_dataframe(path: str, df: pd.DataFrame) -> None:
    """Salva o DataFrame no arquivo correspondente."""
    df.to_excel(path, index=False, engine="openpyxl")
    logger.info("Dados salvos em %s (%d registros)", path, len(df))


def _get_next_id(df: pd.DataFrame, id_column: str) -> int:
    """Retorna o próximo ID incremental para a coluna informada."""
    if df.empty:
        return 1
    return int(df[id_column].max()) + 1


# ---------------------------
# Funções para clientes
# ---------------------------
def get_all_clients() -> pd.DataFrame:
    return _load_dataframe(DATA_FILES["clientes"], CLIENT_COLUMNS)


def get_client_by_id(client_id: int) -> Optional[Dict]:
    df = get_all_clients()
    if df.empty:
        return None
    row = df[df["id_cliente"] == client_id]
    if row.empty:
        return None
    return row.iloc[0].to_dict()


def add_client(data: Dict) -> int:
    df = get_all_clients()
    new_id = _get_next_id(df, "id_cliente")
    data["id_cliente"] = new_id
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    _save_dataframe(DATA_FILES["clientes"], df)
    return new_id


def update_client(client_id: int, data: Dict) -> bool:
    df = get_all_clients()
    if df.empty:
        return False
    idx = df.index[df["id_cliente"] == client_id]
    if len(idx) == 0:
        return False
    for key, value in data.items():
        df.loc[idx, key] = value
    _save_dataframe(DATA_FILES["clientes"], df)
    return True


# ---------------------------
# Funções para orçamentos
# ---------------------------
def get_all_budgets() -> pd.DataFrame:
    return _load_dataframe(DATA_FILES["orcamentos"], ORCAMENTO_COLUMNS)


def get_budget_by_id(budget_id: int) -> Optional[Dict]:
    df = get_all_budgets()
    filtered = df[df["id_orcamento"] == budget_id]
    if filtered.empty:
        return None
    return filtered.iloc[0].to_dict()


def add_budget(data: Dict) -> int:
    df = get_all_budgets()
    new_id = _get_next_id(df, "id_orcamento")
    data["id_orcamento"] = new_id
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    _save_dataframe(DATA_FILES["orcamentos"], df)
    return new_id


def update_budget(budget_id: int, data: Dict) -> bool:
    df = get_all_budgets()
    idx = df.index[df["id_orcamento"] == budget_id]
    if len(idx) == 0:
        return False
    for key, value in data.items():
        df.loc[idx, key] = value
    _save_dataframe(DATA_FILES["orcamentos"], df)
    return True


# ---------------------------
# Funções para serviços
# ---------------------------
def get_all_services() -> pd.DataFrame:
    return _load_dataframe(DATA_FILES["servicos"], SERVICO_COLUMNS)


def add_service(data: Dict) -> int:
    df = get_all_services()
    new_id = _get_next_id(df, "id_servico")
    data["id_servico"] = new_id
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    _save_dataframe(DATA_FILES["servicos"], df)
    return new_id


# ---------------------------
# Funções para financeiro
# ---------------------------
def get_all_financial_entries() -> pd.DataFrame:
    return _load_dataframe(DATA_FILES["financeiro"], FINANCEIRO_COLUMNS)


def add_financial_entry(data: Dict) -> int:
    df = get_all_financial_entries()
    new_id = _get_next_id(df, "id_lancamento")
    data["id_lancamento"] = new_id
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    _save_dataframe(DATA_FILES["financeiro"], df)
    return new_id


# ---------------------------
# Funções para funcionários
# ---------------------------
def get_all_employees() -> pd.DataFrame:
    return _load_dataframe(DATA_FILES["funcionarios"], FUNCIONARIOS_COLUMNS)


def get_employee_by_id(employee_id: int) -> Optional[Dict]:
    df = get_all_employees()
    filtered = df[df["id_funcionario"] == employee_id]
    if filtered.empty:
        return None
    return filtered.iloc[0].to_dict()


def add_employee(data: Dict) -> int:
    df = get_all_employees()
    new_id = _get_next_id(df, "id_funcionario")
    data["id_funcionario"] = new_id
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    _save_dataframe(DATA_FILES["funcionarios"], df)
    return new_id


def update_employee(employee_id: int, data: Dict) -> bool:
    df = get_all_employees()
    idx = df.index[df["id_funcionario"] == employee_id]
    if len(idx) == 0:
        return False
    for key, value in data.items():
        df.loc[idx, key] = value
    _save_dataframe(DATA_FILES["funcionarios"], df)
    return True


# ---------------------------
# Utilidades diversas
# ---------------------------
def get_data_files() -> Dict[str, str]:
    """Retorna um mapeamento com o caminho completo de cada planilha."""
    return DATA_FILES.copy()


def ensure_all_files_exist() -> None:
    """Utilitário chamado no início da aplicação para garantir os arquivos."""
    _ensure_file(DATA_FILES["clientes"], CLIENT_COLUMNS)
    _ensure_file(DATA_FILES["orcamentos"], ORCAMENTO_COLUMNS)
    _ensure_file(DATA_FILES["servicos"], SERVICO_COLUMNS)
    _ensure_file(DATA_FILES["financeiro"], FINANCEIRO_COLUMNS)
    _ensure_file(DATA_FILES["funcionarios"], FUNCIONARIOS_COLUMNS)


def parse_budget_items(items_json: str) -> List[Dict]:
    """Converte a string JSON de itens em lista de dicionários."""
    if not items_json:
        return []
    try:
        return json.loads(items_json)
    except json.JSONDecodeError:
        return []


def serialize_budget_items(items: List[Dict]) -> str:
    """Serializa os itens de orçamento para armazenar na planilha."""
    return json.dumps(items, ensure_ascii=False)


def format_currency(value: float) -> str:
    """Retorna valores numéricos formatados."""
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def month_boundaries(date: datetime) -> Dict[str, datetime]:
    """Retorna o primeiro e o último dia do mês para facilitar filtros."""
    first_day = date.replace(day=1)
    if date.month == 12:
        next_month = date.replace(year=date.year + 1, month=1, day=1)
    else:
        next_month = date.replace(month=date.month + 1, day=1)
    last_day = next_month - pd.Timedelta(days=1)
    return {"start": first_day, "end": last_day}
