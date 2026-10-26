"""Gera site/dados/site.json a partir do dossiê e dos resultados.

Uso: python3 site/gerar_dados.py
Malha dos estados: IBGE (servicodados.ibge.gov.br, qualidade mínima), baixada uma vez
para site/dados/br_uf.geojson.
"""
import csv
import json
import math
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOSSIE = RAIZ / "dados/derivados/dossie"
RES = RAIZ / "resultados"
SAIDA = RAIZ / "site/dados"
MALHA_URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
             "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF")

COD_UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
          "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
          "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
          "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
NOME_UF = {"AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
           "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
           "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul",
           "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
           "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
           "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina",
           "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins", "ZZ": "Exterior"}
REGIAO = {"N": "AC AM AP PA RO RR TO", "NE": "AL BA CE MA PB PE PI RN SE",
          "CO": "DF GO MS MT", "SE": "ES MG RJ SP", "S": "PR RS SC"}
NOME_REGIAO = {"N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul"}


def ler(nome):
    return json.load(open(DOSSIE / f"{nome}.json", encoding="utf-8"))


def mapa():
    arq = SAIDA / "br_uf.geojson"
    if not arq.exists():
        with urllib.request.urlopen(MALHA_URL, timeout=60) as r:
            arq.write_bytes(r.read())
    geo = json.load(open(arq))
    k = math.cos(math.radians(15))
    lon0, lat0, esc = -74.2, 5.6, 16.0  # recorte do Brasil continental

    def xy(p):
        return (round((p[0] - lon0) * k * esc, 1), round((lat0 - p[1]) * esc, 1))

    estados = {}
    for f in geo["features"]:
        uf = COD_UF[f["properties"]["codarea"]]
        g = f["geometry"]
        polis = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        d, maior, area_max = [], None, -1
        for poli in polis:
            for anel in poli:
                pts = [xy(p) for p in anel]
                d.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
            anel = [xy(p) for p in poli[0]]
            a = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1]))) / 2
            if a > area_max:
                area_max, maior = a, anel
        # centróide do maior polígono
        A = cx = cy = 0.0
        for (x1, y1), (x2, y2) in zip(maior, maior[1:] + maior[:1]):
            c = x1 * y2 - x2 * y1
            A += c
            cx += (x1 + x2) * c
            cy += (y1 + y2) * c
        A /= 2
        estados[uf] = {"d": "".join(d), "cx": round(cx / (6 * A), 1), "cy": round(cy / (6 * A), 1)}
    return estados


def logs_uf(caminho):
    txt = open(caminho, encoding="utf-8").read() if caminho.exists() else ""
    feitos = [int(m) for m in re.findall(r"^\s+(\d+)/10800", txt, re.M)]
    return feitos[-1] if feitos else 0


def benford_ano(linhas):
    """Testes por estado que passaram no gate (desvio ou segue), agregados por ano."""
    anos = defaultdict(lambda: {"testes": 0, "desvios": 0, "meio": ""})
    for b in linhas:
        if b["veredito"] in ("desvio", "segue"):
            a = anos[b["ano"]]
            a["meio"] = b["meio"]
            a["testes"] += 1
            a["desvios"] += b["veredito"] == "desvio"
    return [{"ano": k, **v} for k, v in sorted(anos.items())]


def prorrogacao():
    """Votos depois das 17h nas mesmas 10.800 urnas, 1º × 2º turno (liminar até 19h no 2º)."""
    out = {}
    for p in ("3220", "3221"):
        arq = RES / f"logs_nacional_{p}.json"
        if not arq.exists():
            return None
        v = [x for x in json.load(open(arq))["urnas"].values() if x.get("votos_log")]
        tot = sum(x["votos_log"] for x in v)
        out[p] = {"urnas": len(v), "votos": tot, "apos17h": sum(x["votos_apos_17h"] for x in v),
                  "urnas_15min": sum(1 for x in v if x["minutos_apos_17h"] >= 15),
                  "ultima_hora": sum(x["ultima_hora"] * x["votos_log"] for x in v) / tot}
    return out


