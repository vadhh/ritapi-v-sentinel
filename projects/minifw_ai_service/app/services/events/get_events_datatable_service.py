from typing import List, Dict, Any


def get_events_datatable(
    draw: int = 1,
    start: int = 0,
    length: int = 10,
    search_value: str = "",
    order_column: int = 0,
    order_dir: str = "desc"
) -> Dict[str, Any]:
    """
    Get events with DataTables server-side processing
    
    Args:
        draw: DataTables draw counter
        start: Starting record index
        length: Number of records per page
        search_value: Search keyword
        order_column: Column index to sort by
        order_dir: Sort direction (asc/desc)
    
    Returns:
        Dict with DataTables response format
    """
    from app.services.events.get_events_service import get_recent_events
    
    # Get all events
    all_events = get_recent_events(limit=10000)
    
    # Filter events based on search
    if search_value:
        filtered_events = _filter_events(all_events, search_value)
    else:
        filtered_events = all_events
    
    # Get total counts
    total_records = len(all_events)
    filtered_records = len(filtered_events)
    
    # Sort events
    sorted_events = _sort_events(filtered_events, order_column, order_dir)
    
    # Paginate
    paginated_events = sorted_events[start:start + length]
    
    # Return DataTables format
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": paginated_events
    }


def _filter_events(events: List[Dict], search_value: str) -> List[Dict]:
    """
    Filter events by search value
    
    Args:
        events: List of event dictionaries
        search_value: Search keyword
    
    Returns:
        Filtered list of events
    """
    search_lower = search_value.lower()
    filtered = []
    
    for event in events:
        # Search in all event fields
        if (search_lower in event.get('time', '').lower() or
            search_lower in event.get('type', '').lower() or
            search_lower in event.get('source', '').lower() or
            search_lower in event.get('status', '').lower()):
            filtered.append(event)
    
    return filtered


def _sort_events(events: List[Dict], order_column: int, order_dir: str) -> List[Dict]:
    """
    Sort events by column
    
    Args:
        events: List of event dictionaries
        order_column: Column index (0=time, 1=type, 2=source, 3=status)
        order_dir: Sort direction (asc/desc)
    
    Returns:
        Sorted list of events
    """
    # Column mapping
    column_map = {
        0: 'time',
        1: 'type',
        2: 'source',
        3: 'status'
    }
    
    sort_key = column_map.get(order_column, 'time')
    reverse = (order_dir == 'desc')
    
    try:
        # Sort events
        sorted_events = sorted(
            events,
            key=lambda x: x.get(sort_key, ''),
            reverse=reverse
        )
        return sorted_events
    except Exception as e:
        # If sorting fails, return unsorted
        print(f"Sorting error: {e}")
        return events