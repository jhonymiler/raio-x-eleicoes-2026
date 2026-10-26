# benford-eleicoes-2026

Análise forense de Benford sobre dados eleitorais oficiais do TSE.
Orientação de uso em [README.md](README.md); teoria em [docs/benford-teoria.md](docs/benford-teoria.md).

## Fatos do repositório

- **Sem dependências externas.** Python 3.11+ e stdlib apenas. χ², Kuiper e a
  gama incompleta regularizada estão implementados em `scripts/benford.py`.
  Não adicionar numpy/scipy/pandas sem necessidade medida.
- `dados/` tem ~2,9 GB e está no `.gitignore`. Os CSVs do TSE são **latin-1**,
  delimitados por `;`, com campos entre aspas.
- O CSV por seção de 2022 contém os dois turnos (campo `NR_TURNO`); o de 2026
  contém só o 1º turno.
- Série histórica: `scripts/historico.py` lê os zips `votacao_candidato_munzona`
  de `dados/historico/` sem extrair (presidente = `_BR.csv`; 1998 só tem
  `_BRASIL.csv` e grava os votos em `QT_VOTOS_NOMINAIS_VALIDOS`, com
  `QT_VOTOS_NOMINAIS` zerado). 2022/2026 vêm dos CSVs por seção.
- Nível município = municípios brasileiros: **excluir `SG_UF == "ZZ"`** (~145
  cidades no exterior). Porte = **votos válidos** (votáveis < 95), igual à API
  do 2T. O 2T fechado está em `totais_2t_municipio_6258.csv` (`totais_2t.ler`);
  `resultado_2t_municipio_6258.csv` é um retrato parcial de 99,87%.
- Boletins de urna: `bweb_<t>t_<UF>_<timestamp>.zip` no CDN do TSE (nome com
  timestamp — achar via API CKAN `dadosabertos.tse.jus.br/api/3/action/package_search`),
  ~190 MB por UF, com `.sha512` ao lado. No BU o cargo é `CD_CARGO_PERGUNTA`.
  CE 1T 2026: 23.765 seções, 0 diferenças contra a totalização.
- Rodar a análise completa do 1º turno leva ~30 s; a varredura dos 5.757
  municípios pela API leva ~35 s com 24 conexões.

## Invariantes de método

Estes não são preferências — são o que separa a análise de um alarme falso.

1. **Gate antes de qualquer teste.** `bf.fourier_empirico` estima |φ(2πk)| da
   amostra e compara com o ruído √(1/n). Excesso ≫ 1 significa que a forma do
   dado não é Benford, e desvio nos dígitos não é interpretável.
2. **Nunca usar o gate lognormal (`bf.sigma_decadas`) para decidir.** Nesses
   dados ele erra por ~100×. Está no código só como referência didática.
3. **Nunca aplicar primeiro dígito a votos por seção.** Faixa estreita demais
   (|φ| ≈ 350× o ruído). O nível válido é o total por município.
4. **Nenhum desvio é reportado sem controle.** Variáveis que ninguém manipula
   (`controle_estrutural.py`) e a mesma medição em 2022 (`decomposicao.py`).
5. **Apuração parcial não é auditoria.** Totais municipais incompletos
   distorcem os dígitos e inflam a razão de Fourier. Checar
   `totalizacao_encerrada` antes de concluir qualquer coisa.
6. Benford é filtro de atenção, nunca evidência. A auditoria que prova algo é
   conferir boletim de urna assinado contra a totalização.

## API de divulgação do TSE

- Base: `https://resultados.tse.jus.br/oficial/ele2026/<cd_eleicao>`
- Códigos: `6257` Presidente 1T · `6258` Presidente 2T · `6259`/`6260`
  Governador 1T/2T. Lista completa em `/oficial/comum/config/ele-c.json`.
- Resumo nacional: `/dados/br/br-c0001-e00<cd>-u.json`
- Município: `/dados/<uf>/<uf><cd_mun>-c0001-e00<cd>-u.json` (sufixo `-u`,
  **não** `-r`, que não existe neste ciclo)
