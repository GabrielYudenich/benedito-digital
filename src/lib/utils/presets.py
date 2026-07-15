def get_global_preset_settings(preset_name: str) -> dict:
    preset = (preset_name or "").strip().lower()
    if preset == "conservador":
        return {
            "profile_label": "Rapido",
            "upscale_quality": "Rapido",
            "upscale_scale": "Auto",
            "use_upscale": False,
            "view_upscale": False,
            "prefer_swinir": False,
        }
    if preset == "nitro":
        return {
            "profile_label": "Maximo",
            "upscale_quality": "Maximo",
            "upscale_scale": "x4",
            "use_upscale": True,
            "view_upscale": True,
            "prefer_swinir": True,
        }
    # Cinema (default)
    return {
        "profile_label": "Qualidade",
        "upscale_quality": "Qualidade",
        "upscale_scale": "Auto",
        "use_upscale": False,
        "view_upscale": False,
        "prefer_swinir": True,
    }
