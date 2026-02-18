import json
from jsonschema import validate, ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import JsonSchema
import logging

logger = logging.getLogger("schema_enforcer")

class JsonEnforcerService:
    # --- FUNGSI VALIDASI PAYLOAD ---
    @staticmethod
    def validate_payload(endpoint: str, method: str, payload_raw, version: str = "v1"):
        """
        Validate JSON payload against the most specific schema found (endpoint, method, version).
        If the specific version is not found, it falls back to version 'v1'.
        """
        # 1. Try to parse payload
        try:
            if isinstance(payload_raw, (str, bytes)):
                payload = json.loads(payload_raw)
            elif isinstance(payload_raw, dict):
                payload = payload_raw
            else:
                return {"valid": False, "message": "Unsupported payload type: Must be JSON string, bytes, or dict"}
        except json.JSONDecodeError as e:
            return {"valid": False, "message": f"Malformed JSON: {e}"}
        
        if not payload:
             return {"valid": True, "message": "Empty or Null payload, skipped schema validation"}

        # 2. Find the appropriate schema
        method_upper = method.upper()
        
        # -- A. Coba cari skema dengan versi SPESIFIK yang diminta --
        schema = JsonSchema.objects.filter(
            endpoint=endpoint, 
            method=method_upper, 
            version=version, 
            is_active=True
        ).first()

        # -- B. Jika skema spesifik tidak ditemukan, coba FALLBACK ke versi default (v1) --
        fallback_used = False
        if not schema and version != "v1":
            logger.info(f"Schema for {method_upper} {endpoint} v{version} not found. Trying fallback to v1.")
            schema = JsonSchema.objects.filter(
                endpoint=endpoint, 
                method=method_upper, 
                version="v1", 
                is_active=True
            ).first()
            fallback_used = True

        if not schema:
            return {"valid": True, "message": f"No active schema configured for {method} {endpoint} (version {version}), validation skipped"}

        # 3. Perform Validation
        try:
            schema_data = schema.schema_json
            
            if isinstance(schema_data, str): 
                schema_data = json.loads(schema_data)

            validate(instance=payload, schema=schema_data)
            
            # Jika validasi berhasil
            version_info = f" (using fallback v1)" if fallback_used else ""
            return {
                "valid": True, 
                "message": f"Payload is valid{version_info}",
                "rollout_mode": schema.rollout_mode
            }
            
        except ValidationError as e:
            # Jika validasi skema gagal
            return {
                "valid": False, 
                "message": f"Schema validation failed: {e.message}",
                "rollout_mode": schema.rollout_mode
            }
        except Exception as e:
            logger.error(f"Error processing schema for {endpoint}: {e}")
            return {"valid": False, "message": f"Unexpected error during schema processing: {e}"}


    # --- FUNGSI CRUD SKEMA ---

    @staticmethod
    def create_schema(data: dict):
        """
        Create a new JsonSchema entry.
        Raises ValueError if unique constraint (endpoint, method, version) is violated.
        """
        # 1. Normalisasi data method
        data['method'] = data.get('method', '').upper()
        
        # 2. Validasi unik sebelum membuat objek
        if JsonSchema.objects.filter(
            endpoint=data.get('endpoint'),
            method=data['method'],
            version=data.get('version', 'v1')
        ).exists():
            raise ValueError("Schema with this endpoint, method, and version already exists.")

        # 3. Buat objek
        try:
            schema = JsonSchema.objects.create(
                name=data.get('name'),
                endpoint=data.get('endpoint'),
                method=data['method'],
                schema_json=data.get('schema_json', {}),
                description=data.get('description'),
                version=data.get('version', 'v1'),
                rollout_mode=data.get('rollout_mode', 'monitor'),
                is_active=data.get('is_active', True)
            )
            return schema
        except DjangoValidationError as e:
            raise ValueError(f"Data validation failed: {e}")
        except Exception as e:
            raise Exception(f"Failed to create schema: {e}")

    @staticmethod
    def get_schema(schema_id: int):
        """
        Retrieve a JsonSchema entry by ID.
        Returns None if not found.
        """
        try:
            return JsonSchema.objects.get(pk=schema_id)
        except JsonSchema.DoesNotExist:
            return None

    @staticmethod
    def update_schema(schema_id: int, data: dict):
        """
        Update an existing JsonSchema entry by ID.
        Raises ValueError if unique constraint is violated during update.
        Returns the updated JsonSchema object, or None if ID not found.
        """
        try:
            schema = JsonSchema.objects.get(pk=schema_id)
        except JsonSchema.DoesNotExist:
            return None

        # 1. Normalisasi data method
        if 'method' in data:
            data['method'] = data['method'].upper()
        
        # 2. Validasi unik jika endpoint, method, atau version diubah
        new_endpoint = data.get('endpoint', schema.endpoint)
        new_method = data.get('method', schema.method)
        new_version = data.get('version', schema.version)

        # Cek apakah kombinasi baru sudah ada di objek lain
        if (new_endpoint != schema.endpoint or 
            new_method != schema.method or 
            new_version != schema.version):
            
            if JsonSchema.objects.filter(
                endpoint=new_endpoint,
                method=new_method,
                version=new_version
            ).exclude(pk=schema_id).exists():
                raise ValueError("Update failed: Schema with this endpoint, method, and version already exists.")

        # 3. Update fields
        for field, value in data.items():
            setattr(schema, field, value)

        try:
            schema.full_clean() # Pengecekan validasi model lainnya (jika ada)
            schema.save()
            return schema
        except DjangoValidationError as e:
            raise ValueError(f"Data validation failed: {e}")
        except Exception as e:
            raise Exception(f"Failed to update schema: {e}")

    @staticmethod
    def delete_schema(schema_id: int):
        """
        Delete a JsonSchema entry by ID.
        Returns True if deleted, False if not found.
        """
        try:
            schema = JsonSchema.objects.get(pk=schema_id)
            schema.delete()
            return True
        except JsonSchema.DoesNotExist:
            return False

    @staticmethod
    def list_schemas(limit: int = 100, offset: int = 0):
        """
        List JsonSchema entries with basic pagination.
        """
        return JsonSchema.objects.all().order_by('-timestamp')[offset:offset + limit]