PISTA_PRORROGACAO = {
    "id": "prorrogacao", "nivel": "2 · 2º turno", "ordem": 14,
    "titulo": "A prorrogação até 19h trouxe uma disparada de votos para o Lula?",
    "hipotese_fraude": "Votos inseridos depois das 17h, aproveitando a liminar do ministro Zanin que estendeu a votação.",
    "hipotese_inocente": "A prorrogação, pedida pelas duas campanhas, quase não foi aplicada: mesários não foram avisados e fecharam às 17h.",
    "teste": "Contei, no log de cada uma das mesmas 10.800 urnas sorteadas, os votos computados depois das 17h, no 1º e no 2º turno. O log não diz em quem foi o voto, então o teste mede o máximo que a prorrogação poderia ter mudado.",
    "achado": "Só 741 de 2.677.782 votos da amostra (0,028%) foram computados depois das 17h no 2º turno, contra 3,53% no 1º turno, que não teve prorrogação. Só 23 das 10.800 urnas votaram mais de 15 minutos além das 17h. No país inteiro, isso dá no máximo cerca de 39 mil votos: mesmo que todos fossem do Lula, seriam 0,9% da margem de 4.430.191.",
    "status": "sem sinal", "impacto": "no máximo ~39 mil votos; margem de 4.430.191",
    "proximo": "Nada a fazer: o horário de cada voto está no log assinado de cada urna.",
}


def matriz_nacional(m):
    """Matriz 1T -> 2T com restricoes (cada linha soma 100%). Valor central =
    media dos ajustes por estado e por estado x tercil; faixa = IC 95% e os
    dois ajustes."""
    rot = {"lula": "Lula (1º turno)", "flavio": "Flávio (1º turno)", "cury": "Augusto Cury",
           "renan": "Renan Santos", "caiado": "Ronaldo Caiado", "zema": "Romeu Zema",
           "outros": "Demais eliminados", "bn": "Branco/nulo no 1º turno", "abst": "Não votou no 1º turno"}
    out = []
    for k, o in enumerate(m["origens"]):
        n = m["eleitores_1t"][o]
        r = {"origem": rot[o], "votos_1t": n}
        for j, d in enumerate(m["destinos"]):
            a, b = m["fluxos"][k][j], m["fluxos_tercil"][k][j]
            lo, hi = m["ic95"][k][j]
            r[d] = round((a + b) / 2 / n, 4) if n else 0
            r[d + "_faixa"] = [round(min(a, b, lo) / n, 3), round(max(a, b, hi) / n, 3)] if n else [0, 0]
        out.append(r)
    return out


def transf_uf(r, n_mun):
    """Para onde foram, no estado, os eleitores da direita eliminada (Renan,
    Caiado, Zema) e de todos os eliminados. Estimativa entre municipios: com
    poucos municipios (DF tem 1) nao ha como estimar."""
    if not r or n_mun < 5:
        return None
    out = {}
    for k in ("direita", "elim"):
        x = r[k]
        if not x["n"]:
            continue
        larg = max(x["lula_faixa"][1] - x["lula_faixa"][0], x["flavio_faixa"][1] - x["flavio_faixa"][0])
        out[k] = {"n": x["n"], "lula": x["lula"], "flavio": x["flavio"],
                  "lf": x["lula_faixa"], "ff": x["flavio_faixa"], "incerta": larg > .35}
    return out


