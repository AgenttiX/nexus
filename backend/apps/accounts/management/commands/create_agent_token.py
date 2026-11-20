"""Create an agent token from the command line."""

from argparse import ArgumentParser

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import AgentToken, User


class Command(BaseCommand):
    """Create a bearer token with which an AI agent can use the MCP server."""

    help = "Create an agent token for a user and print it once."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare the command's arguments."""
        parser.add_argument("username")
        parser.add_argument("name", help="Which agent will use the token.")
        parser.add_argument(
            "scopes", nargs="*", metavar="feature=access", help="For example sleep=read finance=write."
        )

    def handle(self, *args: object, **options: object) -> None:
        """Create the token and print its plaintext."""
        username, name, scope_arguments = str(options["username"]), str(options["name"]), options["scopes"]
        assert isinstance(scope_arguments, list)  # noqa: S101 - argparse gives a list for nargs="*"
        user = User.objects.filter(username=username).first()
        if user is None:
            msg = f"No user named {username!r}."
            raise CommandError(msg)
        scopes: dict[str, str] = {}
        for item in scope_arguments:
            feature, _, access = str(item).partition("=")
            scopes[feature] = access
        try:
            _, plaintext = AgentToken.objects.create_token(user, name, scopes)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        self.stdout.write(plaintext)
