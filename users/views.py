from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from organizations.serializers import OrganizationSerializer

from .serializers import CustomTokenObtainPairSerializer, SelectOrganizationSerializer, SignupSerializer, UserSerializer
from .utils import build_refresh_token, tokens_to_dict


class SignupView(APIView):
   
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        user = result["user"]
        organization = result["organization"]

        # Reuse the same token serializer as login so both entry points
        # produce identically-shaped tokens/claims.
        refresh = CustomTokenObtainPairSerializer.get_token(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "organization": OrganizationSerializer(organization).data,
                "role": result["membership"].role,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    
    serializer_class = CustomTokenObtainPairSerializer

class SelectOrganizationView(APIView):
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SelectOrganizationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        membership = serializer.membership  # set in validate_organization_id

        refresh = build_refresh_token(request.user, membership=membership)
    
        return Response(
            {
                "organization": {
                    "id": str(membership.organization_id),
                    "name": membership.organization.name,
                    "slug": membership.organization.slug,
                },
                "role": membership.role,
                "tokens": tokens_to_dict(refresh),
            },
            status=status.HTTP_200_OK,
        )


    

