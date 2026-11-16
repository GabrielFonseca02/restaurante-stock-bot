"""Helper para navegar pelo HTML com Beautiful Soup."""

from bs4 import BeautifulSoup, Tag


class TagComTextoDireto(Tag):
    @property
    def texto_direto(self) -> str:
        return texto_direto(self)


def parse_html(html_content: str | bytes) -> BeautifulSoup:
    """Retorna o HTML como Beautiful Soup para usar find, find_all e select."""
    return BeautifulSoup(
        html_content, "html.parser", element_classes={Tag: TagComTextoDireto}
    )

def texto_direto(elemento: Tag) -> str:
    """Extrai apenas o texto do elemento, sem o texto de tags filhas."""
    return "".join(elemento.find_all(string=True, recursive=False)).strip()
