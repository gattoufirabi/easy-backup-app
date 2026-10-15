"""Types de fichiers affichés dans les sous-onglets.

La correspondance extension → type est faite par le moteur Go
(engine/categories.go) ; les noms ci-dessous doivent y correspondre.
"""

OTHER = "Autres"
ORDER = ["Images", "Vidéos", "Audio", "Documents", "Archives", OTHER]

ICONS = {
    "Images": "🖼️",
    "Vidéos": "🎬",
    "Audio": "🎵",
    "Documents": "📄",
    "Archives": "🗜️",
    OTHER: "📦",
}
