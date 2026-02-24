from django.urls import path
from .views import ValidatePayloadView, JsonSchemaListView, JsonSchemaDetailView

urlpatterns = [
    # 1. Validasi Payload (POST)
    # Endpoint untuk memvalidasi payload JSON yang masuk
    path("validate/", ValidatePayloadView.as_view(), name="schema-validate-payload"),
    # 2. CRUD Skema (List & Create)
    # GET: Mengambil daftar semua skema
    # POST: Membuat skema baru
    path("schemas/", JsonSchemaListView.as_view(), name="schema-list-create"),
    # 3. CRUD Skema (Detail)
    # GET: Mengambil detail skema tertentu
    # PUT/PATCH: Memperbarui skema tertentu
    # DELETE: Menghapus skema tertentu
    path(
        "schemas/<int:pk>/",
        JsonSchemaDetailView.as_view(),
        name="schema-detail-update-delete",
    ),
]
