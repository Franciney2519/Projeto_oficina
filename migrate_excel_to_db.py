"""
Script de migração única: importa dados dos arquivos Excel para o PostgreSQL.

Como usar:
    1. Configure DATABASE_URL no arquivo .env ou como variável de ambiente.
    2. Execute: python migrate_excel_to_db.py
    3. Execute apenas UMA vez. Rodar novamente vai duplicar os registros.
"""
import os
import sys

# Carrega .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não configurada. Configure o .env e tente novamente.")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EXCEL_FILES = {
    "clientes":    os.path.join(BASE_DIR, "dados_clientes.xlsx"),
    "orcamentos":  os.path.join(BASE_DIR, "dados_orcamentos.xlsx"),
    "servicos":    os.path.join(BASE_DIR, "dados_servicos.xlsx"),
    "financeiro":  os.path.join(BASE_DIR, "dados_financeiro.xlsx"),
    "funcionarios": os.path.join(BASE_DIR, "dados_funcionarios.xlsx"),
}

TABLE_ID_MAP = {
    "clientes":    "id_cliente",
    "orcamentos":  "id_orcamento",
    "servicos":    "id_servico",
    "financeiro":  "id_lancamento",
    "funcionarios": "id_funcionario",
}


def get_conn():
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def create_tables(conn):
    """Cria todas as tabelas no banco antes de migrar."""
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
                id_lancamento            SERIAL PRIMARY KEY,
                data                     TEXT,
                tipo_lancamento          TEXT,
                categoria                TEXT,
                descricao                TEXT,
                valor                    NUMERIC,
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
    print("  Tabelas criadas com sucesso.\n")


def migrate_table(conn, table_name: str, excel_path: str, id_col: str):
    if not os.path.exists(excel_path):
        print(f"  [PULAR] Arquivo não encontrado: {excel_path}")
        return 0

    df = pd.read_excel(excel_path, engine="openpyxl")
    if df.empty:
        print(f"  [VAZIO] {excel_path} não tem dados.")
        return 0

    # Converte NaN para None
    df = df.where(pd.notnull(df), None)

    # Pandas lê colunas inteiras com NaN como float64 (ex: 1.0).
    # Colunas de ID precisam ser int para o PostgreSQL aceitar.
    for col in df.columns:
        if df[col].dtype == object:
            continue
        if 'id' in col.lower() or col in ('relacionado_orcamento_id', 'relacionado_servico_id'):
            df[col] = df[col].apply(lambda x: int(x) if x is not None else None)

    rows = df.to_dict(orient="records")

    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            cols = list(row.keys())
            vals = [row[c] for c in cols]
            placeholders = ", ".join(["%s"] * len(cols))
            col_names = ", ".join(cols)
            sql = (
                f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT ({id_col}) DO NOTHING"
            )
            try:
                cur.execute(sql, vals)
                inserted += cur.rowcount
            except Exception as e:
                print(f"  [ERRO] Linha ignorada ({row.get(id_col)}): {e}")
                conn.rollback()
                # Reabre cursor após rollback
                cur = conn.cursor()
    conn.commit()
    return inserted


def reset_sequences(conn):
    """Atualiza as sequences dos IDs para evitar conflito após inserção direta."""
    tables = {
        "clientes":    "id_cliente",
        "orcamentos":  "id_orcamento",
        "servicos":    "id_servico",
        "financeiro":  "id_lancamento",
        "funcionarios": "id_funcionario",
    }
    with conn.cursor() as cur:
        for table, id_col in tables.items():
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{id_col}'), "
                f"COALESCE(MAX({id_col}), 0) + 1, false) FROM {table}"
            )
    conn.commit()
    print("  Sequences dos IDs atualizadas.")


def main():
    print("=== Migração Excel → PostgreSQL ===\n")
    conn = get_conn()
    try:
        print("Criando tabelas no banco...")
        create_tables(conn)

        for table, excel_path in EXCEL_FILES.items():
            id_col = TABLE_ID_MAP[table]
            print(f"Migrando tabela '{table}'...")
            count = migrate_table(conn, table, excel_path, id_col)
            print(f"  {count} registro(s) inserido(s).\n")

        print("Atualizando sequences...")
        reset_sequences(conn)

        print("\n=== Migração concluída com sucesso! ===")
        print("Você já pode fazer o deploy na nuvem.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
