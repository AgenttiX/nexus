"""Serializers for investments."""

from rest_framework import serializers

from apps.investments import providers, services
from apps.investments.models import Asset, Holding, Provider


class AssetSerializer(serializers.ModelSerializer[Asset]):
    """An asset."""

    class Meta:
        model = Asset
        fields = ("id", "provider", "symbol", "name", "currency")


class HoldingSerializer(serializers.ModelSerializer[Holding]):
    """A holding. On creation the asset is named by its provider and symbol."""

    asset = AssetSerializer(read_only=True)
    provider = serializers.ChoiceField(choices=Provider.choices, write_only=True, required=False)
    symbol = serializers.CharField(max_length=50, write_only=True, required=False)

    class Meta:
        model = Holding
        fields = ("id", "asset", "provider", "symbol", "quantity", "cost", "note")

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Look up the asset of a new holding. The asset of an existing holding cannot be changed."""
        provider, symbol = attrs.pop("provider", None), attrs.pop("symbol", None)
        if self.instance is not None:
            return attrs
        if not provider or not symbol:
            msg = "A new holding needs a provider and a symbol."
            raise serializers.ValidationError(msg)
        try:
            attrs["asset"] = services.get_or_create_asset(str(provider), str(symbol))
        except providers.UnknownAssetError as error:
            raise serializers.ValidationError(
                {"symbol": "The provider does not know this symbol."}
            ) from error
        except Exception as error:
            raise serializers.ValidationError(
                {"symbol": "Prices could not be fetched. Try again later."}
            ) from error
        return attrs


class PositionSerializer(serializers.Serializer[object]):
    """A holding with its latest price and value. Unknown values are null."""

    holding = HoldingSerializer()
    price = serializers.DecimalField(max_digits=20, decimal_places=8, allow_null=True)
    price_date = serializers.DateField(allow_null=True)
    value_eur = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    gain_eur = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)


class ValuePointSerializer(serializers.Serializer[object]):
    """The total value of the portfolio on one day."""

    date = serializers.DateField()
    value_eur = serializers.DecimalField(max_digits=14, decimal_places=2)


class PortfolioSerializer(serializers.Serializer[object]):
    """The portfolio with its total value and its development over the last year."""

    total_eur = serializers.DecimalField(max_digits=14, decimal_places=2)
    positions = PositionSerializer(many=True)
    history = ValuePointSerializer(many=True)
