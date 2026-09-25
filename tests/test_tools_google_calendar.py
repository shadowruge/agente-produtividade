from tools.google_calendar import criar_evento, listar_eventos


def test_listar_eventos_sem_resultados(mock_google_service):
    mock_google_service.events().list().execute.return_value = {}

    resultado = listar_eventos.invoke({"dias": 5})

    assert "Nenhum evento" in resultado
    assert "5" in resultado


def test_listar_eventos_formata_saida(mock_google_service):
    mock_google_service.events().list().execute.return_value = {
        "items": [
            {"start": {"dateTime": "2026-09-24T10:00:00-03:00"}, "summary": "Dentista"},
            {"start": {"date": "2026-09-25"}},  # evento de dia inteiro, sem título
        ]
    }

    resultado = listar_eventos.invoke({})

    assert "Dentista" in resultado
    assert "2026-09-24T10:00:00-03:00" in resultado
    assert "(sem título)" in resultado


def test_listar_eventos_usa_intervalo_padrao_de_7_dias(mock_google_service):
    mock_google_service.events().list().execute.return_value = {}

    resultado = listar_eventos.invoke({})

    assert "7 dias" in resultado


def test_criar_evento_chama_api_com_dados_corretos(mock_google_service):
    mock_google_service.events().insert().execute.return_value = {
        "summary": "Reunião",
        "htmlLink": "https://calendar.google.com/evento123",
    }

    resultado = criar_evento.invoke(
        {
            "titulo": "Reunião",
            "inicio": "2026-09-24T14:00:00",
            "fim": "2026-09-24T15:00:00",
            "descricao": "Alinhamento semanal",
        }
    )

    _, kwargs = mock_google_service.events().insert.call_args
    assert kwargs["calendarId"] == "primary"
    assert kwargs["body"]["summary"] == "Reunião"
    assert kwargs["body"]["start"]["dateTime"] == "2026-09-24T14:00:00"
    assert kwargs["body"]["end"]["dateTime"] == "2026-09-24T15:00:00"
    assert "Reunião" in resultado
    assert "https://calendar.google.com/evento123" in resultado
