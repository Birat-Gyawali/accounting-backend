from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from organizations.models import Membership, Organization, Role
from organizations.serializers import OrganizationSerializer
from .utils import build_refresh_token

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of a User -- never exposes the password hash."""

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone_number", "created_at"]
        read_only_fields = fields


class SignupSerializer(serializers.Serializer):
    

    organization_name = serializers.CharField(max_length=255)

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        
        organization = Organization.objects.create(name=validated_data["organization_name"])

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
            phone_number=validated_data.get("phone_number", ""),
        )

        membership = Membership.objects.create(
            organization=organization,
            user=user,
            role=Role.OWNER,
        )

        return {"user": user, "organization": organization, "membership": membership}

class SelectOrganizationSerializer(serializers.Serializer):
    
    organization_id = serializers.UUIDField()

    def validate_organization_id(self, value):
        request = self.context["request"]
        membership = (
            Membership.objects.select_related("organization")
            .filter(
                organization_id=value,
                organization__is_active=True,
                user=request.user,
                is_active=True,
            )
            .first()
        )
        if membership is None:
            raise serializers.ValidationError("You do not have access to this organization.")

        self.membership = membership
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
   
    @classmethod
    def get_token(cls, user):
        return build_refresh_token(user, membership=None)

    def validate(self, attrs):
        data = super().validate(attrs)  # does the actual email+password check

        data["user"] = UserSerializer(self.user).data
        data["organizations"] = [
            {
                "id": str(membership.organization_id),
                "name": membership.organization.name,
                "slug": membership.organization.slug,
                "role": membership.role,
            }
            for membership in self.user.memberships.select_related("organization").filter(is_active=True)
        ]
        return data