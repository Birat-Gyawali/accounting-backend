from rest_framework.routers import DefaultRouter

from .views import PartyViewSet

router = DefaultRouter()
router.register(r"parties", PartyViewSet, basename="party")

urlpatterns = router.urls