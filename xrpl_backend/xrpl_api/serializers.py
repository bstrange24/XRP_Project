from rest_framework import serializers
from .models import XrplAccountData # XRPLAccount

class XRPLAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = XrplAccountData
        fields = '__all__'