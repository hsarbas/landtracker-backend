from geographiclib.geodesic import Geodesic


geod = Geodesic.WGS84


def next_point(lat: float, lon: float, theta_deg: float, distance_m: float):
    r = geod.Direct(lat, lon, theta_deg, distance_m)
    return r["lat2"], r["lon2"]
