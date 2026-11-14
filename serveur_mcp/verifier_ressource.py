"""
verifier_ressource.py : vérifie la ressource « agence » comme le ferait un vrai agent.

Image simple : on joue le rôle d'un CLIENT qui se présente au guichet (le serveur MCP),
demande « qu'est-ce que vous proposez ? », puis lit l'affiche au mur (la ressource).

Lancement, depuis la racine du dépôt (venv activé, base créée) :
    python serveur_mcp/verifier_ressource.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVEUR = Path(__file__).parent / "serveur.py"


async def main():
    # 1. On dit comment lancer le serveur : le client le démarre lui-même (transport stdio)
    parametres = StdioServerParameters(command=sys.executable, args=[str(SERVEUR)])

    async with stdio_client(parametres) as (lecture, ecriture):
        async with ClientSession(lecture, ecriture) as session:
            # 2. Poignée de main MCP : le client et le serveur se présentent
            await session.initialize()

            # 3. Ce que propose le guichet : les outils (actions) et les ressources (affiches)
            outils = await session.list_tools()
            ressources = await session.list_resources()
            print("Outils     :", [o.name for o in outils.tools])
            print("Ressources :", [str(r.uri) for r in ressources.resources])

            # 4. On lit l'affiche « agence »
            contenu = await session.read_resource("agence://infos")
            print("\nContenu de agence://infos :")
            print(contenu.contents[0].text)


if __name__ == "__main__":
    asyncio.run(main())
