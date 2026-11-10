# WakaTime — ativação dos gráficos do perfil

O GitHub Actions usa Python para gerar SVGs locais consultando somente a API oficial do WakaTime. Não há serviço terceirizado recebendo tokens.

## Uma única configuração manual

1. Abra https://wakatime.com/oauth e gere um **token OAuth pessoal** com permissão de leitura das suas estatísticas. Não use a API Key da extensão de programação.
2. Acesse https://github.com/axrobert/axrobert/settings/secrets/actions e clique em **New repository secret**.
3. Nome: WAKATIME_OAUTH_TOKEN. Valor: token OAuth pessoal. Não compartilhe esse valor.
4. Após integrar o PR na main, execute: https://github.com/axrobert/axrobert/actions/workflows/wakatime-stats.yml (Run workflow).

## Comportamento

- Consulta estatísticas oficiais dos últimos 30 e 7 dias e resumos diários.
- Preserva os quatro caminhos de SVG existentes no README.
- O ranking não inventa posições. Em caso de ausência de posição confirmada, exibe “Sem posição pública disponível”.
- Execução agendada a cada 6 horas ou manual.
- Falhas de autenticação, dados ou XML interrompem o workflow antes da publicação; os arquivos existentes não são sobrescritos por cartões de erro.
- Nenhum token do GitHub é repassado a sites terceiros.
- Não necessita instalar pacotes de Python.

## Diagnóstico

- Sem WAKATIME_OAUTH_TOKEN: configure o secret conforme acima.
- HTTP 401/403: confirme o OAuth e suas permissões; API Key de plugin não é compatível.
- Dados vazios: verifique se seu editor registra atividade no WakaTime.
- Falha no push: confirme a permissão de escrita para GitHub Actions e proteção da branch.

## Testes locais sem credenciais

python -m unittest discover -s tests -p 'test_wakatime*.py' -v

Este PR corrige o gerador, mas não repara os SVGs antigos até a primeira execução bem-sucedida após configurar o OAuth.