def atualizar_pistas(pistas):
    """Fecha as pistas que estavam em aberto com os testes de conferir_2t.py e fechar_pendencias.py."""
    pen = RES / "pendencias.json"
    c2 = RES / "conferir_2t.json"
    if not (pen.exists() and c2.exists()):
        return pistas
    p, c = json.load(open(pen)), json.load(open(c2))
    e, i, f, cad, cr, vi = c["escola"], c["integridade"], p["flavio_perdeu"], p["cadastro"], p["crescimento"], p["viradas"]
    novo = {
        "escola": {"status": "explicada", "impacto": "saldo de 3.460 votos",
                   "achado": f"No 2º turno, com urnas recarregadas, {e['mesmo_lado_2t']} das {e['secoes']} seções medidas voltaram a destoar das vizinhas no mesmo sentido e com a mesma força (correlação {e['correlacao']:.2f} entre os turnos). Das 60 que já existiam em 2022, 55 já destoavam igual. Isso é composição estável do eleitorado da seção, não urna alterada. Só 1 seção (BA, zona 170, seção 262) destoou no 1º turno e não no 2º.",
                   "proximo": "Nada a fazer na urna. A seção de Camaçari (BA) pode ser conferida pelo boletim impresso do 1º turno."},
        "viradas": {"status": "explicada", "impacto": "—",
                    "achado": f"Comparando 2º turno com 2º turno (os dois finalistas frente a frente, sem os outros 11 candidatos do 1º turno), só {vi['anomalas_2t']} das {vi['comparados']} cidades mudam fora do padrão, dentro da linha histórica. As 3 têm candidatos locais fortes: São Julião e Pedro Laurentino (PI) com deputados do PT da cidade, Belo Monte (AL) com deputados do MDB. As 7 viradas do 1º turno vinham da divisão dos votos entre 13 candidatos.",
                    "proximo": "Nada a fazer."},
        "crescimento": {"status": "explicada", "impacto": "cadastro, não urna",
                        "achado": f"Nos {cr['medidos']} municípios, a população cresceu acima do dobro da média do Brasil em {cr['pop_cresceu_mais_que_o_dobro_do_brasil']} (Censo 2022 → estimativa 2025): mineração, litoral e região metropolitana. Em todos os 17 o Lula perdeu espaço desde 2022: os eleitores novos não favoreceram quem ganhou. O eleitorado cresceu mais que a população em todos, o padrão de quem transfere o título para a cidade da casa de praia ou do trabalho.",
                        "proximo": "Revisão do eleitorado pelo TRE, que é rotina."},
        "cadastro": {"status": "explicada", "impacto": "até 708.713 votos; margem de 4.430.191",
                     "achado": f"{cad['ja_acima_em_2022']} dos {cad['municipios']} municípios já tinham mais eleitores que moradores CONTADOS pelo Censo 2022, com {cad['excesso_2022']:,} eleitores a mais: o excesso é antigo, não foi criado para 2026. Esses municípios se moveram menos para o Lula que os vizinhos (correlação −0,27), o contrário do que uma fraude a favor dele faria.".replace(",", "."),
                     "proximo": "Revisão do eleitorado pelos TREs, que é rotina."},
        "segundo_turno": {"status": "explicada", "impacto": "no máximo ~56 mil votos na diferença (1,3% da margem de 4.430.191)",
                          "achado": f"A conta fecha nos 5.571 municípios; o Lula levou 74% dos votos em jogo, menos onde eles eram de direita. Nos {f['municipios_2026']} municípios onde o Flávio perdeu votos, {f['com_queda_de_comparecimento']} tiveram menos gente votando, e isso responde por {f['perda_onde_comparecimento_caiu']:,} dos {f['perda_total']:,} votos perdidos. Nos diários dessas urnas os votos caem 4,7% e a identificação pela digital fica igual (90,9% → 90,8%), sem rajada no fim do dia. O que sobra são 12.683 votos em 210 cidades e 21.487 votos que mudaram de lado em 290 cidades.".replace(",", "."),
                          "proximo": "Nada a fazer na urna. A ligação com a cobertura do Bolsa Família é assunto de comportamento do eleitor, não de contagem."},
        "integridade": {"achado": f"1º turno: 0 diferenças em 3.800.511 registros de 499.206 seções. 2º turno: {i['municipios_completos']} municípios sorteados inteiros ({i['secoes']:,} seções, {i['votos']:,} votos) conferidos pelo boletim assinado de cada urna, 0 diferenças.".replace(",", ".")},
        "ponto_cego": {"achado": "Não dá para testar com os arquivos públicos. O teste oficial que cobre esse ponto (urnas sorteadas votadas com cédulas de papel, filmado) foi feito nos dois turnos; o TSE e o TRE-SP divulgaram em 25/10/2026 que no 2º turno as cédulas corresponderam aos votos nas urnas."},
    }
    for x in pistas:
        x.update(novo.get(x["id"], {}))
    return pistas


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    nacional = ler("nacional")[0]
    estados = {e["uf"]: e for e in ler("estados")}
    municipios = ler("municipios")
    escola = ler("escola_atipicas")
    klimek = ler("klimek_canto")
    cadastro = ler("cadastro_populacao")
    mig_uf = {m["uf"]: m for m in ler("migracao_uf")}
    mig_mun = {m["id"]: m for m in ler("migracao_municipios")}
    viradas = ler("viradas_casos")
    logs3220 = json.load(open(RES / "logs_nacional_3220.json"))
    migracao = json.load(open(RES / "migracao.json"))
    realidade = json.load(open(RES / "realidade.json"))
    transf = json.load(open(RES / "transferencia.json"))
    matriz = json.load(open(RES / "matriz_transferencia.json"))
    lula_perdeu = {m["id"] for m in migracao["municipios"] if m["lula2"] < m["lula1"]}
    for m in migracao["municipios"]:
        if m["id"] not in lula_perdeu:
            continue
        if m["id"] in mig_mun:
            mm = mig_mun[m["id"]]
            mm["alertas"] = " · ".join(a for a in (mm["alertas"], "Lula perdeu votos") if a)
        else:       # o dossie so lista municipios com algum outro alerta
            mig_mun[m["id"]] = {k: m[k] for k in ("id", "uf", "municipio", "lula1", "lula2", "flavio1", "flavio2",
                                                  "eliminados", "direita", "comp1", "comp2", "parcela_lula")}
            mig_mun[m["id"]].update(alertas="Lula perdeu votos", dturn=round(m["dturn"], 5))

    t2 = {}
    t2_uf = defaultdict(lambda: defaultdict(int))
    for r in csv.DictReader(open(RAIZ / "dados/totais_2t_municipio_6258.csv", encoding="utf-8")):
        mid = f"{r['uf']}-{int(r['cd_municipio'])}"
        v = {k: int(r[k]) for k in ("secoes", "aptos", "comparecimento", "brancos", "nulos", "lula", "flavio")}
        t2[mid] = v
        for k, x in v.items():
            t2_uf[r["uf"]][k] += x

    cad = {c["id"]: c for c in cadastro}
    vir = {v["id"]: v for v in viradas}

    # municípios: lista compacta para busca e ficha
    muns = []
    for m in municipios:
        s = t2.get(m["id"], {})
        validos2 = (s.get("lula", 0) + s.get("flavio", 0)) or None
        alertas = [a for a in (m["alertas"] or "").split(" · ") if a]
        mm = mig_mun.get(m["id"])
        if mm:
            alertas += [a for a in mm["alertas"].split(" · ") if a]
        if m["id"] in lula_perdeu:
            alertas.append("Lula perdeu votos")
        if m["id"] in cad:
            alertas.append("mais eleitores que moradores")
        if m["id"] in vir:
            alertas.append("virou desde 2022")
        muns.append({
            "id": m["id"], "uf": m["uf"], "n": m["municipio"], "sec": m["secoes"], "apt": m["aptos"],
            "l1": m["share_lula"], "l22": m["share_lula_2022"], "sw": m["swing_lula"],
            "cr": m["cresc_validos"], "bio": m["biom_tx"], "turn": m["turn"],
            "zs": m["z_swing"], "zc": m["z_cresc"],
            "l2": round(s["lula"] / validos2, 5) if validos2 else None,
            "v2l": s.get("lula"), "v2f": s.get("flavio"),
            "esc": m["alertas_escola"], "a": sorted(set(alertas)),
            "cad": cad[m["id"]]["aptos_pop"] if m["id"] in cad else None,
            "pop": cad[m["id"]]["populacao"] if m["id"] in cad else None,
        })

    por_uf = {}
    for uf, e in estados.items():
        lg = logs3220["por_uf"].get(uf, {})
        s2 = t2_uf.get(uf, {})
        v2 = (s2.get("lula", 0) + s2.get("flavio", 0)) or None
        mg = mig_uf.get(uf, {})
        cads = [c for c in cadastro if c["uf"] == uf]
        por_uf[uf] = {
            "uf": uf, "nome": NOME_UF.get(uf, uf),
            "regiao": next((NOME_REGIAO[r] for r, l in REGIAO.items() if uf in l.split()), "—"),
            "secoes": e["secoes"], "aptos": e["aptos"], "comparecimento": e["comparecimento"],
            "turn": e["turn"], "l1": e["votos_lula"], "f1": e["votos_flavio"],
            "sl1": e["share_lula"], "sf1": e["share_flavio"],
            "sl22": e["share_lula_2022"], "sw": e["swing_lula"], "z_sw": e["z_swing"],
            "bio": e["biom_tx"], "z05": e["z05_flavio"],
            "bu_reg": e["bu_registros"], "bu_votos": e["bu_votos"], "tot_votos": e["tot_votos"],
            "dif": e["diferencas"], "proc": e["problemas_processo"],
            "municipios": e["municipios"], "mun_alerta": e["municipios_alerta"],
            "escola": sum(1 for x in escola if x["id"].startswith(uf + "-")),
            "klimek": sum(1 for x in klimek if x["id"].startswith(uf + "-")),
            "l2": s2.get("lula"), "f2": s2.get("flavio"),
            "sl2": round(s2["lula"] / v2, 5) if v2 else None,
            "mig": {k: mg.get(k) for k in ("ganho_lula", "ganho_flavio", "eliminados", "direita", "cury", "dcomp")} if mg else None,
            "transf": transf_uf(matriz["por_uf"].get(uf), e["municipios"]),
            "cad_mun": len(cads), "cad_exc": sum(max(0, c["aptos"] - c["populacao"]) for c in cads),
            "logs": {k: lg.get(k) for k in ("urnas", "votos", "manual_pct", "seq10", "concentrado_fim",
                                            "defeito", "rapidos_20s", "votos_apos_17h_pct",
                                            "urnas_ate_19h", "urnas_fecharam_17h")} if lg else None,
        }

    def comp(lista, campos):
        return [{k: x.get(k) for k in campos} for x in lista]

    site = {
        "gerado": nacional,
        "turno2": {"lula": 64256232, "flavio": 59826041, "pl": "51,79", "pf": "48,21",
                   "margem": 4430191, "hora": "25/10/2026 23:27", "secoes": sum(v["secoes"] for v in t2.values()),
                   "aptos": 158745502, "comparecimento": 128236074},
        "balanco": {
            "aptos": [158745007, 158745502], "comparecimento": [125275835, 128236074],
            "lula": [53879538, 64256232], "flavio": [56104503, 59826041], "bn": [5969801, 4153801],
            "eliminados": [["Augusto Cury", 3448569], ["Renan Santos", 2675887], ["Ronaldo Caiado", 2605148],
                           ["Romeu Zema", 326488], ["Outros 7", 265901]],
            "livres": 11137993,
        },
        "migracao": {"nacional": migracao["nacional"], "faixas": migracao["faixas_direita"]},
        "transferencia": transf["brasil"]["coef"],
        "matriz": matriz_nacional(matriz),
        "realidade": {"brasil": realidade["brasil"], "acima": {k: v for k, v in realidade["aptos_acima_populacao"].items() if k != "lista"}},
        "logs3220": {"urnas": 10800, "por_uf": logs3220["por_uf"]},
        "logs3221_feitos": logs_uf(RES / "logs_nacional_3221.txt"),
        "pistas": atualizar_pistas(ler("pistas") + ([PISTA_PRORROGACAO] if prorrogacao() else [])),
        "pendencias": json.load(open(RES / "pendencias.json")) if (RES / "pendencias.json").exists() else None,
        "conferir_2t": {k: v for k, v in json.load(open(RES / "conferir_2t.json")).items() if k != "integridade"}
        | {"integridade": {k: v for k, v in json.load(open(RES / "conferir_2t.json"))["integridade"].items() if k != "lista"}}
        if (RES / "conferir_2t.json").exists() else None,
        "prorrogacao": prorrogacao(),
        "logs3221": {"por_uf": json.load(open(RES / "logs_nacional_3221.json"))["por_uf"]}
        if (RES / "logs_nacional_3221.json").exists() else None,
        "estados": por_uf,
        "mapa": mapa(),
        "municipios": muns,
        "escola": escola,
        "klimek": klimek,
        "cadastro": sorted(cadastro, key=lambda c: -c["aptos_pop"]),
        "migracao_mun": sorted(mig_mun.values(), key=lambda m: m["id"]),
        "viradas": viradas,
        "viradas_base": ler("viradas_base"),
        "lideres": ler("lideres_locais"),
        "biometria_faixas": ler("biometria_faixas"),
        "biometria_modelos": ler("biometria_modelos"),
        "logs_grupos": ler("logs_grupos"),
        "benford": comp(ler("benford_historico"), ("ano", "meio", "candidato", "municipios", "mad", "p", "excesso_gate", "veredito")),
        "benford_ano": benford_ano(ler("benford_estados")),
        "problemas": ler("problemas"),
        "residuo_escola": ler("residuo_escola"),
        "fontes": ler("fontes"),
        "nomes_uf": NOME_UF,
    }
    out = SAIDA / "site.json"
    out.write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{out} {out.stat().st_size/1e6:.2f} MB · {len(muns)} municípios · {len(por_uf)} UFs")


if __name__ == "__main__":
    main()
