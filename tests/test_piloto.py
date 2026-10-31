"""Verificações da persistência e das métricas do protocolo experimental."""

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from grasp_vnd.comparacao import comparar
from grasp_vnd.experimentos import linha_experimento, resumir
from grasp_vnd.problema import salvar_instancia
from scripts.piloto_experimental import executar_piloto, validar_resultado
from scripts.analisar_piloto import cargas, projetar
from grasp_vnd.gerador import gerar_instancia


def test_resumo_inclui_percentual_pareado_e_sem_melhoria(manual):
    base = linha_experimento("manual.json", manual, comparar(manual, 0, 1))
    linhas = []
    for g, v in ((7, 5), (5, 5), (6, 5)):
        linhas.append({**base, "makespan_grasp": g, "makespan_vnd": v,
                       "reducao_percentual": 100 * (g - v) / g})
    resumo = resumir(linhas)[0]
    assert resumo["execucoes_com_melhoria"] == 2
    assert resumo["percentual_execucoes_com_melhoria"] == 100 * 2 / 3
    assert resumo["execucoes_sem_melhoria"] == 1
    assert resumo["media_grasp"] == 6
    assert resumo["desvio_amostral_grasp"] == 1
    assert resumo["media_reducao_percentual"] == sum(r["reducao_percentual"] for r in linhas) / 3


def test_timeout_preserva_primeira_execucao(manual, tmp_path, monkeypatch):
    entrada = tmp_path / "entrada.json"
    salvar_instancia(manual, entrada)
    chamadas = []

    class ProcessoFalso:
        def __init__(self, comando, **kwargs):
            self.seed = int(comando[comando.index("--seed") + 1])
            self.returncode = None
            chamadas.append(self.seed)
            if self.seed == 0:
                destino = Path(comando[comando.index("--saida") + 1])
                destino.write_text(json.dumps(asdict(comparar(manual, 0, 1))), encoding="utf-8")

        def communicate(self, timeout=None):
            if self.seed == 1 and self.returncode is None:
                raise subprocess.TimeoutExpired("teste", timeout)
            self.returncode = 0
            return "", ""

        def kill(self):
            self.returncode = -9

        def poll(self):
            return self.returncode

    monkeypatch.setattr("scripts.piloto_experimental.subprocess.Popen", ProcessoFalso)
    saida = tmp_path / "piloto"
    manifesto = executar_piloto([entrada], [0, 1, 2], 1, 0.5, saida)
    assert manifesto["status"] == "interrompido_timeout"
    assert manifesto["execucoes_concluidas"] == 1
    assert chamadas == [0, 1]
    assert (saida / "detalhado.csv").exists()
    assert (saida / "resumo.csv").exists()
    assert (saida / "execucoes/00-seed0.json").exists()
    gravado = json.loads((saida / "manifesto.json").read_text(encoding="utf-8"))
    assert [r["status"] for r in gravado["execucoes"]] == ["concluida", "timeout"]
    with pytest.raises(ValueError, match="não vazio"):
        executar_piloto([entrada], [0], 1, 0.5, saida)


def test_validacao_independente_rejeita_objetivo_incorreto(manual, tmp_path):
    caminho = tmp_path / "manual.json"
    salvar_instancia(manual, caminho)
    dados = asdict(comparar(manual, 0, 1))
    dados["vnd"]["makespan"] += 1
    with pytest.raises(ValueError, match="avaliação independente"):
        validar_resultado(caminho, dados)


def test_projecao_escala_grasp_mas_aplica_vnd_uma_vez(tmp_path):
    linhas = []
    arquivos = []
    for n, m, g, v in ((11, 3, 4.1234567890123, 2.0123456789012), (50, 4, 10.0, 8.0)):
        instancia = gerar_instancia(n, m, 0)
        caminho = tmp_path / f"{n}.json"
        salvar_instancia(instancia, caminho)
        arquivos.append(caminho)
        linhas.append({
            "instancia": instancia.identificador, "arquivo": str(caminho),
            "sha256_instancia": str(n), "iteracoes": 100, "alpha": 0.5,
            "origem": "SINTETICA", "makespan_grasp": 10, "makespan_vnd": 9,
            "tempo_grasp_s": g, "tempo_adicional_vnd_s": v, "tempo_total_s": g + v,
            "reducao_percentual": 10.0, "realocacoes_aceitas": 1,
        })
    alvo = gerar_instancia(21, 2, 0)
    caminho_alvo = tmp_path / "21.json"
    salvar_instancia(alvo, caminho_alvo)
    arquivos.append(caminho_alvo)
    projecao = projetar(linhas, arquivos, iteracoes=1000, execucoes=30)
    assert projecao[0]["tempo_grasp_por_execucao_s"] == pytest.approx(10 * linhas[0]["tempo_grasp_s"])
    assert projecao[0]["tempo_vnd_por_execucao_s"] == pytest.approx(linhas[0]["tempo_adicional_vnd_s"])
    assert projecao[0]["tempo_lote_total_s"] == pytest.approx(30 * (10 * linhas[0]["tempo_grasp_s"] + linhas[0]["tempo_adicional_vnd_s"]))
    wg11, _ = cargas(11, 3)
    wg50, _ = cargas(50, 4)
    wg21, _ = cargas(21, 2)
    assert wg11 == pytest.approx(11 ** 2 / 3)
    peso = (21 - 11) / (50 - 11)
    esperado = 10 * wg21 * ((1 - peso) * linhas[0]["tempo_grasp_s"] / wg11 + peso * linhas[1]["tempo_grasp_s"] / wg50)
    assert projecao[2]["tempo_grasp_por_execucao_s"] == pytest.approx(esperado)
    assert projecao[2]["base"] == "interpolacao_taxas_por_carga"
    assert all(r["tipo_dado"] == "PROJECAO_NAO_MEDIDA" for r in projecao)
