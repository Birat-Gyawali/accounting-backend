from django.contrib import admin
from django.urls import path
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    path('api/', include('parties.urls')),
    path('api/accounting/', include('accounting.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/purchases/', include('purchases.urls')),
    path('api/', include('payments.urls')),
    path('api/', include('organizations.urls')),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path('api/reports/', include('reports.urls'))
]
