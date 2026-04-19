"""
Camada de acesso a dados usando PostgreSQL (Supabase).

Configure a variável de ambiente DATABASE_URL com a connection string do Supabase:
  postgresql://postgres:<senha>@db.<projeto>.supabase.co:5432/postgres

Localmente: crie um arquivo .env com DATABASE_URL=... e use python-dotenv,
ou exporte a variável antes de rodar: set DATABASE_URL=...
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Colunas mantidas para compatibilidade com o restante do app
CLIENT_COLUMNS = [
    "id_cliente", "nome", "telefone_whatsapp", "email",
    "endereco_rua", "endereco_numero", "endereco_bairro",
    "endereco_cidade", "endereco_uf", "endereco_cep",
    "carro_marca", "carro_modelo", "carro_ano", "carro_placa", "observacoes",
]
ORCAMENTO_COLUMNS = [
    "id_orcamento", "id_cliente", "data_criacao", "status", "carro_km",
    "carro_cor", "responsavel_planejado_id", "responsavel_planejado_nome",
    "itens", "valor_total", "texto_whatsapp", "data_aprovacao",
    "data_conclusao", "forma_pagamento",
]
SERVICO_COLUMNS = [
    "id_servico", "id_orcamento", "id_cliente", "data_execucao",
    "descricao_servico", "tipo_servico", "valor", "observacoes", "responsavel",
]
FINANCEIRO_COLUMNS = [
    "id_lancamento", "data", "tipo_lancamento", "categoria", "descricao",
    "valor", "relacionado_orcamento_id", "relacionado_servico_id",
]
FUNCIONARIOS_COLUMNS = [
    "id_funcionario", "nome", "telefone", "cargo", "observacoes", "ativo",
]


def _get_conn():
    """Abre uma conexão PostgreSQL. Lança erro claro se DATABASE_URL não estiver configurada."""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL não configurada. Exporte a variável de ambiente antes de iniciar."
        )
    # Supabase exige SSL; psycopg2 usa sslmode=require por padrão para URLs postgres://
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db() -> None:
    """Cria todas as tabelas caso ainda não existam. Chamar uma vez na inicialização."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id_cliente      SERIAL PRIMARY KEY,
                    nome            TEXT,
                    telefone_whatsapp TEXT,
                    email           TEXT,
                    endereco_rua    TEXT,
                    endereco_numero TEXT,
                    endereco_bairro TEXT,
                    endereco_cidade TEXT,
                    endereco_uf     TEXT,
                    endereco_cep    TEXT,
                    carro_marca     TEXT,
                    carro_modelo    TEXT,
                    carro_ano       TEXT,
                    carro_placa     TEXT,
                    observacoes     TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orcamentos (
                    id_orcamento               SERIAL PRIMARY KEY,
                    id_cliente                 INTEGER,
                    data_criacao               TEXT,
                    status                     TEXT,
                    carro_km                   TEXT,
                    carro_cor                  TEXT,
                    responsavel_planejado_id   TEXT,
                    responsavel_planejado_nome TEXT,
                    itens                      TEXT,
                    valor_total                NUMERIC,
                    texto_whatsapp             TEXT,
                    data_aprovacao             TEXT,
                    data_conclusao             TEXT,
                    forma_pagamento            TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS servicos (
                    id_servico        SERIAL PRIMARY KEY,
                    id_orcamento      INTEGER,
                    id_cliente        INTEGER,
                    data_execucao     TEXT,
                    descricao_servico TEXT,
                    tipo_servico      TEXT,
                    valor             NUMERIC,
                    observacoes       TEXT,
                    responsavel       TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS financeiro (
                    id_lancamento           SERIAL PRIMARY KEY,
                    data                    TEXT,
                    tipo_lancamento         TEXT,
                    categoria               TEXT,
                    descricao               TEXT,
                    valor                   NUMERIC,
                    relacionado_orcamento_id INTEGER,
                    relacionado_servico_id   INTEGER
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS funcionarios (
                    id_funcionario SERIAL PRIMARY KEY,
                    nome           TEXT,
                    telefone       TEXT,
                    cargo          TEXT,
                    observacoes    TEXT,
                    ativo          TEXT
                )
            """)
        conn.commit()
        logger.info("Tabelas verificadas/criadas com sucesso.")
    finally:
        conn.close()


def _rows_to_df(rows, columns: List[str]) -> pd.DataFrame:
    """Converte lista de RealDictRow em DataFrame com as colunas corretas."""
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame([dict(r) for r in rows])
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


# ---------------------------
# Clientes
# ---------------------------

def get_all_clients() -> pd.DataFrame:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clientes ORDER BY id_cliente")
            return _rows_to_df(cur.fetchall(), CLIENT_COLUMNS)
    finally:
        conn.close()


def get_client_by_id(client_id: int) -> Optional[Dict]:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clientes WHERE id_cliente = %s", (client_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def add_client(data: Dict) -> int:
    data.pop("id_cliente", None)
    cols = [c for c in CLIENT_COLUMNS if c != "id_cliente"]
    values = [data.get(c) for c in cols]
    sql = (
        f"INSERT INTO clientes ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id_cliente"
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            new_id = cur.fetchone()["id_cliente"]
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_client(client_id: int, data: Dict) -> bool:
    data.pop("id_cliente", None)
    if not data:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in data)
    values = list(data.values()) + [client_id]
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE clientes SET {set_clause} WHERE id_cliente = %s",
                values,
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()


# ---------------------------
# Orçamentos
# ---------------------------

def get_all_budgets() -> pd.DataFrame:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orcamentos ORDER BY id_orcamento")
            return _rows_to_df(cur.fetchall(), ORCAMENTO_COLUMNS)
    finally:
        conn.close()


def get_budget_by_id(budget_id: int) -> Optional[Dict]:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orcamentos WHERE id_orcamento = %s", (budget_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def add_budget(data: Dict) -> int:
    data.pop("id_orcamento", None)
    cols = [c for c in ORCAMENTO_COLUMNS if c != "id_orcamento"]
    values = [data.get(c) for c in cols]
    sql = (
        f"INSERT INTO orcamentos ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id_orcamento"
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            new_id = cur.fetchone()["id_orcamento"]
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_budget(budget_id: int, data: Dict) -> bool:
    data.pop("id_orcamento", None)
    if not data:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in data)
    values = list(data.values()) + [budget_id]
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE orcamentos SET {set_clause} WHERE id_orcamento = %s",
                values,
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()


# ---------------------------
# Serviços
# ---------------------------

def get_all_services() -> pd.DataFrame:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM servicos ORDER BY id_servico")
            return _rows_to_df(cur.fetchall(), SERVICO_COLUMNS)
    finally:
        conn.close()


def add_service(data: Dict) -> int:
    data.pop("id_servico", None)
    cols = [c for c in SERVICO_COLUMNS if c != "id_servico"]
    values = [data.get(c) for c in cols]
    sql = (
        f"INSERT INTO servicos ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id_servico"
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            new_id = cur.fetchone()["id_servico"]
        conn.commit()
        return new_id
    finally:
        conn.close()


# ---------------------------
# Financeiro
# ---------------------------

def get_all_financial_entries() -> pd.DataFrame:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM financeiro ORDER BY id_lancamento")
            return _rows_to_df(cur.fetchall(), FINANCEIRO_COLUMNS)
    finally:
        conn.close()


def add_financial_entry(data: Dict) -> int:
    data.pop("id_lancamento", None)
    cols = [c for c in FINANCEIRO_COLUMNS if c != "id_lancamento"]
    values = [data.get(c) for c in cols]
    sql = (
        f"INSERT INTO financeiro ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id_lancamento"
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            new_id = cur.fetchone()["id_lancamento"]
        conn.commit()
        return new_id
    finally:
        conn.close()


# ---------------------------
# Funcionários
# ---------------------------

def get_all_employees() -> pd.DataFrame:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM funcionarios ORDER BY id_funcionario")
            return _rows_to_df(cur.fetchall(), FUNCIONARIOS_COLUMNS)
    finally:
        conn.close()


def get_employee_by_id(employee_id: int) -> Optional[Dict]:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM funcionarios WHERE id_funcionario = %s", (employee_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def add_employee(data: Dict) -> int:
    data.pop("id_funcionario", None)
    cols = [c for c in FUNCIONARIOS_COLUMNS if c != "id_funcionario"]
    values = [data.get(c) for c in cols]
    sql = (
        f"INSERT INTO funcionarios ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id_funcionario"
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            new_id = cur.fetchone()["id_funcionario"]
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_employee(employee_id: int, data: Dict) -> bool:
    data.pop("id_funcionario", None)
    if not data:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in data)
    values = list(data.values()) + [employee_id]
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE funcionarios SET {set_clause} WHERE id_funcionario = %s",
                values,
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()


# ---------------------------
# Utilitários (mantidos idênticos)
# ---------------------------

def ensure_all_files_exist() -> None:
    """Compatibilidade: agora inicializa o banco em vez de criar arquivos."""
    init_db()


def get_data_files() -> Dict[str, str]:
    return {}


def parse_budget_items(items_json: str) -> List[Dict]:
    if not items_json:
        return []
    try:
        return json.loads(items_json)
    except json.JSONDecodeError:
        return []


def serialize_budget_items(items: List[Dict]) -> str:
    return json.dumps(items, ensure_ascii=False)


def format_currency(value: float) -> str:
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def month_boundaries(date: datetime) -> Dict[str, datetime]:
    first_day = date.replace(day=1)
    if date.month == 12:
        next_month = date.replace(year=date.year + 1, month=1, day=1)
    else:
        next_month = date.replace(month=date.month + 1, day=1)
    last_day = next_month - pd.Timedelta(days=1)
    return {"start": first_day, "end": last_day}
