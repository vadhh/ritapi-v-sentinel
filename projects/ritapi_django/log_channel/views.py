from django.contrib.auth.decorators import login_required
from django.shortcuts import render
# Pastikan RequestLog diimport dari lokasi yang benar
from .models import RequestLog  
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import timedelta
from django.utils import timezone
# Hapus import ops.ops_services.models import Service
# Hapus import render dan Paginator yang redundant
# from utils.log_parser import parse_scan_log
import os
from django.conf import settings


def requestlog_list(request):
    """Menampilkan daftar RequestLog dengan filter dan pagination."""
    query = request.GET.get("q", "")
    # Diubah: decision_filter menjadi action_filter
    action_filter = request.GET.get("action", "") 
    # Dihapus: service_id
    page_number = request.GET.get("page", 1)

    logs = RequestLog.objects.all().order_by("-timestamp")

    if query:
        # Filter berdasarkan IP address
        logs = logs.filter(ip_address__icontains=query)

    if action_filter:
        # Filter berdasarkan action (allow/block/monitor)
        logs = logs.filter(action=action_filter)
        
    # Dihapus: if service_id: logs = logs.filter(service_id=service_id)

    paginator = Paginator(logs, 10)  # 10 rows per page
    page_obj = paginator.get_page(page_number)
    
    # Dihapus: Ambil semua service untuk dropdown filter di UI
    # services = Service.objects.all().order_by("host_name") 

    context = {
        "logs": page_obj,
        "query": query,
        # Diubah: decision_filter menjadi action_filter
        "action_filter": action_filter, 
        # Dihapus: service_id dan services
    }
    return render(request, "ops_template/requestlog_list.html", context)


def export_requestlog_excel(request):
    """Export RequestLog ke Excel dengan filter."""
    # Ambil parameter filter dari query string
    query = request.GET.get("q", "")
    # Diubah: decision_filter menjadi action_filter
    action_filter = request.GET.get("action", "") 
    # Dihapus: service_id

    # Query dasar
    logs = RequestLog.objects.all().order_by("-timestamp")

    # 🔍 Filter berdasarkan IP (search)
    if query:
        logs = logs.filter(ip_address__icontains=query)

    # 🧱 Filter berdasarkan action (allow/block/monitor)
    if action_filter:
        # Diubah: decision menjadi action
        logs = logs.filter(action=action_filter) 

    # Dihapus: 🧩 Filter berdasarkan service

    # Buat workbook Excel
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Request Logs"

    # Header (kolom Service dihapus, Decision menjadi Action, Reason menjadi Reasons)
    ws.append([
        "No.", "IP Address", "Path", "Method", "Body Size",
        "Score", "Label", "Action", "Reasons", "Timestamp", "Session Duration (ms)"
    ])

    # Isi data ke Excel
    for idx, log in enumerate(logs, start=1):
        ws.append([
            idx,
            log.ip_address,
            log.path,
            log.method,
            log.body_size,
            log.score,
            log.label, # Field baru
            log.action, # Diubah: decision menjadi action
            log.reasons or "-", # Diubah: reason menjadi reasons
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.session_duration_ms or "-", # Field baru
        ])

    # Siapkan response untuk download
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="request_logs.xlsx"'

    wb.save(response)
    return response


def requestlog_data(request):
    """Endpoint JSON untuk data log (misalnya untuk tabel atau feed langsung)."""
    query = request.GET.get("q", "")
    # Diubah: decision_filter menjadi action_filter
    action_filter = request.GET.get("action", "") 
    # Dihapus: service_id

    logs = RequestLog.objects.all().order_by("-timestamp")

    # 🔍 Filter berdasarkan IP (search)
    if query:
        logs = logs.filter(ip_address__icontains=query)

    # 🧱 Filter berdasarkan action
    if action_filter:
        logs = logs.filter(action=action_filter)

    # Dihapus: 🧩 Filter berdasarkan service

    # ⚡ Batasi hasil agar ringan
    logs = logs[:200]

    data = []
    for log in logs:
        data.append({
            "ip_address": log.ip_address,
            "path": log.path,
            "method": log.method,
            "score": log.score,
            "label": log.label, # Field baru
            "action": log.action, # Diubah: decision menjadi action
            "reasons": log.reasons or "-", # Diubah: reason menjadi reasons
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "session_duration_ms": log.session_duration_ms, # Field baru
        })

    return JsonResponse({"data": data})


def requestlog_chart_data(request):
    """Endpoint JSON untuk data chart (misalnya 7 hari terakhir)."""
    # Dihapus: service_id filter

    # Ambil data 7 hari terakhir
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)

    # Query dasar
    logs = RequestLog.objects.filter(timestamp__range=(start_date, end_date))

    # Dihapus: 🧩 Filter berdasarkan service

    # Hitung jumlah berdasarkan tanggal dan action
    logs = (
        logs.annotate(date=TruncDate("timestamp"))
        # Diubah: decision menjadi action
        .values("date", "action") 
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # Format ke bentuk chart-friendly
    chart_data = {}
    
    # Ambil semua nilai action unik untuk membuat deret data dinamis
    all_actions = RequestLog.objects.values_list('action', flat=True).distinct()
    # Pastikan 'allow', 'block', dan 'monitor' selalu ada untuk inisialisasi
    relevant_actions = set(['allow', 'block', 'monitor']).union(set(a.lower() for a in all_actions))
    
    for entry in logs:
        date_str = entry["date"].strftime("%Y-%m-%d")
        # Diubah: decision menjadi action
        action = entry["action"].lower() 
        count = entry["count"]

        if date_str not in chart_data:
            chart_data[date_str] = {a: 0 for a in relevant_actions}
            
        chart_data[date_str][action] = count

    labels = sorted(list(chart_data.keys()))
    
    # Siapkan datasets untuk chart
    datasets = []
    
    # Mapping warna sederhana (Anda mungkin ingin memindahkannya ke settings)
    color_map = {
        'allow': 'rgb(75, 192, 192)',
        'block': 'rgb(255, 99, 132)',
        'monitor': 'rgb(255, 205, 86)',
    }

    for action in sorted(list(relevant_actions)):
        datasets.append({
            "label": action.capitalize(),
            "data": [chart_data[d][action] for d in labels],
            "backgroundColor": color_map.get(action, 'rgb(100, 100, 100)'), # Default abu-abu
            "borderColor": color_map.get(action, 'rgb(100, 100, 100)'),
            "fill": False,
        })
        
    return JsonResponse({
        "labels": labels,
        "datasets": datasets,
    })
    
# Fungsi ini tidak menggunakan RequestLog, jadi tidak perlu disesuaikan.
# def scan_log_view(request):
#     log_path = "/home/sydeco/Videos/ritapi-x/scan.log"
#     print("LOG PATH:", log_path)
#     print("FILE EXISTS:", os.path.exists(log_path))
#     print("FILE SIZE:", os.path.getsize(log_path) if os.path.exists(log_path) else "NO FILE")
#     print("ini log path",log_path)
#     logs = parse_scan_log(log_path)
#     print("ini lognya",logs)
#     paginator = Paginator(logs, 10)
#     page_number = request.GET.get("page")
#     page_obj = paginator.get_page(page_number)

#     return render(request, "ops_template/scan_log_table.html", {"page_obj": page_obj})