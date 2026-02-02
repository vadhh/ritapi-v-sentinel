from app.services.events.get_events_datatable_service import get_events_datatable


def events_datatable_controller(
    draw: int,
    start: int,
    length: int,
    search_value: str,
    order_column: int,
    order_dir: str
):
    """
    Controller for DataTables API endpoint
    
    Args:
        draw: DataTables draw counter
        start: Starting record index
        length: Number of records per page
        search_value: Search keyword
        order_column: Column index to sort
        order_dir: Sort direction
    
    Returns:
        DataTables response dictionary
    """
    return get_events_datatable(
        draw=draw,
        start=start,
        length=length,
        search_value=search_value,
        order_column=order_column,
        order_dir=order_dir
    )