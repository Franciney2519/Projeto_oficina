# Manual de Uso - Oficina Mecânica

Este manual é para usuários finais operarem o sistema (executável ou desenvolvedor). Cada seção indica onde clicar e o que preencher.

## Acesso e login
- Não há login. Abra pp.exe (onefile) ou pp/app.exe (onedir) e o navegador abrirá em http://127.0.0.1:5000/.

## Menu principal
- Dashboard: visão geral.
- Clientes: cadastro e edição de clientes.
- Histórico de Serviços: lista serviços executados, com filtro por cliente.
- Orçamentos: criar, listar, editar, aprovar/concluir, gerar PDF/recibo.
- Financeiro: registrar despesas e filtrar entradas/saídas.

## Dashboard
- Filtro de período: escolha Mês e Ano e clique em “Aplicar” (ou “Limpar” para voltar ao atual).
- Cartões: Clientes cadastrados (total), Orçamentos em aberto (status diferente de “Concluído”), Saldo do período (entradas – saídas).
- Gráfico: barras de Entradas/ Saídas e linha de Saldo dos últimos 12 meses.
- Ações rápidas: links para Clientes, Novo orçamento, Orçamentos, Financeiro.

## Clientes
1) Clique em “Clientes”.
2) Para cadastrar: preencha Nome, WhatsApp, e dados do veículo (placa, modelo, etc.) e salve.
3) Para editar: clique em “Editar” no cliente desejado, ajuste campos e salve.
4) Histórico do cliente: botão “Histórico” mostra serviços realizados; filtre por data se quiser.

## Orçamentos
### Criar novo
1) Menu “Novo Orçamento” ou “Orçamentos” → “Novo”.
2) Selecione o cliente, informe forma de pagamento e adicione itens (descrição, tipo, quantidade, valor unitário).
3) Salve. A tela mostra resumo, texto para WhatsApp e botão “Baixar PDF”.

### Listar e detalhes
- Menu “Orçamentos”: lista mais recentes primeiro. Ações: Detalhar, Editar, Efetivar (se não concluído), Baixar PDF, Reprovar.
- Detalhes: mostra itens, valores e texto para WhatsApp com link de envio.

### Efetivar (aprovar/concluir)
1) Em “Detalhes”, clique “Efetivar”.
2) Escolha Forma de pagamento e Data.
3) Escolha Status final:
   - “Aprovado (aguardando execução)”: apenas marca aprovação; **não** gera financeiro, serviços ou recibo.
   - “Concluído”: grava serviços, cria lançamento de entrada no financeiro, ajusta valor com taxa se cartão, e abre a tela de pagamento concluído.
4) Tela de pagamento concluído: botões “Baixar comprovante” (recibo PDF) e “Enviar via WhatsApp” com mensagem pronta. O recibo só fica disponível se concluído.

### Observações
- Pagamento no cartão aplica taxa de 3% (já calculada).
- Recibo só é liberado para status concluído.

## Histórico de Serviços
- Menu “Histórico de Serviços”: lista os serviços com cliente, valor, data, status do orçamento. Filtre por cliente no seletor superior.

## Financeiro
### Registrar despesa
1) Menu “Financeiro”.
2) Preencha Data, Tipo de despesa, Categoria (conforme o tipo), Descrição e Valor.
3) Salve. A despesa é lançada como saída.

### Filtrar lançamentos
- Filtros por data inicial/final e por tipo (Entrada ou Saída). Clique em “Filtrar”.
- A tela mostra total de entradas, saídas e saldo do período filtrado.

## Geração de PDFs e WhatsApp
- Orçamento PDF: botão “Baixar PDF” nas telas de orçamento criado ou detalhes.
- Recibo PDF: botão “Baixar comprovante” na tela de pagamento concluído (apenas com status concluído).
- WhatsApp: links prontos em “Orçamento criado” (texto de orçamento), “Detalhes do orçamento”, e na tela de “Pagamento concluído” (confirmação de pagamento).

## Arquivos e dados
- Planilhas Excel ficam na mesma pasta do executável ou na pasta _internal do bundle. São criadas automaticamente se não existirem.
- Ao atualizar/editar planilhas externamente, clique em “Atualizar base” no menu para recarregar.

## Dicas e resolução de problemas
- Se o navegador não abrir: acesse manualmente http://127.0.0.1:5000/.
- Se aparecer erro de dados: use “Atualizar base” para recriar/validar planilhas.
- Recibo não aparece? Verifique se o orçamento está como “Concluído”.
- Para ambiente de testes, copie as planilhas para outro diretório e rode o app lá.
