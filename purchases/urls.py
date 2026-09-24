from rest_framework.routers import DefaultRouter
from .views import PurchaseBillViewSet


router = DefaultRouter()
router.register(r"bills", PurchaseBillViewSet, basename="purchase-bill")

urlpatterns = router.urls