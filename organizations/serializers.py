from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Organization, Membership, Role

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "currency", "pan_number", "is_active", "created_at"]
        read_only_fields = fields


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "email", "full_name", "role", "role_display", "is_active", "created_at"]
        read_only_fields = ["id", "user", "email", "full_name", "role_display", "created_at"]


class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.STAFF)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        organization_id = self.context["organization_id"]
        email = attrs["email"]

        if Membership.objects.filter(organization_id=organization_id, user__email__iexact=email).exists():
            raise serializers.ValidationError({"email": "This user is already a member of this organization."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        organization_id = self.context["organization_id"]
        email = validated_data["email"]
        full_name = validated_data.get("full_name", "")
        role = validated_data["role"]
        password = validated_data["password"]

        # Check if user exists
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
            )

        membership = Membership.objects.create(
            organization_id=organization_id,
            user=user,
            role=role,
            is_active=True,
        )
        return membership


class MembershipUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["role", "is_active"]

    def validate(self, attrs):
        # Prevent changing own role (checked in view)
        # Prevent deactivating last OWNER
        if "is_active" in attrs and attrs["is_active"] is False:
            if self.instance.role == Role.OWNER:
                org_id = self.instance.organization_id
                other_owners = Membership.objects.filter(
                    organization_id=org_id, role=Role.OWNER, is_active=True
                ).exclude(pk=self.instance.pk)
                if not other_owners.exists():
                    raise serializers.ValidationError("Cannot deactivate the last OWNER of this organization.")
        return attrs