from tools.notion_tools import buscar_notion, criar_nota


def test_buscar_notion_sem_resultados(mock_notion_client):
    mock_notion_client.search.return_value = {"results": []}

    resultado = buscar_notion.invoke({"consulta": "reunião"})

    assert resultado == "Nenhuma página encontrada."


def test_buscar_notion_formata_titulos(mock_notion_client):
    mock_notion_client.search.return_value = {
        "results": [
            {
                "url": "https://notion.so/pagina1",
                "properties": {
                    "Name": {
                        "type": "title",
                        "title": [{"plain_text": "Reunião"}, {"plain_text": " semanal"}],
                    }
                },
            }
        ]
    }

    resultado = buscar_notion.invoke({"consulta": "reunião"})

    assert "Reunião semanal" in resultado
    assert "https://notion.so/pagina1" in resultado


def test_criar_nota_usa_database_e_titulo_configurados(mock_notion_client, monkeypatch):
    monkeypatch.setenv("NOTION_TITLE_PROP", "Nome")
    mock_notion_client.pages.create.return_value = {"url": "https://notion.so/nova-pagina"}

    resultado = criar_nota.invoke({"titulo": "Comprar leite", "conteudo": "Linha 1\nLinha 2"})

    _, kwargs = mock_notion_client.pages.create.call_args
    assert kwargs["parent"]["database_id"] == "database-fake"
    assert "Nome" in kwargs["properties"]
    assert kwargs["properties"]["Nome"]["title"][0]["text"]["content"] == "Comprar leite"
    assert len(kwargs["children"]) == 2  # uma linha por bloco de parágrafo
    assert "Comprar leite" in resultado
    assert "https://notion.so/nova-pagina" in resultado


def test_criar_nota_ignora_linhas_em_branco(mock_notion_client):
    mock_notion_client.pages.create.return_value = {"url": "https://notion.so/x"}

    criar_nota.invoke({"titulo": "Nota", "conteudo": "linha\n\n   \noutra linha"})

    _, kwargs = mock_notion_client.pages.create.call_args
    assert len(kwargs["children"]) == 2
