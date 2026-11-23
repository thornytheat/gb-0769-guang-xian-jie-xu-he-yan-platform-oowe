from app.errors import InspectionError


def build_registry(entries, length_mm):
    """Validate entry bounds and attach cumulative coil length at every registry position."""
    ordered = sorted(entries, key=lambda row: (row['route_mm'], row['id']))
    cumulative, coils, clears = 0, [], []
    for row in ordered:
        if not 0 <= row['route_mm'] <= length_mm:
            raise InspectionError('SLACK_OUTSIDE_LINK', 'slack')
        cumulative += row['length_mm']
        point = {**row, 'cumulative_mm': cumulative}
        (coils if row['kind'] == 'COIL' else clears).append(point)
    return {'entries': coils + clears, 'coils': coils, 'clears': clears,
            'coverage_mm': max((row['route_mm'] for row in ordered), default=0),
            'total_coil_mm': cumulative,
            'present': bool(ordered)}


def to_route_half(chain_half, coils):
    """Convert instrument chain distance (half-mm units) to route distance.

    A coil at route position R with length C is measured by the instrument at R + C(previous),
    i.e. chain = route + cumulative coil length before the point. Subtract every coil whose
    instrument position is not past the reading.
    """
    correction = 0
    for coil in coils:
        instrument_half = coil['route_mm'] * 2 + coil['cumulative_mm'] * 2
        if instrument_half <= chain_half:
            correction = coil['cumulative_mm'] * 2
        else:
            break
    return chain_half - correction


def covered(route_mm, registry):
    """A route point is covered once the latest registry entry reaches it."""
    return registry['present'] and route_mm <= registry['coverage_mm']
