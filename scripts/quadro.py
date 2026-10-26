#!/usr/bin/env python3
"""Mapa da investigação: fichas (nós) e linhas (ligações) do quadro de cortiça.

Cada nó é um fato ou uma pista, com números tirados dos resultados; fatos
externos (decisões, pesquisas, notas) levam a fonte. Cada linha liga fatos
que se explicam ou se contradizem. Usado por exportar_dossie.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from pistas import n, pct, pp

RAIZ = Path(__file__).parent.parent
FASES = ["Antecedentes", "Código e comando", "1º turno · 4/10", "Entre os turnos",
         "2º turno · 25/10", "Cadastro e população"]


def ler(nome):
    p = RAIZ / "resultados" / f"{nome}.json"
    return json.loads(p.read_text()) if p.exists() else None


def gerar() -> dict[str, list]:
    inv, ap, lg, vr = ler("investigacao"), ler("aprofundamento"), ler("logs_urna"), ler("viradas")
    ib, mig, real, hist = ler("idade_biometria"), ler("migracao"), ler("realidade"), ler("historico")
    ln1, ln2 = ler("logs_nacional_3220"), ler("logs_nacional_3221")
    nac, mn = inv["nacional"], mig["nacional"]
    g = lg["grupos"]
    # totais oficiais incluem o exterior (ZZ), que a migração por município deixa de fora
    import csv
    with open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8") as fh:
        tt = list(csv.DictReader(fh))
    L2, F2 = sum(int(x["lula"]) for x in tt), sum(int(x["flavio"]) for x in tt)
    margem = L2 - F2
    bolo = mn["ganho_lula"] + mn["ganho_flavio"]
    precisa = (mn["lula1"] - mn["flavio1"] + bolo) / 2 / bolo        # fração do bolo para o Flávio vencer
    exc = sum(max(0, m["aptos"] - m["populacao"]) for m in real["municipios"])
    exc_comp = sum(max(0, m["comparecimento"] - .78 * m["populacao"]) for m in real["municipios"])
    acima = real["aptos_acima_populacao"]
    norte = [u for u in mig["por_uf"] if u["dcomp"] < 0]
    norte_fl = [u["uf"] for u in norte if u["ganho_flavio"] < 0]

    def taxa(meio):
        t = [c["veredito"] for a in hist if a["meio"] == meio for c in a["candidatos"][:2]]
        t += [b["veredito"] for a in hist if a["meio"] == meio
              for nr in list(a["estados"])[:2] for b in a["estados"][nr].values()]
        v = [x for x in t if x in ("segue", "desvio")]
        return sum(1 for x in v if x == "desvio") / len(v)

    N = []

    def no(id, fase, titulo, texto, status, pista="", fonte="", url=""):
        N.append({"id": id, "fase": fase, "ordem": sum(1 for x in N if x["fase"] == fase) + 1,
                  "titulo": titulo, "texto": texto, "status": status, "pista": pista,
                  "fonte": fonte, "url": url})

    F0, F1, F2_, F3, F4, F5 = FASES
    no("a_benford", F0, "Papel × urna (1994–2026)",
       f"Desvios de Benford: {pct(taxa('papel'))} dos testes no papel, {pct(taxa('urna'))} na urna. Todos os de 1994 são de FHC, eleito no papel.",
       "sem sinal", "benford")
    no("a_voto_impresso", F0, "Voto impresso: 2002 → 2021",
       "Lula sancionou o voto impresso em 2009; o STF derrubou por unanimidade em 2020; a PEC caiu em 2021 por 229 a 218, com PL, PSD, MDB e PSDB também contra.",
       "fato", fonte="Congresso em Foco; Poder360",
       url="https://www.congressoemfoco.com.br/legislativo/voto-impresso-como-cada-deputado-votou-em-pec-que-foi-derrubada/")
    no("a_defesa", F0, "Nota da Defesa, 10/11/2022",
       "Houve “restrições ao acesso adequado” ao código e às bibliotecas de terceiros. A fiscalização “não apontou” fraude, mas “não excluiu” a possibilidade.",
       "aberta", fonte="Ministério da Defesa (governo Bolsonaro)",
       url="https://static.poder360.com.br/2022/11/nota-ministerio-defesa-relatorio-eleicoes-10-nov-2022.pdf")
    no("c_codigo", F1, "Código aberto desde 2/10/2025",
       "Inspecionaram União Brasil, Senado, SBC, CNC, CGU, PGR e CNMP. Não achei registro de inspeção do PL nem das Forças Armadas em 2026.",
       "aberta", fonte="TSE; MPF",
       url="https://www.tse.jus.br/comunicacao/noticias/2026/Abril/eleicoes-2026-codigos-fonte-dos-sistemas-eleitorais-continuam-abertos-para-inspecao")
    no("c_tse", F1, "Quem comandou 2026",
       "TSE presidido por Nunes Marques, com André Mendonça de vice: os dois ministros que Bolsonaro indicou ao STF.",
       "fato", fonte="Agência Brasil",
       url="https://agenciabrasil.ebc.com.br/justica/noticia/2026-05/nunes-marques-toma-posse-na-presidencia-do-tse-e-vai-comandar-eleicoes")
    no("c_ponto_cego", F1, "A urna gravou o voto digitado?",
       "Nenhum dado público permite verificar isso urna por urna. É o argumento técnico a favor do voto impresso.",
       "fora do alcance", "ponto_cego")
    no("t1_bu", F2_, "Boletim × resultado oficial",
       f"{n(nac['diferencas'])} diferenças em {n(nac['registros_bu'])} registros de {n(nac['secoes'])} seções, conferidos voto a voto.",
       "sem sinal", "integridade")
    if ln1:
        u = [x for x in ln1["urnas"].values() if x.get("votos_log")]
        bate = sum(1 for x in u if x["votos_log"] == x["bu_comp_1t"])
        fim = sum(1 for x in u if x.get("padrao") == "concentrado na última hora")
        no("t1_logs", F2_, "Diário das urnas (amostra nacional)",
           f"{n(len(u))} urnas sorteadas nos 27 estados: {n(bate)} batem com o boletim; {n(fim)} com liberações sem digital concentradas no fim do dia.",
           "sem sinal", "logs")
    else:
        no("t1_logs", F2_, "Diário das urnas",
           f"{n(sum(x['log_bate_bu'] for x in g.values()))} de {n(sum(x['com_log'] for x in g.values()))} logs batem com o boletim; nenhuma urna com liberações concentradas no fim do dia.",
           "sem sinal", "logs")
    no("t1_biometria", F2_, "Liberação sem digital",
       f"Efeito no voto some com a idade no modelo ({pp(ib['modelos']['so_biometria']['biom']['coef'])} → {pp(ib['modelos']['biometria_idade']['biom']['coef'])}). Logs: leitor com defeito desde cedo.",
       "explicada", "biometria")
    kl = ap["klimek_canto"]
    no("t1_klimek", F2_, "Quase 100% para um candidato",
       f"{n(kl['n'])} seções; aldeias e quilombos; {pct(kl['identificados_digital_pct'])} dos votantes identificados pela própria digital.",
       "explicada", "klimek")
    e = ap["escola"]
    no("t1_escola", F2_, "Seções que destoam da escola",
       f"{n(e['n'])} de {n(nac['secoes_testaveis_escola'])} seções; logs normais; saldo de {n(e['votos_saldo'])} votos.",
       "aberta", "escola")
    no("t1_viradas", F2_, "Cidades que viraram",
       f"{n(len(vr['casos']))} municípios, todas as seções na mesma direção; líderes locais com 30–43% na cidade.",
       "explicada em parte", "viradas")
    no("e_pesquisas", F3, "Pesquisas: Flávio na frente",
       "Flávio liderou 17 de 18 pesquisas; na véspera, Datafolha e Quaest 51 × 49. O resultado ficou ~2,8 pontos fora delas.",
       "fato", fonte="CNN Brasil; Guia do Investidor",
       url="https://www.cnnbrasil.com.br/eleicoes/ultimas-pesquisas-segundo-turno-eleicao/")
    no("e_bolsa", F3, "Bolsa Família antecipado",
       "Pago 4 dias antes do 2º turno. Juristas divergem se é abuso de poder político, que é julgado na Justiça Eleitoral. Não é fraude na urna.",
       "aberta", fonte="Jornal de Brasília; Terra",
       url="https://jornaldebrasilia.com.br/noticias/politica-e-poder/governo-lula-adianta-pagamento-do-bolsa-familia-antes-do-segundo-turno/")
    no("t2_zanin", F4, "Votação prorrogada até 19h",
       "Liminar do ministro Zanin (STF), a pedido das duas campanhas, por alagamentos e transporte. Execução desigual: urnas fecharam às 17h em vários lugares.",
       "fato", fonte="Exame; Metrópoles",
       url="https://exame.com/brasil/por-que-o-tse-decidiu-prorrogar-o-horario-de-votacao-ate-as-19h/")
    no("t2_resultado", F4, "Resultado do 2º turno",
       f"Lula {n(L2)} × Flávio {n(F2)}: margem de {n(margem)} votos, com 100% apurado.",
       "fato")
    no("t2_bolo", F4, "De onde veio a virada",
       f"Bolo de {n(bolo)} votos (eliminados, brancos e nulos, comparecimento). O Flávio precisava de {pct(precisa)} para vencer e levou {pct(1 - mn['parcela_lula'])}.",
       "explicada em parte", "segundo_turno")
    no("t2_flavio_perdeu", F4, "Flávio perdeu votos entre os turnos",
       f"Em {n(mn['alertas']['Flávio perdeu votos'])} municípios, concentrados no Nordeste. Em {n(mn['alertas']['Lula ganhou mais que o bolo'])}, o Lula ganhou mais que o bolo.",
       "aberta", "segundo_turno")
    no("t2_norte", F4, "Comparecimento caiu no Norte, MA e PI",
       f"Subiu no resto do país e caiu em {', '.join(u['uf'] for u in norte)}. Em {', '.join(norte_fl)} foi o Flávio quem perdeu votos.",
       "aberta", "segundo_turno")
    no("t2_fecha", F4, "A conta fecha",
       f"Lula + Flávio + brancos + nulos = comparecimento em {n(mn['municipios'] - mn['nao_fecham'])} de {n(mn['municipios'])} municípios.",
       "sem sinal", "segundo_turno")
    if ln2:
        u = [x for x in ln2["urnas"].values() if x.get("votos_log")]
        tot = sum(x["votos_log"] for x in u) or 1
        no("t2_logs", F4, "O comparecimento extra é de gente real?",
           f"{n(len(u))} urnas do 2º turno: {pct(sum(x['hab_manual'] for x in u) / tot, 1)} liberados sem digital; "
           f"{n(sum(1 for x in u if x.get('padrao') == 'concentrado na última hora'))} com liberações concentradas no fim; "
           f"{pct(sum(x['votos_apos_17h'] for x in u) / tot, 1)} dos votos depois das 17h.",
           "sem sinal" if not sum(1 for x in u if x.get('padrao') == 'concentrado na última hora') else "aberta",
           "segundo_turno")
    else:
        no("t2_logs", F4, "O comparecimento extra é de gente real?",
           "Leitura dos logs de 10.800 urnas do 2º turno em andamento.", "aberta", "segundo_turno")
    no("p_cadastro", F5, "Mais eleitores que moradores",
       f"{n(acima['municipios'])} municípios; {n(exc)} eleitores além da população do IBGE. Pior caso: ~{n(2 * exc_comp)} votos de diferença, contra margem de {n(margem)}.",
       "aberta", "cadastro")
    no("t1_cresc", F5, "Votos que cresceram demais",
       "Cidades com crescimento anormal de votos desde 2022, como Canaã dos Carajás, Maricá e o litoral de SC; Anhanguera (GO) com comparecimento baixo.",
       "aberta", "crescimento")
    no("q", "Pergunta", "Houve fraude que mudou o resultado?",
       f"Nenhum rastro encontrado nos dados públicos. As pistas abertas somam no máximo ~{n(2 * exc_comp + e['votos_saldo'])} votos, contra margem de {n(margem)}. O ponto cego segue fora do alcance.",
       "fato")

    E = []

    def linha(a, b, rot):
        E.append({"id": f"{a}>{b}", "de": a, "para": b, "rotulo": rot})
    linha("a_voto_impresso", "c_ponto_cego", "sem papel, sem conferência")
    linha("a_defesa", "c_codigo", "acesso restrito em 2022")
    linha("a_defesa", "c_ponto_cego", "pediu análise do código executado")
    linha("c_codigo", "c_ponto_cego", "inspeção ≠ código que rodou")
    linha("c_tse", "q", "comando com indicados de Bolsonaro")
    linha("a_benford", "q", "papel e urna iguais")
    linha("t1_bu", "q", "a soma confere")
    linha("t1_biometria", "t1_logs", "leitor com defeito")
    linha("t1_klimek", "t1_logs", "logs normais")
    linha("t1_escola", "t1_logs", "logs normais")
    linha("t1_escola", "q", "saldo pequeno")
    linha("t1_viradas", "q", "política local")
    linha("t1_cresc", "p_cadastro", "mesmo fenômeno")
    linha("e_pesquisas", "t2_resultado", "erro de ~2,8 pontos")
    linha("e_bolsa", "t2_flavio_perdeu", "Nordeste: testar")
    linha("t2_zanin", "t2_norte", "transporte e alagamentos")
    linha("t2_norte", "t2_resultado", "custou votos ao Flávio")
    linha("t2_flavio_perdeu", "t2_bolo", "virada no Nordeste")
    linha("t2_bolo", "t2_resultado", "explica a margem")
    linha("t2_logs", "t2_bolo", "comparecimento extra")
    linha("t2_fecha", "t2_resultado", "soma confere")
    linha("p_cadastro", "t2_resultado", "pior caso < margem")
    linha("t2_resultado", "q", "")
    linha("c_ponto_cego", "q", "fora do alcance")
    return {"quadro_nos": N, "quadro_linhas": E, "fases": FASES}


if __name__ == "__main__":
    q = gerar()
    for x in q["quadro_nos"]:
        print(f"{x['fase'][:12]:<12} {x['status']:<18} {x['titulo']}: {x['texto'][:110]}")
    print(len(q["quadro_linhas"]), "linhas")