- Municípios disponíveis: `/config/mun-e00<cd>-cm.json`
- **A API responde 403 a requisições com cabeçalho `Origin`.** Nenhuma página
  de navegador consegue chamá-la direto — por isso `scripts/dashboard.py`
  existe como proxy.
- **A API tem limite de taxa e bloqueia o IP com HTTP 429.** Medido em
  25/10/2026: 24 conexões varrendo os 5.757 municípios a cada 5 min
  (~19 req/s sustentados) levou a 429 em ~40 min, derrubando **também** os
  endpoints estáticos de config. O bloqueio durou ~25 min. O corpo do 429 é
  HTML com um id de requisição, não JSON — quem só faz `json.load` quebra com
  `JSONDecodeError` e esconde a causa real.
  - `coletar_2t.pegar` agora aplica throttle global de `REQ_POR_S = 4.0`,
    detecta 429, levanta `Bloqueado` e entra em cooldown de 10 min.
  - Uma varredura completa leva ~24 min nesse ritmo. **Não aumentar a taxa
    sem medir** — o teto real do TSE é desconhecido.
  - `pkill -f dashboard.py` mata o próprio shell (o padrão casa com a linha
    de comando dele). Usar `pgrep -f 'dashboard[.]py'` e `kill` nos PIDs.

## Dashboard

`python3 scripts/dashboard.py [porta] [--auto MINUTOS]` (padrão 8765, sem
varredura automática). Serve `scripts/dashboard.html` e faz proxy do resumo
nacional (1 requisição, cache de 30 s).

A varredura dos municípios custa 5.757 requisições, então é **sob demanda**
pelo botão na página (`/api/varrer`), nunca em laço curto. `--auto` aceita no
mínimo 20 min, por segurança.
A página é para leigos: a camada de cima usa só os vereditos de
`historico.veredito()` (poucos / não se aplica / desvio / segue), que é o
único lugar onde a regra mora — o painel ao vivo importa a mesma função.
O conteúdo técnico fica num `<details>` no fim.

## Investigação forense (1º turno 2026)

Pipeline, nesta ordem (cada um lê a saída do anterior; ~15 min no total):
`investigar.py` → `idade_biometria.py` → `aprofundar.py` → `logs_urna.py` →
`viradas.py` → `exportar_dossie.py` (gera os JSON de `dados/derivados/dossie/`,
com as fichas de `pistas.py`). Dossiê público (tipo Dashboard):
https://claude.ai/artifact/6hWk8PCf7GpwDaEsqFy3yN — página e script em
`dados/derivados/dossie/pagina/`; dados entram como arquivos anexados.

- Arquivos assinados por seção: `resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/`
  (3220 = `CD_PLEITO` do 1T). Índice `dados/<uf>/<mun5>/<zona4>/<sec4>/p003220-<uf>-m..-z..-s..-aux.json`.
  O `log.jez` é **zip**; pode trazer `logd.dat` **e** um `.jez` aninhado (urna trocada) — somar os dois.
- Liberação manual no log = "Solicitação de dado pessoal do eleitor para habilitação manual".
  "Biometria coletada não é do mesário" identifica o **mesário**, não o eleitor.
- Horário no BU é local. O oeste do AM usa UTC−5: referência = **moda** da hora de abertura do município.
- Último dígito inclina (0 > 9) quando a contagem cai dentro da dezena; o teste é
  o excesso de 0 e 5 **acima da reta**, nunca o χ² cru (com n = 100 mil tudo dá p ≈ 0).
- Perfil do eleitorado por seção (idade, biometria cadastrada): `perfil_eleitor_secao_ATUAL_<UF>.zip`.

Regras de método somadas às invariantes:
7. **Alerta = improvável E grande.** z robusto > 5 **e** piso de efeito (5 pontos;
   15% no crescimento). Com poucos municípios o MAD encolhe e o z sozinho alarma por 2 pontos.
8. **Todo sinal enfrenta uma hipótese inocente testável** antes de virar achado
   (ex.: biometria × idade; Klimek × 2022 e digital; virada × líder local e seção a seção).
9. **Comparar com 2022 seção a seção:** fraude em 2026 aparece como *mudança* em
   relação às vizinhas de escola, não como diferença que já existia.
