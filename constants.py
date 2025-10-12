# Add these to your existing VTO_ENDPOINTS list in constants.py

SUPER_ADMIN_API_KEY = "OptimoSight987654321"
GUEST_API_KEY = "OptimosightGuest999"
GUEST_LIMIT = 20
RESET_PERIOD_HOURS = 24
VTO_ENDPOINTS = [
    "/api/vto/upload",
    "/api/vto/apply_eyeshadow", 
    "/api/vto/apply_lipstick",
    "/api/vto/apply_blush",
    "/api/vto/apply_eyeliner",
    "/api/vto/apply_foundation",
    "/api/vto/apply_contour",
    "/api/vto/apply_concealer",
    "/api/vto/live_makeup",
    "/api/vto/live_makeup_page/lipstick",
    "/api/vto/live_makeup_page/blush",
    "/api/vto/live_makeup_page/eyeshadow",
    "/api/vto/live_makeup_page/eyeliner",
    "/api/vto/live_makeup_page/foundation",
    "/api/vto/live_makeup_page/contour",
    "/api/vto/live_makeup_page/concealer",
    # NEW: Add tracking endpoints
    "/api/vto/track_color_update",
    "/api/vto/track_makeup_application"
]


# VTO_ENDPOINTS = [
#     "/api/vto/upload",
#     "/api/vto/apply_eyeshadow", 
#     "/api/vto/apply_lipstick",
#     "/api/vto/live_makeup",
#     "/api/vto/live_makeup_page/lipstick",
#     "/api/vto/live_makeup_page/blush",
#     "/api/vto/live_makeup_page/eyeshadow",
#     "/api/vto/live_makeup_page/eyeliner",
#     "/api/vto/live_makeup_page/foundation",
#     "/api/vto/live_makeup_page/contour",
#     "/api/vto/live_makeup_page/concealer",
#     # NEW: Add tracking endpoints
#     "/api/vto/track_color_update",
#     "/api/vto/track_makeup_application"
# ]