from rest_framework.routers import DefaultRouter
from .views import AccountViewSet
from .views import JournalEntryViewSet

router = DefaultRouter()
router.register(r"accounts", AccountViewSet, basename="account")
router.register(r"journal-entries", JournalEntryViewSet, basename="journal-entry")
urlpatterns = router.urls