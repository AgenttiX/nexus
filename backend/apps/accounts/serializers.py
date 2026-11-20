"""Serializers for accounts."""

from typing import Any

from rest_framework import serializers

from apps.accounts.models import AgentToken, User


class CurrentUserSerializer(serializers.ModelSerializer[User]):
    """The signed-in user, as shown in the interface."""

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email")
        read_only_fields = fields


class AgentTokenSerializer(serializers.ModelSerializer[AgentToken]):
    """An agent token without its secret, which cannot be recovered after creation."""

    class Meta:
        model = AgentToken
        fields: tuple[str, ...] = ("id", "name", "hint", "scopes", "created_at", "expires_at", "last_used_at")
        read_only_fields = ("id", "hint", "created_at", "last_used_at")

    def validate_name(self, value: str) -> str:
        """Reject a name that the user already uses, as the database would."""
        user = self.context["request"].user
        if AgentToken.objects.for_user(user).filter(name=value).exists():
            msg = "You already have a token with this name."
            raise serializers.ValidationError(msg)
        return value

    def create(self, validated_data: dict[str, Any]) -> AgentToken:
        """Create the token and keep its plaintext for the response."""
        token, plaintext = AgentToken.objects.create_token(**validated_data)
        self.plaintext = plaintext
        return token


class CreatedAgentTokenSerializer(AgentTokenSerializer):
    """A newly created agent token, including the secret. Shown exactly once."""

    token = serializers.SerializerMethodField()

    class Meta(AgentTokenSerializer.Meta):
        fields = (*AgentTokenSerializer.Meta.fields, "token")

    def get_token(self, obj: AgentToken) -> str:
        """Return the plaintext that ``create`` generated."""
        return self.plaintext
