from rest_framework import serializers
from .models import XRPLAccount

class XRPLAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = XRPLAccount
        fields = '__all__'