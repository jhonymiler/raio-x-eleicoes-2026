#!/usr/bin/env python3
"""Converte os resultados da investigacao (investigar, aprofundar,
idade_biometria, logs_urna, viradas, historico, pistas) nos conjuntos de
dados (JSON, lista de linhas) que o painel publico cita um a um.

Saida: dados/derivados/dossie/<id>.json

Uso:  python3 scripts/exportar_dossie.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pistas as fichas  # noqa: E402
import quadro  # noqa: E402

RAIZ = Path(__file__).parent.parent
NOMES_C = {"13": "Lula", "22": "Flávio Bolsonaro"}
OUT = RAIZ / "dados" / "derivados" / "dossie"
A, B = "13", "22"


def r(x, n=5):
    return None if x is None else round(x, n)


def main() -> None:
    inv = json.loads((RAIZ / "resultados" / "investigacao.json").read_text())
    hist = json.loads((RAIZ / "resultados" / "historico.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    ds: dict[str, list] = {}

    n = inv["nacional"]
    est = inv["estados"]
    tot_ap = sum(e["aptos"] for e in est.values())
    tot_cp = sum(e["comp"] for e in est.values())
    vA = sum(e["votos"][A] for e in est.values())
    vB = sum(e["votos"][B] for e in est.values())
    val = sum(e["validos"] for e in est.values())
    ds["nacional"] = [{
        "secoes": n["secoes"], "registros_bu": n["registros_bu"],
        "registros_totalizacao": n["registros_tot"], "diferencas": n["diferencas"],
        "aptos": tot_ap, "comparecimento": tot_cp, "turn": r(tot_cp / tot_ap),
        "votos_lula": vA, "votos_flavio": vB, "validos": val,
        "share_lula": r(vA / val), "share_flavio": r(vB / val),
        "secoes_testaveis_escola": n["secoes_testaveis_escola"],
        "alertas_escola": n["alertas_escola"],
        "sd_residuo_escola": r(n["sd_residuo_escola"]),
        "problemas_processo": sum(n["problemas"].values()),
        "estados_alerta": sum(1 for e in est.values() if status_uf(e) != "ok"),
        "municipios_alerta": sum(1 for ls in inv["municipios"].values() for x in ls if x["alertas"]),
        "biom_n_alto": n["biom_vies"].get("n_alto"),
        "biom_res_alto": r(n["biom_vies"].get("media_alto")),
        "biom_res_baixo": r(n["biom_vies"].get("media_baixo")),
        "biom_z": r(n["biom_vies"].get("z"), 2),
    }]
    ds["problemas"] = [{"problema": k, "secoes": v}
                       for k, v in sorted(n["problemas"].items(), key=lambda x: -x[1])]
    h = n["dist_residuo"]
    w = (h["ate"] - h["de"]) / len(h["h"])
    ds["residuo_escola"] = [{"residuo": r(h["de"] + (i + .5) * w, 4), "secoes": q}
                            for i, q in enumerate(h["h"])]

    ds["estados"] = []
    ds["klimek"] = []
    for uf, e in est.items():
        ud = e["ultimo_digito"]
        ds["estados"].append({
            "uf": uf, "status": status_uf(e), "secoes": e["secoes"], "aptos": e["aptos"],
            "comparecimento": e["comp"], "turn": r(e["turn"]),
            "votos_lula": e["votos"][A], "votos_flavio": e["votos"][B],
            "share_lula": r(e["sA"]), "share_flavio": r(e["sB"]),
            "share_lula_2022": r(e["sA_2022"]), "share_bolsonaro_2022": r(e["sB_2022"]),
            "swing_lula": r(e["swing"]), "z_swing": r(e["z_swing"], 2),
            "biom_tx": r(e["biom_tx"]),
            "p_ultdig_lula": r(ud[A]["p"], 4), "p_ultdig_flavio": r(ud[B]["p"], 4),
            "p_ultdig_aptos": r(ud["aptos"]["p"], 4), "n_ultdig_lula": ud[A]["n"],
            "exc05_lula": r(ud[A].get("excesso_0_5")), "z05_lula": r(ud[A].get("z_0_5"), 2),
            "exc05_flavio": r(ud[B].get("excesso_0_5")), "z05_flavio": r(ud[B].get("z_0_5"), 2),
            "incl_lula": r(ud[A].get("inclinacao")), "incl_flavio": r(ud[B].get("inclinacao")),
            "extremos_lula": e["extremos"][A], "extremos_flavio": e["extremos"][B],
            "alertas_escola": e["alertas_escola"],
            "bu_registros": e["integridade"]["registros"],
            "bu_votos": e["integridade"]["votos_bu"],
            "tot_votos": e["integridade"]["votos_tot"],
            "diferencas": e["integridade"]["difs"],
            "problemas_processo": sum(e["problemas"].values()),
            "municipios": len(inv["municipios"].get(uf, [])),
            "municipios_alerta": sum(1 for x in inv["municipios"].get(uf, []) if x["alertas"]),
        })
        for cand, grade in e["klimek"].items():
            for i, linha in enumerate(grade):
                for j, q in enumerate(linha):
                    if q:
                        ds["klimek"].append({"uf": uf, "candidato": cand,
                                             "comparecimento": r((i + .5) / 20, 3),
                                             "share": r((j + .5) / 20, 3), "secoes": q})

    ds["municipios"] = [{
        "id": f"{uf}-{x['mun']}", "uf": uf, "municipio": x["nome"], "secoes": x["secoes"],
        "aptos": x["aptos"], "turn": r(x["turn"]), "share_lula": r(x["sA"]),
        "share_lula_2022": r(x["sA_2022"]), "swing_lula": r(x["swing"]),
        "cresc_validos": r(x["cresc"]), "biom_tx": r(x["biom_tx"]),
        "z_swing": r(x.get("z_swing"), 2), "z_turn": r(x.get("z_turn"), 2),
        "z_biom": r(x.get("z_biom"), 2), "z_cresc": r(x.get("z_cresc"), 2),
        "alertas": " ".join(x["alertas"]), "n_alertas": len(x["alertas"]),
        "alertas_escola": x["alertas_escola"],
        "problemas_processo": sum(x["problemas"].values()),
    } for uf, ls in inv["municipios"].items() for x in ls]

    ds["zonas"] = [{
        "id": f"{chave}-{z['zona']}", "municipio_id": chave, "zona": z["zona"],
        "secoes": z["secoes"], "aptos": z["aptos"], "turn": r(z["turn"]),
        "share_lula": r(z["sA"]), "biom_tx": r(z["biom_tx"]),
        "alertas_escola": z["alertas_escola"],
        "problemas_processo": sum(z["problemas"].values()),
    } for chave, zs in inv["zonas"].items() for z in zs]

    ds["secoes"] = [{
        "id": f"{s['uf']}-{s['mun']}-{s['zona']}-{s['secao']}",
        "municipio_id": f"{s['uf']}-{s['mun']}", "uf": s["uf"], "municipio": s["mun_nome"],
        "zona": s["zona"], "secao": s["secao"], "local": s["local"],
        "aptos": s["aptos"], "comparecimento": s["comp"], "turn": r(s["turn"]),
        "votos_lula": s["votos"][A], "votos_flavio": s["votos"][B],
        "brancos": s["votos"]["95"], "nulos": s["votos"]["96"],
        "share_lula": r(s["sA"]), "z_escola": r(s["zA"], 2),
        "biom_sem_hab": s["biom"], "urna": s["urna"], "dt_carga": s["dt_carga"],
        "abertura": s["abre"], "encerramento": s["fecha"], "emissao_bu": s["emite"],
        "tipo_urna": s["tipo"], "problemas": " | ".join(s["problemas"]),
    } for s in inv["secoes"]]

    ds["benford_historico"] = [{
        "id": f"{a['ano']}-{c['numero']}", "ano": a["ano"], "meio": a["meio"],
        "candidato": c["nome"], "share": r(c["share"]), "municipios": c["n"],
        "mad": r(c["mad"]), "p": c["p"], "excesso_gate": r(c["excesso"], 2),
        "veredito": c["veredito"]} for a in hist for c in a["candidatos"]]
    ds["benford_estados"] = [{
        "id": f"{a['ano']}-{nr}-{uf}", "ano": a["ano"], "meio": a["meio"],
        "candidato": next(c["nome"] for c in a["candidatos"] if c["numero"] == nr),
        "uf": uf, "municipios": b["n"], "mad": r(b["mad"]), "p": b["p"],
        "excesso_gate": r(b["excesso"], 2), "veredito": b["veredito"]}
        for a in hist for nr, ufs in a["estados"].items() for uf, b in ufs.items()]

    ds["fontes"] = fontes()

    ap = json.loads((RAIZ / "resultados" / "aprofundamento.json").read_text())
    ib = json.loads((RAIZ / "resultados" / "idade_biometria.json").read_text())
    lg = json.loads((RAIZ / "resultados" / "logs_urna.json").read_text())
    vr = json.loads((RAIZ / "resultados" / "viradas.json").read_text())
    fx = fichas.gerar()
    ds["pistas"], ds["fluxo"], ds["contexto"] = fx["pistas"], fx["fluxo"], fx["contexto"]
    st_p = [x["status"] for x in fx["pistas"]]
    g = lg["grupos"]
    ds["nacional"][0].update({
        "alertas_escola": ap["escola"]["n"],
        "logs_auditados": sum(x["com_log"] for x in g.values()),
        "logs_batem": sum(x["log_bate_bu"] for x in g.values()),
        "pistas": len(st_p), "pistas_abertas": st_p.count("aberta"),
        "pistas_sem_sinal": st_p.count("sem sinal"),
        "pistas_explicadas": st_p.count("explicada") + st_p.count("explicada em parte"),
        "pistas_fora": st_p.count("fora do alcance"),
        "aberturas_atrasadas": n["problemas"].get("abertura atrasada (> 30 min)", 0),
    })
    rot = {"controle": "Amostra aleatória (controle)", "escola_novas": "Seções novas que destoam da escola",
           "escola_antigas": "Seções antigas que destoam da escola", "klimek": "Canto de Klimek",
           "biometria_alta": "Liberação sem digital ≥ 30%"}
    ds["logs_grupos"] = [{
        "grupo": rot[k], "secoes": x["secoes"], "com_log": x["com_log"], "log_bate_bu": x["log_bate_bu"],
        "manual_pct": r(x["manual_pct"], 4), "maior_seq_manual": x["maior_seq_manual"],
        "rapidos_20s_pct": r(x["rapidos_20s_pct"], 5), "ultima_hora": r(x["ultima_hora_mediana"], 4),
        "intervalo_s": x["intervalo_mediano"], "logs_multiplos": x["logs_multiplos"],
        "padrao_defeito": x["padroes"].get("defeito desde cedo, espalhado no dia", 0),
        "padrao_intermediario": x["padroes"].get("intermediário", 0),
        "padrao_ultima_hora": x["padroes"].get("concentrado na última hora", 0),
    } for k, x in g.items()]
    ds["biometria_faixas"] = [{
        "faixa": f"{int(f['de']*100)}–{int(round(f['ate']*100))}%", "secoes": f["secoes"],
        "res_2022": r(f["res22"]), "res_2026": r(f["res26"]), "mudanca": r(f["delta"])}
        for f in ap["biometria"]["faixas"]]
    ds["biometria_modelos"] = [{
        "modelo": nome, "variavel": v, "coef": r(c["coef"]), "ep": r(c["ep"]), "z": r(c["z"], 2)}
        for nome, mm in (("Só liberação sem digital", ib["modelos"]["so_biometria"]),
                         ("+ idade 60+", ib["modelos"]["biometria_idade"]),
                         ("+ idade, escolaridade e cadastro biométrico", ib["modelos"]["completo"]))
        for v, c in mm.items()]
    ds["viradas_base"] = [{"periodo": f"{b['de']}→{b['para']}", "municipios": b["municipios"]}
                          for b in vr["linha_base"]]
    ds["viradas_casos"] = [{
        "id": c["id"], "uf": c["uf"], "municipio": c["municipio"], "virada": r(c["virada"]),
        "secoes": c["secoes"], "mesma_direcao": c["secoes_mesma_direcao"],
        "min": r(c["min"]), "max": r(c["max"])} for c in vr["casos"]]
    ds["lideres_locais"] = [{
        "id": f"{x['municipio']}-{x['cargo']}", "uf": x["uf"], "municipio": x["municipio"],
        "cargo": x["cargo"], "candidato": x["candidato"], "partido": x["partido"],
        "share_cidade": r(x["share_cidade"]), "share_estado": r(x["share_estado"])}
        for x in vr["lideres"]]
    ds["klimek_canto"] = [{
        "id": s["id"], "municipio": s["mun"], "local": s["local_nome"], "tipo_local": s["local_cat"],
        "candidato": NOMES_C[s["candidato"]], "aptos": s["aptos"], "comparecimento": s["comp"],
        "turn": r(s["turn"]), "share_2026": r(s["share26"]), "share_2022": r(s["share22"]),
        "identificados_digital": None if s["identificados_digital"] is None else round(s["identificados_digital"]),
        "log": (lg["secoes"].get(s["id"]) or {}).get("votos_log")} for s in ap["klimek_canto"]["lista"]]
    ds["escola_atipicas"] = [{
        "id": s["id"], "municipio": s["mun"], "local": s["local_nome"], "z": r(s["z"], 2),
        "a_favor": "Lula" if s["z"] > 0 else "Flávio", "res_2026": r(s["res26"]), "res_2022": r(s["res22"]),
        "nova": s["res22"] is None, "aptos": s["aptos"], "comparecimento": s["comp"],
        "votos_lula": s["lula"], "votos_flavio": s["flavio"],
        "idade60_vs_vizinhas": r(s["idade60_vs_vizinhas"]),
        "log_manual": (lg["secoes"].get(s["id"]) or {}).get("hab_manual"),
        "log_votos": (lg["secoes"].get(s["id"]) or {}).get("votos_log")} for s in ap["escola"]["lista"]]

    q = quadro.gerar()
    ds["quadro_nos"], ds["quadro_linhas"] = q["quadro_nos"], q["quadro_linhas"]
    mig = json.loads((RAIZ / "resultados" / "migracao.json").read_text())
    ds["migracao_uf"] = [{k: (r(v) if isinstance(v, float) else v) for k, v in u.items()} for u in mig["por_uf"]]
    ds["migracao_faixas"] = [{k: (r(v) if isinstance(v, float) else v) for k, v in x.items()} for x in mig["faixas_direita"]]
    ds["migracao_municipios"] = [{
        "id": m["id"], "uf": m["uf"], "municipio": m["municipio"], "alertas": " · ".join(m["alertas"]),
        "lula1": m["lula1"], "lula2": m["lula2"], "flavio1": m["flavio1"], "flavio2": m["flavio2"],
        "eliminados": m["eliminados"], "direita": m["direita"], "comp1": m["comp1"], "comp2": m["comp2"],
        "parcela_lula": r(m["parcela_lula"]), "dturn": r(m.get("dturn"))}
        for m in mig["municipios"] if m["alertas"]]
    real = json.loads((RAIZ / "resultados" / "realidade.json").read_text())
    ds["cadastro_populacao"] = [{
        "id": m["id"], "uf": m["uf"], "municipio": m["municipio"], "populacao": m["populacao"],
        "aptos": m["aptos"], "comparecimento": m["comparecimento"], "aptos_pop": r(m["aptos_pop"], 3),
        "comp_pop": r(m["comp_pop"], 3), "lula": m["lula"], "flavio": m["flavio"]}
        for m in sorted(real["municipios"], key=lambda m: -m["aptos_pop"]) if m["aptos_pop"] > 1]
    for k, v in ds.items():
        (OUT / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
        print(f"{k:<18} {len(v):>6} linhas  {(OUT / f'{k}.json').stat().st_size/1e3:>8.0f} KB")


def status_uf(e) -> str:
    """Estado em alerta se QUALQUER indicador valido para qualquer UF disparar."""
    ud = e["ultimo_digito"]
    if e["integridade"]["difs"]:
        return "divergencia"
    sinais = [abs(e["z_swing"] or 0) > 5 and abs(e["swing"] or 0) >= .05,
              any((ud[c].get("z_0_5") or 0) > 4 and ud[c]["excesso_0_5"] > .005 for c in (A, B)),
              e["alertas_escola"] > 0, sum(e["problemas"].values()) > 0]
    return "atencao" if any(sinais) else "ok"


def fontes() -> list:
    out = []
    for f in sorted((RAIZ / "dados" / "bu").glob("bweb_1t_*.zip.sha512")):
        nome = f.name[:-7]
        out.append({"arquivo": nome, "tipo": "Boletim de urna (BU), 1º turno",
                    "url": "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/" + nome,
                    "sha512": f.read_text().split()[0]})
    out += [
        {"arquivo": "votacao_secao_2026_BR.zip", "tipo": "Resultado oficial por seção (totalização)",
         "url": "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip", "sha512": ""},
        {"arquivo": "votacao_secao_2022_BR.zip", "tipo": "Resultado oficial por seção, 2022 (comparação)",
         "url": "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_BR.zip", "sha512": ""},
    ] + [{"arquivo": f"votacao_candidato_munzona_{y}.zip", "tipo": f"Votação por município, {y}",
          "url": f"https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_{y}.zip",
          "sha512": ""} for y in (1994, 1998, 2002, 2006, 2010, 2014, 2018)]
    return out


if __name__ == "__main__":
    main()
