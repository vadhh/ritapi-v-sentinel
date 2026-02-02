# ops/views.py
import ipaddress
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from json_schema.models import JsonSchema
# Import JsonEnforcerService
from json_schema.services import JsonEnforcerService 
from django.views.decorators.http import require_POST
import json



def jsonschema_dashboard(request):
    """
    Dashboard CRUD JsonSchema with modal
    """
    schemas = JsonSchema.objects.all().order_by("-timestamp")
    paginator = Paginator(schemas, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    return render(request, "ops_template/json_dashboard.html", {
        "page_obj": page_obj,
    })


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip



def jsonschema_create(request):
    if request.method == "POST":
        name = request.POST.get("name")
        endpoint = request.POST.get("endpoint")
        method = request.POST.get("method", "POST")
        schema_json = request.POST.get("schema_json")
        description = request.POST.get("description")
        rollout_mode = request.POST.get("rollout_mode", "monitor")
        version = request.POST.get("version", "v1") 

        try:
            schema_data = json.loads(schema_json) if schema_json else {}
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "message": "Schema JSON Invalid"
            }, status=400)

        create_data = {
            'name': name,
            'endpoint': endpoint,
            'method': method,
            'schema_json': schema_data,
            'description': description,
            'rollout_mode': rollout_mode,
            'version': version,
            'is_active': True 
        }
        
        try:
            # Apply changes directly
            JsonEnforcerService.create_schema(create_data)
            
            return JsonResponse({
                "success": True,
                "message": "Schema successfully created"
            })
                
        except ValueError as e:
            # Catch error from JsonEnforcerService (e.g., unique constraint violation)
            return JsonResponse({
                "success": False,
                # Pesan diubah ke Bahasa Inggris
                "message": f"Failed to create schema: {str(e)}" 
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "success": False,
                # Pesan diubah ke Bahasa Inggris
                "message": f"Failed to process request: {str(e)}"
            }, status=500)
    return JsonResponse({"success": False}, status=400)



def jsonschema_update(request, pk):
    schema = get_object_or_404(JsonSchema, pk=pk)
    if request.method == "POST":
        name = request.POST.get("name")
        endpoint = request.POST.get("endpoint")
        method = request.POST.get("method", "POST")
        schema_json = request.POST.get("schema_json")
        description = request.POST.get("description")
        rollout_mode = request.POST.get("rollout_mode", "monitor")
        version = request.POST.get("version", "v1") 

        try:
            schema_data = json.loads(schema_json) if schema_json else {}
        except json.JSONDecodeError:
            return JsonResponse({
                "success": False,
                "message": "Schema JSON Invalid"
            }, status=400)
        
        update_data = {
            'name': name,
            'endpoint': endpoint,
            'method': method,
            'schema_json': schema_data,
            'description': description,
            'rollout_mode': rollout_mode,
            'version': version,
        }
        
        try:
            # Apply changes directly
            updated_schema = JsonEnforcerService.update_schema(pk, update_data)
            
            if not updated_schema:
                 return JsonResponse({
                    "success": False,
                    "message": "Schema not found"
                }, status=404)

            return JsonResponse({
                "success": True,
                "message": "Schema updated successfully"
            })
                
        except ValueError as e:
            # Catch error from JsonEnforcerService (e.g., unique constraint violation)
            return JsonResponse({
                "success": False,
                # Pesan diubah ke Bahasa Inggris
                "message": f"Failed to update schema: {str(e)}" 
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "success": False,
                # Pesan diubah ke Bahasa Inggris
                "message": f"Failed to process request: {str(e)}"
            }, status=500)
    return JsonResponse({"success": False}, status=400)



def jsonschema_delete(request, pk):
    schema = get_object_or_404(JsonSchema, pk=pk)
    
    if request.method == "POST":
        
        try:
            # Apply changes directly
            deleted = JsonEnforcerService.delete_schema(pk)

            if not deleted:
                 return JsonResponse({
                    "success": False,
                    # Pesan diubah ke Bahasa Inggris
                    "message": "Schema not found"
                }, status=404)

            return JsonResponse({
                "success": True,
                # Pesan diubah ke Bahasa Inggris
                "message": "Schema successfully deleted"
            })
                
        except Exception as e:
            return JsonResponse({
                "success": False,
                # Pesan diubah ke Bahasa Inggris
                "message": f"Failed to process request: {str(e)}"
            }, status=500)
    
    # For GET request or non-POST, return error
    return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)



@require_POST
def jsonschema_toggle(request, pk):
    schema = get_object_or_404(JsonSchema, pk=pk)
    
    # Data toggle just reverses is_active
    new_active_status = not schema.is_active
    
    try:
        # Apply changes directly using update_schema
        update_data = {
            'is_active': new_active_status
        }
        
        updated_schema = JsonEnforcerService.update_schema(pk, update_data)
        
        if not updated_schema:
             return JsonResponse({
                "success": False,
                # Pesan diubah ke Bahasa Inggris
                "message": "Schema not found"
            }, status=404)

        return JsonResponse({
            "success": True,
            # Pesan diubah ke Bahasa Inggris
            "message": "Schema status successfully updated",
            "is_active": updated_schema.is_active
        })
            
    except Exception as e:
        return JsonResponse({
            "success": False,
            # Pesan diubah ke Bahasa Inggris
            "message": f"Failed to process request: {str(e)}"
        }, status=500)