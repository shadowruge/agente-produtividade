from tools.gmail import criar_rascunho, ler_email, listar_emails


def test_listar_emails_sem_resultados(mock_google_service):
    mock_google_service.users().messages().list().execute.return_value = {}

    resultado = listar_emails.invoke({})

    assert resultado == "Nenhum e-mail encontrado."


def test_listar_emails_formata_saida(mock_google_service):
    mock_google_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}]
    }
    mock_google_service.users().messages().get().execute.return_value = {
        "payload": {
            "headers": [
                {"name": "From", "value": "alguem@exemplo.com"},
                {"name": "Subject", "value": "Assunto de teste"},
                {"name": "Date", "value": "Wed, 23 Sep 2026 10:00:00 -0300"},
            ]
        }
    }

    resultado = listar_emails.invoke({"consulta": "is:unread", "maximo": 5})

    assert "msg1" in resultado
    assert "alguem@exemplo.com" in resultado
    assert "Assunto de teste" in resultado
    _, kwargs = mock_google_service.users().messages().list.call_args
    assert kwargs["q"] == "is:unread"
    assert kwargs["maxResults"] == 5


def test_ler_email_extrai_texto_simples(mock_google_service):
    corpo_b64 = "T2xhLCB0dWRvIGJlbT8="  # "Ola, tudo bem?"
    mock_google_service.users().messages().get().execute.return_value = {
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": corpo_b64},
            "headers": [
                {"name": "From", "value": "chefe@empresa.com"},
                {"name": "Subject", "value": "Reunião"},
                {"name": "Date", "value": "hoje"},
            ],
        },
        "snippet": "resumo",
    }

    resultado = ler_email.invoke({"id_email": "abc123"})

    assert "chefe@empresa.com" in resultado
    assert "Reunião" in resultado
    assert "Ola, tudo bem?" in resultado


def test_ler_email_usa_snippet_se_sem_corpo(mock_google_service):
    mock_google_service.users().messages().get().execute.return_value = {
        "payload": {"headers": []},
        "snippet": "prévia do e-mail",
    }

    resultado = ler_email.invoke({"id_email": "abc123"})

    assert "prévia do e-mail" in resultado


def test_criar_rascunho_nao_envia_apenas_cria(mock_google_service):
    resultado = criar_rascunho.invoke(
        {"para": "destino@exemplo.com", "assunto": "Oi", "corpo": "Mensagem de teste"}
    )

    mock_google_service.users().drafts().create.assert_called_once()
    _, kwargs = mock_google_service.users().drafts().create.call_args
    assert kwargs["userId"] == "me"
    assert "raw" in kwargs["body"]["message"]
    assert "destino@exemplo.com" in resultado
    assert "Rascunho criado" in resultado
