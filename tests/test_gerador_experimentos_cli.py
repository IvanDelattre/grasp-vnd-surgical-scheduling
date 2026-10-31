import csv
import json

import pytest

from grasp_vnd.cli import main
from grasp_vnd.experimentos import executar_experimentos, resumir
from grasp_vnd.gerador import gerar_instancia, gerar_suite
from grasp_vnd.problema import carregar_instancia, salvar_instancia


def test_suite_tamanhos_perfis_e_reprodutibilidade(tmp_path):
    arquivos = gerar_suite(tmp_path)
    assert len(arquivos) == 14
    instancias = [carregar_instancia(c) for c in arquivos]
    assert {len(i.cirurgias) for i in instancias} == {11, 21, 50, 75, 100, 130, 200}
    assert {i.metadados["perfil"] for i in instancias} == {"simples", "sequencia"}
    assert all(i.origem == "SINTETICA" and i.identificador.startswith("SINTETICA-") for i in instancias)
    a, b = gerar_instancia(11, 3, 12), gerar_instancia(11, 3, 12)
    assert a.para_dict() == b.para_dict()


def test_experimentos_csv_e_resumo(manual, tmp_path):
    caminho = tmp_path / "manual.json"
    salvar_instancia(manual, caminho)
    linhas = executar_experimentos([caminho], [1, 2, 3], 3, diretorio_saida=tmp_path / "saida")
    assert len(linhas) == 3
    assert all(r["makespan_vnd"] <= r["makespan_grasp"] for r in linhas)
    assert all(r["origem"] == "SINTETICA" for r in linhas)
    with (tmp_path / "saida/detalhado.csv").open(encoding="utf-8", newline="") as arquivo:
        gravadas = list(csv.DictReader(arquivo))
    assert len(gravadas) == 3
    assert json.loads(gravadas[0]["solucao_vnd"]) == json.loads(linhas[0]["solucao_vnd"])
    resumo = resumir(linhas)
    assert resumo[0]["execucoes"] == 3
    assert resumo[0]["melhor_grasp"] == min(r["makespan_grasp"] for r in linhas)
    assert resumo[0]["media_tempo_total_s"] >= 0
    assert (tmp_path / "saida/resumo.csv").exists()


def test_cli_gerar_comparar_experimentar(tmp_path, capsys):
    caminho = tmp_path / "instancias/pequena.json"
    assert main(["gerar", "--cirurgias", "5", "--salas", "2", "--saida", str(caminho)]) == 0
    capsys.readouterr()
    resultado = tmp_path / "resultado.json"
    assert main(["comparar", str(caminho), "--iteracoes", "3", "--saida", str(resultado)]) == 0
    impresso = json.loads(capsys.readouterr().out)
    assert impresso == json.loads(resultado.read_text(encoding="utf-8"))
    assert main(["experimentar", str(caminho.parent), "--iteracoes", "2", "--seeds", "4", "5", "--saida", str(tmp_path / "csv")]) == 0
    assert (tmp_path / "csv/resumo.csv").exists()


def test_cli_erro_amigavel(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["gerar", "--cirurgias", "0", "--salas", "2", "--saida", str(tmp_path / "x.json")])
    assert exc.value.code == 2
    assert "inteiro" in capsys.readouterr().err


@pytest.mark.parametrize("seeds", [[], [1, 1], [-1]])
def test_experimentos_rejeitam_seeds_invalidas(manual, tmp_path, seeds):
    caminho = tmp_path / "instancia.json"
    salvar_instancia(manual, caminho)
    with pytest.raises(ValueError):
        executar_experimentos([caminho], seeds, diretorio_saida=tmp_path)
