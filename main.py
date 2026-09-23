import argparse

import config  # noqa: F401  (carrega o .env)


def modo_cli() -> None:
    from agents.productivity_agent import ProductivityAgent

    agente = ProductivityAgent()
    print("Agente de produtividade (digite 'sair' para encerrar)")
    while True:
        try:
            texto = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if texto.lower() in {"sair", "exit", "quit"}:
            break
        if texto:
            print("\nAgente:", agente.perguntar("cli", texto)["resposta"])


def main() -> None:
    p = argparse.ArgumentParser(description="Agente de produtividade")
    p.add_argument("--cli", action="store_true", help="usar o chat no terminal em vez da interface web")
    p.add_argument("--auth", action="store_true", help="apenas autorizar a conta Google e sair")
    p.add_argument("--host", default="127.0.0.1", help="use 127.0.0.1: a interface acessa seu e-mail e agenda")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    if args.auth:
        from config.google_auth import get_credentials

        get_credentials()
        print("Google autorizado. token.json salvo.")
    elif args.cli:
        modo_cli()
    else:
        import uvicorn

        uvicorn.run("web.server:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
