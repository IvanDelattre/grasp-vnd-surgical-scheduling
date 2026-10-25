"""Modelo validado e entrada/saída JSON; tempos em blocos de 30 minutos."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

Solucao = list[list[str]]


def inteiro(valor: object, nome: str, minimo: int = 0) -> None:
    """Rejeita inclusive bool, que em Python é uma subclasse de int."""
    if type(valor) is not int or valor < minimo:
        raise ValueError(f"{nome} deve ser inteiro >= {minimo}")


@dataclass(frozen=True)
class Cirurgia:
    id: str
    duracao: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("ID da cirurgia deve ser texto não vazio")
        inteiro(self.duracao, "duração", 1)


@dataclass(frozen=True)
class Instancia:
    identificador: str
    numero_salas: int
    cirurgias: tuple[Cirurgia, ...]
    preparacao: tuple[tuple[int, ...], ...]
    origem: str = "NAO_INFORMADA"
    metadados: Mapping[str, Any] = field(default_factory=dict)
    _indices: Mapping[str, int] = field(init=False, repr=False, compare=False)
    duracoes: Mapping[str, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.identificador, str) or not self.identificador.strip():
            raise ValueError("Identificador deve ser texto não vazio")
        inteiro(self.numero_salas, "número de salas", 1)
        cirurgias = tuple(self.cirurgias)
        matriz = tuple(tuple(linha) for linha in self.preparacao)
        if not cirurgias or not all(isinstance(c, Cirurgia) for c in cirurgias):
            raise ValueError("Informe pelo menos uma Cirurgia válida")
        ids = [c.id for c in cirurgias]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs de cirurgias devem ser únicos")
        n = len(ids)
        if len(matriz) != n or any(len(linha) != n for linha in matriz):
            raise ValueError("Matriz de preparação deve ser N x N")
        for linha in matriz:
            for valor in linha:
                inteiro(valor, "preparação")
        if not isinstance(self.origem, str) or not self.origem.strip():
            raise ValueError("Origem deve ser texto não vazio")
        object.__setattr__(self, "cirurgias", cirurgias)
        object.__setattr__(self, "preparacao", matriz)
        object.__setattr__(self, "metadados", MappingProxyType(deepcopy(dict(self.metadados))))
        object.__setattr__(self, "_indices", MappingProxyType(dict(zip(ids, range(n)))))
        object.__setattr__(self, "duracoes", MappingProxyType({c.id: c.duracao for c in cirurgias}))

    def setup(self, anterior: str, seguinte: str) -> int:
        """Consulta p[anterior, seguinte], sem supor simetria."""
        return self.preparacao[self._indices[anterior]][self._indices[seguinte]]

    def para_dict(self) -> dict[str, Any]:
        return {
            "identificador": self.identificador,
            "numero_salas": self.numero_salas,
            "unidade_minutos": 30,
            "origem": self.origem,
            "cirurgias": [{"id": c.id, "duracao": c.duracao} for c in self.cirurgias],
            "preparacao": [list(linha) for linha in self.preparacao],
            "metadados": deepcopy(dict(self.metadados)),
        }


def instancia_de_dict(dados: dict[str, Any]) -> Instancia:
    """A linha/coluna i da matriz corresponde à cirurgia i no JSON."""
    try:
        if not isinstance(dados, dict):
            raise ValueError("Raiz do JSON deve ser um objeto")
        unidade = dados.get("unidade_minutos", 30)
        if type(unidade) is not int or unidade != 30:
            raise ValueError("unidade_minutos deve ser 30")
        return Instancia(
            identificador=dados["identificador"],
            numero_salas=dados["numero_salas"],
            cirurgias=tuple(Cirurgia(c["id"], c["duracao"]) for c in dados["cirurgias"]),
            preparacao=tuple(tuple(linha) for linha in dados["preparacao"]),
            origem=dados.get("origem", "NAO_INFORMADA"),
            metadados=dados.get("metadados", {}),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Estrutura de instância inválida: {exc}") from exc


def carregar_instancia(caminho: str | Path) -> Instancia:
    return instancia_de_dict(json.loads(Path(caminho).read_text(encoding="utf-8-sig")))


def salvar_instancia(instancia: Instancia, caminho: str | Path) -> None:
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(instancia.para_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
