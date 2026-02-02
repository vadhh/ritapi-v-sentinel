import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import JsonEnforcerService
from .models import JsonSchema
from django.db import IntegrityError # Untuk menangani kendala DB yang mungkin terlewat

# Inisialisasi logger
logger = logging.getLogger(__name__)

# --- 1. VIEWS UNTUK VALIDASI PAYLOAD ---

class ValidatePayloadView(APIView):
    """
    Endpoint untuk memvalidasi payload JSON terhadap skema aktif yang cocok.
    Contoh: POST /validate/
    """
    def post(self, request):
        endpoint = request.data.get('endpoint')
        method = request.data.get('method')
        payload = request.data.get('payload') # Payload yang dikirim sebagai bagian dari body request
        version = request.data.get('version', 'v1')

        if not endpoint or not method or payload is None:
            logger.warning("Missing required fields in ValidatePayloadView POST request.")
            return Response(
                {"error": "Missing required fields: endpoint, method, and payload."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Panggil service validation
        result = JsonEnforcerService.validate_payload(
            endpoint=endpoint,
            method=method,
            payload_raw=payload,
            version=version
        )
        
        # Logika sederhana untuk respons berdasarkan rollout_mode (opsional)
        if result['valid']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            # Jika tidak valid dan mode enforce, kembalikan 400 atau 403
            rollout_mode = result.get('rollout_mode', 'monitor')
            response_status = status.HTTP_400_BAD_REQUEST if rollout_mode == 'enforce' else status.HTTP_200_OK
            
            # Jika mode enforce, log error dan kembalikan status error
            if rollout_mode == 'enforce':
                logger.error(f"Schema enforcement block: Endpoint={endpoint}, Method={method}, Error={result['message']}")
                return Response(result, status=response_status)
            else:
                # Jika mode monitor, log warning dan tetap kembalikan 200
                logger.warning(f"Schema violation detected (Monitor mode): Endpoint={endpoint}, Method={method}, Error={result['message']}")
                return Response(result, status=status.HTTP_200_OK)


# --- 2. VIEWS UNTUK MANAJEMEN SKEMA (CRUD) ---

class JsonSchemaListView(APIView):
    """
    List semua skema (GET) dan buat skema baru (POST).
    Endpoint: /schemas/
    """
    
    def get(self, request):
        limit = int(request.query_params.get('limit', 100))
        offset = int(request.query_params.get('offset', 0))
        
        schemas = JsonEnforcerService.list_schemas(limit=limit, offset=offset)
        
        # Serialisasi sederhana
        data = [{
            "id": s.id,
            "name": s.name,
            "endpoint": s.endpoint,
            "method": s.method,
            "version": s.version,
            "rollout_mode": s.rollout_mode,
            "is_active": s.is_active,
            "timestamp": s.timestamp,
        } for s in schemas]
        
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data
        
        # Cek ketersediaan field dasar
        if not data.get('endpoint') or not data.get('method') or not data.get('schema_json'):
            return Response(
                {"error": "Missing required fields: endpoint, method, or schema_json."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            schema = JsonEnforcerService.create_schema(data)
            logger.info(f"Schema created: ID={schema.id}, Endpoint={schema.endpoint} v{schema.version}")
            return Response(
                {"message": "Schema created successfully", "id": schema.id},
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            # Menangkap ValueError dari service (kendala unik atau validasi data)
            logger.warning(f"Schema creation failed (Conflict/Validation): {e}")
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            logger.exception(f"Unexpected error during schema creation: {e}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JsonSchemaDetailView(APIView):
    """
    Retrieve, Update, dan Delete skema tunggal.
    Endpoint: /schemas/<int:pk>/
    """
    
    def get(self, request, pk):
        schema = JsonEnforcerService.get_schema(pk)
        if not schema:
            return Response({"error": "Schema not found"}, status=status.HTTP_404_NOT_FOUND)

        data = {
            "id": schema.id,
            "name": schema.name,
            "endpoint": schema.endpoint,
            "method": schema.method,
            "schema_json": schema.schema_json,
            "description": schema.description,
            "version": schema.version,
            "rollout_mode": schema.rollout_mode,
            "is_active": schema.is_active,
            "timestamp": schema.timestamp,
        }
        return Response(data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        data = request.data
        
        try:
            schema = JsonEnforcerService.update_schema(pk, data)
            if not schema:
                return Response({"error": "Schema not found"}, status=status.HTTP_404_NOT_FOUND)
            
            logger.info(f"Schema updated: ID={schema.id}")
            return Response(
                {"message": "Schema updated successfully", "id": schema.id},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            # Menangkap ValueError dari service (kendala unik atau validasi data)
            logger.warning(f"Schema update failed (Conflict/Validation) for ID {pk}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            logger.exception(f"Unexpected error during schema update for ID {pk}: {e}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        deleted = JsonEnforcerService.delete_schema(pk)
        
        if deleted:
            logger.info(f"Schema deleted: ID={pk}")
            return Response({"message": f"Schema ID {pk} deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        
        return Response({"error": "Schema not found"}, status=status.HTTP_404_NOT_FOUND)