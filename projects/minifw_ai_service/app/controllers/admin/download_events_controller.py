from fastapi.responses import StreamingResponse
from app.services.events.download_events_service import generate_events_excel_report
from datetime import datetime


def download_events_controller(action_filter: str = None):
    """
    Controller for downloading events as Excel report

    Args:
        action_filter: Filter by action type (allow, deny, block, all)

    Returns:
        StreamingResponse with Excel file
    """
    # Generate Excel report
    excel_file = generate_events_excel_report(action_filter)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if action_filter and action_filter.lower() != "all":
        filename = f"events_{action_filter.lower()}_{timestamp}.xlsx"
    else:
        filename = f"events_all_{timestamp}.xlsx"

    # Return as streaming response
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
