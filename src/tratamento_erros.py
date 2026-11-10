"""Tratamento das falhas de consulta e leitura da NFC-e."""

import sys

import aiohttp


class ErroAplicacao(RuntimeError):
    """Falha esperada no fluxo da NFC-e."""


class ErroConsulta(ErroAplicacao):
    """Falha na comunicação com a SEFAZ."""


class TratadorErros:
    @classmethod
    def classificar_consulta(cls, erro: Exception, timeout: int) -> str:
        """Retorna a mensagem de falhas temporárias ou encerra a consulta."""
        if isinstance(erro, aiohttp.ClientSSLError):
            raise ErroConsulta(
                "Não foi possível estabelecer uma conexão segura com a SEFAZ."
            ) from erro
        if isinstance(erro, aiohttp.TooManyRedirects):
            raise ErroConsulta("A SEFAZ retornou redirecionamentos em excesso.") from erro
        if isinstance(erro, aiohttp.ClientResponseError):
            return cls.tratar_http(erro)
        if isinstance(erro, TimeoutError):
            return f"A SEFAZ não respondeu em até {timeout} segundos."
        if isinstance(erro, (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError)):
            return "Não foi possível concluir a comunicação com a SEFAZ."
        if isinstance(erro, UnicodeError):
            raise ErroConsulta("A resposta da SEFAZ veio com codificação inválida.") from erro
        raise ErroConsulta("Não foi possível realizar a consulta à SEFAZ.") from erro

    @staticmethod
    def tratar_http(erro: aiohttp.ClientResponseError) -> str:
        if 500 <= erro.status < 600:
            return f"O serviço da SEFAZ está indisponível (HTTP {erro.status})."
        if erro.status == 429:
            raise ErroConsulta(
                "A SEFAZ limitou as consultas (HTTP 429). Tente novamente mais tarde."
            ) from erro
        raise ErroConsulta(f"A SEFAZ recusou a consulta (HTTP {erro.status}).") from erro

    @staticmethod
    def xml_invalido() -> ErroAplicacao:
        return ErroAplicacao("A SEFAZ retornou uma resposta XML inválida.")

    @staticmethod
    def qr_invalido() -> ErroAplicacao:
        return ErroAplicacao("O QR Code não contém texto UTF-8 válido.")

    @staticmethod
    def falha_webcam() -> ErroAplicacao:
        return ErroAplicacao("Falha do OpenCV durante a leitura pela webcam.")

    @staticmethod
    def falha_dependencias() -> ErroAplicacao:
        return ErroAplicacao(
            "Não foi possível carregar as dependências da leitura por câmera."
        )

    @staticmethod
    def exibir(erro: Exception) -> int:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
