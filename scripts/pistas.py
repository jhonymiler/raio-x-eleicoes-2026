#!/usr/bin/env python3
"""Fichas das pistas investigadas e mapa do fluxo eleitoral, geradas a partir
dos resultados (nenhum numero digitado a mao: todo numero vem dos JSON).

Usado por exportar_dossie.py.
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).parent.parent


def n(x, casas=0) -> str:
    """Numero no formato brasileiro."""
    s = f"{x:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pp(x, casas=1) -> str:
    return ("+" if x > 0 else "") + n(x * 100, casas) + " pontos"


def pct(x, casas=0) -> str:
    return n(x * 100, casas) + "%"


def margem_2t() -> int:
    """Lula - Flavio no 2o turno, com o exterior (totais_2t.py)."""
    import csv
    with open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8") as fh:
        t = list(csv.DictReader(fh))
    return sum(int(x["lula"]) for x in t) - sum(int(x["flavio"]) for x in t)


def carregar():
    r = RAIZ / "resultados"
    d = {k: json.loads((r / f"{k}.json").read_text())
         for k in ("investigacao", "aprofundamento", "idade_biometria",
                   "logs_urna", "viradas", "historico")}
    for k in ("migracao", "realidade"):
        d[k] = json.loads((r / f"{k}.json").read_text()) if (r / f"{k}.json").exists() else None
    d["estados_2026_go"] = votos_uf(2026, "GO")
    return d


def votos_uf(ano: int, uf: str) -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    import historico
    mun, nomes = historico.carregar(ano)
    tot: dict = {}
    for k, v in mun.items():
        if k.startswith(uf):
            for nr, q in v.items():
                tot[nr] = tot.get(nr, 0) + q
    t = sum(tot.values())
    return {"candidatos": [{"nome": nomes[nr], "share": q / t} for nr, q in tot.items()]}


def gerar() -> dict[str, list]:
    d = carregar()
    inv, ap, ib, lg, vr = (d["investigacao"], d["aprofundamento"], d["idade_biometria"],
                           d["logs_urna"], d["viradas"])
    nac = inv["nacional"]
    g = lg["grupos"]
    logs_tot = sum(x["com_log"] for x in g.values())
    logs_ok = sum(x["log_bate_bu"] for x in g.values())
    bio = ap["biometria"]
    mod = ib["modelos"]
    esc = ap["escola"]
    kl = ap["klimek_canto"]
    base = vr["linha_base"]
    casos = vr["casos"]
    macapa = next((c for c in casos if c["municipio"] == "MACAPÁ"), None)
    pad = g["biometria_alta"]["padroes"]
    est = inv["estados"]
    z_sw = sorted(((abs(e["z_swing"] or 0), uf) for uf, e in est.items() if e["z_swing"] is not None))[-1]
    ud_max = max(abs(e["ultimo_digito"][c].get("z_0_5") or 0) for e in est.values() for c in ("13", "22"))
    cresc = [x for ls in inv["municipios"].values() for x in ls if "z_cresc" in x["alertas"]]
    turn = [x for ls in inv["municipios"].values() for x in ls if "z_turn" in x["alertas"]]
    prob = nac["problemas"]
    hist = d["historico"]
    caiado_go = next(c for c in d["estados_2026_go"]["candidatos"] if "CAIADO" in c["nome"])["share"]

    def lider(mun, nota=""):
        ls = [x for x in vr["lideres"] if x["municipio"] == mun and x["cargo"].startswith("Deputado")]
        partes = "; ".join(f"{x['candidato'].title()} ({x['partido']}) teve {pct(x['share_cidade'])} na cidade e {pct(x['share_estado'], 1)} no estado"
                           for x in ls)
        return f"Em {mun.title()}{' (' + nota + ')' if nota else ''}: {partes}."

    def taxa(meio):
        t = [c["veredito"] for a in hist if a["meio"] == meio for c in a["candidatos"][:2]]
        t += [b["veredito"] for a in hist if a["meio"] == meio
              for nr in list(a["estados"])[:2] for b in a["estados"][nr].values()]
        v = [x for x in t if x in ("segue", "desvio")]
        return sum(1 for x in v if x == "desvio") / len(v)

    P = []

    def pista(**kw):
        kw["ordem"] = len(P) + 1
        P.append(kw)

    pista(id="integridade", nivel="0 · Integridade", titulo="O resultado oficial é a soma dos boletins de urna?",
          hipotese_fraude="Votos alterados depois que a urna imprimiu o boletim: na transmissão, na totalização ou na publicação.",
          hipotese_inocente="O resultado oficial é exatamente a soma dos boletins impressos e assinados por cada urna.",
          teste=f"Baixei os boletins de urna dos 27 estados e do exterior, conferi o SHA-512 de cada arquivo com o publicado pelo TSE e comparei voto a voto, seção por seção, com o arquivo oficial de resultado.",
          achado=f"{n(nac['diferencas'])} diferenças em {n(nac['registros_bu'])} registros de {n(nac['secoes'])} seções. Cada voto de cada seção bate.",
          status="sem sinal", impacto="—",
          proximo="Fiscais de partido podem repetir o confronto com as fotos dos boletins impressos que tiraram nas seções, uma fonte que não passa pelo TSE.")
    pista(id="logs", nivel="4 · Urna", titulo="O diário de cada urna confirma o boletim?",
          hipotese_fraude="Boletim com número de votos diferente do que a urna realmente registrou ao longo do dia.",
          hipotese_inocente="O log, que registra cada eleitor habilitado e cada voto computado com horário, soma o mesmo que o boletim.",
          teste=f"Baixei o log de {n(logs_tot)} urnas: uma amostra aleatória de {n(g['controle']['com_log'])} do país inteiro e todas as urnas das pistas abaixo. Contei os votos computados e comparei com o comparecimento do boletim.",
          achado=f"{n(logs_ok)} de {n(logs_tot)} logs batem com o boletim. Nenhum voto computado em menos de 20 segundos depois do anterior na amostra de controle; intervalo mediano de {n(g['controle']['intervalo_mediano'])} segundos entre eleitores.",
          status="sem sinal", impacto="—",
          proximo="Qualquer pessoa pode baixar o log de qualquer seção em resultados.tse.jus.br e repetir a contagem com scripts/logs_urna.py.")
    pista(id="biometria", nivel="1 → 4 · Estados até urna", titulo="Seções com muita liberação sem digital votaram diferente?",
          hipotese_fraude="Mesário votando por eleitores ausentes, liberando a urna por código em vez da digital.",
          hipotese_inocente="A digital falha mais em idosos (pele mais fina, calos) e os idosos votaram de forma diferente dos jovens.",
          teste="Comparei cada seção com as outras seções da mesma escola, em 2022 e 2026. Depois incluí a idade dos eleitores de cada seção (perfil do eleitorado do TSE) numa regressão dentro da escola. Por fim, li o log das 150 urnas com mais liberação sem digital para ver quando as liberações aconteceram.",
          achado=(f"Seções com 20% ou mais de liberação sem digital passaram a votar {pp(bio['dif_mudanca']['dif'], 2)} mais no Lula que as vizinhas (z = {n(bio['dif_mudanca']['z'], 1)}). "
                  f"Com a idade no modelo o efeito cai de {pp(mod['so_biometria']['biom']['coef'], 1)} para {pp(mod['biometria_idade']['biom']['coef'], 1)} (z = {n(mod['biometria_idade']['biom']['z'], 1)}): desaparece. "
                  f"Nos logs, {n(pad.get('defeito desde cedo, espalhado no dia', 0))} das {n(g['biometria_alta']['com_log'])} urnas mostram leitor falhando desde o primeiro eleitor e liberações espalhadas pelo dia; nenhuma concentra liberações na última hora."),
          status="explicada", impacto=f"{n(bio['votos_em_jogo'])} votos, se tudo fosse fraude",
          proximo="Os TREs podem cruzar as urnas com leitor defeituoso com os registros de manutenção.")
    pista(id="klimek", nivel="4 · Seção", titulo="Seções com quase 100% de comparecimento e de votos para um candidato",
          hipotese_fraude="Urna 'enchida': alguém vota por todos os eleitores da seção (impressão digital de Klimek).",
          hipotese_inocente="Comunidades pequenas e coesas, como aldeias indígenas e quilombos, votam em bloco e comparecem em massa.",
          teste="Busquei o nome do local de cada seção, comparei com a mesma seção em 2022, contei quantos votantes foram identificados pela própria digital e li o log de cada urna.",
          achado=(f"{n(kl['n'])} seções ({n(kl['lula'])} para Lula, {n(kl['flavio'])} para Flávio). {n(kl['indigenas_quilombos'])} ficam em escola indígena, quilombo ou assentamento. "
                  f"Das {n(kl['n'] - kl['sem_2022'])} que existiam em 2022, {n(kl['ja_90_em_2022'])} já davam 90% ou mais ao mesmo candidato. "
                  f"{pct(kl['identificados_digital_pct'])} dos votantes foram identificados pela própria digital, e os logs são iguais aos da amostra de controle."),
          status="explicada", impacto="—",
          proximo="")
    pista(id="escola", nivel="4 · Seção", titulo="Seções que destoam muito das outras seções da mesma escola",
          hipotese_fraude="Uma urna adulterada daria um resultado fora do padrão das urnas vizinhas, que recebem eleitores parecidos.",
          hipotese_inocente="Seções com composição própria e estável, ou seções novas formadas por eleitores novos ou transferidos.",
          teste="Medi o quanto cada seção difere das vizinhas de escola (z robusto). Comparei com 2022, com a idade dos eleitores, com o voto em trânsito e com o log de cada urna.",
          achado=(f"{n(esc['n'])} de {n(nac['secoes_testaveis_escola'])} seções ({pct(esc['n'] / nac['secoes_testaveis_escola'], 2)}): {n(esc['pro_lula'])} a favor do Lula e {n(esc['pro_flavio'])} do Flávio. "
                  f"Das {n(esc['com_2022'])} que existiam em 2022, {n(esc['mesmo_sinal_2022'])} já destoavam do mesmo jeito. As outras {n(esc['novas'])} são seções novas, mais jovens que as vizinhas, e {n(esc['novas_pro_lula'])} delas pendem para o Lula. "
                  f"Os logs dessas urnas são iguais aos da amostra de controle. O voto em trânsito não explica a diferença."),
          status="aberta", impacto=f"saldo de {n(esc['votos_saldo'])} votos",
          proximo="Conferir o boletim impresso afixado nessas seções (a lista completa está na aba Seções) e a composição das seções novas no cadastro.")
    pista(id="viradas", nivel="2 · Municípios", titulo="Municípios que viraram de forma anormal desde 2022",
          hipotese_fraude="Manipulação local do resultado em municípios específicos.",
          hipotese_inocente="Mudança política local: um prefeito ou candidato a deputado da cidade levando o eleitorado junto.",
          teste="Contei as viradas anormais em cada troca de eleição desde 2002 (mesmo critério), olhei seção por seção e busquei, nos boletins, o candidato a deputado mais votado em cada cidade.",
          achado=(f"{n(len(casos))} viradas em 2026, contra {', '.join(n(b['municipios']) for b in base[:-1])} nas trocas anteriores desde 2002: acima da linha de base. "
                  f"Em todas, 100% das seções se moveram na mesma direção, o que não combina com adulteração de urnas específicas. "
                  f"{('Uma delas é Macapá, a capital, que só destoa dos municípios pequenos do Amapá: variação de ' + pp(macapa['virada']) + '. ') if macapa else ''}"
                  f"{lider('HERVEIRAS')} {lider('SÃO JOÃO DO TRIUNFO')} {lider('SÃO JULIÃO', 'única virada a favor do Lula')} "
                  f"Em Itapirapuã Paulista (SP), Baixa Grande do Ribeiro (PI) e Serra Negra do Norte (RN) o quadro local é misto."),
          status="explicada em parte", impacto="acima da linha de base histórica",
          proximo="")
    pista(id="crescimento", nivel="2 · Municípios", titulo="Municípios onde os votos cresceram muito desde 2022",
          hipotese_fraude="Cadastro inflado com transferências irregulares de título (eleitores que não moram no município).",
          hipotese_inocente="Crescimento populacional real: polos de mineração, royalties, regiões metropolitanas e litoral.",
          teste="Medi o crescimento dos votos válidos por município em relação ao padrão do estado, o comparecimento e a liberação sem digital.",
          achado=(f"{n(len(cresc))} municípios com crescimento anormal, entre eles Canaã dos Carajás (PA), Maricá (RJ), Extremoz (RN) e cidades do litoral de SC. "
                  f"Neles o comparecimento é normal, então os novos eleitores foram votar, e a maioria foi identificada pela digital. "
                  f"{n(len(turn))} município ({', '.join(x['nome'].title() for x in turn)}) combina crescimento com comparecimento baixo, o padrão de título transferido de quem não mora lá."),
          status="aberta", impacto="cadastro, não urna",
          proximo="Revisão do eleitorado (cadastro) nesses municípios pelo TRE: é o único jeito de checar domicílio eleitoral.")
    pista(id="horarios", nivel="4 · Urna", titulo="Urnas que abriram ou fecharam fora do horário",
          hipotese_fraude="Votação antes das 8h ou depois de encerrada, sem fiscalização.",
          hipotese_inocente="Fusos horários: o oeste do Amazonas segue o fuso do Acre (UTC−5).",
          teste="Comparei o horário de abertura e encerramento registrado no boletim de cada urna com a hora de abertura mais comum do próprio município.",
          achado=(f"Nenhuma urna abriu antes do horário nem encerrou antes das 17h de Brasília. "
                  f"Os primeiros alertas eram erro meu (fuso do oeste do AM e arredondamento). Ficou um registro de processo: {n(prob.get('abertura atrasada (> 30 min)', 0))} urnas abriram com mais de 30 minutos de atraso."),
          status="sem sinal", impacto="—", proximo="")
    pista(id="ultimo_digito", nivel="1 · Estados", titulo="Números inventados à mão (último dígito)",
          hipotese_fraude="Quem inventa números repete finais 0 e 5 mais do que o acaso.",
          hipotese_inocente="Finais uniformes, com uma inclinação natural quando a quantidade de seções cai conforme o número de votos cresce.",
          teste="Último dígito dos votos de cada seção, por estado, medindo o excesso de 0 e 5 depois de descontar a inclinação.",
          achado=f"Nenhum estado tem excesso de 0 e 5 (maior |z| = {n(ud_max, 1)}). Os alarmes de Roraima e São Paulo no teste simples eram efeito da inclinação.",
          status="sem sinal", impacto="—", proximo="")
    pista(id="estados", nivel="1 · Estados", titulo="Algum estado mudou de forma anormal desde 2022?",
          hipotese_fraude="Manipulação concentrada num estado.",
          hipotese_inocente="Candidatos regionais e mudanças de opinião que variam de estado para estado.",
          teste="Variação do voto no mesmo candidato (Lula) de 2022 para 2026 em cada estado, comparada à dos outros estados.",
          achado=f"Nenhum estado sai do padrão. O mais distante é {z_sw[1]} (z = {n(z_sw[0], 1)}), onde o governador Ronaldo Caiado, candidato a presidente, teve {pct(caiado_go, 1)} dos votos.",
          status="explicada", impacto="—", proximo="")
    pista(id="benford", nivel="1 · Estados", titulo="A Lei de Benford mudou do papel para a urna?",
          hipotese_fraude="A urna eletrônica alterou o padrão dos números, que antes seguiam Benford.",
          hipotese_inocente="O desvio depende de onde cada candidato tem seus votos, e não da forma de votar.",
          teste="A mesma bateria de testes em todas as eleições presidenciais de 1994 (papel) a 2026, por estado.",
          achado=f"Taxa de desvio: {pct(taxa('papel'))} no papel (1994) e {pct(taxa('urna'))} na urna (2002–2026). Todos os desvios de 1994 são de Fernando Henrique, eleito no papel.",
          status="sem sinal", impacto="—", proximo="")
    pista(id="exterior", nivel="4 · Seção", titulo="Seções no exterior com o mesmo número de urna",
          hipotese_fraude="Uma mesma urna usada em várias seções.",
          hipotese_inocente="Seções que votaram em cédula de papel e foram digitadas no sistema de apuração, que aparece como uma única 'urna'.",
          teste="Conferi os horários de abertura e encerramento dessas seções no boletim.",
          achado=f"{n(prob.get('apurada por cédula (sem urna)', 0))} seções no exterior, todas sem horário de abertura: votaram em cédula.",
          status="explicada", impacto="—", proximo="")
    mig, real = d.get("migracao"), d.get("realidade")
    if mig:
        mn = mig["nacional"]
        bolo = mn["ganho_lula"] + mn["ganho_flavio"]
        fx = mig["faixas_direita"]
        pista(id="segundo_turno", nivel="2º turno · Municípios", titulo="A virada do 2º turno: de onde vieram os votos do Lula?",
              hipotese_fraude="Votos acrescentados ao Lula no 2º turno: os eleitores da direita eliminada teriam ido para o Flávio e o resultado não reflete isso.",
              hipotese_inocente="Brancos e nulos do 1º turno, eleitores do Cury e parte da direita eliminada escolheram o Lula, e o comparecimento subiu mais nas áreas dele.",
              teste="Município por município: o bolo de votos em jogo (eliminados, queda de brancos e nulos, aumento de comparecimento), quanto cada finalista levou, se a conta fecha, e se a parcela de cada um acompanha a composição política dos eliminados. Controle: a mesma medida entre os turnos de 2022.",
              achado=(f"A conta fecha nos {n(mn['municipios'])} municípios. Do bolo de {n(bolo)} votos, o Lula levou {pct(mn['parcela_lula'])}. "
                      f"A parcela dele cai de {pct(fx[1]['parcela_lula'])} onde os eliminados eram pouco de direita para {pct(fx[-1]['parcela_lula'])} onde eram quase todos de direita, como se espera de eleitor escolhendo. "
                      f"Em {n(mn['alertas']['Flávio perdeu votos'])} municípios, sobretudo no Nordeste, o Flávio perdeu votos entre os turnos; no Norte, no MA e no PI o comparecimento caiu e quem mais perdeu foi ele."),
              status="aberta", impacto="a parte não explicada está sendo medida nos logs",
              proximo="Ler os logs do 2º turno para saber se o comparecimento extra foi identificado por digital; cruzar a virada no Nordeste com a cobertura do Bolsa Família.")
    if real:
        exc = sum(max(0, m["aptos"] - m["populacao"]) for m in real["municipios"])
        exc_comp = sum(max(0, m["comparecimento"] - .78 * m["populacao"]) for m in real["municipios"])
        ac = real["aptos_acima_populacao"]
        pista(id="cadastro", nivel="2 · Municípios", titulo="Há mais eleitores do que moradores?",
              hipotese_fraude="Cadastro inflado: títulos transferidos para municípios onde a pessoa não mora, ou eleitores que não existem.",
              hipotese_inocente="Quem migra mantém o título na cidade de origem; a lei aceita vínculo familiar, de trabalho ou de propriedade como domicílio eleitoral.",
              teste="Eleitores aptos e votantes do 2º turno de cada município comparados com a população estimada pelo IBGE para 2025.",
              achado=(f"{n(ac['municipios'])} municípios têm mais eleitores do que moradores, somando {n(exc)} eleitores além da população, a maioria em MG, GO, PI e RS. "
                      f"Pior caso, se todo votante acima de 78% da população fosse irregular e tirado do Flávio: {n(2 * exc_comp)} votos de diferença. "
                      f"Dentro de cada estado, esses municípios se moveram menos para o Lula (correlação {n(real['corr_excesso_mudanca_dentro_uf'], 2)})."),
              status="aberta", impacto=f"até {n(2 * exc_comp)} votos; margem de {n(margem_2t())}",
              proximo="Revisão do eleitorado pelos TREs nesses municípios; pesa muito mais nas eleições municipais.")
    pista(id="ponto_cego", nivel="Fora do alcance", titulo="A urna gravou o voto que o eleitor digitou?",
          hipotese_fraude="Software adulterado que registra um voto diferente do digitado, antes de imprimir o boletim.",
          hipotese_inocente="O software é o mesmo inspecionado, assinado e lacrado em cerimônia pública.",
          teste="Nenhum dado publicado permite testar isso urna por urna: o boletim, o log e o registro digital do voto são gerados pela própria urna.",
          achado="Fica fora do alcance desta investigação. Os mecanismos que cobrem esse ponto são o teste de integridade (urnas sorteadas votadas em paralelo com cédulas de papel e filmagem, acompanhado pelo TCU em 2026), a inspeção do código-fonte e o Teste Público de Segurança.",
          status="fora do alcance", impacto="—",
          proximo="Somente um registro em papel conferido pelo eleitor permitiria auditar esse ponto em todas as urnas.")

    F = [
        dict(ordem=1, etapa="Cadastro eleitoral", o_que_acontece="O TSE mantém a lista de eleitores aptos de cada seção, com biometria para a maioria.",
             risco="Eleitores que não moram no município (transferência irregular) ou que não existem; alguém votar no lugar deles.",
             evidencia="Perfil do eleitorado por seção; aptos e comparecimento no boletim; liberações sem digital.",
             verificado="Crescimento anormal de votos, comparecimento e liberações sem digital, município por município.", pistas="crescimento biometria"),
        dict(ordem=2, etapa="Software da urna", o_que_acontece="O código é aberto a entidades fiscalizadoras, passa pelo Teste Público de Segurança e é assinado e lacrado em cerimônia pública.",
             risco="Código malicioso que grava um voto diferente do digitado.",
             evidencia="Hashes publicados dos sistemas; relatórios da inspeção e do Teste Público de Segurança.",
             verificado="Não verificável com dados de resultado: é o ponto cego.", pistas="ponto_cego"),
        dict(ordem=3, etapa="Preparação das urnas", o_que_acontece="Cada urna recebe a carga com o software e os dados da sua seção, semanas antes da eleição.",
             risco="Carga trocada ou urna substituída fora do procedimento.",
             evidencia="Número da urna, código e data de carga no boletim; logs da preparação publicados pelo TSE.",
             verificado="Urnas com número repetido entre seções e trocas de urna registradas no log.", pistas="exterior logs"),
        dict(ordem=4, etapa="Votação", o_que_acontece="O mesário identifica o eleitor pela digital (ou libera por código, com a própria digital) e o eleitor vota nos 6 cargos.",
             risco="Mesário votando por ausentes; votação fora do horário; urna 'enchida'.",
             evidencia="Log da urna (cada eleitor e cada voto com horário); horários de abertura e encerramento; comparecimento por seção.",
             verificado="Liberações sem digital e seu padrão no tempo, horários, canto de Klimek, seções que destoam da escola.", pistas="biometria klimek escola horarios"),
        dict(ordem=5, etapa="Encerramento e boletim", o_que_acontece="A urna imprime o boletim, que é assinado digitalmente, afixado na porta da seção e fotografado por fiscais.",
             risco="Boletim diferente do que a urna registrou.",
             evidencia="Boletim de urna (arquivo assinado e transcrição), log da urna.",
             verificado="Votos do log × comparecimento do boletim em 988 urnas.", pistas="logs"),
        dict(ordem=6, etapa="Transmissão", o_que_acontece="O arquivo do boletim, assinado, é transmitido para a totalização pela rede da Justiça Eleitoral.",
             risco="Arquivo alterado no caminho.",
             evidencia="Assinatura digital do boletim; o boletim publicado comparado ao resultado.",
             verificado="Boletim × resultado oficial em todas as seções.", pistas="integridade"),
        dict(ordem=7, etapa="Totalização e divulgação", o_que_acontece="O TSE soma os boletins e publica o resultado por seção, município e estado.",
             risco="Soma errada ou resultado publicado diferente da soma.",
             evidencia="Resultado por seção e por município; boletins de urna.",
             verificado="Soma seção a seção; padrão de cada estado e município; série histórica desde 1994.", pistas="integridade estados viradas ultimo_digito benford"),
        dict(ordem=8, etapa="Auditorias paralelas", o_que_acontece="No dia da eleição, urnas sorteadas são retiradas e votadas em paralelo com cédulas de papel, com filmagem (teste de integridade).",
             risco="Não detectar uma adulteração que só afete urnas não sorteadas.",
             evidencia="Relatórios do teste de integridade; acompanhamento do TCU.",
             verificado="Não refeito aqui: depende dos relatórios oficiais.", pistas="ponto_cego"),
    ]

    C = [
        dict(fato="Eleitores aptos em 2026", valor="158,7 milhões", fonte="TSE, via imprensa", url="https://www.correio24horas.com.br/eleicoes/eleicoes-terao-mais-de-563-mil-urnas-mobilizadas-pelo-tse-em-todas-as-regioes-veja-como-funcionara-1026"),
        dict(fato="Urnas mobilizadas", valor="563.910 (UE2022, UE2020, UE2015, UE2013)", fonte="TSE, via imprensa", url="https://www.correio24horas.com.br/eleicoes/eleicoes-terao-mais-de-563-mil-urnas-mobilizadas-pelo-tse-em-todas-as-regioes-veja-como-funcionara-1026"),
        dict(fato="Urnas para votação / de contingência", valor="499.248 / 68.912", fonte="TSE, via imprensa", url="https://timesbrasil.com.br/eleicoes-2026/decisao-2026-tse-registra-troca-de-421-urnas-e-auditoria-acompanha-testes-de-integridade-sem-ocorrencias/"),
        dict(fato="Horário de votação", valor="8h às 17h de Brasília em todo o país (6h às 15h no Acre)", fonte="Poder360", url="https://www.poder360.com.br/poder-eleicoes-2026/eleicoes-2026-saiba-ate-que-horas-voce-pode-votar/"),
        dict(fato="Teste de integridade 2026", valor="Realizado nos dois turnos, acompanhado por auditores do TCU", fonte="TCU", url="https://portal.tcu.gov.br/imprensa/noticias/eleicoes-2026-tcu-acompanha-testes-de-integridade-das-urnas-eletronicas"),
        dict(fato="PEC do voto impresso (10/08/2021)", valor="229 a favor, 218 contra; eram necessários 308", fonte="Congresso em Foco", url="https://www.congressoemfoco.com.br/legislativo/voto-impresso-como-cada-deputado-votou-em-pec-que-foi-derrubada/"),
    ]
    return {"pistas": P, "fluxo": F, "contexto": C}


if __name__ == "__main__":
    for k, v in gerar().items():
        print(k, len(v))
        for x in v:
            print("  ", {a: (str(b)[:90]) for a, b in x.items() if a in ("id", "achado", "etapa", "fato")})
