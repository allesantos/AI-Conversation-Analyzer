"""CLI operacional — desbloqueio e cota de IA na demo.

Uso (API container na VPS):
  python -m app.cli unlock-user email@exemplo.com
  python -m app.cli lock-user email@exemplo.com
  python -m app.cli show-user email@exemplo.com
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import update

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.demo_access import get_demo_quota, is_demo_owner_email, user_has_ai_access
from app.models.user import User
from app.repositories.user import UserRepository


async def _set_access(email: str, enabled: bool) -> int:
    settings = get_settings()
    normalized = email.strip().lower()
    if not normalized:
        print("E-mail inválido.", file=sys.stderr)
        return 1

    if is_demo_owner_email(normalized, settings) and not enabled:
        print(
            f"Conta owner ({settings.demo_owner_email}) não pode ser bloqueada.",
            file=sys.stderr,
        )
        return 1

    async with SessionLocal() as session:
        users = UserRepository(session)
        user = await users.get_by_email(normalized)
        if user is None:
            print(f"Usuário não encontrado: {normalized}", file=sys.stderr)
            return 1

        await session.execute(
            update(User).where(User.id == user.id).values(ai_access_enabled=enabled)
        )
        await session.commit()
        state = "LIBERADO" if enabled else "BLOQUEADO"
        print(f"{normalized}: IA {state}")
    return 0


async def _show_user(email: str) -> int:
    settings = get_settings()
    normalized = email.strip().lower()
    async with SessionLocal() as session:
        user = await UserRepository(session).get_by_email(normalized)
        if user is None:
            print(f"Usuário não encontrado: {normalized}", file=sys.stderr)
            return 1
        effective = user_has_ai_access(user, settings)
        print(f"{user.email}")
        print(f"  ai_access_enabled={user.ai_access_enabled}")
        print(f"  effective_access={effective}")
        if effective:
            quota = await get_demo_quota(session, user, settings)
            if quota.unlimited:
                print("  quota=unlimited (owner)")
            else:
                print(
                    f"  llm={quota.llm_used}/{quota.llm_limit} "
                    f"(restam {quota.llm_remaining})"
                )
                print(
                    f"  audio_sec={quota.audio_seconds_used:.1f}/"
                    f"{quota.audio_seconds_limit:.0f} "
                    f"(restam {quota.audio_seconds_remaining:.1f}s)"
                )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI demo AI access")
    sub = parser.add_subparsers(dest="command", required=True)

    unlock = sub.add_parser("unlock-user", help="Libera uso de IA para o e-mail")
    unlock.add_argument("email")

    lock = sub.add_parser("lock-user", help="Bloqueia uso de IA para o e-mail")
    lock.add_argument("email")

    show = sub.add_parser("show-user", help="Mostra status de acesso e cota de IA")
    show.add_argument("email")

    args = parser.parse_args(argv)

    if args.command == "unlock-user":
        return asyncio.run(_set_access(args.email, True))
    if args.command == "lock-user":
        return asyncio.run(_set_access(args.email, False))
    if args.command == "show-user":
        return asyncio.run(_show_user(args.email))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
