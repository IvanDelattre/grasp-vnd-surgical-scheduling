"""Estatísticas descritivas da análise; não são dados experimentais."""

import json
import math
from copy import deepcopy

import pytest

from grasp_vnd.gerador import gerar_instancia
from grasp_vnd.problema import salvar_instancia
from scripts.analisar_principal import agregar, auditar


def linhas_estatisticas(tmp_path, pares):
    instancia = gerar_instancia(3, 2, 2020)
    caminho = tmp_path / "instancia.json"
    salvar_instancia(instancia, caminho)
    return [{
        "instancia": instancia.identificador, "arquivo": str(caminho),
        "sha256_instancia": "fixture", "iteracoes": 1000, "alpha": 0.5,
        "origem": "SINTETICA", "seed": seed,
        "makespan_grasp": g, "makespan_vnd": v,
        "tempo_grasp_s": 1.000123456789 + seed * 2,
        "tempo_adicional_vnd_s": 0.100123456789 + seed * 0.2,
        "tempo_total_s": 1.100246913578 + seed * 2.2,
        "reducao_percentual": 100 * (g - v) / g,
        "realocacoes_aceitas": int(v < g),
    } for seed, (g, v) in enumerate(pares)]


def test_analise_preserva_percentuais_pareados_e_precisao(tmp_path):
    linhas = linhas_estatisticas(tmp_path, [(7, 5), (9, 9)])
    antes = deepcopy(linhas)
    r = agregar(linhas)[0]
    assert r["media_grasp"] == 8
    assert r["media_vnd"] == 7
    assert r["desvio_amostral_grasp"] == pytest.approx(math.sqrt(2))
    assert r["desvio_amostral_vnd"] == pytest.approx(math.sqrt(8))
    assert r["media_reducao_percentual"] == pytest.approx(100 / 7)
    assert r["media_reducao_percentual"] != 100 * (8 - 7) / 8
    assert r["execucoes_com_melhoria"] == r["execucoes_sem_melhoria"] == 1
    assert r["percentual_execucoes_com_melhoria"] == 50
    assert r["custo_adicional_percentual"] == 100 * r["media_tempo_adicional_vnd_s"] / r["media_tempo_grasp_s"]
    assert r["media_tempo_grasp_s"] != round(r["media_tempo_grasp_s"], 6)
    assert linhas == antes


def test_analise_registra_ausencia_de_melhoria(tmp_path):
    r = agregar(linhas_estatisticas(tmp_path, [(10, 10), (10, 10)]))[0]
    assert r["execucoes_com_melhoria"] == 0
    assert r["execucoes_sem_melhoria"] == 2
    assert r["media_reducao_percentual"] == 0
    assert r["desvio_amostral_grasp"] == r["desvio_amostral_vnd"] == 0


def test_auditoria_nao_publica_lote_parcial_como_completo(tmp_path):
    saida, piloto = tmp_path / "principal", tmp_path / "piloto"
    saida.mkdir()
    piloto.mkdir()
    (saida / "manifesto.json").write_text(json.dumps({"status": "em_execucao"}), encoding="utf-8")
    (piloto / "manifesto.json").write_text("{}", encoding="utf-8")
    preflight = tmp_path / "antes.json"
    preflight.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Lote incompleto"):
        auditar(saida, piloto, preflight)
