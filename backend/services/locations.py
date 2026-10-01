"""Known areas and their approximate coordinates.

Using fixed area centroids means the app works without any paid maps API,
and donors never have to share an exact home address (privacy by design).
"""
import math

AREAS = {
    "Karachi": {
        "Saddar": (24.8556, 67.0281), "Clifton": (24.8138, 67.0300), "DHA": (24.7986, 67.0647),
        "PECHS": (24.8700, 67.0600), "Gulshan-e-Iqbal": (24.9180, 67.0971),
        "Gulistan-e-Johar": (24.9136, 67.1306), "North Nazimabad": (24.9425, 67.0381),
        "Nazimabad": (24.9120, 67.0300), "FB Area": (24.9300, 67.0750), "Korangi": (24.8300, 67.1300),
        "Malir": (24.8933, 67.2050), "Shah Faisal": (24.8800, 67.1600), "Lyari": (24.8700, 66.9950),
        "Orangi": (24.9500, 66.9900),
    },
    "Hyderabad": {
        "Latifabad": (25.3700, 68.3600), "Qasimabad": (25.3900, 68.3200),
        "Hyderabad Saddar": (25.3920, 68.3700), "Hirabad": (25.4000, 68.3750),
        "Kohsar": (25.3550, 68.3450),
    },
}


def area_coords(city: str, area: str):
    try:
        return AREAS[city][area]
    except KeyError:
        raise ValueError(f"Unknown area '{area}' in city '{city}'")


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
