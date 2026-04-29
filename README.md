# Oficina Mecânica — R R A AUTOS

Aplicação web em Flask para gestão completa de uma oficina mecânica: clientes, veículos, orçamentos, serviços, financeiro e funcionários. Usa PostgreSQL (Supabase) como banco de dados e pode ser implantado em Railway, Render ou qualquer plataforma compatível com Python + Gunicorn.

---

## Funcionalidades

- **Clientes e veículos**: cadastro de clientes com múltiplos veículos (marca, modelo, ano, placa, cor). Veículos podem ser adicionados, editados e removidos individualmente.
- **Orçamentos**: criação com seleção de cliente e veículo específico, adição dinâmica de itens (produto/serviço/outros), cálculo automático com taxa de 3% para cartão de crédito.
- **Fluxo de orçamento**:
  - `Em análise` → `Aprovado` (aguarda execução, sem lançamento financeiro) → `Concluído` (gera serviços + entrada no financeiro + comprovante)
  - Ou diretamente `Reprovado`
- **PDF e WhatsApp**: geração de PDF de orçamento e recibo; texto pronto para envio via WhatsApp.
- **Financeiro**: lançamentos de entrada e saída, com geração automática ao concluir orçamentos.
- **Dashboard**: cartões com KPIs do mês (clientes, orçamentos em aberto, saldo) e gráfico de barras dos últimos 12 meses (entradas, saídas, saldo).
- **Funcionários**: cadastro com ativação/desativação.

---

## Requisitos

- Python 3.10+
- PostgreSQL (Supabase ou outro)
- Dependências: `flask`, `pandas`, `psycopg2-binary`, `fpdf2`, `gunicorn`, `python-dotenv`, `pillow` (opcional)

---

## Configuração local

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz:

```
DATABASE_URL=postgresql://usuario:senha@host:5432/postgres
SECRET_KEY=sua-chave-secreta
APP_USERNAME=admin
APP_PASSWORD=sua-senha
```

Inicie:

```bash
python app.py
```

A aplicação abre em `http://127.0.0.1:5000/`.

---

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | — | Connection string PostgreSQL (obrigatória) |
| `SECRET_KEY` | `oficina-mecanica-secret-dev` | Chave de sessão Flask |
| `APP_USERNAME` | `admin` | Usuário do login |
| `APP_PASSWORD` | `oficina123` | Senha do login |

---

## Banco de dados

As tabelas são criadas automaticamente na primeira execução via `init_db()` em `data_access.py`. Ao inicializar, o sistema também:

- Cria a tabela `veiculos` (separada de `clientes`)
- Adiciona a coluna `id_veiculo` em `orcamentos` (se não existir)
- Migra automaticamente os dados de carro já presentes nos registros de clientes para a nova tabela `veiculos`

### Tabelas

| Tabela | Descrição |
|---|---|
| `clientes` | Dados pessoais e de endereço |
| `veiculos` | Veículos por cliente (múltiplos por cliente) |
| `orcamentos` | Orçamentos com vínculo a cliente e veículo |
| `servicos` | Serviços executados (gerados ao concluir orçamento) |
| `financeiro` | Lançamentos financeiros |
| `funcionarios` | Funcionários da oficina |

---

## Segurança (Supabase RLS)

Se o advisor do Supabase exportar erros `rls_disabled_in_public`, use:

```bash
python exportar_seguranca_supabase.py --csv "c:\caminho\Supabase Performance Security Lints (...).csv" --out supabase_security_hardening.sql
```

Depois execute o arquivo `supabase_security_hardening.sql` no SQL Editor do Supabase.

---

## Implantação (Railway / Render)

Configure as variáveis de ambiente na plataforma. O `Procfile` já está configurado para Gunicorn:

```
web: gunicorn app:app
```

O `ProxyFix` já está ativado para reconhecer HTTPS atrás do proxy da plataforma.

---

## Estrutura principal

```
app.py            — Rotas Flask, lógica de negócio, geração de PDFs
data_access.py    — CRUD no PostgreSQL (psycopg2)
templates/        — HTML com Bootstrap 5 + Chart.js
static/           — Arquivos estáticos (logo, CSS adicional)
```

---

## Configurações de negócio

No topo de `app.py`:

- `COMPANY_INFO` — razão social, CNPJ, endereço e telefone usados nos PDFs
- `PAYMENT_OPTIONS` — formas de pagamento disponíveis
- `_calculate_total_with_payment` — lógica de taxa (atualmente 3% para cartão de crédito)
- `VALIDADE_PADRAO` / `OBSERVACOES_PADRAO` — textos padrão no PDF de orçamento
